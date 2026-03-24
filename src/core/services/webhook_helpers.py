"""Webhook helper utilities for HMAC-signed webhook delivery."""

import hashlib
import hmac
import json
from typing import Any

import httpx
from loguru import logger


def compute_hmac_signature(payload_json: str, secret: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload."""
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_json.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def build_webhook_headers(payload_json: str, webhook_secret: str | None) -> dict[str, str]:
    """Build headers for webhook request, including HMAC if secret is set."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if webhook_secret:
        headers["X-Signature-SHA256"] = compute_hmac_signature(payload_json, webhook_secret)
    return headers


async def send_webhook_with_retries(
    callback_url: str,
    payload: dict[str, Any],
    webhook_secret: str | None = None,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Send webhook with HMAC signing and exponential backoff retries.

    Args:
        callback_url: Webhook URL
        payload: Webhook payload dict
        webhook_secret: HMAC secret (optional, skips signing if None)
        max_retries: Maximum retry attempts

    Returns:
        Dict with success status and details

    Raises:
        httpx.HTTPError: If all retries fail
    """
    import asyncio

    payload_json = json.dumps(payload, default=str)
    headers = build_webhook_headers(payload_json, webhook_secret)

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(callback_url, content=payload_json, headers=headers)
                response.raise_for_status()
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "response": response.json() if response.content else None,
                    "attempt": attempt + 1,
                }
        except httpx.HTTPError as e:
            if attempt < max_retries - 1:
                wait_time = 2**attempt
                logger.warning(
                    f"Webhook attempt {attempt + 1} failed, retrying in {wait_time}s: {e}",
                    extra={"callback_url": callback_url},
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(
                    f"All webhook attempts failed: {e}",
                    exc_info=True,
                    extra={"callback_url": callback_url},
                )
                raise

    raise RuntimeError("Webhook retry logic failed")
