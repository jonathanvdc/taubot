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
    let toTransaction (counter: byref<TransactionId>) (request: TransactionRequest): Transaction =
      { Id = Interlocked.Increment(&counter)
        PerformedAt = DateTime.UtcNow
        Account = request.Account
        Authorization = request.Authorization
        AccessToken = request.AccessToken
        Action = request.Action }
