"""Tests for PTO read and decision endpoints (Week 3 spec, Sections 3.2–3.5)."""

from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import PTOBalance, PTORequest, User

EXPECTED_REQUEST_KEYS = {
    "request_id",
    "employee_id",
    "employee_name",
    "start_date",
    "end_date",
    "hours",
    "reason",
    "status",
    "flags",
    "manager_comment",
    "created_at",
}


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, autocommit=False, autoflush=False)() as session:
        yield session


@pytest.fixture()
def org(db_session: Session) -> dict[str, User | PTORequest]:
    """Create two managers, three employees (120h starting balance), and sample requests."""
    manager_alice = User(
        name="Alice Manager",
        email="alice@example.com",
        password_hash="x",
        role="manager",
    )
    manager_charlie = User(
        name="Charlie Manager",
        email="charlie@example.com",
        password_hash="x",
        role="manager",
    )
    db_session.add_all([manager_alice, manager_charlie])
    db_session.flush()

    bob = User(
        name="Bob Employee",
        email="bob@example.com",
        password_hash="x",
        role="employee",
        manager_id=manager_alice.employee_id,
    )
    carol = User(
        name="Carol Employee",
        email="carol@example.com",
        password_hash="x",
        role="employee",
        manager_id=manager_alice.employee_id,
    )
    dana = User(
        name="Dana Employee",
        email="dana@example.com",
        password_hash="x",
        role="employee",
        manager_id=manager_charlie.employee_id,
    )
    db_session.add_all([bob, carol, dana])
    db_session.flush()

    db_session.add_all(
        [
            PTOBalance(
                employee_id=bob.employee_id,
                total_hours=120,
                used_hours=40,
                pending_hours=16,
            ),
            PTOBalance(
                employee_id=carol.employee_id,
                total_hours=120,
                used_hours=0,
                pending_hours=24,
            ),
            PTOBalance(
                employee_id=dana.employee_id,
                total_hours=120,
                used_hours=0,
                pending_hours=8,
            ),
        ]
    )

    req_bob_approved = PTORequest(
        employee_id=bob.employee_id,
        start_date=date(2026, 10, 12),
        end_date=date(2026, 10, 16),
        hours=40,
        reason="Fall break",
        status="approved",
        rule_flags=[],
        manager_comment="Enjoy!",
        reviewed_by=manager_alice.employee_id,
    )
    req_bob_pending = PTORequest(
        employee_id=bob.employee_id,
        start_date=date(2026, 11, 16),
        end_date=date(2026, 11, 17),
        hours=16,
        reason="Personal days",
        status="pending",
        rule_flags=[
            {
                "code": "SHORT_NOTICE",
                "message": "Submitted with less than 7 days' notice.",
            }
        ],
    )
    req_carol_pending = PTORequest(
        employee_id=carol.employee_id,
        start_date=date(2026, 12, 7),
        end_date=date(2026, 12, 9),
        hours=24,
        reason="Winter trip",
        status="pending",
        rule_flags=[],
    )
    req_dana_pending = PTORequest(
        employee_id=dana.employee_id,
        start_date=date(2026, 12, 14),
        end_date=date(2026, 12, 14),
        hours=8,
        reason="Doctor appointment",
        status="pending",
        rule_flags=[],
    )
    db_session.add_all(
        [req_bob_approved, req_bob_pending, req_carol_pending, req_dana_pending]
    )
    db_session.commit()

    return {
        "alice": manager_alice,
        "charlie": manager_charlie,
        "bob": bob,
        "carol": carol,
        "dana": dana,
        "req_bob_approved": req_bob_approved,
        "req_bob_pending": req_bob_pending,
        "req_carol_pending": req_carol_pending,
        "req_dana_pending": req_dana_pending,
    }


@pytest.fixture()
def client_as(db_session: Session):
    """Return a TestClient authenticated as the given user."""
    def _make_client(user: User) -> TestClient:
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(app)

    yield _make_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/v1/pto/balance
# ---------------------------------------------------------------------------

def test_get_balance_returns_spec_fields(client_as, org):
    bob = org["bob"]
    client = client_as(bob)
    response = client.get("/api/v1/pto/balance")
    assert response.status_code == 200
    assert response.json() == {
        "employee_id": bob.employee_id,
        "total_hours": 120,
        "used_hours": 40,
        "pending_hours": 16,
        "available_hours": 64,
    }


def test_get_balance_missing_returns_404(client_as, org):
    client = client_as(org["alice"])
    response = client.get("/api/v1/pto/balance")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BALANCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# GET /api/v1/pto/requests (visibility, filtering, pagination)
# ---------------------------------------------------------------------------

def test_employee_only_sees_own_requests(client_as, org):
    bob = org["bob"]
    client = client_as(bob)
    response = client.get("/api/v1/pto/requests")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert {r["employee_id"] for r in body["requests"]} == {bob.employee_id}
    for item in body["requests"]:
        assert set(item.keys()) == EXPECTED_REQUEST_KEYS
        assert item["employee_name"] == "Bob Employee"


def test_manager_only_sees_assigned_team_requests(client_as, org):
    alice = org["alice"]
    bob = org["bob"]
    carol = org["carol"]
    dana = org["dana"]

    client = client_as(alice)
    response = client.get("/api/v1/pto/requests")
    assert response.status_code == 200
    body = response.json()

    assert body["total"] == 3
    returned_emp_ids = {r["employee_id"] for r in body["requests"]}
    assert returned_emp_ids == {bob.employee_id, carol.employee_id}
    assert dana.employee_id not in returned_emp_ids


def test_list_requests_status_filter(client_as, org):
    client = client_as(org["bob"])
    response = client.get("/api/v1/pto/requests", params={"status": "pending"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["requests"]) == 1
    assert body["requests"][0]["status"] == "pending"
    assert body["requests"][0]["flags"] == [
        {
            "code": "SHORT_NOTICE",
            "message": "Submitted with less than 7 days' notice.",
        }
    ]


def test_list_requests_invalid_status_returns_422(client_as, org):
    client = client_as(org["bob"])
    response = client.get("/api/v1/pto/requests", params={"status": "invalid"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_list_requests_pagination(client_as, org):
    client = client_as(org["alice"])
    page_1 = client.get("/api/v1/pto/requests", params={"limit": 2, "offset": 0}).json()
    page_2 = client.get("/api/v1/pto/requests", params={"limit": 2, "offset": 2}).json()

    assert page_1["total"] == 3
    assert len(page_1["requests"]) == 2
    assert page_2["total"] == 3
    assert len(page_2["requests"]) == 1
    assert page_1["requests"][0]["request_id"] != page_2["requests"][0]["request_id"]


# ---------------------------------------------------------------------------
# GET /api/v1/pto/requests/{request_id}
# ---------------------------------------------------------------------------

def test_employee_can_view_own_request_detail(client_as, org):
    bob = org["bob"]
    req = org["req_bob_pending"]
    client = client_as(bob)

    response = client.get(f"/api/v1/pto/requests/{req.request_id}")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == EXPECTED_REQUEST_KEYS
    assert body["request_id"] == req.request_id
    assert body["employee_name"] == "Bob Employee"
    assert body["hours"] == 16
    assert body["flags"][0]["code"] == "SHORT_NOTICE"


def test_employee_cannot_view_other_employee_request_returns_403(client_as, org):
    bob = org["bob"]
    carol_req = org["req_carol_pending"]
    client = client_as(bob)

    response = client.get(f"/api/v1/pto/requests/{carol_req.request_id}")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_manager_can_view_assigned_employee_request(client_as, org):
    alice = org["alice"]
    bob_req = org["req_bob_pending"]
    client = client_as(alice)

    response = client.get(f"/api/v1/pto/requests/{bob_req.request_id}")
    assert response.status_code == 200
    assert response.json()["request_id"] == bob_req.request_id


def test_manager_cannot_view_unassigned_employee_request_returns_403(client_as, org):
    alice = org["alice"]
    dana_req = org["req_dana_pending"]
    client = client_as(alice)

    response = client.get(f"/api/v1/pto/requests/{dana_req.request_id}")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_get_nonexistent_request_returns_404(client_as, org):
    client = client_as(org["bob"])
    response = client.get("/api/v1/pto/requests/99999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REQUEST_NOT_FOUND"


# ---------------------------------------------------------------------------
# PATCH /api/v1/pto/requests/{request_id}/decision
# ---------------------------------------------------------------------------

def test_manager_approves_request_moves_pending_to_used(
    client_as, db_session: Session, org
):
    alice = org["alice"]
    bob = org["bob"]
    req = org["req_bob_pending"]  # 16 hours

    client = client_as(alice)
    response = client.patch(
        f"/api/v1/pto/requests/{req.request_id}/decision",
        json={"decision": "approved", "manager_comment": "Request approved."},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == EXPECTED_REQUEST_KEYS
    assert body["request_id"] == req.request_id
    assert body["status"] == "approved"
    assert body["manager_comment"] == "Request approved."

    db_session.expire_all()
    updated_req = db_session.get(PTORequest, req.request_id)
    assert updated_req.reviewed_by == alice.employee_id
    assert updated_req.reviewed_at is not None

    balance = db_session.get(PTOBalance, bob.employee_id)
    assert balance.used_hours == 56
    assert balance.pending_hours == 0
    assert balance.available_hours == 64


def test_manager_denies_request_returns_pending_hours_to_available(
    client_as, db_session: Session, org
):
    alice = org["alice"]
    carol = org["carol"]
    req = org["req_carol_pending"]  # 24 hours

    client = client_as(alice)
    response = client.patch(
        f"/api/v1/pto/requests/{req.request_id}/decision",
        json={"decision": "denied", "manager_comment": "Peak week, coverage needed."},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == EXPECTED_REQUEST_KEYS
    assert body["status"] == "denied"
    assert body["manager_comment"] == "Peak week, coverage needed."

    db_session.expire_all()
    updated_req = db_session.get(PTORequest, req.request_id)
    assert updated_req.reviewed_by == alice.employee_id
    assert updated_req.reviewed_at is not None

    balance = db_session.get(PTOBalance, carol.employee_id)
    assert balance.used_hours == 0
    assert balance.pending_hours == 0
    assert balance.available_hours == 120


def test_employee_cannot_decide_request_returns_403(client_as, org):
    bob = org["bob"]
    req = org["req_bob_pending"]
    client = client_as(bob)

    response = client.patch(
        f"/api/v1/pto/requests/{req.request_id}/decision",
        json={"decision": "approved"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_manager_cannot_decide_unassigned_employee_request_returns_403(client_as, org):
    alice = org["alice"]
    dana_req = org["req_dana_pending"]
    client = client_as(alice)

    response = client.patch(
        f"/api/v1/pto/requests/{dana_req.request_id}/decision",
        json={"decision": "approved"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_cannot_decide_request_twice_returns_409(
    client_as, db_session: Session, org
):
    alice = org["alice"]
    bob = org["bob"]
    already_approved = org["req_bob_approved"]

    client = client_as(alice)
    response = client.patch(
        f"/api/v1/pto/requests/{already_approved.request_id}/decision",
        json={"decision": "denied", "manager_comment": "Changed my mind"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_DECIDED"

    db_session.expire_all()
    balance = db_session.get(PTOBalance, bob.employee_id)
    assert balance.used_hours == 40
    assert balance.pending_hours == 16


def test_decide_nonexistent_request_returns_404(client_as, org):
    client = client_as(org["alice"])
    response = client.patch(
        "/api/v1/pto/requests/99999/decision",
        json={"decision": "approved"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REQUEST_NOT_FOUND"


def test_decide_invalid_decision_value_returns_422(client_as, org):
    alice = org["alice"]
    req = org["req_bob_pending"]
    client = client_as(alice)

    response = client.patch(
        f"/api/v1/pto/requests/{req.request_id}/decision",
        json={"decision": "maybe"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"