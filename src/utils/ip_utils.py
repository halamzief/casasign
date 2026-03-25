"""Utilities for extracting real client IP from proxied requests."""

from fastapi import Request
from loguru import logger


def get_client_ip(request: Request) -> str:
    """Extract real client IP from request, checking proxy headers.

    Checks X-Forwarded-For and X-Real-IP headers first (set by Caddy/nginx),
    then falls back to request.client.host.

    Args:
        request: FastAPI Request object

    Returns:
        Client IP address string
    """
    # X-Forwarded-For: client, proxy1, proxy2 — first entry is the original client
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the first (leftmost) IP — this is the original client
        client_ip = forwarded_for.split(",")[0].strip()
        if client_ip:
            logger.debug("IP from X-Forwarded-For", ip=client_ip)
            return client_ip

    # X-Real-IP: set by some reverse proxies (Caddy, nginx)
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        logger.debug("IP from X-Real-IP", ip=real_ip)
        return real_ip.strip()

    # Fallback to direct connection IP
    direct_ip = request.client.host if request.client else "unknown"
    logger.debug("IP from direct connection", ip=direct_ip)
    return direct_ip
