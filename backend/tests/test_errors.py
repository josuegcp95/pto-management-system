"""Tests for the standard error response format."""

from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.errors import AppError, register_exception_handlers
from app.main import app


def make_test_app() -> FastAPI:
    """A small app with routes that trigger each kind of error."""
    test_app = FastAPI()
    register_exception_handlers(test_app)

    class SampleRequest(BaseModel):
        start_date: date

    @test_app.get("/app-error")
    def raise_app_error():
        raise AppError(
            "INVALID_DATE_RANGE",
            "The start date must be on or before the end date.",
            details={"field": "start_date"},
        )

    @test_app.post("/validate")
    def validate(body: SampleRequest):
        return {"ok": True}

    @test_app.get("/crash")
    def crash():
        raise RuntimeError("database password is hunter2")

    return test_app


# raise_server_exceptions=False lets us inspect the 500 response instead of
# having the test client re-raise the error.
client = TestClient(make_test_app(), raise_server_exceptions=False)


def assert_error_shape(body: dict) -> None:
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}


def test_app_error_returns_400_with_code_and_details():
    response = client.get("/app-error")

    assert response.status_code == 400
    body = response.json()
    assert_error_shape(body)
    assert body["error"]["code"] == "INVALID_DATE_RANGE"
    assert body["error"]["details"] == {"field": "start_date"}


def test_unknown_route_returns_404():
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert_error_shape(body)
    assert body["error"]["code"] == "NOT_FOUND"


def test_validation_error_returns_422_with_field_list():
    response = client.post("/validate", json={"start_date": "not-a-date"})

    assert response.status_code == 422
    body = response.json()
    assert_error_shape(body)
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["fields"][0]["field"] == "start_date"


def test_unexpected_error_returns_500_without_internal_details():
    response = client.get("/crash")

    assert response.status_code == 500
    body = response.json()
    assert_error_shape(body)
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "hunter2" not in response.text


def test_main_app_uses_standard_errors():
    response = TestClient(app).get("/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"