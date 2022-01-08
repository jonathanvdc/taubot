module BankTerminal.Options

open CommandLine

type Options =
    { [<Option("account-name", HelpText = "The name of the account to use.", Required = true)>]
      AccountName: string

      [<Option("access-token", HelpText = "An access token for the account.", Required = true)>]
      RootAccessToken: string

      [<Option("server", HelpText = "A URL to the central bank server.", Required = true)>]
      ServerUrl: string }

let inline (|Success|Help|Version|Fail|) (result: ParserResult<'a>) =
    match result with
    | :? (Parsed<'a>) as parsed -> Success(parsed.Value)
    | :? (NotParsed<'a>) as notParsed when notParsed.Errors.IsHelp() -> Help
    | :? (NotParsed<'a>) as notParsed when notParsed.Errors.IsVersion() -> Version
    | :? (NotParsed<'a>) as notParsed -> Fail(notParsed.Errors)
    | _ -> failwith "invalid parser result"

let parseOptions argv =
    Parser.Default.ParseArguments<Options>(argv)
