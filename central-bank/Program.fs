module CentralBank.Entry

open System
open System.Threading
open Suave
open CentralBank.Accounting

[<EntryPoint>]
let main argv =
    let cts = new CancellationTokenSource()
    let conf = { defaultConfig with cancellationToken = cts.Token }
    let transaction = { AccessToken = None; Account = "@government"; Authorization = SelfAuthorized; Action = MintAction (10m, "@government") };
    let listening, server = startWebServerAsync conf (Successful.OK (transaction |> Json.toJson |> UTF8.toString))

    Async.Start(server, cts.Token)
    printfn "Make requests now"
    Console.ReadKey true |> ignore

    cts.Cancel()
    0
