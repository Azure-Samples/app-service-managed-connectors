from collections.abc import Awaitable, Callable
from typing import Any


class InvalidPayloadError(ValueError):
    pass


async def process_emails(
    payload: Any, flag_email: Callable[[str], Awaitable[None]], prefix: str
) -> dict[str, int]:
    if not prefix.strip():
        raise ValueError("TEST_SUBJECT_PREFIX must be nonempty.")
    body = payload.get("body") if isinstance(payload, dict) else None
    emails = body.get("value") if isinstance(body, dict) else None
    if not isinstance(emails, list) or any(
        not isinstance(email, dict)
        or not isinstance(email.get("id"), str)
        or not email["id"].strip()
        or not isinstance(email.get("subject"), str)
        for email in emails
    ):
        raise InvalidPayloadError("Expected body.value with email IDs and subjects.")
    flagged = 0
    for email in emails:
        if not email["subject"].startswith(prefix):
            continue
        await flag_email(email["id"])
        flagged += 1
    return {"received": len(emails), "flagged": flagged}
