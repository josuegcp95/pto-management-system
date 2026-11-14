"""Tests for authentication, JWT handling, and role-based access control."""

from datetime import timedelta
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import (
    create_access_token,
    get_assigned_employee,
    hash_password,
    require_manager,
    router as auth_router,
    verify_password,
)
from app.config import get_settings
from app.database import Base, get_db
from app.errors import register_exception_handlers
from app.models import User

TEST_JWT_SECRET = "test-only-jwt-secret-key"


@pytest.fixture(autouse=True)
def configure_test_jwt_secret(monkeypatch):
    """Ensure JWT_SECRET is always set during tests (including in CI)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "jwt_secret", TEST_JWT_SECRET)


@pytest.fixture()
def db_session():
    """In-memory SQLite session shared across a single test."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with TestingSession() as session:
        yield session


@pytest.fixture()
def client(db_session: Session):
    """TestClient wired with the auth router, error handlers, and test DB."""
    test_app = FastAPI()
    register_exception_handlers(test_app)
    test_app.include_router(auth_router)

    @test_app.get("/api/v1/manager-only")
    def manager_only_route(manager: User = Depends(require_manager)):
        return {"manager_id": manager.employee_id}

    @test_app.get("/api/v1/manager/employees/{employee_id}")
    def manager_employee_route(
        employee_id: int,
        db: Session = Depends(get_db),
        manager: User = Depends(require_manager),
    ):
        employee = get_assigned_employee(employee_id, db, manager)
        return {"employee_id": employee.employee_id, "name": employee.name}

    def override_get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = override_get_db
    return TestClient(test_app)


@pytest.fixture()
def sample_users(db_session: Session) -> dict[str, User]:
    """Create two managers and two employees in the test database."""
    manager_a = User(
        name="Alice Manager",
        email="alice@example.com",
        password_hash=hash_password("manager-pass-123"),
        role="manager",
    )
    manager_b = User(
        name="charlie Manager",
        email="charlie@example.com",
        password_hash=hash_password("manager-pass-456"),
        role="manager",
    )
    db_session.add_all([manager_a, manager_b])
    db_session.flush()

    employee_bob = User(
        name="Bob Employee",
        email="bob@example.com",
        password_hash=hash_password("employee-pass-123"),
        role="employee",
        manager_id=manager_a.employee_id,
    )
    employee_dana = User(
        name="Dana Employee",
        email="dana@example.com",
        password_hash=hash_password("employee-pass-456"),
        role="employee",
        manager_id=manager_b.employee_id,
    )
    db_session.add_all([employee_bob, employee_dana])
    db_session.commit()

    return {
        "manager_a": manager_a,
        "manager_b": manager_b,
        "bob": employee_bob,
        "dana": employee_dana,
    }


# ---------------------------------------------------------------------------
# Password Hashing
# ---------------------------------------------------------------------------

def test_password_hash_and_verify():
    hashed = hash_password("correct-horse-battery-staple")
    assert hashed != "correct-horse-battery-staple"
    assert verify_password("correct-horse-battery-staple", hashed) is True
    assert verify_password("wrong-password", hashed) is False


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------

def test_login_success_returns_jwt_and_user(
    client: TestClient, sample_users: dict[str, User]
):
    bob = sample_users["bob"]
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "employee-pass-123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 20
    assert body["user"] == {
        "employee_id": bob.employee_id,
        "name": "Bob Employee",
        "email": "bob@example.com",
        "role": "employee",
        "manager_id": sample_users["manager_a"].employee_id,
    }


def test_login_wrong_password_returns_401(
    client: TestClient, sample_users: dict[str, User]
):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_login_unknown_email_returns_401(
    client: TestClient, sample_users: dict[str, User]
):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "employee-pass-123"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


# ---------------------------------------------------------------------------
# GET /api/v1/users/me & Token Validation
# ---------------------------------------------------------------------------

def test_get_me_returns_current_user(
    client: TestClient, sample_users: dict[str, User]
):
    bob = sample_users["bob"]
    token = create_access_token(bob)
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "employee_id": bob.employee_id,
        "name": "Bob Employee",
        "email": "bob@example.com",
        "role": "employee",
        "manager_id": sample_users["manager_a"].employee_id,
    }


def test_get_me_missing_token_returns_401(client: TestClient):
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_get_me_invalid_token_returns_401(client: TestClient):
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer not-a-valid-jwt-token"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_get_me_expired_token_returns_401(
    client: TestClient, sample_users: dict[str, User]
):
    expired_token = create_access_token(
        sample_users["bob"], expires_delta=timedelta(seconds=-10)
    )
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


# ---------------------------------------------------------------------------
# Role-Based Access Control (Employee vs. Manager & Assigned Hierarchy)
# ---------------------------------------------------------------------------

def test_manager_only_route_allows_manager(
    client: TestClient, sample_users: dict[str, User]
):
    manager_a = sample_users["manager_a"]
    token = create_access_token(manager_a)
    response = client.get(
        "/api/v1/manager-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == {"manager_id": manager_a.employee_id}


def test_manager_only_route_rejects_employee_with_403(
    client: TestClient, sample_users: dict[str, User]
):
    bob = sample_users["bob"]
    token = create_access_token(bob)
    response = client.get(
        "/api/v1/manager-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_manager_can_access_assigned_employee(
    client: TestClient, sample_users: dict[str, User]
):
    manager_a = sample_users["manager_a"]
    bob = sample_users["bob"]
    token = create_access_token(manager_a)
    response = client.get(
        f"/api/v1/manager/employees/{bob.employee_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "employee_id": bob.employee_id,
        "name": "Bob Employee",
    }


def test_manager_cannot_access_unassigned_employee_returns_403(
    client: TestClient, sample_users: dict[str, User]
):
    # manager_a tries to access dana, who reports to manager_b
    manager_a = sample_users["manager_a"]
    dana = sample_users["dana"]
    token = create_access_token(manager_a)
    response = client.get(
        f"/api/v1/manager/employees/{dana.employee_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_manager_lookup_nonexistent_employee_returns_404(
    client: TestClient, sample_users: dict[str, User]
):
    manager_a = sample_users["manager_a"]
    token = create_access_token(manager_a)
    response = client.get(
        "/api/v1/manager/employees/99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"