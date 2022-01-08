module BankTerminal.EntryPoint

open System
open Options
open Accounting
open Accounting.Commands

/// The terminal's state.
type State =
    {
      /// The central bank transaction client.
      BankClient: TransactionClient

      /// The account's name.
      Account: AccountId

      /// The account's access token.
      AccessToken: AccessTokenId }


let formatTransactionError (error: TransactionError) = error.ToString()

let formatCommandError (error: CommandError) = error.ToString()

let formatScopes (scopes: AccessScope Set) =
    scopes
    |> Set.map string
    |> List.ofSeq
    |> List.sort
    |> String.concat ", "

let formatTransactionResult (request: TransactionRequest) (result: TransactionResult) =
    match result with
    | SuccessfulResult id -> sprintf "Transaction performed with ID %d." id
    | AccessScopesResult scopes ->
        formatScopes scopes
        |> match request.Action with
           | QueryPrivilegesAction -> sprintf "Privileges assigned to %s: %s." request.Account
           | _ -> sprintf "Access scopes: %s."
    | AccessTokenResult id ->
        match request.Action with
        | CreateTokenAction (_, scopes) ->
            sprintf "Created access token for %s with ID `%s` and scopes %s." request.Account id (formatScopes scopes)
        | OpenAccountAction (name, _) -> sprintf "Opened account %s with access token ID `%s`" name id
        | _ -> sprintf "Access token with ID `%s`" id
    | BalanceResult value -> sprintf "%s's balance is %d." request.Account value
    | HistoryResult transactions ->
        // TODO: format this better.
        sprintf "Transactions: %A" transactions

let replyTo (query: string) (response: string) = async { printf "%s" response }

/// Handles an incoming message.
let handleMessage (state: State) (message: string) =
    async {
        try
            // Parse the command as a transaction request.
            match parseAsTransactionRequest state.Account state.AccessToken message with
            | Ok request ->
                // Perform the transaction.
                let! response = state.BankClient.PerformTransactionAsync(request)

                // Report the result.
                match response with
                | Ok result ->
                    return!
                        result
                        |> formatTransactionResult request
                        |> replyTo message
                | Error e -> return! e |> formatTransactionError |> replyTo message
            | Error e -> return! e |> formatCommandError |> replyTo message
        with
        | e ->
            eprintfn "Exception encountered: %A" e
            return! replyTo message (sprintf "Whoops. I encountered an internal exception.")
    }

let rec inputLoop (state: State) =
    async {
        let input = Console.ReadLine()

        if input <> null then
            let! _ = handleMessage state input
            return! inputLoop state
    }

[<EntryPoint>]
let main argv =
    match parseOptions argv with
    | Fail _ -> 1
    | Help _
    | Version _ -> 0
    | Success opts ->
        // Create a central bank client.
        use bankClient = new TransactionClient(opts.ServerUrl)

        inputLoop
            { BankClient = bankClient
              Account = opts.AccountName
              AccessToken = opts.RootAccessToken }
        |> Async.RunSynchronously

        0
