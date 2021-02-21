namespace Accounting

open System

/// A unique account identifier.
type AccountId = string

type CurrencyAmount = decimal

/// A unique access token identifier.
type AccessTokenId = string

/// A unique transaction identifier.
type TransactionId = uint64

/// An access scope, which defines which transactions may be
/// performed. Access scopes may affect either access tokens or
/// user privileges.
type AccessScope =
    /// Allows for any action to be performed.
    | UnboundedScope

    /// Allows for the account's balance to be queried.
    | QueryBalanceScope

    /// Allows for this account's transaction history to be queried.
    | QueryHistoryScope

    /// Allows for this account's authorizations to be queried.
    | QueryPrivilegesScope

    /// Allows transfers.
    | TransferScope

    /// Allows for the minting of new currency.
    | MintScope

    /// Allows for the opening of new accounts.
    | OpenAccountScope

    /// Allows an account to perform actions as another account
    /// without proxy access. Admin accounts cannot perform types
    /// of actions they are themselves not privileged for (e.g.,
    /// an admin cannot mint currency using someone else's account
    /// unless the admin has minting privileges).
    | AdminScope

/// An action that an account can perform.
type AccountAction =
    /// Transfers an amount from one account to another.
    | TransferAction of amount: CurrencyAmount * destination: AccountId

    /// Generates an amount and adds it to the account balance.
    | MintAction of amount: CurrencyAmount

    /// An action that queries an account's balance.
    | QueryBalanceAction

    /// An action that queries an account's privileges.
    | QueryPrivilegesAction

    /// An action that queries an account's history starting at a particular
    /// point in time.
    | QueryHistoryAction of since: DateTime

    /// An action that opens a new account and creates a token that
    /// can be used to configure the new account.
    | OpenAccountAction of accountId: AccountId * tokenId : AccessTokenId

    /// An action that creates a new token.
    | CreateTokenAction of tokenId: AccessTokenId * tokenScopes: AccessScope Set

    /// An action that adds privileges to an account.
    | AddPrivilegesAction of accountId: AccountId * privileges: AccessScope Set

    /// An action that removes privileges from an account.
    | RemovePrivilegesAction of accountId: AccountId * privileges: AccessScope Set

/// A description of how a transaction is authorized.
type TransactionAuthorization =
    /// Indicates that a transaction is ultimately authorized
    /// by the account to which the transaction applies.
    | SelfAuthorized

    /// Indicates that a transaction is authorized by an
    /// admin with heightened privileges.
    | AdminAuthorized of adminId: AccountId

    /// Indicates that a transaction is authorized by proxy.
    | ProxyAuthorized of proxy: AccountId * tail: TransactionAuthorization

/// A transaction is an action performed by an account.
/// Transactions are self-contained and contain all information
/// required to validate the transaction.
type Transaction =
    {
      /// The transaction's unique identifier.
      Id: TransactionId

      /// The point in time at which the transaction was performed.
      PerformedAt: DateTime

      /// The account performing the transaction.
      Account: AccountId

      /// The authorization (chain) for the transaction.
      Authorization: TransactionAuthorization

      /// An optional access token that is used as the root of the
      /// authorization chain.
      AccessToken: AccessTokenId option

      /// The action being performed.
      Action: AccountAction }

/// The result of successfully applying a transaction.
type TransactionResult =
    /// Indicates that the transaction was successfully applied
    /// and that no further feedback is provided.
    | SuccessfulResult of transactionId: TransactionId

    /// A result that is composed of a list of past transactions.
    | HistoryResult of transactions: Transaction list

    /// Produces the balance of an account.
    | BalanceResult of amount: CurrencyAmount

    /// Returns an access token.
    | AccessTokenResult of tokenId: AccessTokenId

    /// Produces a set of access scopes.
    | AccessScopesResult of scopes: AccessScope Set

type TransactionError =
    /// Indicates the the transaction was inadequately authorized.
    | UnauthorizedError

    /// Indicates that there were not enough funds to complete a
    /// transaction.
    | InsufficientFundsError

    /// Indicates that the destination account does not exist.
    | DestinationDoesNotExistError

    /// Indicates that a transaction specified an invalid amount.
    | InvalidAmountError

    /// A response to an account creation request, indicating that
    /// the account already exists.
    | AccountAlreadyExistsError

    /// A response to a token creation request, indicating that
    /// the token already exists.
    | TokenAlreadyExistsError

    /// Indicates that the action has not been implemented (yet).
    | ActionNotImplementedError

    /// Indicates that a network error occurred.
    | NetworkError of statusCode: Net.HttpStatusCode * responseBody: string

/// Applies a transaction. If the transaction can be applied,
/// a result is returned; otherwise, an error is returned.
type TransactionProcessor<'state> = Transaction -> 'state -> Result<'state * TransactionResult, TransactionError>
