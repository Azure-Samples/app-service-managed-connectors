"""Read-only verification after sending a real test-prefix email."""

import json
import subprocess


def run_json(*args):
    return json.loads(subprocess.check_output(args, text=True))


def az(*args):
    return run_json("az", *args, "-o", "json")


env = run_json("azd", "env", "get-values", "--output", "json")
prefix = env["TEST_SUBJECT_PREFIX"]
if not prefix.strip():
    raise ValueError("TEST_SUBJECT_PREFIX must be nonempty.")
scope = ["--subscription", env["AZURE_SUBSCRIPTION_ID"], "-g", env["AZURE_RESOURCE_GROUP"]]
namespace_id = (
    f"/subscriptions/{env['AZURE_SUBSCRIPTION_ID']}/resourceGroups/"
    f"{env['AZURE_RESOURCE_GROUP']}/providers/Microsoft.Web/"
    f"connectorGateways/{env['CONNECTOR_NAMESPACE']}"
)


def arm(path):
    return az("rest", "--url", f"https://management.azure.com{path}?api-version=2026-05-01-preview")


trigger_identity = az("identity", "show", "--ids", env["TRIGGER_IDENTITY_ID"])
expected_principals = {trigger_identity["principalId"]}
connection = arm(namespace_id + "/connections/" + env["OFFICE365_CONNECTION_NAME"])
assert connection["properties"]["overallStatus"] == "Connected"
results = []
for app in json.loads(env["APPLICATIONS"]):
    identity = az("identity", "show", *scope, "-n", "id-" + app["name"])
    expected_principals.add(identity["principalId"])
    settings = {s["name"]: s["value"] for s in az(
        "webapp", "config", "appsettings", "list", *scope, "-n", app["name"],
    )}
    assert settings["AZURE_CLIENT_ID"] == identity["clientId"]
    assert settings["TEST_SUBJECT_PREFIX"] == prefix
    assert settings["OFFICE365_CONNECTION_RUNTIME_URL"] == env["OFFICE365_CONNECTION_RUNTIME_URL"]
    raw_auth = az("webapp", "auth", "show", *scope, "-n", app["name"])
    auth = raw_auth.get("properties", raw_auth)
    assert auth["platform"]["enabled"]
    assert auth["globalValidation"]["requireAuthentication"]
    assert auth["globalValidation"]["unauthenticatedClientAction"] == "Return401"
    validation = auth["identityProviders"]["azureActiveDirectory"]["validation"]
    assert app["audience"] in validation["allowedAudiences"]
    assert validation["defaultAuthorizationPolicy"]["allowedPrincipals"]["identities"] == [
        trigger_identity["principalId"]
    ]
    for invalid_token in (False, True):
        cmd = [
            "curl", "--silent", "--show-error", "--max-time", "60",
            "-o", "/dev/null", "-w", "%{http_code}",
            "-H", "Content-Type: application/json", "--data", '{"body":{"value":[]}}',
        ]
        if invalid_token:
            cmd.extend(["-H", "Authorization: Bearer invalid-validation-token"])
        status = subprocess.check_output([*cmd, app["url"] + "/api/webhook"], text=True)
        assert status == "401", (app["language"], invalid_token, status)
    trigger_name = "validation-" + app["language"]
    trigger = az("connector-namespace", "trigger", "show", *scope,
                 "--namespace", env["CONNECTOR_NAMESPACE"], "-n", trigger_name)["properties"]
    assert trigger["state"] == "Enabled"
    assert trigger["settings"]["disableSplitOn"]
    assert {"name": "subjectFilter", "value": prefix} in trigger["parameters"]
    assert trigger["notificationDetails"]["authentication"]["identity"] == env["TRIGGER_IDENTITY_ID"]
    assert trigger["notificationDetails"]["authentication"]["audience"] == app["audience"]
    runs = az("connector-namespace", "trigger", "run", "list", *scope,
              "--namespace", env["CONNECTOR_NAMESPACE"], "-n", trigger_name, "--max-items", "5")
    if not runs:
        raise RuntimeError(f"{trigger_name}: no real event runs")
    # The preview CLI's run-show schema drops the current API's top-level fields.
    run = arm(f"{namespace_id}/triggerConfigs/{trigger_name}/runs/{runs[0]['id']}")
    output = run["notification"]["outputs"]
    assert output["statusCode"] == 200, (trigger_name, output["statusCode"])
    assert output["body"]["received"] >= 1
    assert output["body"]["flagged"] >= 1
    results.append({
        "language": app["language"], "endpoint": app["url"],
        "runId": runs[0]["id"], "callbackStatus": output["statusCode"],
        "received": output["body"]["received"], "flagged": output["body"]["flagged"],
        "unauthenticatedStatus": 401, "invalidTokenStatus": 401,
    })
policies = arm(namespace_id + "/connections/" + env["OFFICE365_CONNECTION_NAME"] + "/accessPolicies")
actual_principals = {p["properties"]["principal"]["identity"]["objectId"] for p in policies["value"]}
assert actual_principals == expected_principals
print(json.dumps({"results": results, "connectionAccessPolicies": "exactly five expected identities"}, indent=2))
