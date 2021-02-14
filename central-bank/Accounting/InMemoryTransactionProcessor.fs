module CentralBank.Accounting.InMemoryTransactionProcessor

open CentralBank.Accounting.Helpers

type AccountData =
    { Balance: CurrencyAmount
      ProxyAccess: AccountId Set
      Privileges: AccessScope Set
      Tokens: Map<AccessTokenId, AccessScope Set> }

type State =
    {
      /// A mapping of accounts to their current states.
      Accounts: Map<AccountId, AccountData>

      /// A list of all previously applied non-query transactions,
      /// in reverse order (latest transaction first).
      History: Transaction list }

/// Gets an account's associated data, if it exists.
let getAccount accountId state = Map.tryFind accountId state.Accounts

/// Checks if an account exists.
let accountExists accountId state =
    Map.containsKey accountId state.Accounts

/// Sets an account's data. Returns a new state.
let setAccount accountId data state =
    { state with
          Accounts = Map.add accountId data state.Accounts }

let addTransaction transaction state =
    { state with
          History = transaction :: state.History }

let privileges accountId state =
    match getAccount accountId state with
    | Some accountData -> accountData.Privileges
    | None -> Set.empty

let tokenScopes tokenId accountId state =
    match getAccount accountId state with
    | Some accountData ->
        match Map.tryFind tokenId accountData.Tokens with
        | Some result -> result
        | None -> Set.empty
    | None -> Set.empty

let hasPrivilege privilege accountId state =
    privileges accountId state
    |> Set.contains privilege

/// Checks if an account is an admin account.
let isAdmin = hasPrivilege AdminScope

/// Ensures that a proxy chain checks out.
let rec checkProxyChain (state: State) (chain: AccountId list) =
    match chain with
    | x :: y :: zs ->
        match getAccount x state with
        | Some accountData ->
            Set.contains y accountData.ProxyAccess
            && checkProxyChain state (y :: zs)
        | None -> false
    | [ x ] -> accountExists x state
    | [] -> false

/// Authenticates a transaction. Returns a Boolean value that indicates whether
/// or not the transaction could be authenticated.
let authenticate transaction state: bool =
    // Check that the proxy chain is okay.
    checkProxyChain state (proxyChain transaction)
    // Check that the authorizer is an admin if the transaction is admin-authorized.
    && (not (isAdminAuthorized transaction)
        || hasPrivilege AdminScope (finalAuthorizer transaction) state)
    // Check that the account to which the transaction applies can perform
    // the transaction.
    && isInScopeForAny transaction.Action (privileges transaction.Account state)
    // Check that the access token is up to scratch.
    && match transaction.AccessToken with
       | Some token ->
           tokenScopes token (finalAuthorizer transaction) state
           |> isInScopeForAny transaction.Action
       | None -> true

let apply (state: State) (transaction: Transaction): Result<State * TransactionResult, TransactionError> =
    match validateAction transaction.Action, authenticate transaction state with
    | Error e, _ -> Error e
    | Ok _, false -> Error UnauthorizedError
    | Ok _, true ->
        match transaction.Action with
        | MintAction amount ->
            let srcId = transaction.Account

            match getAccount srcId state with
            | Some srcAcc ->
                let newState =
                    state
                    |> setAccount
                        srcId
                        { srcAcc with
                              Balance = srcAcc.Balance + amount }
                    |> addTransaction transaction

                Ok(newState, SuccessfulResult)
            | None -> Error UnauthorizedError

        | TransferAction (amount, destId) ->
            let srcId = transaction.Account

            match getAccount srcId state, getAccount destId state with
            | Some srcAcc, Some destAcc ->
                let newBalance = srcAcc.Balance - amount

                if newBalance < 0.0m then
                    Error InsufficientFundsError
                else
                    let newState =
                        state
                        |> setAccount
                            destId
                            { destAcc with
                                  Balance = destAcc.Balance + amount }
                        |> setAccount srcId { srcAcc with Balance = newBalance }
                        |> addTransaction transaction

                    Ok(newState, SuccessfulResult)
            | None, _ -> Error UnauthorizedError
            | _, None -> Error DestinationDoesNotExistError
