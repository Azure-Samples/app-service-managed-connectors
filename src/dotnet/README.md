# C# / ASP.NET Core

Receive an Outlook event at `/api/webhook` and flag only test-prefix messages.

- [Program.cs](Program.cs): typed payload deserialization, managed-identity
  `Office365Client`, callback routing, and error handling.
- [Processing.cs](Processing.cs): batch validation and subject-prefix filtering.
- Runtime: .NET 10; pinned `Azure.Connectors.Sdk` and `Azure.Identity` packages.

From the repository root:

```bash
dotnet run --project tests/dotnet/Checks.csproj -- tests/payloads.json
```

Follow the shared [setup and deployment instructions](../../README.md#deploy-to-azure)
to provision only this authenticated app and its connector. From the repository
root, run `cd src/dotnet`, create an AZD environment, then run `azd provision`
and `azd deploy`. This folder's `azure.yaml` does not deploy the other languages.

Local tests replace the outbound action. Local ASP.NET Core does not implement
the deployed Easy Auth policy. See the shared [authentication model](../../README.md#architecture-and-authentication)
and [live verification steps](../../README.md#connect-outlook-and-create-triggers).

For a more advanced workflow, see the separate
[.NET email-triage sample](https://github.com/Azure-Samples/app-service-connectors-net-e2e-email-users-teams).
