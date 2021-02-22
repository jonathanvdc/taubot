module Accounting.InMemoryTransactionProcessor

open Accounting.Helpers

type AccountData =
    { Balance: CurrencyAmount
      ProxyAccess: AccountId Set
      Privileges: AccessScope Set
      Tokens: Map<AccessTokenId, AccessScope Set> }

type State =
    {
      /// A mapping of accounts to their current states.
      Accounts: Map<AccountId, AccountData>

      /// The default set of privileges for an account.
      DefaultPrivileges: AccessScope Set }

/// Gets an account's associated data, if it exists.
let getAccount accountId state = Map.tryFind accountId state.Accounts

/// Checks if an account exists.
let accountExists accountId state =
    Map.containsKey accountId state.Accounts

/// Sets an account's data. Returns a new state.
let setAccount accountId data state =
    { state with
          Accounts = Map.add accountId data state.Accounts }

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
let isAdmin accountId state =
    hasPrivilege AdminScope accountId state
    || hasPrivilege UnboundedScope accountId state

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
let authenticate (transaction: Transaction) state: bool =
    // Check that the proxy chain is okay.
    checkProxyChain state (proxyChain transaction)
    // Check that the authorizer is an admin if the transaction is admin-authorized.
    && (not (isAdminAuthorized transaction)
        || isAdmin (finalAuthorizer transaction) state)
    // Check that the account to which the transaction applies can perform
    // the transaction.
    && isInScopeForAny transaction.Action (privileges transaction.Account state)
    // Check that the access token is up to scratch.
    && match transaction.AccessToken with
       | Some token ->
           tokenScopes token (finalAuthorizer transaction) state
           |> isInScopeForAny transaction.Action
       | None -> true

/// An initial, empty state for an in-memory transaction processor.
let emptyState =
    { Accounts = Map.empty
      DefaultPrivileges =
          Set.ofList [ QueryBalanceScope
                       QueryHistoryScope
                       QueryPrivilegesScope
                       TransferScope ] }

/// Processes a transaction.
let apply (transaction: Transaction) (state: State): Result<State * TransactionResult, TransactionError> =
    match validateAction transaction.Action, authenticate transaction state, getAccount transaction.Account state with
    | Error e, _, _ -> Error e
    | Ok _, false, _ -> Error UnauthorizedError
    | Ok _, true, None -> Error UnauthorizedError
    | Ok _, true, Some srcAcc ->
        match transaction.Action with
        // Some actions like history querying are intentionally not
        // implemented by this processor. Processors that build on
        // this processor can implement them instead.
        | QueryHistoryAction _ -> Error ActionNotImplementedError

        | QueryBalanceAction -> Ok(state, BalanceResult srcAcc.Balance)
        | QueryPrivilegesAction -> Ok(state, AccessScopesResult srcAcc.Privileges)

        | AddPrivilegesAction (accId, privileges) ->
            match getAccount accId state with
            | Some destAcc ->
                let newState =
                    state
                    |> setAccount
                        accId
                        { destAcc with
                              Privileges = Set.union destAcc.Privileges privileges }

                Ok(newState, SuccessfulResult transaction.Id)
            | None -> Error DestinationDoesNotExistError

        | RemovePrivilegesAction (accId, privileges) ->
            match getAccount accId state with
            | Some destAcc ->
                let newState =
                    state
                    |> setAccount
                        accId
                        { destAcc with
                              Privileges = Set.difference destAcc.Privileges privileges }

                Ok(newState, SuccessfulResult transaction.Id)
            | None -> Error DestinationDoesNotExistError

        | OpenAccountAction (newId, tokenId) ->
            if accountExists newId state then
                Error AccountAlreadyExistsError
            else
                // In addition to actually opening an account, we will generate
                // a token that can be used to further configure the account.
                // This token will have unbounded scope. The account opener is
                // assumed to be a trusted third party (and needs special
                // permission to open accounts).
                let newState =
                    state
                    |> setAccount
                        newId
                        { Balance = 0L
                          Privileges = state.DefaultPrivileges
                          ProxyAccess = Set.empty
                          Tokens =
                              Map.empty
                              |> Map.add tokenId (Set.singleton UnboundedScope) }

                Ok(newState, AccessTokenResult tokenId)

        | CreateTokenAction (tokenId, scopes) ->
            match Map.tryFind tokenId srcAcc.Tokens with
            | Some _ -> Error TokenAlreadyExistsError
            | None ->
                let newState =
                    state
                    |> setAccount
                        transaction.Account
                        { srcAcc with
                              Tokens = srcAcc.Tokens |> Map.add tokenId scopes }

                Ok(newState, AccessTokenResult tokenId)

        | MintAction amount ->
            let newState =
                state
                |> setAccount
                    transaction.Account
                    { srcAcc with
                          Balance = srcAcc.Balance + amount }

            Ok(newState, SuccessfulResult transaction.Id)

        | TransferAction (amount, destId) ->
            let srcId = transaction.Account

            match getAccount destId state with
            | Some destAcc ->
                let newBalance = srcAcc.Balance - amount

                if newBalance < 0L then
                    Error InsufficientFundsError
                else
                    let newState =
                        state
                        |> setAccount
                            destId
                            { destAcc with
                                  Balance = destAcc.Balance + amount }
                        |> setAccount srcId { srcAcc with Balance = newBalance }

                    Ok(newState, SuccessfulResult transaction.Id)
            | None -> Error DestinationDoesNotExistError
