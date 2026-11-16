"""Load demo accounts, balances, and sample PTO requests for local dev and alpha demo.

Safe to run multiple times: existing demo records are updated in place
and balances are recalculated from the seeded requests.

Run from backend/:
    python -m scripts.seed
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import get_session_local
from app.models import PTOBalance, PTORequest, User
from app.rule_engine import (
    LONG_REQUEST,
    RULE_MESSAGES,
    SHORT_NOTICE,
    calculate_hours,
)

DEMO_PASSWORD = "password123"
STARTING_TOTAL_HOURS = 120


@dataclass(frozen=True)
class DemoUserSpec:
    name: str
    email: str
    role: str


@dataclass(frozen=True)
class DemoRequestSpec:
    employee_email: str
    start_date: date
    end_date: date
    reason: str
    status: str  # "pending", "approved", or "denied"
    flag_codes: list[str] = field(default_factory=list)
    manager_comment: str | None = None
    reviewed_at: datetime | None = None


MANAGER_SPEC = DemoUserSpec(
    name="Alice Manager",
    email="manager@example.com",
    role="manager",
)

EMPLOYEE_SPECS: list[DemoUserSpec] = [
    DemoUserSpec(name="Bob Employee", email="bob@example.com", role="employee"),
    DemoUserSpec(name="Carol Employee", email="carol@example.com", role="employee"),
    DemoUserSpec(name="David Employee", email="david@example.com", role="employee"),
]

REQUEST_SPECS: list[DemoRequestSpec] = [
    # Bob: 1 approved (40h) + 1 pending over Thanksgiving week (24h; Thu/Fri are holidays)
    DemoRequestSpec(
        employee_email="bob@example.com",
        start_date=date(2026, 10, 12),
        end_date=date(2026, 10, 16),
        reason="Fall family vacation",
        status="approved",
        manager_comment="Approved. Enjoy your trip!",
        reviewed_at=datetime(2026, 10, 1, 14, 30, tzinfo=timezone.utc),
    ),
    DemoRequestSpec(
        employee_email="bob@example.com",
        start_date=date(2026, 11, 23),
        end_date=date(2026, 11, 27),
        reason="Thanksgiving week travel",
        status="pending",
    ),
    # Carol: 1 approved (16h) + 1 pending with SHORT_NOTICE flag (16h) + 1 denied (24h)
    DemoRequestSpec(
        employee_email="carol@example.com",
        start_date=date(2026, 9, 14),
        end_date=date(2026, 9, 15),
        reason="Dental surgery and recovery",
        status="approved",
        manager_comment="Approved.",
        reviewed_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
    ),
    DemoRequestSpec(
        employee_email="carol@example.com",
        start_date=date(2026, 11, 18),
        end_date=date(2026, 11, 19),
        reason="Last-minute personal errand",
        status="pending",
        flag_codes=[SHORT_NOTICE],
    ),
    DemoRequestSpec(
        employee_email="carol@example.com",
        start_date=date(2026, 12, 21),
        end_date=date(2026, 12, 23),
        reason="Early holiday travel",
        status="denied",
        manager_comment="Denied due to year-end coverage needs.",
        reviewed_at=datetime(2026, 11, 10, 16, 15, tzinfo=timezone.utc),
    ),
    # David: 1 pending with LONG_REQUEST flag (12 workdays = 96h)
    DemoRequestSpec(
        employee_email="david@example.com",
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 16),
        reason="Extended winter trip",
        status="pending",
        flag_codes=[LONG_REQUEST],
    ),
]


def _upsert_user(
    db: Session,
    spec: DemoUserSpec,
    password_hash: str,
    manager_id: int | None,
) -> User:
    user = db.scalars(select(User).where(User.email == spec.email)).first()
    if user is None:
        user = User(
            name=spec.name,
            email=spec.email,
            password_hash=password_hash,
            role=spec.role,
            manager_id=manager_id,
        )
        db.add(user)
    else:
        user.name = spec.name
        user.password_hash = password_hash
        user.role = spec.role
        user.manager_id = manager_id
    db.flush()
    return user


def _upsert_request(
    db: Session,
    employee: User,
    manager: User,
    spec: DemoRequestSpec,
) -> PTORequest:
    hours = calculate_hours(spec.start_date, spec.end_date)
    flags = [{"code": code, "message": RULE_MESSAGES[code]} for code in spec.flag_codes]
    reviewed_by = manager.employee_id if spec.status in ("approved", "denied") else None

    req = db.scalars(
        select(PTORequest).where(
            PTORequest.employee_id == employee.employee_id,
            PTORequest.start_date == spec.start_date,
            PTORequest.end_date == spec.end_date,
        )
    ).first()

    if req is None:
        req = PTORequest(
            employee_id=employee.employee_id,
            start_date=spec.start_date,
            end_date=spec.end_date,
            hours=hours,
            reason=spec.reason,
            status=spec.status,
            rule_flags=flags,
            manager_comment=spec.manager_comment,
            reviewed_by=reviewed_by,
            reviewed_at=spec.reviewed_at,
        )
        db.add(req)
    else:
        req.hours = hours
        req.reason = spec.reason
        req.status = spec.status
        req.rule_flags = flags
        req.manager_comment = spec.manager_comment
        req.reviewed_by = reviewed_by
        req.reviewed_at = spec.reviewed_at
    db.flush()
    return req


def _sync_balance(db: Session, user: User) -> PTOBalance:
    requests = db.scalars(
        select(PTORequest).where(PTORequest.employee_id == user.employee_id)
    ).all()

    used_hours = sum(r.hours for r in requests if r.status == "approved")
    pending_hours = sum(r.hours for r in requests if r.status == "pending")

    balance = db.get(PTOBalance, user.employee_id)
    if balance is None:
        balance = PTOBalance(
            employee_id=user.employee_id,
            total_hours=STARTING_TOTAL_HOURS,
            used_hours=used_hours,
            pending_hours=pending_hours,
        )
        db.add(balance)
    else:
        balance.total_hours = STARTING_TOTAL_HOURS
        balance.used_hours = used_hours
        balance.pending_hours = pending_hours
    db.flush()
    return balance


def seed_demo_data(db: Session) -> dict[str, User]:
    """Seed demo manager, employees, requests, and synchronized PTO balances."""
    shared_password_hash = hash_password(DEMO_PASSWORD)

    manager = _upsert_user(db, MANAGER_SPEC, shared_password_hash, manager_id=None)
    users_by_email: dict[str, User] = {manager.email: manager}

    for emp_spec in EMPLOYEE_SPECS:
        emp = _upsert_user(
            db,
            emp_spec,
            shared_password_hash,
            manager_id=manager.employee_id,
        )
        users_by_email[emp.email] = emp

    for req_spec in REQUEST_SPECS:
        employee = users_by_email[req_spec.employee_email]
        _upsert_request(db, employee, manager, req_spec)

    for user in users_by_email.values():
        _sync_balance(db, user)

    db.commit()
    return users_by_email


def main() -> None:
    SessionLocal = get_session_local()
    with SessionLocal() as db:
        users = seed_demo_data(db)
        print(f"Demo data loaded successfully (password for all accounts: {DEMO_PASSWORD})\n")
        for email, user in users.items():
            balance = db.get(PTOBalance, user.employee_id)
            print(
                f"- {user.name:<15} | {email:<20} | role={user.role:<8} | "
                f"total={balance.total_hours}h, used={balance.used_hours}h, "
                f"pending={balance.pending_hours}h, available={balance.available_hours}h"
            )


if __name__ == "__main__":
    main()