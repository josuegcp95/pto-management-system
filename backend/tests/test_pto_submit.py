"""Tests for POST /api/v1/pto/requests (submit a PTO request)."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import PTOBalance, PTORequest, User


def next_monday(weeks_ahead: int = 2) -> date:
    """A Monday a few weeks out, so dates are always in the future and never short notice."""
    today = date.today()
    return today + timedelta(days=(7 - today.weekday()) + 7 * (weeks_ahead - 1))


def a_week_without_holidays(weeks_ahead: int = 2) -> tuple[date, date]:
    """A Mon–Fri week with no company holidays (40 hours)."""
    from app.rule_engine import COMPANY_HOLIDAYS

    start = next_monday(weeks_ahead)
    while any(start + timedelta(days=d) in COMPANY_HOLIDAYS for d in range(5)):
        start += timedelta(days=7)
    return start, start + timedelta(days=4)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session


@pytest.fixture()
def employee(db_session: Session) -> User:
    user = User(name="Bob Employee", email="bob@example.com", password_hash="x", role="employee")
    db_session.add(user)
    db_session.flush()
    db_session.add(PTOBalance(employee_id=user.employee_id, total_hours=120))
    db_session.commit()
    return user


@pytest.fixture()
def client(db_session: Session, employee: User):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: employee
    yield TestClient(app)
    app.dependency_overrides.clear()


def submit(client: TestClient, start: date, end: date, reason: str | None = None):
    body = {"start_date": start.isoformat(), "end_date": end.isoformat()}
    if reason is not None:
        body["reason"] = reason
    return client.post("/api/v1/pto/requests", json=body)


def balance_of(db_session: Session, user: User) -> PTOBalance:
    db_session.expire_all()
    return db_session.get(PTOBalance, user.employee_id)


# ---------------------------------------------------------------------------
# Successful submissions
# ---------------------------------------------------------------------------


def test_clean_request_is_saved_as_pending(client, db_session, employee):
    start, end = a_week_without_holidays()

    response = submit(client, start, end, "Family vacation")

    assert response.status_code == 201
    body = response.json()
    assert body["employee_id"] == employee.employee_id
    assert body["employee_name"] == "Bob Employee"
    assert body["hours"] == 40
    assert body["status"] == "pending"
    assert body["reason"] == "Family vacation"
    assert body["flags"] == []
    assert db_session.get(PTORequest, body["request_id"]) is not None


def test_submission_reserves_pending_hours(client, db_session, employee):
    start, end = a_week_without_holidays()

    submit(client, start, end)

    balance = balance_of(db_session, employee)
    assert balance.pending_hours == 40
    assert balance.available_hours == 80


def test_flagged_request_is_saved_with_flags(client, db_session, employee):
    # Use up most of the balance so the next request exceeds it.
    balance = db_session.get(PTOBalance, employee.employee_id)
    balance.used_hours = 100
    db_session.commit()
    start, end = a_week_without_holidays()

    response = submit(client, start, end)

    assert response.status_code == 201
    codes = [flag["code"] for flag in response.json()["flags"]]
    assert codes == ["INSUFFICIENT_BALANCE"]


def test_short_notice_request_is_flagged(client):
    from app.rule_engine import is_workday

    # The next workday within the coming week (always less than 7 days' notice).
    start = next(
        date.today() + timedelta(days=d) for d in range(1, 7)
        if is_workday(date.today() + timedelta(days=d))
    )

    response = submit(client, start, start)

    assert response.status_code == 201
    assert "SHORT_NOTICE" in [flag["code"] for flag in response.json()["flags"]]


def test_employee_comes_from_token_not_body(client, employee):
    start, end = a_week_without_holidays()
    body = {"start_date": start.isoformat(), "end_date": end.isoformat(), "employee_id": 9999}

    response = client.post("/api/v1/pto/requests", json=body)

    assert response.status_code == 201
    assert response.json()["employee_id"] == employee.employee_id


def test_blank_reason_is_stored_as_none(client):
    start, end = a_week_without_holidays()

    response = submit(client, start, end, "   ")

    assert response.json()["reason"] is None


# ---------------------------------------------------------------------------
# Rejections
# ---------------------------------------------------------------------------


def test_end_before_start_returns_400(client, db_session, employee):
    start, end = a_week_without_holidays()

    response = submit(client, end, start)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_DATE_RANGE"
    assert balance_of(db_session, employee).pending_hours == 0  # nothing reserved


def test_start_in_past_returns_400(client):
    yesterday = date.today() - timedelta(days=1)

    response = submit(client, yesterday, yesterday)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "START_DATE_IN_PAST"


def test_overlapping_request_returns_409(client, db_session, employee):
    start, end = a_week_without_holidays()
    submit(client, start, end)

    response = submit(client, end, end + timedelta(days=3))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "OVERLAPPING_REQUEST"
    assert balance_of(db_session, employee).pending_hours == 40  # only the first request


def test_overlap_with_denied_request_is_allowed(client, db_session, employee):
    start, end = a_week_without_holidays()
    db_session.add(PTORequest(
        employee_id=employee.employee_id, start_date=start, end_date=end,
        hours=40, status="denied", rule_flags=[],
    ))
    db_session.commit()

    response = submit(client, start, end)

    assert response.status_code == 201


def test_invalid_date_format_returns_422(client):
    response = client.post(
        "/api/v1/pto/requests", json={"start_date": "next friday", "end_date": "2027-01-01"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_reason_over_500_characters_returns_422(client):
    start, end = a_week_without_holidays()

    response = submit(client, start, end, "x" * 501)

    assert response.status_code == 422


def test_missing_balance_returns_404(client, db_session, employee):
    db_session.delete(db_session.get(PTOBalance, employee.employee_id))
    db_session.commit()
    start, end = a_week_without_holidays()

    response = submit(client, start, end)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BALANCE_NOT_FOUND"


def test_submit_requires_login(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        start, end = a_week_without_holidays()
        response = submit(TestClient(app), start, end)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
