module Accounting.Commands

type Token = { StartIndex: int; Text: string }

type Command =
    /// A command that performs another command as an admin.
    | AdminCommand of keyword: Token * proxiedAccount: Token * inner: Command
    /// A command that performs another command via proxy.
    | ProxyCommand of keyword: Token * proxiedAccount: Token * inner: Command
    /// A command that requests the balance of the user's account.
    | QueryBalanceCommand of keyword: Token

type CommandError =
    | UnexpectedToken of token: Token
    | UnexpectedProxy of keyword: Token
    | UnexpectedAdmin of keyword: Token
    | UnfinishedCommand

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

/// Parses a sequence of command tokens.
let rec parseTokens (tokens: Token list) =
    match tokens with
    | [ { Text = "bal" } as t ]
    | [ { Text = "balance" } as t ] -> Ok(QueryBalanceCommand t)
    | { Text = "admin" } as t :: proxyId :: cmd ->
        parseTokens cmd
        |> Result.map (fun inner -> AdminCommand(t, proxyId, inner))
    | { Text = "proxy" } as t :: proxyId :: cmd ->
        parseTokens cmd
        |> Result.map (fun inner -> ProxyCommand(t, proxyId, inner))
    | t :: _ -> Error(UnexpectedToken t)
    | [] -> Error UnfinishedCommand

/// Parses a command.
let parse = tokenize >> parseTokens

/// Builds an account, authorization pair for a transaction from a proxy chain
/// and an optional admin proxy ID.
/// This function translates the author-centric model of a command to the
/// account-centric model of a reuqest.
let buildAuthorization (proxyChain: AccountId list) (adminProxyId: AccountId option) (authorName: string) =
    let acc, auth =
        match adminProxyId with
        | Some accName -> accName, AdminAuthorized authorName
        | None -> authorName, SelfAuthorized

    let rec applyProxies chain =
        match chain with
        | x :: xs ->
            let acc, auth = applyProxies xs
            x, ProxyAuthorized(acc, auth)
        | [] -> acc, auth

    applyProxies proxyChain

/// Converts a command to a transaction request.
let toTransactionRequest (authorName: string) (accessTokenId: string) (command: Command) =
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
        | AdminCommand (keyword, _, _) -> Error(UnexpectedAdmin keyword)
        | ProxyCommand (keyword, _, _) -> Error(UnexpectedProxy keyword)

    // If we managed to parse the action, then we now compose the request
    // itself.
    let composeRequest action =
        let acc, auth = buildAuthorization proxies adminProxyId authorName

        { Account = acc
          Authorization = auth
          AccessToken = Some accessTokenId
          Action = action }

    Result.map composeRequest parsedAction
