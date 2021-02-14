module CentralBank.Accounting.Helpers

/// Constructs the proxy chain that authorizes a transaction. A proxy chain
/// is a list of account IDs where successive elements in the chain must
/// have proxy access.
let rec proxyChain (authorization: TransactionAuthorization) (finalAccount: AccountId) =
    match authorization with
    | SelfAuthorized -> [ finalAccount ]
    | AdminAuthorized adminId -> [ adminId ]
    | ProxyAuthorized (proxy, tail) -> proxy :: proxyChain tail finalAccount

/// Tests if an action is within an access token scope's ability to perform.
let isInScope (action: AccountAction) (scope: AccessTokenScope) =
    match action, scope with
    | _, UnboundedScope -> true
    | TransferAction _, TransferScope -> true
    | _, _ -> false
