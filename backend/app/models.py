"""Core SQLAlchemy ORM models for the PTO Management System.

Aligns with the Unit 3 System Design Specification (Sections 3 & 5) and
persists rule flags and hours produced by app/rule_engine.py.
"""

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym
from sqlalchemy.types import JSON

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Employee or manager account and reporting hierarchy (Spec Section 5)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('employee', 'manager')", name="ck_users_role"),
    )

    employee_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="employee"
    )
    manager_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.employee_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
        server_default=func.now(),
    )

    # Relationships
    manager: Mapped["User | None"] = relationship(
        "User", remote_side=[employee_id], back_populates="direct_reports"
    )
    direct_reports: Mapped[list["User"]] = relationship(
        "User", back_populates="manager"
    )
    balance: Mapped["PTOBalance | None"] = relationship(
        "PTOBalance",
        back_populates="employee",
        uselist=False,
        cascade="all, delete-orphan",
    )
    pto_requests: Mapped[list["PTORequest"]] = relationship(
        "PTORequest",
        back_populates="employee",
        foreign_keys="PTORequest.employee_id",
        cascade="all, delete-orphan",
    )


class PTOBalance(Base):
    """PTO hour balances per employee (Spec Section 3.2 & Section 5)."""

    __tablename__ = "pto_balances"
    __table_args__ = (
        CheckConstraint("total_hours >= 0", name="ck_pto_balances_total_nonnegative"),
        CheckConstraint("used_hours >= 0", name="ck_pto_balances_used_nonnegative"),
        CheckConstraint(
            "pending_hours >= 0", name="ck_pto_balances_pending_nonnegative"
        ),
    )

    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.employee_id", ondelete="CASCADE"),
        primary_key=True,
    )
    total_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    used_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
        server_default=func.now(),
    )

    employee: Mapped["User"] = relationship("User", back_populates="balance")

    @property
    def available_hours(self) -> int:
        """Derived available PTO hours (total - used - pending) per Spec Section 3.2."""
        return self.total_hours - self.used_hours - self.pending_hours


class PTORequest(Base):
    """PTO request record, rule flags, and manager decision (Spec Sections 3.1-3.5 & 5)."""

    __tablename__ = "pto_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'denied')",
            name="ck_pto_requests_status",
        ),
        CheckConstraint(
            "start_date <= end_date", name="ck_pto_requests_date_range"
        ),
        CheckConstraint("hours > 0", name="ck_pto_requests_hours_positive"),
    )

    request_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.employee_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )

    # Rule flags from app.rule_engine.evaluate_request: list[{"code": ..., "message": ...}]
    rule_flags: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    # Alias so both request.rule_flags and request.flags work seamlessly
    flags = synonym("rule_flags")

    # Manager decision fields (Spec Section 3.5)
    manager_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.employee_id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps (Spec Section 2 & 3.1: ISO 8601 UTC)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
        server_default=func.now(),
    )

    employee: Mapped["User"] = relationship(
        "User", back_populates="pto_requests", foreign_keys=[employee_id]
    )
    reviewer: Mapped["User | None"] = relationship(
        "User", foreign_keys=[reviewed_by]
    )