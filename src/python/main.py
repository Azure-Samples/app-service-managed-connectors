import json
import logging
import os
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from azure.connectors.office365 import Office365Client, UpdateEmailFlag
from azure.connectors.sdk import ConnectorException, ManagedIdentityTokenProvider
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from processing import InvalidPayloadError, process_emails

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("connector")


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value or not value.strip():
        raise ValueError(f"Missing required setting: {name}")
    return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime_url = required("OFFICE365_CONNECTION_RUNTIME_URL")
    parsed = urlparse(runtime_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Connection URL must use HTTPS.")
    app.state.prefix = required("TEST_SUBJECT_PREFIX")
    token_provider = ManagedIdentityTokenProvider(client_id=required("AZURE_CLIENT_ID"))
    async with Office365Client(runtime_url, token_provider) as client:
        app.state.client = client
        yield


app = FastAPI(lifespan=lifespan)


@app.get("/healthz")
async def health():
    return {"status": "healthy"}


@app.post("/api/webhook")
async def webhook(request: Request):
    async def flag_email(message_id: str) -> None:
        await request.app.state.client.flag_async(
            input=UpdateEmailFlag(flag={"flagStatus": "flagged"}),
            message_id=message_id,
        )

    try:
        payload = await request.json()
        result = await process_emails(payload, flag_email, request.app.state.prefix)
    except (json.JSONDecodeError, InvalidPayloadError) as exc:
        logger.warning("Invalid connector payload: %s", type(exc).__name__)
        return JSONResponse(status_code=400, content={"error": "Invalid connector payload"})
    except ConnectorException as exc:
        logger.error("Connector action failed: %s", type(exc).__name__)
        return JSONResponse(status_code=502, content={"error": "Connector action failed"})
    logger.info("connector_processed received=%s flagged=%s", result["received"], result["flagged"])
    return result
