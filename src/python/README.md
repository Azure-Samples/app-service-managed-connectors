# Python / FastAPI

Receive an Outlook event at `/api/webhook` and flag only test-prefix messages.

- [main.py](main.py): client lifespan, callback routing, and error handling.
- [processing.py](processing.py): batch validation and subject-prefix filtering.
- Runtime: Python 3.14; pinned `azure-connectors==0.5.0b1`.

From the repository root:

```bash
python3 -m venv src/python/.venv
src/python/.venv/bin/python -m pip install -r src/python/requirements.txt
src/python/.venv/bin/python -m unittest discover -s tests -p test_python.py -v
```

Follow the shared [setup and deployment instructions](../../README.md#deploy-to-azure)
to provision the authenticated app and its connector. After provisioning, deploy
this language with `azd deploy python --no-prompt`.

The configured startup command is
`python -m uvicorn main:app --host 0.0.0.0 --port 8000`. Use the SDK's
`ManagedIdentityTokenProvider` and await `flag_async(input=..., message_id=...)`.
Local tests replace the outbound action and do not implement Easy Auth. See the
shared [authentication model](../../README.md#architecture-and-authentication)
and [live verification steps](../../README.md#connect-outlook-and-create-triggers).
