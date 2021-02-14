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

    member this.ApplyPrimeMover action state =
        this.ApplyAction(this.CreatePrimeMoverTransaction action) state

    member this.QueryPrimeMover action state =
        this.ApplyQuery(this.CreatePrimeMoverTransaction action) state

    [<TestMethod>]
    member this.TestQueryInitialBalance() =
        this.InitialState
        |> this.QueryPrimeMover(QueryBalanceAction)
        |> (=) (BalanceResult 0m)
        |> Assert.IsTrue

    [<TestMethod>]
    member this.TestOpenAccount() =
        this.InitialState
        |> this.ApplyPrimeMover(OpenAccountAction "user")
        |> this.ApplyQuery(this.CreateAdminTransaction QueryBalanceAction "user")
        |> (=) (BalanceResult 0m)
        |> Assert.IsTrue

    [<TestMethod>]
    member this.TestMint() =
        this.InitialState
        |> this.ApplyPrimeMover(MintAction 10m)
        |> this.ApplyQuery(this.CreatePrimeMoverTransaction QueryBalanceAction)
        |> (=) (BalanceResult 10m)
        |> Assert.IsTrue

    [<TestMethod>]
    member this.TestOpenMintAndTransfer() =
        this.InitialState
        |> this.ApplyPrimeMover(OpenAccountAction "user")
        |> this.ApplyPrimeMover(MintAction 10m)
        |> this.ApplyPrimeMover(TransferAction(10m, "user"))
        |> this.ApplyQuery(this.CreateAdminTransaction QueryBalanceAction "user")
        |> (=) (BalanceResult 10m)
        |> Assert.IsTrue
