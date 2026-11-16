"""Tests for the demo data seed script (scripts/seed.py)."""

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth import verify_password
from app.database import Base
from app.models import PTOBalance, PTORequest, User
from app.rule_engine import calculate_hours
from scripts.seed import DEMO_PASSWORD, STARTING_TOTAL_HOURS, seed_demo_data


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with TestingSession() as session:
        yield session


def test_seed_creates_manager_and_three_assigned_employees(db_session: Session):
    seed_demo_data(db_session)

    managers = db_session.scalars(select(User).where(User.role == "manager")).all()
    employees = db_session.scalars(select(User).where(User.role == "employee")).all()

    assert len(managers) == 1
    assert len(employees) == 3
    manager = managers[0]
    for emp in employees:
        assert emp.manager_id == manager.employee_id
        assert verify_password(DEMO_PASSWORD, emp.password_hash) is True
    assert verify_password(DEMO_PASSWORD, manager.password_hash) is True


def test_seed_creates_all_statuses_and_flagged_requests(db_session: Session):
    seed_demo_data(db_session)

    requests = db_session.scalars(select(PTORequest)).all()
    statuses = {r.status for r in requests}
    assert statuses == {"pending", "approved", "denied"}

    flagged = [r for r in requests if r.rule_flags]
    assert len(flagged) >= 1
    flag_codes = {flag["code"] for r in flagged for flag in r.rule_flags}
    assert "SHORT_NOTICE" in flag_codes


def test_seed_request_hours_and_employee_balances_match_policy(db_session: Session):
    seed_demo_data(db_session)

    employees = db_session.scalars(select(User).where(User.role == "employee")).all()
    for emp in employees:
        balance = db_session.get(PTOBalance, emp.employee_id)
        assert balance is not None
        assert balance.total_hours == STARTING_TOTAL_HOURS

        emp_requests = db_session.scalars(
            select(PTORequest).where(PTORequest.employee_id == emp.employee_id)
        ).all()
        for req in emp_requests:
            assert req.hours == calculate_hours(req.start_date, req.end_date)

        expected_used = sum(r.hours for r in emp_requests if r.status == "approved")
        expected_pending = sum(r.hours for r in emp_requests if r.status == "pending")
        assert balance.used_hours == expected_used
        assert balance.pending_hours == expected_pending
        assert balance.available_hours == STARTING_TOTAL_HOURS - expected_used - expected_pending


def test_seed_is_idempotent_when_run_multiple_times(db_session: Session):
    seed_demo_data(db_session)
    first_user_count = db_session.scalar(select(func.count()).select_from(User))
    first_req_count = db_session.scalar(select(func.count()).select_from(PTORequest))
    first_balances = {
        b.employee_id: (b.total_hours, b.used_hours, b.pending_hours)
        for b in db_session.scalars(select(PTOBalance)).all()
    }

    # Run a second time on the same database
    seed_demo_data(db_session)
    second_user_count = db_session.scalar(select(func.count()).select_from(User))
    second_req_count = db_session.scalar(select(func.count()).select_from(PTORequest))
    second_balances = {
        b.employee_id: (b.total_hours, b.used_hours, b.pending_hours)
        for b in db_session.scalars(select(PTOBalance)).all()
    }

    assert second_user_count == first_user_count
    assert second_req_count == first_req_count
    assert second_balances == first_balances