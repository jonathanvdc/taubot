module Accounting.Helpers

/// Constructs the proxy chain that authorizes a transaction. A proxy chain
/// is a list of account IDs where successive elements in the chain must
/// have proxy access.
let proxyChain transaction =
    let rec impl authorization =
        match authorization with
        | SelfAuthorized -> [ transaction.Account ]
        | AdminAuthorized adminId -> [ adminId ]
        | ProxyAuthorized (proxy, tail) -> proxy :: impl tail

    impl transaction.Authorization

/// Gets the account that ultimately authorized a transaction. This
/// corresponds to the final account in a proxy chain.
let finalAuthorizer transaction =
    let rec impl authorization =
        match authorization with
        | SelfAuthorized -> transaction.Account
        | AdminAuthorized adminId -> adminId
        | ProxyAuthorized (_, tail) -> impl tail

    impl transaction.Authorization

/// Tells if a transaction is ultimately authorized by an admin.
let isAdminAuthorized transaction =
    let rec impl authorization =
        match authorization with
        | SelfAuthorized -> false
        | AdminAuthorized _ -> true
        | ProxyAuthorized (_, tail) -> impl tail

    impl transaction.Authorization

/// Tests if an action is within an access scope's ability to perform.
let isInScope action scope =
    match action, scope with
    | _, UnboundedScope -> true
    | TransferAction _, TransferScope -> true
    | MintAction _, MintScope -> true
    | QueryBalanceAction, QueryBalanceScope -> true
    | OpenAccountAction _, OpenAccountScope -> true
    | _, _ -> false

/// Tests if an action is within one of a sequence of access scopes' abilities
/// to perform.
let isInScopeForAny action scopes =
    Seq.tryFind (isInScope action) scopes
    |> Option.isSome

let validateAction action =
    match action with
    | MintAction amount when amount <= 0m -> Error InvalidAmountError
    | TransferAction (amount, _) when amount <= 0m -> Error InvalidAmountError
    | _ -> Ok()
