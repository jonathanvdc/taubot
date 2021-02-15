module Accounting.LedgerProcessor

open System
open System.IO
open Newtonsoft.Json

/// A ledger processor's state.
type State<'a> =
    {
      /// The inner state.
      InnerState: 'a

      /// Applies a transaction to the inner state.
      InnerApply: 'a TransactionProcessor

      /// A path to the ledger file.
      LedgerPath: string }

/// Reads a ledger, returning a sequence of transactions.
/// Returns None if the ledger does not exist.
let readLedger (ledgerPath: string) =
    try
        File.ReadLines ledgerPath
        |> Seq.map JsonConvert.DeserializeObject<Transaction>
        |> Some
    with
    | :? FileNotFoundException
    | :? DirectoryNotFoundException -> None

/// Writes a transaction to a ledger.
let writeToLedger (transaction: Transaction) (ledgerPath: string) =
    File.AppendAllText(
        ledgerPath,
        JsonConvert.SerializeObject transaction
        + Environment.NewLine
    )

/// Processes a transaction.
let apply (transaction: Transaction) (state: 'a State): Result<'a State * TransactionResult, TransactionError> =
    match state.InnerApply transaction state.InnerState with
    | Error e -> Error e
    | Ok (newState, response) ->
        writeToLedger transaction state.LedgerPath
        Ok({ state with InnerState = newState }, response)

/// Reads a ledger's contents and creates a ledger processor.
let load emptyState innerApply initialTransactions ledgerPath =
    let wrap state =
        { InnerState = state
          InnerApply = innerApply
          LedgerPath = ledgerPath }

    let accumulateTransaction state t =
        match innerApply t state with
        | Ok (newState, _) -> newState
        | Error _ -> state

    let transactions =
        match readLedger ledgerPath with
        | None -> initialTransactions
        | Some ts -> ts

    transactions
    |> Seq.fold accumulateTransaction emptyState
    |> wrap
