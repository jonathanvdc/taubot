module CentralBank.Main

open System
open System.Threading
open Microsoft.AspNetCore.Builder
open Microsoft.AspNetCore.Hosting
open Microsoft.AspNetCore.Http
open Microsoft.Extensions.Hosting
open Microsoft.Extensions.DependencyInjection
open Giraffe
open FSharp.Control.Tasks.V2

open LiteDB
open LiteDB.FSharp

open Accounting
open Accounting.Helpers

type AppState =
    {
      /// The transaction processor's state.
      mutable TransactionProcessorState: InMemoryTransactionProcessor.State HistoryDatabaseProcessor.State

      /// A lock on the transaction processor's state.
      StateLock: ReaderWriterLockSlim

      /// A random number generator.
      Rng: Random }

let applyTransaction = HistoryDatabaseProcessor.apply

/// Processes a transaction.
let processTransaction (request: TransactionRequest) (state: AppState) =
    let transaction =
        { Id = generateTokenId state.Rng
          PerformedAt = DateTime.UtcNow
          Account = request.Account
          Authorization = request.Authorization
          AccessToken = request.AccessToken
          Action = request.Action }

    // Check that the transaction has an access token. Transactions without
    // access tokens are possible, but they may not originate from beyond
    // the central bank server.
    match transaction.AccessToken, isQuery transaction.Action with
    | None, _ -> Error UnauthorizedError
    | Some _, true ->
        try
            // Acquire a write lock so the state cannot be modified as we
            // read it.
            state.StateLock.EnterReadLock()

            // Apply the transaction and return the result. We don't have
            // to update the state because queries do not change state.
            match applyTransaction transaction state.TransactionProcessorState with
            | Ok (_, response) -> Ok response
            | Error e -> Error e

        finally
            // Release the read lock so other threads can modify the state.
            state.StateLock.ExitReadLock()
    | Some _, false ->
        try
            // Acquire a write lock so no two threads modify the state at the
            // same time.
            state.StateLock.EnterWriteLock()

            // Apply the transaction and respond.
            match applyTransaction transaction state.TransactionProcessorState with
            | Ok (newState, response) ->
                state.TransactionProcessorState <- newState
                Ok response
            | Error e -> Error e

        finally
            // Release the write lock so other threads can modify the state.
            state.StateLock.ExitWriteLock()

let configureServices (services: IServiceCollection) =
    // Add Giraffe dependencies
    services.AddGiraffe() |> ignore

[<EntryPoint>]
let main _ =
    use database = new LiteDatabase("transactions.db", FSharpBsonMapper())
    use stateLock = new ReaderWriterLockSlim()

    let appState =
        { TransactionProcessorState =
              InMemoryTransactionProcessor.emptyState
              |> HistoryDatabaseProcessor.wrap database InMemoryTransactionProcessor.apply
          StateLock = stateLock
          Rng = Random() }

    /// Processes a transaction request.
    let processTransactionRequest (next: HttpFunc) (ctx: HttpContext) =
        task {
            let! request =
                ctx.BindJsonAsync<TransactionRequest>()
                |> Async.AwaitTask

            return! json (processTransaction request appState) next ctx
        }

    /// Routes requests.
    let webApp =
        POST
        >=> route "/api/transaction"
        >=> processTransactionRequest

    let configureApp (app: IApplicationBuilder) =
        // Add Giraffe to the ASP.NET Core pipeline
        app.UseGiraffe webApp

    Host
        .CreateDefaultBuilder()
        .ConfigureWebHostDefaults(fun webHostBuilder ->
            webHostBuilder
                .Configure(configureApp)
                .ConfigureServices(configureServices)
            |> ignore)
        .Build()
        .Run()

    0
