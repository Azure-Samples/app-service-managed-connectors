"""Create the four test-only triggers after Outlook consent."""

import json
import subprocess


def run_json(*args):
    return json.loads(subprocess.check_output(args, text=True))


env = run_json("azd", "env", "get-values", "--output", "json")
prefix = env["TEST_SUBJECT_PREFIX"]
if not prefix.strip():
    raise ValueError("TEST_SUBJECT_PREFIX must be nonempty.")
scope = [
    "--subscription", env["AZURE_SUBSCRIPTION_ID"],
    "--resource-group", env["AZURE_RESOURCE_GROUP"],
    "--namespace", env["CONNECTOR_NAMESPACE"],
]
connection = run_json(
    "az", "connector-namespace", "connection", "show", *scope,
    "--connection-name", env["OFFICE365_CONNECTION_NAME"], "-o", "json",
)
if connection["properties"]["overallStatus"] != "Connected":
    raise RuntimeError("Complete Outlook consent before creating triggers.")

existing = run_json("az", "connector-namespace", "trigger", "list", *scope, "-o", "json")
existing_names = {trigger["name"] for trigger in existing}
apps = json.loads(env["APPLICATIONS"])
for app in apps:
    name = f"validation-{app['language']}"
    if name in existing_names:
        print(f"{name}: already exists; not modified")
        continue
    result = run_json(
        "az", "connector-namespace", "trigger", "create", *scope,
        "--name", name,
        "--operation-name", "OnNewEmailV3",
        "--connection-details", json.dumps({
            "connectionName": env["OFFICE365_CONNECTION_NAME"],
            "connectorName": "office365",
        }),
        "--parameters", json.dumps([{"name": "subjectFilter", "value": prefix}]),
        "--settings", json.dumps({"disableSplitOn": True}),
        "--notification-details", json.dumps({
            "callbackUrl": f"{app['url'].rstrip('/')}/api/webhook",
            "httpMethod": "Post",
            "authentication": {
                "type": "ManagedServiceIdentity",
                "identity": env["TRIGGER_IDENTITY_ID"],
                "audience": app["audience"],
            },
        }),
        "--metadata", json.dumps({
            "destinationType": "appService",
            "appServiceName": app["name"],
            "appServiceResourceGroup": env["AZURE_RESOURCE_GROUP"],
            "appServiceSubscriptionId": env["AZURE_SUBSCRIPTION_ID"],
            "appServiceRoutePath": "/api/webhook",
            "appServiceMsiAudience": app["audience"],
        }),
        "--description", f"Test-prefix-only {app['language']} documentation validation.",
        "--state", "Enabled", "-o", "json",
    )
    if result["properties"]["provisioningState"] != "Succeeded":
        raise RuntimeError(f"{name}: provisioning did not succeed")
    print(f"{name}: created")
