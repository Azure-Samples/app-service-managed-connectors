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

**Choose one language to deploy.** Each language folder is an independent Azure
Developer CLI project backed by shared infrastructure. Provisioning or deploying
from that folder creates only its app, not the other three.

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

For the selected language, the infrastructure creates one isolated resource
group, **one Linux B1 instance and one app**, one connector namespace, one Outlook
connection, two user-assigned managed identities, and one single-tenant Entra
registration with a federated identity credential. There are no client secrets.
Two connection access policies grant access to the namespace and app identities.

Authentication applies to the **entire app**, including `/healthz`.
Opening an app in a browser returns HTTP 401 by design. Do not copy that policy
unchanged into an existing app that also needs to accept users or other clients.
Local test servers do not implement Easy Auth and must remain on loopback.

## Prerequisites

- Bash on Linux, macOS, or WSL; Git and curl.
- Only the runtime for your chosen app: [.NET 10 SDK](https://dotnet.microsoft.com/download)
  for C#, Node.js 24 with npm for JavaScript or TypeScript, or Python 3.14 with
  venv support for Python. The optional trigger and verification helpers also
  require Python 3. The full cross-language local test suite needs all runtimes.
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

## Get the samples

```bash
git clone https://github.com/Azure-Samples/app-service-managed-connectors.git
cd app-service-managed-connectors
```

## Run local checks (optional)

For one language, follow its linked README. Contributors can run the entire
suite from the repository root with all runtimes installed:

```bash
npm ci --prefix src/javascript
npm ci --prefix src/typescript
python3 -m venv src/python/.venv
src/python/.venv/bin/python -m pip install -r src/python/requirements.txt

npm test --prefix src/javascript
npm test --prefix src/typescript
src/python/.venv/bin/python -m unittest discover -s tests -p test_python.py -v
dotnet run --project tests/dotnet/Checks.csproj -- tests/payloads.json
python3 tests/local_smoke.py
python3 -m unittest discover -s tests -p test_deployment.py -v
```

Unit tests substitute a fake action callback. The HTTP smoke test starts each
real server on loopback, checks startup, skips unrelated subjects, rejects
malformed payloads, and stops its processes. It does not use Azure credentials
or make real connector calls. The GitHub Actions workflow runs these local
checks, compiles all four language parameter files, and checks single-app
resource counts and helper behavior. It does not deploy Azure resources or
access a mailbox.

## Deploy to Azure

These commands create billable resources. Review [infra/main.bicep](infra/main.bicep)
and use a new environment name to keep the sample isolated. First enter
**one** language folder from the repository root:

| Language | Select this project |
|---|---|
| C# | `cd src/dotnet` |
| JavaScript | `cd src/javascript` |
| TypeScript | `cd src/typescript` |
| Python | `cd src/python` |

Run all following `azd` commands and helper scripts from that selected folder.
Its `azure.yaml` includes exactly one service, and its Bicep parameter file fixes
the matching infrastructure language. There is intentionally no root `azure.yaml`
that deploys all languages.

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
azd deploy --no-prompt
azd show
azd env get-values --output json
```

Both `azd deploy` and `azd up` in the selected folder target only that language.
Outputs include
`AZURE_RESOURCE_GROUP`, `CONNECTOR_NAMESPACE`, `TRIGGER_IDENTITY_ID`, and
`APPLICATION` (language, app name, HTTPS URL, audience, and registration client ID).
Keep the selected folder's local `.azure` environment for verification and
cleanup; do not commit it. Resource names include the selected language so
separate language projects don't overwrite each other's resources.

To try another language, select its folder and create a new environment there.
This creates a separate billable deployment; clean up the first one if you no
longer need it. If you used an earlier revision that deployed all four apps,
clean up that old environment separately. This change does not delete existing
apps, registrations, or resources.

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

2. Create the selected app's filtered trigger from its language folder:

   ```bash
   python3 ../../infra/create-triggers.py
   ```

   The script requires a connected Outlook connection and creates one
   `OnNewEmailV3` trigger for the selected app. It leaves an existing trigger unchanged.

   To configure it manually instead, choose Outlook **When a new email arrives
   (V3)**, select `outlook-validation`, set **Subject Filter** to
   `[connector-pivots]`, and turn **off** **Split messages into individual messages**.
   Select **App Service**, the matching app, `/api/webhook`, the namespace's managed
   identity, and the app's audience from `APPLICATION`. Keep the batch intact:
   these handlers expect an array in `body.value`, not an individual message.

3. Send one harmless test email to the connected mailbox with subject
   `[connector-pivots] language validation`.
4. Run the live verification script after the event is delivered:

   ```bash
   python3 ../../tests/cloud_verify.py
   ```

   It checks the latest run of the selected app's trigger for HTTP 200 and a nonzero flagged
   count, verifies HTTP 401 for missing and malformed bearer tokens, and checks
   the callback allowlist and two connection access policies. A run can take
   time to appear; a failing check is not a successful verification.
5. Inspect the selected app's `connector_processed` log and confirm the Outlook
   flag. Check the actual callback result as well as the mailbox effect.

All four implementations have been live-tested with a real Outlook event and
flag action, each returning `received=1, flagged=1`. That is evidence for this
specific scenario in the earlier four-app validation environment, not every
connector, performance at scale, or production readiness. The single-language
deployment configuration is checked locally and in CI, not yet live-deployed.
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

1. From the selected language folder, before removing your local environment,
   record `APPLICATION.clientId` from `azd env get-values --output json`. This
   identifies the app registration, not the managed identity.
2. Delete only this sample's resource group (shown in `AZURE_RESOURCE_GROUP`),
   through the Azure portal or the prompted `azd down` flow. This removes the B1
   plan, selected app, namespace, connection/trigger, and two managed identities.
3. In **Microsoft Entra ID > App registrations**, delete the registration
   matching that exact client ID. Its display name starts with
   `Connector validation - app-`. Its federated identity credential is removed
   with it; verify the corresponding enterprise application is gone as well.
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
