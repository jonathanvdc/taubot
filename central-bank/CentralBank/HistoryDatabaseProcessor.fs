/// A transaction processor that retains a database of all transactions.
module Accounting.HistoryDatabaseProcessor

open System
open System.IO
open LiteDB

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
    | Error e -> Error e
    | Ok (newState, response) ->
        writeToDatabase transaction state.Database
        Ok({ state with InnerState = newState }, response)
