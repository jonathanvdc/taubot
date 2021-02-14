module CentralBank.Accounting.InMemoryTransactionProcessor

open CentralBank.Accounting.Helpers

type AccountData =
    { Balance: decimal
      ProxyAccess: AccountId Set
      IsAdmin: bool
      Tokens: Map<AccessTokenId, AccessTokenScope list> }

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

/// Checks if an account is an admin account.
let isAdmin accountId state =
    match getAccount accountId state with
    | Some accountData -> accountData.IsAdmin
    | None -> false

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

/// Ensures that the final authorizer is authorized to perform
/// the transaction. This boils down to checking admin privileges.
let rec checkFinalAuthorizer requiresAdmin state accountId authorization =
    match authorization with
    | SelfAuthorized -> not requiresAdmin || isAdmin accountId state
    | AdminAuthorized adminId -> isAdmin adminId state
    | ProxyAuthorized (_, tail) -> checkFinalAuthorizer requiresAdmin state accountId tail

/// Authenticates a transaction. Returns a Boolean value that indicates whether
/// or not the transaction could be authenticated.
let authenticate (state: State) (transaction: Transaction): bool =
    checkProxyChain state (proxyChain transaction.Authorization transaction.Account)
    && checkFinalAuthorizer false state transaction.Account transaction.Authorization

let apply (state: State) (transaction: Transaction): Result<State * TransactionResult, TransactionError> =
    if not (authenticate state transaction) then
        Error UnauthorizedError
    else
        match transaction.Action with
        | MintAction amount ->
            let srcId = transaction.Account

            let finalAuth =
                checkFinalAuthorizer true state srcId transaction.Authorization

            match finalAuth, getAccount srcId state with
            | (true, Some srcAcc) ->
                let newState =
                    state
                    |> setAccount
                        srcId
                        { srcAcc with
                              Balance = srcAcc.Balance + amount }
                    |> addTransaction transaction

                Ok(newState, SuccessfulResult)
            | (true, None) -> Error DestinationDoesNotExistError
            | (false, _) -> Error UnauthorizedError

        | TransferAction (amount, _) when amount <= 0m -> Error InvalidAmountError

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
            | _, None -> Error DestinationDoesNotExistError
            | None, _ -> Error UnauthorizedError
