"""Tests for the core SQLAlchemy models (User, PTOBalance, PTORequest)."""

from datetime import date, datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import PTOBalance, PTORequest, User


@pytest.fixture()
def db_session():
    """In-memory SQLite session with all core tables created."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with TestingSession() as session:
        yield session


def test_tables_registered_in_metadata():
    assert {"users", "pto_balances", "pto_requests"} == set(Base.metadata.tables.keys())


def test_user_and_manager_hierarchy(db_session: Session):
    manager = User(
        name="Alice Manager",
        email="alice@example.com",
        password_hash="hashed_pw_1",
        role="manager",
    )
    db_session.add(manager)
    db_session.flush()

    employee = User(
        name="Bob Employee",
        email="bob@example.com",
        password_hash="hashed_pw_2",
        role="employee",
        manager_id=manager.employee_id,
    )
    db_session.add(employee)
    db_session.commit()

    assert employee.manager == manager
    assert manager.direct_reports == [employee]


def test_pto_balance_calculates_available_hours(db_session: Session):
    user = User(
        name="Bob Employee",
        email="bob@example.com",
        password_hash="hashed_pw",
        role="employee",
    )
    db_session.add(user)
    db_session.flush()

    # Spec Section 3.2 example: total 120, used 40, pending 16 -> available 64
    balance = PTOBalance(
        employee_id=user.employee_id,
        total_hours=120,
        used_hours=40,
        pending_hours=16,
    )
    db_session.add(balance)
    db_session.commit()

    assert balance.available_hours == 64


def test_pto_request_stores_hours_flags_and_manager_decision(db_session: Session):
    manager = User(
        name="Alice Manager",
        email="alice@example.com",
        password_hash="hashed_pw_1",
        role="manager",
    )
    employee = User(
        name="Bob Employee",
        email="bob@example.com",
        password_hash="hashed_pw_2",
        role="employee",
    )
    db_session.add_all([manager, employee])
    db_session.flush()

    flags_payload = [
        {"code": "SHORT_NOTICE", "message": "Submitted with less than 7 days' notice."}
    ]
    req = PTORequest(
        employee_id=employee.employee_id,
        start_date=date(2026, 11, 16),
        end_date=date(2026, 11, 20),
        hours=40,
        reason="Personal vacation",
        status="pending",
        rule_flags=flags_payload,
    )
    db_session.add(req)
    db_session.commit()

    assert req.request_id is not None
    assert req.hours == 40
    assert req.rule_flags == flags_payload
    assert req.flags == flags_payload
    assert req.created_at is not None

    # Simulate manager approval (Spec Section 3.5)
    decision_time = datetime(2026, 10, 31, 14, 0, tzinfo=timezone.utc)
    req.status = "approved"
    req.manager_comment = "Request approved."
    req.reviewed_by = manager.employee_id
    req.reviewed_at = decision_time
    db_session.commit()

    assert req.status == "approved"
    assert req.manager_comment == "Request approved."
    assert req.reviewer == manager
    assert req.reviewed_at.replace(tzinfo=timezone.utc) == decision_time


def test_invalid_role_or_status_rejected_by_check_constraint(db_session: Session):
    bad_user = User(
        name="Invalid Role",
        email="bad@example.com",
        password_hash="hash",
        role="admin",
    )
    db_session.add(bad_user)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()