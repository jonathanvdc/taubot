namespace Accounting.Tests

open Microsoft.VisualStudio.TestTools.UnitTesting
open Accounting
open Accounting.InMemoryTransactionProcessor

[<TestClass>]
type ProcessorTests() =

    member this.InitialState =
        emptyState
        |> setAccount
            "@prime-mover"
            { Balance = 0m
              ProxyAccess = Set.empty
              Privileges = Set.ofList [ UnboundedScope ]
              Tokens = Map.empty }

    member this.CreatePrimeMoverTransaction action =
        { Account = "@prime-mover"
          Action = action
          Authorization = SelfAuthorized
          AccessToken = None }

    member this.CreateAdminTransaction action accountId =
        { Account = accountId
          Action = action
          Authorization = AdminAuthorized "@prime-mover"
          AccessToken = None }

    member this.ExpectSuccess result =
        match result with
        | Ok x -> x
        | Error e -> raise (AssertFailedException("Expected success, got " + e.ToString()))

    member this.ApplyQuery transaction state =
        state
        |> apply transaction
        |> this.ExpectSuccess
        |> snd

    member this.ApplyAction transaction state =
        state
        |> apply transaction
        |> this.ExpectSuccess
        |> fst

    [<TestMethod>]
    member this.TestQueryInitialBalance() =
        this.InitialState
        |> this.ApplyQuery(this.CreatePrimeMoverTransaction QueryBalanceAction)
        |> (=) (BalanceResult 0m)
        |> Assert.IsTrue

    [<TestMethod>]
    member this.TestOpenAccount() =
        this.InitialState
        |> this.ApplyAction(this.CreatePrimeMoverTransaction (OpenAccountAction "user"))
        |> this.ApplyQuery(this.CreateAdminTransaction QueryBalanceAction "user")
        |> (=) (BalanceResult 0m)
        |> Assert.IsTrue
