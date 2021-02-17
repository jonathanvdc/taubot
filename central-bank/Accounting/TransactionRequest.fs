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
      AccessToken: AccessTokenId

      /// The action being performed.
      Action: AccountAction }
