namespace Accounting

/// A transaction request is an action that might become a transaction,
/// but has not yet become one.
type TransactionRequest =
    {
      /// The account performing the transaction.
      Account: AccountId

      /// The authorization (chain) for the transaction.
      Authorization: TransactionAuthorization

      /// An access token that is used as the root of the
      /// authorization chain.
      AccessToken: AccessTokenId option

      /// The action being performed.
      Action: AccountAction }

module TransactionRequest =
    open System
    open System.Threading

    /// Turns a transaction request into a transaction by appending a unique identifier and
    /// a timestamp to the request. Unique identifiers are generated atomically using a counter
    /// variable. The timestamp corresponds to the current time (UTC).
    let toTransaction (counter: byref<TransactionId>) (request: TransactionRequest) : Transaction =
        { Id = Interlocked.Increment(&counter)
          PerformedAt = DateTime.UtcNow
          Account = request.Account
          Authorization = request.Authorization
          AccessToken = request.AccessToken
          Action = request.Action }

    let formatResult (request: TransactionRequest) (result: TransactionResult) =
        let formatScopes (scopes: AccessScope Set) =
            scopes
            |> Set.map string
            |> List.ofSeq
            |> List.sort
            |> String.concat ", "

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
                sprintf
                    "Created access token for %s with ID `%s` and scopes %s."
                    request.Account
                    id
                    (formatScopes scopes)
            | OpenAccountAction (name, _) -> sprintf "Opened account %s with access token ID `%s`" name id
            | _ -> sprintf "Access token with ID `%s`" id
        | BalanceResult value -> sprintf "%s's balance is %d." request.Account value
        | HistoryResult transactions ->
            // TODO: format this better.
            sprintf "Transactions: %A" transactions
