"""PTO request endpoints (Week 3 spec, Sections 3.1–3.5)."""

from datetime import date, datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_manager, verify_manager_for_employee
from app.database import get_db
from app.errors import AppError
from app.models import PTOBalance, PTORequest, User
from app.rule_engine import (
    ACTIVE_STATUSES,
    ERROR_STATUS_CODES,
    ExistingRequest,
    evaluate_request,
)

router = APIRouter(prefix="/api/v1/pto", tags=["pto"])

PTOStatus = Literal["pending", "approved", "denied"]
PTODecision = Literal["approved", "denied"]


# ---------------------------------------------------------------------------
# Schemas (shared by all PTO endpoints)
# ---------------------------------------------------------------------------

class PTOFlag(BaseModel):
    code: str
    message: str


class CreatePTORequest(BaseModel):
    start_date: date
    end_date: date
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class PTORequestResponse(BaseModel):
    """A PTO request as returned by every PTO endpoint."""

    request_id: int
    employee_id: int
    employee_name: str
    start_date: date
    end_date: date
    hours: int
    reason: str | None
    status: str
    flags: list[PTOFlag]
    manager_comment: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, request: PTORequest) -> "PTORequestResponse":
        return cls(
            request_id=request.request_id,
            employee_id=request.employee_id,
            employee_name=request.employee.name,
            start_date=request.start_date,
            end_date=request.end_date,
            hours=request.hours,
            reason=request.reason,
            status=request.status,
            flags=request.rule_flags or [],
            manager_comment=request.manager_comment,
            created_at=request.created_at,
        )


class PTOBalanceResponse(BaseModel):
    """Employee PTO balance (Week 3 spec, Section 3.2)."""

    employee_id: int
    total_hours: int
    used_hours: int
    pending_hours: int
    available_hours: int

    @classmethod
    def from_model(cls, balance: PTOBalance) -> "PTOBalanceResponse":
        return cls(
            employee_id=balance.employee_id,
            total_hours=balance.total_hours,
            used_hours=balance.used_hours,
            pending_hours=balance.pending_hours,
            available_hours=balance.available_hours,
        )


class PTORequestListResponse(BaseModel):
    """Paginated list of PTO requests reusing PTORequestResponse (Week 3 spec, Section 3.3)."""

    requests: list[PTORequestResponse]
    total: int
    limit: int
    offset: int


class PTODecisionRequest(BaseModel):
    """Manager approval or denial payload (Week 3 spec, Section 3.5)."""

    decision: PTODecision
    manager_comment: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=500)
    ] | None = None


# ---------------------------------------------------------------------------
# GET /api/v1/pto/balance
# ---------------------------------------------------------------------------

@router.get("/balance", response_model=PTOBalanceResponse)
def get_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PTOBalanceResponse:
    """Retrieve the logged-in user's PTO balance (Week 3 spec, Section 3.2)."""
    balance = db.get(PTOBalance, current_user.employee_id)
    if balance is None:
        raise AppError(
            "BALANCE_NOT_FOUND",
            "No PTO balance is set up for your account. Please contact Human Resources.",
            status_code=404,
        )
    return PTOBalanceResponse.from_model(balance)


# ---------------------------------------------------------------------------
# POST /api/v1/pto/requests
# ---------------------------------------------------------------------------

@router.post(
    "/requests",
    response_model=PTORequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_request(
    body: CreatePTORequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PTORequestResponse:
    """Submit a PTO request for the logged-in user (Week 3 spec, Section 3.1).

    The employee always comes from the login token, never from the request body.
    The rule engine rejects invalid requests and flags policy concerns; the
    request is saved as pending for the manager to decide.
    """
    # Lock the balance row so two submissions at once can't both use the same hours.
    balance = db.scalars(
        select(PTOBalance)
        .where(PTOBalance.employee_id == current_user.employee_id)
        .with_for_update()
    ).first()
    if balance is None:
        raise AppError(
            "BALANCE_NOT_FOUND",
            "No PTO balance is set up for your account. Please contact Human Resources.",
            status_code=404,
        )

    active_requests = db.scalars(
        select(PTORequest).where(
            PTORequest.employee_id == current_user.employee_id,
            PTORequest.status.in_(ACTIVE_STATUSES),
        )
    ).all()

    result = evaluate_request(
        start_date=body.start_date,
        end_date=body.end_date,
        available_hours=balance.available_hours,
        existing_requests=[
            ExistingRequest(r.start_date, r.end_date, r.status) for r in active_requests
        ],
    )

    if not result.is_valid:
        error = result.errors[0]
        raise AppError(
            error["code"],
            error["message"],
            status_code=ERROR_STATUS_CODES[error["code"]],
        )

    request = PTORequest(
        employee_id=current_user.employee_id,
        start_date=body.start_date,
        end_date=body.end_date,
        hours=result.hours,
        reason=body.reason or None,
        status="pending",
        rule_flags=result.flags,
    )
    db.add(request)

    # Reserve the hours so they can't be requested twice.
    balance.pending_hours += result.hours

    db.commit()
    db.refresh(request)
    return PTORequestResponse.from_model(request)


# ---------------------------------------------------------------------------
# GET /api/v1/pto/requests
# ---------------------------------------------------------------------------

@router.get("/requests", response_model=PTORequestListResponse)
def list_requests(
    status: PTOStatus | None = Query(default=None),
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PTORequestListResponse:
    """List PTO requests visible to the logged-in user (Week 3 spec, Section 3.3).

    Employees see only their own requests; managers see only requests from
    their assigned employees.
    """
    conditions = []
    if current_user.role == "manager":
        conditions.append(User.manager_id == current_user.employee_id)
    else:
        conditions.append(PTORequest.employee_id == current_user.employee_id)

    if status is not None:
        conditions.append(PTORequest.status == status)

    total_stmt = (
        select(func.count(PTORequest.request_id))
        .join(User, PTORequest.employee_id == User.employee_id)
        .where(*conditions)
    )
    total = db.scalar(total_stmt) or 0

    items_stmt = (
        select(PTORequest)
        .join(User, PTORequest.employee_id == User.employee_id)
        .options(joinedload(PTORequest.employee))
        .where(*conditions)
        .order_by(PTORequest.created_at.desc(), PTORequest.request_id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = db.scalars(items_stmt).all()

    return PTORequestListResponse(
        requests=[PTORequestResponse.from_model(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/pto/requests/{request_id}
# ---------------------------------------------------------------------------

@router.get("/requests/{request_id}", response_model=PTORequestResponse)
def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PTORequestResponse:
    """Retrieve a single PTO request (Week 3 spec, Section 3.4)."""
    stmt = (
        select(PTORequest)
        .options(joinedload(PTORequest.employee))
        .where(PTORequest.request_id == request_id)
    )
    pto_request = db.scalars(stmt).first()
    if pto_request is None:
        raise AppError(
            "REQUEST_NOT_FOUND",
            "PTO request not found.",
            status_code=404,
        )

    if current_user.role == "manager":
        verify_manager_for_employee(current_user, pto_request.employee)
    elif pto_request.employee_id != current_user.employee_id:
        raise AppError(
            "FORBIDDEN",
            "You are only authorized to view your own PTO requests.",
            status_code=403,
        )

    return PTORequestResponse.from_model(pto_request)


# ---------------------------------------------------------------------------
# PATCH /api/v1/pto/requests/{request_id}/decision
# ---------------------------------------------------------------------------

@router.patch("/requests/{request_id}/decision", response_model=PTORequestResponse)
def decide_request(
    request_id: int,
    body: PTODecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> PTORequestResponse:
    """Approve or deny a pending PTO request (Week 3 spec, Section 3.5).

    Manager-only, restricted to assigned employees, and cannot be decided twice.
    """
    stmt = (
        select(PTORequest)
        .options(joinedload(PTORequest.employee))
        .where(PTORequest.request_id == request_id)
        .with_for_update()
    )
    pto_request = db.scalars(stmt).first()
    if pto_request is None:
        raise AppError(
            "REQUEST_NOT_FOUND",
            "PTO request not found.",
            status_code=404,
        )

    verify_manager_for_employee(current_user, pto_request.employee)

    if pto_request.status != "pending":
        raise AppError(
            "ALREADY_DECIDED",
            "This PTO request has already been decided.",
            status_code=409,
        )

    balance = db.scalars(
        select(PTOBalance)
        .where(PTOBalance.employee_id == pto_request.employee_id)
        .with_for_update()
    ).first()
    if balance is None:
        raise AppError(
            "BALANCE_NOT_FOUND",
            "No PTO balance is set up for this employee.",
            status_code=404,
        )

    # Remove from pending; move to used only when approved.
    balance.pending_hours = max(0, balance.pending_hours - pto_request.hours)
    if body.decision == "approved":
        balance.used_hours += pto_request.hours

    pto_request.status = body.decision
    pto_request.manager_comment = body.manager_comment or None
    pto_request.reviewed_by = current_user.employee_id
    pto_request.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(pto_request)
    return PTORequestResponse.from_model(pto_request)