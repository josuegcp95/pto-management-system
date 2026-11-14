"""PTO request endpoints (Week 3 spec, Sections 3.1–3.5).

This module currently provides request submission (#13). The read and
decision endpoints (#12) belong in this same router.
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
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
