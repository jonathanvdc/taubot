module TauBot.EntryPoint

open System
open System.IO
open System.Threading
open System.Threading.Tasks
open Discord
open Discord.WebSocket
open Options
open LiteDB
open LiteDB.FSharp
open LiteDB.FSharp.Extensions

/// Tau bot's state.
type State =
    {
      /// The database for storing credentials.
      Database: LiteDatabase

      /// A reader/writer lock for the database.
      DatabaseLock: ReaderWriterLockSlim

      /// The bot's configuration.
      Config: AppConfiguration }

type AccountCredentials =
    {
      /// The Discord user's ID.
      Id: uint64

      /// The account's name.
      Name: string

      /// The account's access token.
      AccessToken: string }

/// Tries to find account credentials for a user.
let tryFindCredentials (state: State) (user: SocketUser) =
    try
        state.DatabaseLock.EnterReadLock()

        state
            .Database
            .GetCollection<AccountCredentials>()
            .tryFindOne <@ fun x -> x.Id = user.Id @>
    finally
        state.DatabaseLock.ExitReadLock()

/// Replies to a message.
let replyTo (message: SocketMessage) (replyBody: string) =
    let responseEmbed =
        EmbedBuilder()
            .WithThumbnailUrl(message.Author.GetAvatarUrl())
            .WithFields(
                [| EmbedFieldBuilder()
                       .WithName(message.Content)
                       .WithValue(replyBody) |]
            )
            .WithFooter(
                EmbedFooterBuilder()
                    .WithText(
                        sprintf
                            "This was sent in response to %s's message; you can safely disregard it if that's not you."
                            message.Author.Username
                    )
            )
            .Build()

    message.Channel.SendMessageAsync(embed = responseEmbed, messageReference = message.Reference)
    |> Async.AwaitTask

/// Handles an incoming message.
let handleMessage (state: State) (message: SocketMessage) =
    async {
        // Ignore messages from bots.
        if message.Author.IsBot then return ()

        match tryFindCredentials state message.Author with
        | Some credentials ->
            let! _ = replyTo message "I know you!"
            return ()
        | None ->
            // Reply to the message by saying that we don't know them.
            let! _ = replyTo message "Howdy! I don't know you yet. Would you like me to create a new account for you?"
            return ()
    }
    |> Async.StartAsTask
    :> Task

let relativeTo (relativeBase: string) (path: string) = Path.Combine(relativeBase, path)

/// Opens the tau bot database.
let openDatabase (configPath: string) (config: AppConfiguration) =
    let databasePath =
        match config.DatabasePath with
        | null -> "database.db"
        | other -> other
        |> relativeTo (Path.GetDirectoryName configPath)

    new LiteDatabase(databasePath, FSharpBsonMapper())

[<EntryPoint>]
let main argv =
    match parseOptions argv with
    | Fail _ -> 1
    | Help _
    | Version _ -> 0
    | Success opts ->
        match parseConfig opts.ConfigPath with
        | Error e ->
            printfn "Error: %s" e
            1
        | Ok config ->
            // Open the database.
            use database = openDatabase opts.ConfigPath config

            // Create a lock for the database.
            use databaseLock = new ReaderWriterLockSlim()

            // Create a Discord client.
            use client = new DiscordSocketClient()

            // Register a handler for messages.
            client.add_MessageReceived (
                Func<SocketMessage, Task>(
                    handleMessage
                        { Database = database
                          DatabaseLock = databaseLock
                          Config = config }
                )
            )

            async {
                // Log in and start listening.
                do!
                    client.LoginAsync(TokenType.Bot, config.DiscordToken)
                    |> Async.AwaitTask

                do! client.StartAsync() |> Async.AwaitTask

                // Block the program until the client calls it a day.
                do! Task.Delay(Timeout.Infinite) |> Async.AwaitTask
            }
            |> Async.RunSynchronously

            0
