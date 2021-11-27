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
open Accounting
open Accounting.Helpers
open Accounting.Commands

/// Tau bot's state.
type State =
    {
      /// The database for storing credentials.
      Database: LiteDatabase

      /// A reader/writer lock for the database.
      DatabaseLock: ReaderWriterLockSlim

      /// The discord client.
      DiscordClient: DiscordSocketClient

      /// The central bank transaction client.
      BankClient: TransactionClient

      /// The bot's configuration.
      Config: AppConfiguration

      /// A random number generator.
      Rng: Random }

type AccountCredentials =
    {
      /// The Discord user's ID.
      Id: string

      /// The account's name.
      Account: AccountId

      /// The account's access token.
      AccessToken: AccessTokenId }

/// Tries to find account credentials for a user.
let tryFindCredentials (state: State) (user: SocketUser) =
    try
        state.DatabaseLock.EnterReadLock()

        let userId = string user.Id

        state
            .Database
            .GetCollection<AccountCredentials>()
            .tryFindOne <@ fun x -> x.Id = userId @>
    finally
        state.DatabaseLock.ExitReadLock()

/// Adds account credentials for a user.
let addCredentials (state: State) (credentials: AccountCredentials) =
    try
        state.DatabaseLock.EnterWriteLock()

        state
            .Database
            .GetCollection<AccountCredentials>()
            .Insert(credentials)
        |> ignore
    finally
        state.DatabaseLock.ExitWriteLock()

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

    async {
        let! _ =
            message.Channel.SendMessageAsync(embed = responseEmbed, messageReference = message.Reference)
            |> Async.AwaitTask

        return ()
    }

let prefixes (state: State) =
    state.Config.Prefixes
    @ [ sprintf "<@%d>" state.DiscordClient.CurrentUser.Id
        sprintf "<@!%d>" state.DiscordClient.CurrentUser.Id ]

/// Reads a message's command, the text that this bot should process.
/// Returns None if the message includes no command for the bot.
let tryReadCommand (state: State) (message: SocketMessage) =
    let content = message.Content.Trim()

    let applicablePrefixes =
        prefixes state
        |> List.filter (fun prefix -> content.StartsWith(prefix))

    match applicablePrefixes with
    | [] -> None
    | prefix :: _ -> Some(content.Substring(prefix.Length).TrimStart())

/// Opens an account for a user.
let openAccount (state: State) (user: SocketUser) =
    let accountName = sprintf "discord/%d" user.Id
    let tokenId = generateTokenId state.Rng

    async {
        let! response =
            state.BankClient.PerformTransactionAsync(
                { Account = state.Config.BotAccountName
                  AccessToken = Some state.Config.BotAccountAccessToken
                  Authorization = SelfAuthorized
                  Action = OpenAccountAction(accountName, tokenId) }
            )

        match response with
        | Ok _ ->
            return
                Ok
                    { Id = string user.Id
                      Account = accountName
                      AccessToken = tokenId }
        | Error e -> return Error e
    }

let formatTransactionError (error: TransactionError) =
    match error with
    | AccountAlreadyExistsError -> "Account already exists."
    | TokenAlreadyExistsError -> "Token already exists."
    | ActionNotImplementedError -> "Command has not been implemented yet."
    | DestinationDoesNotExistError -> "The destination account does not exist."
    | UnauthorizedError -> "You are not authorized to perform that action."
    | InsufficientFundsError -> "You do not have sufficient funds to perform that action."
    | InvalidAmountError -> "That is not a valid amount."
    | NetworkError (code, msg) when String.IsNullOrWhiteSpace(msg) ->
        sprintf "Received an HTTP %s error." (code.ToString())
    | NetworkError (code, msg) -> sprintf "Received an HTTP %s error. Response: %s" (code.ToString()) msg

let formatScopes (scopes: AccessScope Set) =
    scopes
    |> Set.map string
    |> List.ofSeq
    |> List.sort
    |> String.concat ", "

let formatTransactionResult (request: TransactionRequest) (result: TransactionResult) =
    match result with
    | SuccessfulResult id -> sprintf "Transaction performed with ID %d." id
    | AccessScopesResult scopes ->
        formatScopes scopes
        |> match request.Action with
           | QueryPrivilegesAction -> sprintf "Privileges assigned to %s: %s." request.Account
           | _ -> sprintf "Access scopes: %s."
    | AccessTokenResult id ->
        match request.Action with
        | CreateTokenAction (_, scopes) ->
            sprintf "Created access token for %s with ID `%s` and scopes %s." request.Account id (formatScopes scopes)
        | OpenAccountAction (name, _) -> sprintf "Opened account %s with access token ID `%s`" name id
        | _ -> sprintf "Access token with ID `%s`" id
    | BalanceResult value -> sprintf "%s's balance is %d." request.Account value
    | HistoryResult transactions ->
        // TODO: format this better.
        sprintf "Transactions: %A" transactions

let formatCommandError (command: string) (error: CommandError) =
    match error with
    | UnknownCommand t -> sprintf "Unknown command %s." t.Text
    | ExpectedNumber t -> sprintf "Expected a number, found %s." t.Text
    | ExpectedPositiveNumber t -> sprintf "Expected a positive number, found %s." t.Text
    | UnexpectedAdmin t -> sprintf "Misplaced %s command." t.Text
    | UnexpectedProxy t -> sprintf "Misplaced %s command." t.Text
    | UnexpectedToken t -> sprintf "Unexpected token: %s." t.Text
    | UnfinishedCommand -> sprintf "Unfinished or empty command."

let discordMentionRegex = Text.RegularExpressions.Regex(@"\<@?(\d+)\>", Text.RegularExpressions.RegexOptions.Compiled)

/// Expands all Discord mentions in a command by replacing them with (theoretical)
/// account names.
let expandDiscordMentions (command: string) =
    discordMentionRegex.Replace(command, fun x -> sprintf "discord/%s" x.Groups[0].Value)

/// Handles an incoming message.
let handleMessage (state: State) (message: SocketMessage) =
    async {
        try
            // Ignore messages from bots.
            if message.Author.IsBot then return ()

            // Extract the user's command from the message.
            match tryReadCommand state message with
            | None ->
                // Ignore messages that are not addressed to us.
                return ()
            | Some command ->
                let creds = tryFindCredentials state message.Author
                let command = expandDiscordMentions command

                match creds with
                | Some credentials ->
                    // Parse the command as a transaction request.
                    match parseAsTransactionRequest credentials.Account credentials.AccessToken command with
                    | Ok request ->
                        // Perform the transaction.
                        let! response = state.BankClient.PerformTransactionAsync(request)

                        // Report the result.
                        match response with
                        | Ok result ->
                            return!
                                result
                                |> formatTransactionResult request
                                |> replyTo message
                        | Error e -> return! e |> formatTransactionError |> replyTo message
                    | Error e -> return! e |> formatCommandError command |> replyTo message
                | None ->
                    if command.ToLowerInvariant() = "open" then
                        // Open a new account for the user.
                        let! response = openAccount state message.Author

                        match response with
                        | Ok credentials ->
                            // Add the credentials to the database.
                            addCredentials state credentials

                            // Notify the user that we opened an account for them.
                            return! replyTo message "Account opened successfully!"
                        | Error AccountAlreadyExistsError ->
                            return!
                                replyTo message "You already have an account, but it is not registered with this bot."
                        | Error e ->
                            return!
                                replyTo
                                    message
                                    (formatTransactionError e
                                     |> sprintf "error while opening account: %s")
                    else
                        // Reply to the message by saying that we don't know them.
                        return!
                            replyTo
                                message
                                (sprintf
                                    "Howdy! I don't know you yet. Would you like me to create a new account for you? If so, send me the following message: `%s open`"
                                    (prefixes state |> List.head))
        with e ->
            eprintfn "Exception encountered: %A" e
            return! replyTo message (sprintf "Whoops. I encountered an internal exception.")
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

            // Create a central bank client.
            use bankClient = new TransactionClient(config.BankUrl)

            // Register a handler for messages.
            client.add_MessageReceived (
                Func<SocketMessage, Task>(
                    handleMessage
                        { Database = database
                          DatabaseLock = databaseLock
                          DiscordClient = client
                          BankClient = bankClient
                          Config = config
                          Rng = Random() }
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
