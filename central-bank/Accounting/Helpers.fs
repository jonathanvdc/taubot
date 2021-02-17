module Accounting.Helpers
open System

/// Constructs the proxy chain that authorizes a transaction. A proxy chain
/// is a list of account IDs where successive elements in the chain must
/// have proxy access.
let proxyChain (transaction: Transaction) =
    let rec impl authorization =
        match authorization with
        | SelfAuthorized -> [ transaction.Account ]
        | AdminAuthorized adminId -> [ adminId ]
        | ProxyAuthorized (proxy, tail) -> proxy :: impl tail

    impl transaction.Authorization

/// Gets the account that ultimately authorized a transaction. This
/// corresponds to the final account in a proxy chain.
let finalAuthorizer (transaction: Transaction) =
    let rec impl authorization =
        match authorization with
        | SelfAuthorized -> transaction.Account
        | AdminAuthorized adminId -> adminId
        | ProxyAuthorized (_, tail) -> impl tail

    impl transaction.Authorization

/// Tells if a transaction is ultimately authorized by an admin.
let isAdminAuthorized (transaction: Transaction) =
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

/// Tells if an action represents a query. Queries cannot change state; they
/// can only inspect it.
let isQuery action =
    match action with
    | QueryBalanceAction -> true
    | _ -> false

let validateAction action =
    match action with
    | MintAction amount when amount <= 0m -> Error InvalidAmountError
    | TransferAction (amount, _) when amount <= 0m -> Error InvalidAmountError
    | _ -> Ok()

/// Randomly generates a new token ID.
let generateTokenId (rng: Random) =
    // Generate 40 random bytes and base64-encode them.
    let buffer = Array.create 40 1uy
    rng.NextBytes(buffer)
    Convert.ToBase64String buffer
