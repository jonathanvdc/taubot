module Accounting.Commands

/// A text token in a command AST.
type Token = { StartIndex: int; Text: string }

/// A currency amount token in a command AST.
type CurrencyAmountToken = { StartIndex: int; Text: string; Amount: CurrencyAmount }

/// An AST of a command as expressed by a user.
type Command =
    /// A command that performs another command as an admin.
    | AdminCommand of keyword: Token * proxiedAccount: Token * inner: Command
    /// A command that performs another command via proxy.
    | ProxyCommand of keyword: Token * proxiedAccount: Token * inner: Command
    /// A command that requests the balance of the user's account.
    | QueryBalanceCommand of keyword: Token
    /// A command that mints currency.
    | MintCommand of keyword: Token * amount: CurrencyAmountToken
    /// A command that transfers currency.
    | TransferCommand of keyword: Token * amount: CurrencyAmountToken * destionation: Token

/// An error encountered during command parsing.
type CommandError =
    | UnknownCommand of token: Token
    | UnexpectedToken of token: Token
    | ExpectedNumber of token: Token
    | ExpectedPositiveNumber of token: CurrencyAmountToken
    | UnexpectedProxy of keyword: Token
    | UnexpectedAdmin of keyword: Token
    | UnfinishedCommand

// Helpers for currency amount tokens.
module CurrencyAmountToken =
    let parse (token: Token): Result<CurrencyAmountToken, CommandError> =
        match CurrencyAmount.TryParse token.Text with
        | (true, x) -> Ok { StartIndex = token.StartIndex; Text = token.Text; Amount = x }
        | (false, _) -> Error (ExpectedNumber token)

    let assertPositive (token: CurrencyAmountToken): Result<CurrencyAmountToken, CommandError> =
        if token.Amount < 0 then Error (ExpectedPositiveNumber token) else Ok token

/// Tokenizes a command.
let tokenize (command: string) =
    let rec tokenizePart (part: string) (start: int) (head: Token list) =
        let whitespaceIndex =
            part.IndexOfAny([| ' '; '\n'; '\r'; '\t' |])

        if whitespaceIndex = 0 then
            tokenizePart (part.Substring(1)) (start + 1) head
        else if whitespaceIndex >= 0 then
            tokenizePart
                (part.Substring(whitespaceIndex))
                (start + whitespaceIndex)
                ({ Text = part.Substring(0, whitespaceIndex)
                   StartIndex = start }
                 :: head)
        else if part = "" then
            head
        else
            { Text = part; StartIndex = start } :: head

    tokenizePart command 0 [] |> List.rev

/// Takes a token and returns the keyword it represents, if any.
/// This function converts keywords to lower-case and expands
/// abbreviations.
let extractKeyword (keyword: Token) =
    match keyword.Text.ToLowerInvariant() with
    | "bal" -> "balance"
    | other -> other

/// Parses a sequence of command tokens.
let rec parseTokens (tokens: Token list) =
    match tokens with
    | keyword :: tail ->
        match extractKeyword keyword, tail with
        // Balance followed by nothing is the pattern we expect.
        | "balance", [] -> Ok(QueryBalanceCommand keyword)

        // Balance followed by an additional token is gibberish.
        | "balance", t :: _ -> Error(UnexpectedToken t)

        // Mint takes exactly one argument.
        | "mint", [t] -> CurrencyAmountToken.parse t |> Result.map (fun t -> MintCommand(keyword, t))

        // Mint with no arguments or more than one argument is wrong.
        | "mint", [] -> Error UnfinishedCommand
        | "mint", _ :: t :: _ -> Error(UnexpectedToken t)

        // Transfer takes exactly two arguments.
        | "transfer", [destination; amount] ->
            CurrencyAmountToken.parse amount
            |> Result.bind CurrencyAmountToken.assertPositive
            |> Result.map (fun t -> TransferCommand(keyword, t, destination))

        // Catch invalid versions of transfer.
        | "transfer", [] | "transfer", [_] -> Error UnfinishedCommand
        | "transfer", _ :: _ :: t :: _ -> Error(UnexpectedToken t)

        | "admin", proxyId :: tail ->
            parseTokens tail
            |> Result.map (fun inner -> AdminCommand(keyword, proxyId, inner))

        | "admin", [] -> Error UnfinishedCommand

        | "proxy", proxyId :: tail ->
            parseTokens tail
            |> Result.map (fun inner -> ProxyCommand(keyword, proxyId, inner))

        | "proxy", [] -> Error UnfinishedCommand

        | _, _ -> Error(UnknownCommand keyword)
    | [] -> Error UnfinishedCommand

/// Parses a command.
let parse = tokenize >> parseTokens

/// Builds an account, authorization pair for a transaction from a proxy chain
/// and an optional admin proxy ID.
/// This function translates the author-centric model of a command to the
/// account-centric model of a reuqest.
let buildAuthorization (proxyChain: AccountId list) (adminProxyId: AccountId option) (authorAccount: AccountId) =
    let acc, auth =
        match adminProxyId with
        | Some accName -> accName, AdminAuthorized authorAccount
        | None -> authorAccount, SelfAuthorized

    let rec applyProxies chain =
        match chain with
        | x :: xs ->
            let acc, auth = applyProxies xs
            x, ProxyAuthorized(acc, auth)
        | [] -> acc, auth

    applyProxies proxyChain

/// Converts a command to a transaction request.
let toTransactionRequest (authorAccount: AccountId) (accessTokenId: AccessTokenId) (command: Command) =
    // First construct the chain of proxies. Proxy commands must come at
    // the start of any command, so we can simply pop off commands until
    // we have a non-proxy command at the head of the command pseudo-list.
    let rec proxyChain cmd =
        match cmd with
        | ProxyCommand (_, proxyId, inner) ->
            let chain, realCommand = proxyChain inner
            proxyId.Text :: chain, realCommand
        | _ -> [], cmd

    let proxies, command = proxyChain command

    // Ditto for admin authorization, although proxies may precede admin.
    // Also, there can be only one admin authorization command.
    let adminProxyId, command =
        match command with
        | AdminCommand (_, adminId, inner) -> Some adminId.Text, inner
        | _ -> None, command

    // Now parse the action.
    let parsedAction =
        match command with
        | QueryBalanceCommand _ -> Ok QueryBalanceAction
        | MintCommand (_, amount) -> Ok (MintAction amount.Amount)
        | TransferCommand (_, amount, destination) -> Ok (TransferAction(amount.Amount, destination.Text))
        | AdminCommand (keyword, _, _) -> Error(UnexpectedAdmin keyword)
        | ProxyCommand (keyword, _, _) -> Error(UnexpectedProxy keyword)

    // If we managed to parse the action, then we now compose the request
    // itself.
    let composeRequest action =
        let acc, auth =
            buildAuthorization proxies adminProxyId authorAccount

        { Account = acc
          Authorization = auth
          AccessToken = Some accessTokenId
          Action = action }

    Result.map composeRequest parsedAction

/// Parses a command as a transaction request.
let parseAsTransactionRequest (authorAccount: AccountId) (accessTokenId: AccessTokenId) (command: string) =
    parse command
    |> Result.bind (toTransactionRequest authorAccount accessTokenId)
