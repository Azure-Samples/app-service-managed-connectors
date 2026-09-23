"""Offline checks for single-language deployment and connector helpers."""

import contextlib
import io
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = {
    "dotnet": ("dotnet", "DOTNETCORE|10.0"),
    "javascript": ("js", "NODE|24-lts"),
    "typescript": ("ts", "NODE|24-lts"),
    "python": ("python", "PYTHON|3.14"),
}


def environment(language):
    return {
        "AZURE_SUBSCRIPTION_ID": "test-subscription",
        "AZURE_RESOURCE_GROUP": "test-rg",
        "CONNECTOR_NAMESPACE": "test-namespace",
        "OFFICE365_CONNECTION_NAME": "test-connection",
        "OFFICE365_CONNECTION_RUNTIME_URL": "https://example.invalid/connection",
        "TRIGGER_IDENTITY_ID": "test-trigger-identity",
        "TEST_SUBJECT_PREFIX": "[custom-prefix]",
        "APPLICATION": json.dumps({
            "language": language,
            "name": "app-" + language,
            "url": "https://example.invalid",
            "audience": "api://app-" + language,
            "clientId": "registration-client-id",
        }),
    }


def run_script(path, responses):
    with patch("subprocess.check_output", side_effect=responses) as calls:
        with contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(ROOT / path))
    return calls.call_args_list


class DeploymentTests(unittest.TestCase):
    def test_each_project_provisions_only_its_language(self):
        self.assertFalse((ROOT / "azure.yaml").exists())
        for language, (azd_language, runtime) in LANGUAGES.items():
            with self.subTest(language=language):
                config = (ROOT / "src" / language / "azure.yaml").read_text()
                services = config.split("services:\n", 1)[1]
                self.assertEqual(re.findall(r"^  ([a-z]+):$", services, re.M), [language])
                self.assertIn("    project: .\n", services)
                self.assertIn(f"    language: {azd_language}\n", services)
                self.assertIn("    host: appservice\n", services)
                self.assertIn("  path: ../../infra\n", config)
                self.assertIn(f"  module: {language}\n", config)

                env = {
                    **os.environ,
                    "AZURE_ENV_NAME": "offline-check",
                    "AZURE_LOCATION": "westcentralus",
                    "CREATE_CONNECTOR_NAMESPACE": "true",
                    "SERVICE_MANAGEMENT_REFERENCE": "",
                }
                result = subprocess.run(
                    ["az", "bicep", "build-params", "--file",
                     str(ROOT / "infra" / f"{language}.bicepparam"), "--stdout"],
                    env=env, text=True, capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                compiled = json.loads(result.stdout)
                parameters = json.loads(compiled["parametersJson"])["parameters"]
                template = json.loads(compiled["templateJson"])
                self.assertEqual(parameters["sampleLanguage"]["value"], language)
                self.assertTrue(parameters["createConnectorNamespace"]["value"])
                self.assertEqual(parameters["environmentName"]["value"], "offline-check")
                self.assertEqual(template["variables"]["configurations"][language]["runtime"], runtime)
                self.assertNotIn("defaultValue", template["parameters"]["sampleLanguage"])
                self.assertEqual(set(template["parameters"]["sampleLanguage"]["allowedValues"]),
                                 set(LANGUAGES))

                resources = template["resources"]
                self.assertEqual(set(resources),
                                 {"rg", "plan", "triggerIdentity", "namespace", "app", "policies"})
                self.assertTrue(all("copy" not in resource for resource in resources.values()))
                app = resources["app"]["properties"]
                self.assertIn("parameters('sampleLanguage')", app["parameters"]["tags"]["value"])
                self.assertEqual(app["parameters"]["runtime"]["value"],
                                 "[variables('configuration').runtime]")
                self.assertEqual(template["variables"]["configuration"],
                                 "[variables('configurations')[parameters('sampleLanguage')]]")
                app_resources = app["template"]["resources"]
                self.assertEqual(set(app_resources),
                                 {"registration", "servicePrincipal", "federation", "identity", "site", "logs"})
                self.assertTrue(all("copy" not in resource for resource in app_resources.values()))
                self.assertEqual(resources["plan"]["properties"]["parameters"]["skuCapacity"]["value"], 1)
                self.assertEqual(len(resources["policies"]["properties"]["parameters"]["principalIds"]["value"]), 1)
                self.assertEqual(template["outputs"]["APPLICATION"]["type"], "object")
                self.assertNotIn("APPLICATIONS", template["outputs"])

    def test_trigger_creates_only_selected_destination(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                env = environment(language)
                app = json.loads(env["APPLICATION"])
                responses = [
                    json.dumps(env),
                    json.dumps({"properties": {"overallStatus": "Connected"}}),
                    "[]",
                    json.dumps({"properties": {"provisioningState": "Succeeded"}}),
                ]
                calls = run_script("infra/create-triggers.py", responses)
                self.assertEqual(len(calls), 4)
                args = calls[-1].args[0]
                self.assertEqual(args[args.index("--name") + 1], "validation-" + language)
                parameters = json.loads(args[args.index("--parameters") + 1])
                self.assertEqual(parameters, [{"name": "subjectFilter", "value": "[custom-prefix]"}])
                notification = json.loads(args[args.index("--notification-details") + 1])
                self.assertEqual(notification["callbackUrl"], app["url"] + "/api/webhook")
                self.assertEqual(notification["authentication"]["audience"], app["audience"])

    def test_existing_trigger_is_not_recreated(self):
        calls = run_script("infra/create-triggers.py", [
            json.dumps(environment("python")),
            json.dumps({"properties": {"overallStatus": "Connected"}}),
            json.dumps([{"name": "validation-python"}]),
        ])
        self.assertEqual(len(calls), 3)

    def test_empty_prefix_fails_before_cloud_calls(self):
        env = environment("python")
        env["TEST_SUBJECT_PREFIX"] = " "
        for script in ("infra/create-triggers.py", "tests/cloud_verify.py"):
            with self.subTest(script=script):
                with patch("subprocess.check_output", return_value=json.dumps(env)) as calls:
                    with self.assertRaises(ValueError):
                        runpy.run_path(str(ROOT / script))
                    self.assertEqual(calls.call_count, 1)

    def test_live_verifier_checks_one_app_and_two_policies(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                env = environment(language)
                app = json.loads(env["APPLICATION"])
                for extra_policy in (False, True):
                    principals = ["trigger-principal", "app-principal"]
                    if extra_policy:
                        principals.append("unexpected-principal")
                    responses = [
                        env,
                        {"principalId": "trigger-principal"},
                        {"properties": {"overallStatus": "Connected"}},
                        {"principalId": "app-principal", "clientId": "app-client"},
                        [{"name": key, "value": value} for key, value in {
                            "AZURE_CLIENT_ID": "app-client",
                            "TEST_SUBJECT_PREFIX": env["TEST_SUBJECT_PREFIX"],
                            "OFFICE365_CONNECTION_RUNTIME_URL": env["OFFICE365_CONNECTION_RUNTIME_URL"],
                        }.items()],
                        {
                            "platform": {"enabled": True},
                            "globalValidation": {"requireAuthentication": True,
                                                 "unauthenticatedClientAction": "Return401"},
                            "identityProviders": {"azureActiveDirectory": {"validation": {
                                "allowedAudiences": [app["audience"]],
                                "defaultAuthorizationPolicy": {
                                    "allowedPrincipals": {"identities": ["trigger-principal"]}},
                            }}},
                        },
                        401, 401,
                        {"properties": {
                            "state": "Enabled", "settings": {"disableSplitOn": True},
                            "parameters": [{"name": "subjectFilter", "value": env["TEST_SUBJECT_PREFIX"]}],
                            "notificationDetails": {"authentication": {
                                "identity": env["TRIGGER_IDENTITY_ID"], "audience": app["audience"]}},
                        }},
                        [{"id": "test-run"}],
                        {"notification": {"outputs": {"statusCode": 200,
                                                      "body": {"received": 1, "flagged": 1}}}},
                        {"value": [{"properties": {"principal": {"identity": {"objectId": principal}}}}
                                   for principal in principals]},
                    ]
                    encoded = [json.dumps(response) for response in responses]
                    if extra_policy:
                        with self.assertRaises(AssertionError):
                            run_script("tests/cloud_verify.py", encoded)
                    else:
                        calls = run_script("tests/cloud_verify.py", encoded)
                        self.assertEqual(len(calls), len(responses))


if __name__ == "__main__":
    unittest.main()
