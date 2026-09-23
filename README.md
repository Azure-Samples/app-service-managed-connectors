---
page_type: sample
languages:
- csharp
- javascript
- typescript
- python
- bicep
products:
- azure-app-service
name: Managed connectors in Azure App Service
description: Receive Outlook events and call managed connector actions from C#, JavaScript, TypeScript, and Python web apps using managed identities.
urlFragment: app-service-managed-connectors
---

# Managed connectors in Azure App Service

Receive an Office 365 Outlook event in an ordinary HTTP route, then use a managed
connector SDK to flag the email. These four equivalent samples demonstrate
**App Service as a managed connector trigger destination**, without a Functions
trigger binding or a Logic Apps workflow.

| Language | Sample | Framework |
|---|---|---|
| C# | [src/dotnet](src/dotnet) | ASP.NET Core / .NET 10 |
| JavaScript | [src/javascript](src/javascript) | Express / Node.js 24 |
| TypeScript | [src/typescript](src/typescript) | Express / Node.js 24 |
| Python | [src/python](src/python) | FastAPI / Python 3.14 |

**Looking for a complete .NET workflow?** See the separate
[ASP.NET Core email-triage sample](https://github.com/Azure-Samples/app-service-connectors-net-e2e-email-users-teams),
which receives Outlook events, enriches the sender through Office 365 Users,
posts a Teams notification, and flags the email. The C# sample above is the
minimal equivalent of the other language samples in this repository.

Each sample handles `POST /api/webhook`, validates the batch in `body.value`,
and flags only messages whose subject starts with `TEST_SUBJECT_PREFIX`
(default: `[connector-pivots]`). Other messages are counted but not modified.
Successful processing returns `{"received":1,"flagged":1}` for one matching email.
The code does not send email, post Teams messages, or log email contents.

> **Preview:** Managed connectors and these SDKs are in public preview. These are
> evaluation samples, not production-ready applications. API coverage and shapes
> can change. Use a dedicated test mailbox and account for connector consumption
> and App Service charges.

## Architecture and authentication

1. The connector namespace holds an OAuth-authenticated Outlook connection and
   watches for a new email whose subject matches the test filter.
2. Its managed identity requests a Microsoft Entra token for the receiving app.
   App Service built-in authentication (Easy Auth) validates the token and allows
   **only the namespace identity**.
3. The app uses its own managed identity and the connection runtime URL to call
   the Outlook flag operation. The connection manages Outlook authentication.

The infrastructure creates one isolated resource group, **one Linux B1 instance
shared by four apps**, one connector namespace, one Outlook connection, five
user-assigned managed identities, and four single-tenant Entra registrations
with federated identity credentials. There are no client secrets. Connection
access policies grant access only to the namespace identity and four app identities.

Authentication applies to the **entire app**, including `/healthz`.
Opening an app in a browser returns HTTP 401 by design. Do not copy that policy
unchanged into an existing app that also needs to accept users or other clients.
Local test servers do not implement Easy Auth and must remain on loopback.

## Prerequisites

- Bash on Linux, macOS, or WSL; Git and curl.
- [.NET 10 SDK](https://dotnet.microsoft.com/download), Node.js 24 with npm, and
  Python 3.14 with venv support. All three runtimes are required to deploy and
  test the full repository.
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) and
  [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd).
  Bicep must support the Microsoft Graph extension used in `infra/bicepconfig.json`.
- An Azure subscription with permission to create the listed resources, available
  B1 quota, and permission under your tenant's policies to create Entra app
  registrations, service principals, and federated identity credentials.
- A supported region for both Connector Namespace and the App Service runtimes.
  The samples were live-tested in West Central US. Check current
  [Connector Namespace availability](https://learn.microsoft.com/azure/connector-namespace/connector-namespace-overview)
  before choosing another region.
- A test Microsoft 365 mailbox and permission to consent to its Outlook connection.

Install the official Connector Namespace CLI extension used for these samples:

```bash
az extension add --source https://github.com/Azure/Connectors/releases/download/v1.0.0b33/connector_namespace-1.0.0b33-py3-none-any.whl
```

## Get the samples and run local checks

```bash
git clone https://github.com/Azure-Samples/app-service-managed-connectors.git
cd app-service-managed-connectors

npm ci --prefix src/javascript
npm ci --prefix src/typescript
python3 -m venv src/python/.venv
src/python/.venv/bin/python -m pip install -r src/python/requirements.txt

npm test --prefix src/javascript
npm test --prefix src/typescript
src/python/.venv/bin/python -m unittest discover -s tests -p test_python.py -v
dotnet run --project tests/dotnet/Checks.csproj -- tests/payloads.json
python3 tests/local_smoke.py
```

Unit tests substitute a fake action callback. The HTTP smoke test starts each
real server on loopback, checks startup, skips unrelated subjects, rejects
malformed payloads, and stops its processes. It does not use Azure credentials
or make real connector calls. The GitHub Actions workflow runs these local
checks and compiles Bicep; it does not deploy Azure resources or access a mailbox.

## Deploy to Azure

These commands create billable resources. Review [infra/main.bicep](infra/main.bicep)
and use a new environment name to keep the sample isolated.

```bash
az login
azd auth login
azd env new appsvc-connectors-demo --subscription <subscription-id> --location westcentralus --no-prompt
azd env set AZURE_SUBSCRIPTION_ID <subscription-id>
azd env set AZURE_LOCATION westcentralus
```

If your tenant requires a Service Tree reference for app registrations, set
`azd env set SERVICE_MANAGEMENT_REFERENCE <approved-service-tree-id>` before
provisioning. Do not bypass tenant policy.

```bash
azd provision --no-prompt
azd deploy dotnet --no-prompt
azd deploy javascript --no-prompt
azd deploy typescript --no-prompt
azd deploy python --no-prompt
azd show
azd env get-values --output json
```

Deploy sequentially because the apps share B1 memory and CPU. Outputs include
`AZURE_RESOURCE_GROUP`, `CONNECTOR_NAMESPACE`, `TRIGGER_IDENTITY_ID`, and
`APPLICATIONS` (app names, HTTPS URLs, audiences, and registration client IDs).
Keep the local `.azure` environment for verification and cleanup; do not commit it.

For a later provision **while the namespace still exists**, first run:

```bash
azd env set CREATE_CONNECTOR_NAMESPACE false
```

The preview namespace provider can reject identity updates even when unchanged.
For a new deployment after deleting the namespace, use a new environment or set
`CREATE_CONNECTOR_NAMESPACE` back to `true`. Never replace a namespace just to
work around an update error.

## Connect Outlook and create triggers

1. In the [Managed Connectors portal](https://connectors.azure.com), open the
   deployed namespace and its `outlook-validation` connection. Complete OAuth
   sign-in using your test mailbox. Wait for the connection to show **Connected**.
   If using the CLI, request its consent link with the following command,
   replacing the values with your deployment outputs:

   ```bash
   az connector-namespace connection list-consent-links \
     --subscription <subscription-id> \
     --resource-group <resource-group> \
     --namespace <connector-namespace> \
     --connection-name outlook-validation \
     --parameters '[{"parameterName":"token","redirectUrl":"https://portal.azure.com"}]' \
     --query 'value[0].link' -o tsv
   ```

   Open the returned link yourself. Consent links are temporary and sensitive;
   do not commit them or paste them into issues.

2. Create the four filtered triggers:

   ```bash
   python3 infra/create-triggers.py
   ```

   The script requires a connected Outlook connection and creates one
   `OnNewEmailV3` trigger per app. It leaves existing triggers unchanged.

   To configure them manually instead, choose Outlook **When a new email arrives
   (V3)**, select `outlook-validation`, set **Subject Filter** to
   `[connector-pivots]`, and turn **off** **Split messages into individual messages**.
   Select **App Service**, the matching app, `/api/webhook`, the namespace's managed
   identity, and the app's audience from `APPLICATIONS`. Keep the batch intact:
   these handlers expect an array in `body.value`, not an individual message.

3. Send one harmless test email to the connected mailbox with subject
   `[connector-pivots] language validation`.
4. Run the live verification script after the event is delivered:

   ```bash
   python3 tests/cloud_verify.py
   ```

   It checks the latest run of each trigger for HTTP 200 and a nonzero flagged
   count, verifies HTTP 401 for missing and malformed bearer tokens, and checks
   the callback allowlists and five connection access policies. A run can take
   time to appear; a failing check is not a successful verification.
5. Inspect each app's `connector_processed` log and confirm the Outlook flag.
   An Outlook flag alone does not prove all four apps ran.

All four implementations have been live-tested with a real Outlook event and
flag action, each returning `received=1, flagged=1`. That is evidence for this
specific scenario, not every connector, performance at scale, or production readiness.
A valid token from another principal was not exercised; the configured allowlist
is checked separately.

## SDK and deployment considerations

- The pinned Node.js SDK uses `ManagedIdentityTokenProvider` and
  `flagAsync(input, messageId)`. Python uses
  `flag_async(input=..., message_id=...)`. Follow the lockfiles and pinned
  requirements, not examples for a different preview release.
- `OFFICE365_CONNECTION_RUNTIME_URL` is the connection's HTTPS runtime endpoint,
  not the callback URL or an Azure resource ID. `AZURE_CLIENT_ID` selects the
  receiving app's outbound managed identity, not its Entra registration.
- Action failures return an error instead of acknowledging success. Earlier
  actions in a batch may already have succeeded. Setting the same flag is
  idempotent; other actions may need deduplication or durable processing.
- The .NET package is published locally by AZD, so its remote build is disabled.
  Node.js and Python use remote Oryx builds for Linux dependencies.
- Logging configuration is applied after the app settings to avoid concurrent
  writes. After settings changes, allow propagation to Kudu before deploying.
- If AZD runtime-status tracking fails, check Kudu deployment records and
  application logs. A successful upload or an Easy Auth HTTP 401 alone does not
  prove the application started.
- Microsoft Graph Bicep resources
  [do not support what-if](https://learn.microsoft.com/graph/templates/bicep/limitations).
  A failed preview is not a successful deployment validation.

## Clean up

**Deleting the resource group does not delete the Entra app registrations.**

1. Before removing your local environment, record the four `APPLICATIONS[].clientId`
   values from `azd env get-values --output json`. These identify the registrations,
   not the managed identities.
2. Delete only this sample's resource group (shown in `AZURE_RESOURCE_GROUP`),
   through the Azure portal or the prompted `azd down` flow. This removes the B1
   plan, four apps, namespace, connections/triggers, and five managed identities.
3. In **Microsoft Entra ID > App registrations**, delete the four registrations
   matching those exact client IDs. Their display names start with
   `Connector validation - app-`. Their federated identity credentials are removed
   with them; verify their corresponding enterprise applications are gone as well.
4. Do not delete a shared Microsoft Office 365 connector enterprise application
   or unrelated registrations. Verify the sample resource group is gone so that
   its App Service charges stop.

If provisioning failed partway, inspect the deployment and Entra registrations
for objects it created; the final outputs might not have been saved.

## More examples and resources

- [Advanced .NET email-triage sample](https://github.com/Azure-Samples/app-service-connectors-net-e2e-email-users-teams):
  Outlook event, sender enrichment through Office 365 Users, Teams notification,
  and email flagging. This is a separate, richer example, not duplicated here.
- [App Service managed identities](https://learn.microsoft.com/azure/app-service/overview-managed-identity)
- [Configure Microsoft Entra authentication](https://learn.microsoft.com/azure/app-service/configure-authentication-provider-aad)
- [Managed connectors in Azure Functions](https://learn.microsoft.com/azure/azure-functions/functions-connectors-overview)
- [Contributing](CONTRIBUTING.md) and [Code of conduct](.github/CODE_OF_CONDUCT.md)
