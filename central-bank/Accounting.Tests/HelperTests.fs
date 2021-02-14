namespace Accounting.Tests

open Microsoft.VisualStudio.TestTools.UnitTesting
open Accounting
open Accounting.Helpers

[<TestClass>]
type HelperTests() =

    [<TestMethod>]
    member this.LowLevelAccess() =
        // Compose a list of actions and the scopes they require.
        let elements =
            [ (MintAction 10m, MintScope)
              (TransferAction(10m, "@government"), TransferScope)
              (QueryBalanceAction, QueryBalanceScope) ]

        let scopes = List.map snd elements |> Set.ofList

        // Check that every action requires its own scope and no other
        // scope.
        let check (action, scope) =
            Assert.IsTrue(isInScope action scope)
            Assert.IsTrue(isInScopeForAny action scopes)

            Set.remove scope scopes
            |> Set.map (isInScope action >> Assert.IsFalse)
            |> ignore

            Assert.IsFalse(Set.remove scope scopes |> isInScopeForAny action)

        List.map check elements |> ignore

    [<TestMethod>]
    member this.ProxyChainConstruction() =
        { Account = "@government"
          Action = QueryBalanceAction
          Authorization = SelfAuthorized
          AccessToken = None }
        |> proxyChain
        |> (=) [ "@government" ]
        |> Assert.IsTrue

        { Account = "@government"
          Action = QueryBalanceAction
          Authorization = AdminAuthorized "admin"
          AccessToken = None }
        |> proxyChain
        |> (=) [ "admin" ]
        |> Assert.IsTrue

        { Account = "@government"
          Action = QueryBalanceAction
          Authorization = ProxyAuthorized("admin", SelfAuthorized)
          AccessToken = None }
        |> proxyChain
        |> (=) [ "admin"; "@government" ]
        |> Assert.IsTrue

        { Account = "@government"
          Action = QueryBalanceAction
          Authorization = ProxyAuthorized("foo", ProxyAuthorized("admin", SelfAuthorized))
          AccessToken = None }
        |> proxyChain
        |> (=) [ "foo"; "admin"; "@government" ]
        |> Assert.IsTrue

    [<TestMethod>]
    member this.FinalAuthorizerConstruction() =
        { Account = "@government"
          Action = QueryBalanceAction
          Authorization = SelfAuthorized
          AccessToken = None }
        |> finalAuthorizer
        |> (=) "@government"
        |> Assert.IsTrue

        { Account = "@government"
          Action = QueryBalanceAction
          Authorization = AdminAuthorized "admin"
          AccessToken = None }
        |> finalAuthorizer
        |> (=) "admin"
        |> Assert.IsTrue

        { Account = "@government"
          Action = QueryBalanceAction
          Authorization = ProxyAuthorized("admin", SelfAuthorized)
          AccessToken = None }
        |> finalAuthorizer
        |> (=) "@government"
        |> Assert.IsTrue

        { Account = "@government"
          Action = QueryBalanceAction
          Authorization = ProxyAuthorized("foo", ProxyAuthorized("admin", SelfAuthorized))
          AccessToken = None }
        |> finalAuthorizer
        |> (=) "@government"
        |> Assert.IsTrue
