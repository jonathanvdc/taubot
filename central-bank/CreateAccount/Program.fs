open System
open CommandLine
open Accounting
open Accounting.Helpers

type Options =
    { [<Option("account-name", HelpText = "The name of the account to create.", Required = true)>]
      AccountName: string

      [<Option("root-name", HelpText = "The name of the root account.", Required = false)>]
      RootAccountName: string option

      [<Option("root-access-token", HelpText = "An access token for the root account.", Required = true)>]
      RootAccessToken: string

      [<Option("server", HelpText = "A URL to the central bank server.", Required = true)>]
      ServerUrl: string

      [<Option("make-broker",
               Default = false,
               HelpText = "Specifies if the newly created account should be authorized as a broker.",
               Required = false)>]
      MakeBroker: bool }

let inline (|Success|Help|Version|Fail|) (result: ParserResult<'a>) =
    match result with
    | :? (Parsed<'a>) as parsed -> Success(parsed.Value)
    | :? (NotParsed<'a>) as notParsed when notParsed.Errors.IsHelp() -> Help
    | :? (NotParsed<'a>) as notParsed when notParsed.Errors.IsVersion() -> Version
    | :? (NotParsed<'a>) as notParsed -> Fail(notParsed.Errors)
    | _ -> failwith "invalid parser result"

let parseOptions argv =
    Parser.Default.ParseArguments<Options>(argv)

let performRootAction opts action =
    use client = new TransactionClient(opts.ServerUrl)

    let request: TransactionRequest =
        { Account =
              opts.RootAccountName
              |> Option.defaultValue "@root"
          Authorization = SelfAuthorized
          Action = action
          AccessToken = Some opts.RootAccessToken }

    client.PerformTransactionAsync request
    |> Async.RunSynchronously

[<EntryPoint>]
let main argv =
    match parseOptions argv with
    | Success opts ->
        let tokenId = generateTokenId (Random())

        match performRootAction opts (OpenAccountAction(opts.AccountName, tokenId)) with
        | Ok _ ->
            printfn "Account %s has been created. Its access token is: %s" opts.AccountName tokenId

            if opts.MakeBroker then
                match performRootAction opts (AddPrivilegesAction(opts.AccountName, Set.singleton OpenAccountScope)) with
                | Ok _ -> printfn "Account %s has been authorized to open accounts." opts.AccountName
                | Error e -> printfn "Error: %A" e
        | Error AccountAlreadyExistsError -> printfn "Account %s already exists." opts.AccountName
        | Error UnauthorizedError -> printfn "Authorization error. Are you sure your access token ID is correct?"
        | Error e -> printfn "Error: %A" e

        0
    | Fail errs ->
        printfn "Invalid: %A, Errors: %u" argv (Seq.length errs)
        1
    | Help
    | Version -> 0
