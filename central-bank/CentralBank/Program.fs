open System.Threading
open Microsoft.AspNetCore.Builder
open Microsoft.AspNetCore.Hosting
open Microsoft.AspNetCore.Http
open Microsoft.Extensions.Hosting
open Microsoft.Extensions.DependencyInjection
open Giraffe
open FSharp.Control.Tasks.V2

open Accounting
open Accounting.Helpers

let mutable state = InMemoryTransactionProcessor.emptyState
let stateLock = new ReaderWriterLockSlim()

/// Processes a transaction.
let processTransaction transaction =
    // Check that the transaction has an access token. Transactions without
    // access tokens are possible, but they may not originate from beyond
    // the central bank server.
    match transaction.AccessToken, isQuery transaction.Action with
    | None, _ -> Error UnauthorizedError
    | _, true ->
        try
            // Acquire a write lock so the state cannot be modified as we
            // read it.
            stateLock.EnterReadLock()

            // Apply the transaction and return the result. We don't have
            // to update the state because queries do not change state.
            match InMemoryTransactionProcessor.apply transaction state with
            | Ok (_, response) -> Ok response
            | Error e -> Error e

        finally
            // Release the read lock so other threads can modify the state.
            stateLock.ExitReadLock()
    | _, false ->
        try
            // Acquire a write lock so no two threads modify the state at the
            // same time.
            stateLock.EnterWriteLock()

            // Apply the transaction and respond.
            match InMemoryTransactionProcessor.apply transaction state with
            | Ok (newState, response) ->
                state <- newState
                Ok response
            | Error e -> Error e

        finally
            // Release the write lock so other threads can modify the state.
            stateLock.ExitWriteLock()

/// Processes a transaction request.
let processTransactionRequest (next: HttpFunc) (ctx: HttpContext) =
    task {
        let! transaction =
            ctx.BindJsonAsync<Transaction>()
            |> Async.AwaitTask

        return! json (processTransaction transaction) next ctx
    }

/// Routes requests.
let webApp =
    POST
    >=> route "/api/transaction"
    >=> processTransactionRequest

let configureApp (app: IApplicationBuilder) =
    // Add Giraffe to the ASP.NET Core pipeline
    app.UseGiraffe webApp

let configureServices (services: IServiceCollection) =
    // Add Giraffe dependencies
    services.AddGiraffe() |> ignore

[<EntryPoint>]
let main _ =
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
