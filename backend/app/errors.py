"""Standard error responses for the API.

Every error returned by the API uses the format from the Week 3 design spec:

    {"error": {"code": "...", "message": "...", "details": {...}}}

Modules raise ``AppError`` for expected problems (bad input, missing records,
permission issues). Global handlers convert those, FastAPI's built-in HTTP and
validation errors, and any unexpected exception into that same shape.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

# Codes used when FastAPI raises a plain HTTP error (e.g. unknown route).
HTTP_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
}


class AppError(Exception):
    """An expected error with a machine-readable code and a user-facing message.

    Example:
        raise AppError("REQUEST_NOT_FOUND", "PTO request not found.", status_code=404)
    """

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build a JSON response in the standard error format."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or {}}},
        headers=headers,
    )


async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = HTTP_ERROR_CODES.get(exc.status_code, "HTTP_ERROR")
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return error_response(exc.status_code, code, message, headers=getattr(exc, "headers", None))


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Turn Pydantic's error list into a simple, readable list of field problems.
    fields = [
        {
            "field": ".".join(str(part) for part in err["loc"] if part != "body"),
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    return error_response(
        422,
        "VALIDATION_ERROR",
        "One or more fields are invalid.",
        {"fields": fields},
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # Log the full error for us, but never send internal details to the client.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return error_response(500, "INTERNAL_ERROR", "Something went wrong. Please try again later.")


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the standard error handlers to the FastAPI app."""
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)