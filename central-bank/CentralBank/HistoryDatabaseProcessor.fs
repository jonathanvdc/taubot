/// A transaction processor that retains a database of all transactions.
module Accounting.HistoryDatabaseProcessor

open LiteDB
open LiteDB.FSharp.Extensions

/// A history database processor's state.
type State<'a> =
    {
      /// The inner state.
      InnerState: 'a

      /// Applies a transaction to the inner state.
      InnerApply: 'a TransactionProcessor

      /// The database to use for storing entries.
      Database: LiteDatabase }

/// Writes a transaction to the database.
let writeToDatabase (transaction: Transaction) (database: LiteDatabase) =
    database
        .GetCollection<Transaction>()
        .Insert(transaction)
    |> ignore

/// Processes a transaction.
let apply (transaction: Transaction) (state: 'a State): Result<'a State * TransactionResult, TransactionError> =
    match state.InnerApply transaction state.InnerState with
    | Error ActionNotImplementedError ->
        // If the action was not implemented by the inner transaction performer,
        // then now is our time to shine.
        match transaction.Action with
        | QueryHistoryAction since ->
            let results =
                state
                    .Database
                    .GetCollection<Transaction>()
                    .findMany<@ fun t ->
                                    t.PerformedAt >= since
                                    && (t.Account = transaction.Account
                                        || match t.Action with
                                           | TransferAction (_, dest) -> dest = transaction.Account
                                           | _ -> false) @>
                |> List.ofSeq
                |> List.sortByDescending (fun t -> t.PerformedAt)

            Ok(state, HistoryResult results)
        | _ -> Error ActionNotImplementedError
    | Error e -> Error e
    | Ok (newState, response) ->
        writeToDatabase transaction state.Database
        Ok({ state with InnerState = newState }, response)

let wrap database apply state =
    { InnerState = state
      InnerApply = apply
      Database = database }
