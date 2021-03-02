module TauBot.Options

open System.IO
open CommandLine
open Newtonsoft.Json

type Options =
    { [<Value(0, MetaName = "CONFIG_PATH", HelpText = "A path to a JSON configuration file.", Required = true)>]
      ConfigPath: string }

let inline (|Success|Help|Version|Fail|) (result: ParserResult<'a>) =
    match result with
    | :? (Parsed<'a>) as parsed -> Success(parsed.Value)
    | :? (NotParsed<'a>) as notParsed when notParsed.Errors.IsHelp() -> Help
    | :? (NotParsed<'a>) as notParsed when notParsed.Errors.IsVersion() -> Version
    | :? (NotParsed<'a>) as notParsed -> Fail(notParsed.Errors)
    | _ -> failwith "invalid parser result"

let parseOptions argv =
    Parser.Default.ParseArguments<Options>(argv)

type AppConfiguration =
    { [<JsonProperty(Required = Required.Always)>]
      DatabasePath: string
      [<JsonProperty(Required = Required.Always)>]
      BankUrl: string
      [<JsonProperty(Required = Required.Always)>]
      DiscordToken: string
      [<JsonProperty(Required = Required.Always)>]
      BotAccountName: string
      [<JsonProperty(Required = Required.Always)>]
      BotAccountAccessToken: string
      [<JsonProperty(Required = Required.Always)>]
      Prefixes: string list }

/// Parses a configuration file.
let parseConfig configPath =
    try
        configPath
        |> File.ReadAllText
        |> JsonConvert.DeserializeObject<AppConfiguration>
        |> Ok
    with
    | :? DirectoryNotFoundException as e -> Core.Error e.Message
    | :? FileNotFoundException as e -> Core.Error e.Message
