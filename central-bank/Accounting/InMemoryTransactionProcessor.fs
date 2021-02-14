module Accounting.InMemoryTransactionProcessor

open System
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

      /// A list of all previously applied non-query transactions,
      /// in reverse order (latest transaction first).
      History: Transaction list

      /// The default set of privileges for an account.
      DefaultPrivileges: AccessScope Set

      /// The random number generator to use.
      Rng: Random }

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
let authenticate transaction state: bool =
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
      History = []
      DefaultPrivileges =
          Set.ofList [ QueryBalanceScope
                       TransferScope ]
      Rng = Random() }

/// Randomly generates a new token ID.
let generateTokenId state =
    // Generate 40 random bytes and base64-encode them.
    let buffer = Array.create 40 1uy
    state.Rng.NextBytes(buffer)
    Convert.ToBase64String buffer

/// Processes a transaction.
let apply (transaction: Transaction) (state: State): Result<State * TransactionResult, TransactionError> =
    match validateAction transaction.Action, authenticate transaction state, getAccount transaction.Account state with
    | Error e, _, _ -> Error e
    | Ok _, false, _ -> Error UnauthorizedError
    | Ok _, true, None -> Error UnauthorizedError
    | Ok _, true, Some srcAcc ->
        match transaction.Action with
        | QueryBalanceAction -> Ok(state, BalanceResult srcAcc.Balance)

        | OpenAccountAction newId ->
            if accountExists newId state then
                Error AccountAlreadyExistsError
            else
                // In addition to actually opening an account, we will generate
                // a token that can be used to further configure the account.
                // This token will have unbounded scope. The account opener is
                // assumed to be a trusted third party (and needs special
                // permission to open accounts).
                let tokenId = generateTokenId state

                let newState =
                    state
                    |> setAccount
                        newId
                        { Balance = 0m
                          Privileges = state.DefaultPrivileges
                          ProxyAccess = Set.empty
                          Tokens =
                              Map.empty
                              |> Map.add tokenId (Set.singleton UnboundedScope) }
                    |> addTransaction transaction

                Ok(newState, AccessTokenResult tokenId)

        | MintAction amount ->
            let newState =
                state
                |> setAccount
                    transaction.Account
                    { srcAcc with
                          Balance = srcAcc.Balance + amount }
                |> addTransaction transaction

            Ok(newState, SuccessfulResult)

        | TransferAction (amount, destId) ->
            let srcId = transaction.Account

            match getAccount destId state with
            | Some destAcc ->
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
            | None -> Error DestinationDoesNotExistError
