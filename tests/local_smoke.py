import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = {
    "dotnet": ["dotnet", "bin/Debug/net10.0/ConnectorSample.dll"],
    "javascript": ["node", "server.js"],
    "typescript": ["node", "dist/server.js"],
    "python": [".venv/bin/python", "-m", "uvicorn", "main:app", "--host", "127.0.0.1"],
}


def request(url, body=None):
    data = None if body is None else body.encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


for language, base_command in COMMANDS.items():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    command = base_command + (["--port", str(port)] if language == "python" else [])
    env = {
        **os.environ,
        "PORT": str(port),
        "HOST": "127.0.0.1",
        "ASPNETCORE_URLS": f"http://127.0.0.1:{port}",
        "OFFICE365_CONNECTION_RUNTIME_URL": "https://example.invalid/connection",
        "AZURE_CLIENT_ID": "00000000-0000-0000-0000-000000000001",
        "TEST_SUBJECT_PREFIX": "[connector-pivots]",
    }
    with tempfile.TemporaryFile(mode="w+") as log:
        process = subprocess.Popen(command, cwd=ROOT / "src" / language,
                                   env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            url = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 45
            while True:
                if process.poll() is not None:
                    log.seek(0)
                    raise RuntimeError(f"{language} startup failed: {log.read()}")
                try:
                    if request(url + "/healthz")[0] == 200:
                        break
                except (urllib.error.URLError, TimeoutError):
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"{language} did not start")
                time.sleep(0.25)
            status, response = request(url + "/api/webhook", json.dumps({
                "body": {"value": [{"id": "skip-1", "subject": "Unrelated message"}]},
            }))
            assert status == 200, (language, status, response)
            assert json.loads(response) == {"received": 1, "flagged": 0}
            for invalid in ("{", "null", "{}", '{"body":{"value":[null]}}'):
                status, response = request(url + "/api/webhook", invalid)
                assert status == 400, (language, status, response)
            print(f"{language}: startup, callback, filter, and malformed payload checks passed")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
