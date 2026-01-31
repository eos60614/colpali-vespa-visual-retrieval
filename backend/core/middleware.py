"""
ASGI middleware for correlation ID propagation and request error boundaries.

Extracts or generates x-correlation-id on each request, sets it in the
logging context, and returns it in the response. Also provides an error
boundary that logs full error details while returning sanitized responses.
"""

import traceback

from backend.core.logging_config import (
    CORRELATION_HEADER,
    generate_correlation_id,
    get_correlation_id,
    get_logger,
    is_production,
    set_correlation_id,
)

logger = get_logger("middleware")


class CorrelationIdMiddleware:
    """ASGI middleware that manages x-correlation-id for every request.

    - Reads x-correlation-id from incoming request headers.
    - Generates a new one if absent.
    - Sets it in the logging context (contextvars).
    - Injects it into the response headers.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Extract or generate correlation ID
        headers = dict(scope.get("headers", []))
        cid_header = CORRELATION_HEADER.encode("utf-8")
        cid = headers.get(cid_header, b"").decode("utf-8")
        if not cid:
            cid = generate_correlation_id()
        set_correlation_id(cid)

        # Wrap send to inject correlation ID into response headers
        async def send_with_correlation(message):
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers.append(
                    (cid_header, cid.encode("utf-8"))
                )
                message = {**message, "headers": response_headers}
            await send(message)

        await self.app(scope, receive, send_with_correlation)


class ErrorBoundaryMiddleware:
    """ASGI middleware that catches unhandled exceptions at the entrypoint.

    - Logs the full error with stack trace and correlation ID.
    - Returns a sanitized error response (no internals leaked in production).
    - In development, includes the error message for debugging.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        try:
            await self.app(scope, receive, send)
        except Exception as exc:
            cid = get_correlation_id()
            logger.error(
                f"Unhandled exception: {exc}",
                exc_info=True,
            )

            # Build sanitized response (use json.dumps to escape cid properly)
            import json

            if is_production():
                body = json.dumps({
                    "error": "Internal server error",
                    "correlationId": cid,
                }).encode()
            else:
                # Development: include error details for debugging
                body = json.dumps({
                    "error": str(exc),
                    "correlationId": cid,
                    "stackTrace": traceback.format_exc(),
                }).encode()

            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"application/json"),
                    (CORRELATION_HEADER.encode(), cid.encode()),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })
