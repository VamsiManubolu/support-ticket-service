"""Turns every error into the standard {"error": {...}} JSON envelope.
Covers domain errors, validation errors, framework HTTP errors and unexpected 500s."""

import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError, ErrorCode
from app.core.middleware import REQUEST_ID_HEADER, get_request_id
from app.schemas.common import ErrorBody, ErrorResponse, FieldError, ValidationErrorDetails

logger = logging.getLogger(__name__)


# Build a JSON error response in the standard envelope
def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id = get_request_id()
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, details=details or {}, request_id=request_id)
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers=headers,
    )


def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


# 422 for invalid requests, listing each bad field
def _validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # leave out "input" (may contain user data) and "ctx" (not always JSON-safe)
    errors = [
        FieldError(
            field=".".join(str(part) for part in error["loc"]),
            message=error["msg"],
            type=error["type"],
        )
        for error in exc.errors()
    ]
    details = ValidationErrorDetails(errors=errors).model_dump()
    return error_response(422, ErrorCode.VALIDATION_ERROR, "Request validation failed", details)


def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    status = HTTPStatus(exc.status_code)
    return error_response(exc.status_code, status.name, str(exc.detail), headers=exc.headers)


# 500 for unexpected errors; logs the traceback but never returns it
def _unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    # runs outside the middleware, so add the header here
    request_id = get_request_id()
    return error_response(
        500,
        ErrorCode.INTERNAL_ERROR,
        "An unexpected error occurred",
        headers={REQUEST_ID_HEADER: request_id} if request_id else None,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
