"""Authentication and Role-Based Access Control (RBAC) module.

Implements password hashing, JWT issuance/verification, current-user
dependencies, role/hierarchy enforcement, and /api/v1/auth & /api/v1/users/me
endpoints per the Unit 3 System Design Specification.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.errors import AppError
from app.models import User

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# auto_error=False lets us return our standard {"error": {...}} JSON shape via AppError
bearer_scheme = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/api/v1", tags=["auth"])


# ---------------------------------------------------------------------------
# Pydantic Schemas (Spec Section 5 Data Contracts)
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    employee_id: int
    name: str
    email: str
    role: str
    manager_id: int | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ---------------------------------------------------------------------------
# Password Hashing
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT Creation & Decoding
# ---------------------------------------------------------------------------

def _get_jwt_secret() -> str:
    settings = get_settings()
    if not settings.jwt_secret:
        raise RuntimeError(
            "JWT_SECRET is not set. Configure it in backend/.env or environment variables."
        )
    return settings.jwt_secret


def create_access_token(
    user: User,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT for the given user."""
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    )
    payload: dict[str, Any] = {
        "sub": str(user.employee_id),
        "role": user.role,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify and decode a JWT, raising AppError(401) if invalid or expired."""
    try:
        return jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AppError(
            "UNAUTHORIZED",
            "Authentication token has expired.",
            status_code=401,
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise AppError(
            "UNAUTHORIZED",
            "Invalid authentication token.",
            status_code=401,
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI Dependencies & RBAC Helpers
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Reusable dependency that returns the authenticated User from the Bearer token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(
            "UNAUTHORIZED",
            "Missing or invalid authentication token.",
            status_code=401,
        )

    payload = decode_access_token(credentials.credentials)
    sub = payload.get("sub")
    try:
        employee_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise AppError(
            "UNAUTHORIZED",
            "Invalid authentication token payload.",
            status_code=401,
        ) from exc

    user = db.get(User, employee_id)
    if user is None:
        raise AppError(
            "UNAUTHORIZED",
            "User account not found.",
            status_code=401,
        )
    return user


def require_manager(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that restricts an endpoint to users with the 'manager' role."""
    if current_user.role != "manager":
        raise AppError(
            "FORBIDDEN",
            "Manager permissions are required to perform this action.",
            status_code=403,
        )
    return current_user


def verify_manager_for_employee(manager: User, employee: User) -> None:
    """Verify that the user is a manager and supervises the target employee."""
    if manager.role != "manager":
        raise AppError(
            "FORBIDDEN",
            "Manager permissions are required to perform this action.",
            status_code=403,
        )
    if employee.manager_id != manager.employee_id:
        raise AppError(
            "FORBIDDEN",
            "You are only authorized to access records for your assigned employees.",
            status_code=403,
        )


def get_assigned_employee(
    employee_id: int,
    db: Session,
    manager: User,
) -> User:
    """Fetch an employee by ID and confirm they report to the given manager."""
    if manager.role != "manager":
        raise AppError(
            "FORBIDDEN",
            "Manager permissions are required to perform this action.",
            status_code=403,
        )
    employee = db.get(User, employee_id)
    if employee is None:
        raise AppError(
            "NOT_FOUND",
            "Employee not found.",
            status_code=404,
        )
    verify_manager_for_employee(manager, employee)
    return employee


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Authenticate email/password and return a signed JWT."""
    stmt = select(User).where(func.lower(User.email) == body.email.strip().lower())
    user = db.scalars(stmt).first()

    if user is None or not verify_password(body.password, user.password_hash):
        raise AppError(
            "UNAUTHORIZED",
            "Invalid email or password.",
            status_code=401,
        )

    token = create_access_token(user)
    return LoginResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/users/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Retrieve the authenticated user's profile (Spec Section 3)."""
    return UserResponse.model_validate(current_user)