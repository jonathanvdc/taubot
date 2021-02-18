namespace Accounting

open System
open System.Net.Http
open Newtonsoft.Json
open System.Text

/// A client that allows one to interact with a central bank server.
type TransactionClient(baseUrl: string) =
    let httpClient = new HttpClient()

    /// The route to the transaction-posting API.
    static member TransactionRoute = "/api/transaction"

    /// Asynchronously requests for a transaction to be performed.
    member this.PerformTransactionAsync(request: TransactionRequest) =
        async {
            let postUrl =
                sprintf "%s%s" baseUrl TransactionClient.TransactionRoute

            let json = JsonConvert.SerializeObject(request)

            use content =
                new StringContent(json, Encoding.UTF8, "application/json")

            let! response =
                httpClient.PostAsync(postUrl, content)
                |> Async.AwaitTask

            let! body =
                response.Content.ReadAsStringAsync()
                |> Async.AwaitTask

            return
                match response.IsSuccessStatusCode with
                | true -> JsonConvert.DeserializeObject<Result<TransactionResult, TransactionError>>(body)
                | false -> Error(NetworkError(response.StatusCode, body))
        }

    interface IDisposable with
        member this.Dispose() = httpClient.Dispose()
