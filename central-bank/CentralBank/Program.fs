module CentralBank.Main

open System
open System.IO
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

open Options
open Accounting
open Accounting.Helpers

type AppState =
    {
      /// The transaction processor's state.
      mutable TransactionProcessorState: InMemoryTransactionProcessor.State HistoryDatabaseProcessor.State

      /// The transaction ID counter.
      mutable IdCounter: uint64

      /// A lock on the transaction processor's state.
      StateLock: ReaderWriterLockSlim }

let applyTransaction = HistoryDatabaseProcessor.apply

let wrapTransactionRequest (request: TransactionRequest) (state: AppState) =
    { Id = Interlocked.Increment(&state.IdCounter)
      PerformedAt = DateTime.UtcNow
      Account = request.Account
      Authorization = request.Authorization
      AccessToken = request.AccessToken
      Action = request.Action }

/// Processes a trusted transaction.
let processTrustedTransaction (request: TransactionRequest) (state: AppState) =
    let transaction = wrapTransactionRequest request state

    match isQuery transaction.Action with
    | true ->
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
    | false ->
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

/// Processes an untrusted transaction.
let processUntrustedTransaction (request: TransactionRequest) (state: AppState) =
    // Check that the transaction has an access token. Transactions without
    // access tokens are possible, but they may not originate from beyond
    // the central bank server.
    match request.AccessToken with
    | None -> Error UnauthorizedError
    | Some _ -> processTrustedTransaction request state

let configureServices (services: IServiceCollection) =
    // Add Giraffe dependencies
    services.AddGiraffe() |> ignore

/// Registers a root account that can be used to set up further accounts.
let withRoot (state: InMemoryTransactionProcessor.State) =
    InMemoryTransactionProcessor.setAccount
        "@root"
        { Balance = 0m
          ProxyAccess = Set.empty
          Privileges = Set.singleton UnboundedScope
          Tokens = Map.empty }
        state

let okOrPanic result =
    match result with
    | Ok x -> x
    | Error e -> failwithf "%A" e

let rootTransactionRequest (action: AccountAction): TransactionRequest =
    { Account = "@root"
      Authorization = SelfAuthorized
      AccessToken = None
      Action = action }

/// Gets all tokens for the root account. If there are no such tokens,
/// then a new unbounded token is created to facilitate setup.
let rec rootTokens (state: AppState) =
    let rootAcc =
        Map.find "@root" state.TransactionProcessorState.InnerState.Accounts

    if Map.isEmpty rootAcc.Tokens then
        let tokenId = generateTokenId (Random())
        let tokenScopes = Set.singleton UnboundedScope

        let request =
            CreateTokenAction(tokenId, tokenScopes)
            |> rootTransactionRequest

        processTrustedTransaction request state
        |> okOrPanic
        |> ignore

        Map.empty |> Map.add tokenId tokenScopes
    else
        rootAcc.Tokens

let relativeTo (relativeBase: string) (path: string) =
    Path.Combine(relativeBase, path)

let start (configPath: string) (config: AppConfiguration) =
    let databasePath =
        match config.DatabasePath with
        | null -> "database.db"
        | other -> other
        |> relativeTo (Path.GetDirectoryName configPath)

    use database =
        new LiteDatabase(databasePath, FSharpBsonMapper())

    use stateLock = new ReaderWriterLockSlim()

    let appState =
        { TransactionProcessorState =
              InMemoryTransactionProcessor.emptyState
              |> withRoot
              |> HistoryDatabaseProcessor.load database InMemoryTransactionProcessor.apply
          IdCounter =
              HistoryDatabaseProcessor.loadTransactions database
              |> Seq.map (fun t -> t.Id)
              |> Seq.append (Seq.singleton 0UL)
              |> Seq.max
          StateLock = stateLock }

    // Print root account tokens.
    printfn "Root tokens:"

    rootTokens appState
    |> Map.toSeq
    |> Seq.map (fun (k, v) -> sprintf " - %s %A" k (v |> Seq.map (sprintf "%A") |> String.concat ", "))
    |> String.concat Environment.NewLine
    |> printfn "%s"

    /// Processes a transaction request.
    let processTransactionRequest (next: HttpFunc) (ctx: HttpContext) =
        task {
            let! request =
                ctx.BindJsonAsync<TransactionRequest>()
                |> Async.AwaitTask

            return! json (processUntrustedTransaction request appState) next ctx
        }

    /// Routes requests.
    let webApp =
        POST
        >=> route TransactionClient.TransactionRoute
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

[<EntryPoint>]
let main argv =
    match parseOptions argv with
    | Success opts ->
        match parseConfig opts.ConfigPath with
        | Ok config ->
            start opts.ConfigPath config
            0
        | Error e ->
            printfn "Error: %s" e
            1
    | Fail errs ->
        printfn "Invalid: %A, Errors: %u" argv (Seq.length errs)
        1
    | Help
    | Version -> 0
