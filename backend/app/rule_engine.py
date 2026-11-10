"""Deterministic rule engine for PTO requests.

Checks a PTO request against the company policy (app/policy/pto_policy.md)
and returns two kinds of results:

- **errors**: problems that reject the request (it is not saved)
- **flags**: policy concerns saved with the request for the manager to review

The engine never approves or denies anything. Managers make every decision.

Everything here is a pure function: no database, no AI, no current-date
lookups unless ``today`` is omitted. That keeps the rules easy to test.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Policy values (must match app/policy/pto_policy.md)
# ---------------------------------------------------------------------------

HOURS_PER_WORKDAY = 8           # Section 3
ADVANCE_NOTICE_DAYS = 7         # Section 6
MAX_WORKDAYS_WITHOUT_FLAG = 10  # Section 7

# Section 4: company holidays are not deducted from PTO.
COMPANY_HOLIDAYS = frozenset({
    # 2026
    date(2026, 1, 1),    # New Year's Day
    date(2026, 1, 19),   # Martin Luther King Jr. Day
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),   # Juneteenth
    date(2026, 7, 3),    # Independence Day (observed)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving Day
    date(2026, 11, 27),  # Day after Thanksgiving
    date(2026, 12, 24),  # Christmas Eve
    date(2026, 12, 25),  # Christmas Day
    # 2027
    date(2027, 1, 1),    # New Year's Day
    date(2027, 1, 18),   # Martin Luther King Jr. Day
    date(2027, 5, 31),   # Memorial Day
    date(2027, 6, 18),   # Juneteenth (observed)
    date(2027, 7, 5),    # Independence Day (observed)
    date(2027, 9, 6),    # Labor Day
    date(2027, 11, 25),  # Thanksgiving Day
    date(2027, 11, 26),  # Day after Thanksgiving
    date(2027, 12, 23),  # Christmas Eve (observed)
    date(2027, 12, 24),  # Christmas Day (observed)
    date(2027, 12, 31),  # New Year's Day 2028 (observed)
})

# Requests in these statuses count toward overlap checks.
ACTIVE_STATUSES = frozenset({"pending", "approved"})

# ---------------------------------------------------------------------------
# Predefined explanations for every rule code
# ---------------------------------------------------------------------------

# Errors: the request is rejected.
INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
START_DATE_IN_PAST = "START_DATE_IN_PAST"
NO_WORKDAYS = "NO_WORKDAYS"
OVERLAPPING_REQUEST = "OVERLAPPING_REQUEST"

# Flags: the request is saved and shown to the manager.
INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
SHORT_NOTICE = "SHORT_NOTICE"
LONG_REQUEST = "LONG_REQUEST"

RULE_MESSAGES = {
    INVALID_DATE_RANGE: "The start date must be on or before the end date.",
    START_DATE_IN_PAST: "The start date cannot be in the past.",
    NO_WORKDAYS: "The request must include at least one workday (weekends and company holidays don't count).",
    OVERLAPPING_REQUEST: "This request overlaps with another pending or approved request.",
    INSUFFICIENT_BALANCE: "Request exceeds available PTO balance.",
    SHORT_NOTICE: f"Submitted with less than {ADVANCE_NOTICE_DAYS} days' notice.",
    LONG_REQUEST: f"Request is longer than {MAX_WORKDAYS_WITHOUT_FLAG} consecutive workdays.",
}

# HTTP status the API should use for each error code.
ERROR_STATUS_CODES = {
    INVALID_DATE_RANGE: 400,
    START_DATE_IN_PAST: 400,
    NO_WORKDAYS: 400,
    OVERLAPPING_REQUEST: 409,
}

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExistingRequest:
    """The parts of an existing request the rules need."""

    start_date: date
    end_date: date
    status: str


@dataclass
class RuleResult:
    """Outcome of evaluating a request."""

    hours: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    flags: list[dict[str, str]] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True when the request can be saved (flags are allowed)."""
        return not self.errors


def _rule(code: str) -> dict[str, str]:
    return {"code": code, "message": RULE_MESSAGES[code]}


# ---------------------------------------------------------------------------
# Hours calculation
# ---------------------------------------------------------------------------


def is_workday(day: date) -> bool:
    """Monday–Friday and not a company holiday."""
    return day.weekday() < 5 and day not in COMPANY_HOLIDAYS


def count_workdays(start_date: date, end_date: date) -> int:
    """Number of workdays from start to end, inclusive."""
    if end_date < start_date:
        return 0
    total_days = (end_date - start_date).days + 1
    return sum(1 for offset in range(total_days) if is_workday(start_date + timedelta(days=offset)))


def calculate_hours(start_date: date, end_date: date) -> int:
    """PTO hours a request uses: workdays × 8."""
    return count_workdays(start_date, end_date) * HOURS_PER_WORKDAY


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def _overlaps(start_date: date, end_date: date, other: ExistingRequest) -> bool:
    return start_date <= other.end_date and end_date >= other.start_date


def evaluate_request(
    start_date: date,
    end_date: date,
    available_hours: float,
    existing_requests: Iterable[ExistingRequest] = (),
    today: date | None = None,
) -> RuleResult:
    """Check a new request against the PTO policy.

    Args:
        start_date: First day off.
        end_date: Last day off.
        available_hours: Employee's available balance (total - used - pending).
        existing_requests: The employee's other requests, used for overlap checks.
        today: The current date. Pass it explicitly in tests.

    Returns:
        A RuleResult with the request's hours, any errors (reject), and any flags.
    """
    today = today or date.today()
    result = RuleResult()

    # Errors: stop early if the dates themselves are unusable.
    if end_date < start_date:
        result.errors.append(_rule(INVALID_DATE_RANGE))
        return result

    if start_date < today:
        result.errors.append(_rule(START_DATE_IN_PAST))
        return result

    workdays = count_workdays(start_date, end_date)
    if workdays == 0:
        result.errors.append(_rule(NO_WORKDAYS))
        return result

    if any(
        request.status.lower() in ACTIVE_STATUSES and _overlaps(start_date, end_date, request)
        for request in existing_requests
    ):
        result.errors.append(_rule(OVERLAPPING_REQUEST))
        return result

    # The request is valid. Calculate hours and add any flags.
    result.hours = workdays * HOURS_PER_WORKDAY

    if result.hours > available_hours:
        result.flags.append(_rule(INSUFFICIENT_BALANCE))

    if (start_date - today).days < ADVANCE_NOTICE_DAYS:
        result.flags.append(_rule(SHORT_NOTICE))

    if workdays > MAX_WORKDAYS_WITHOUT_FLAG:
        result.flags.append(_rule(LONG_REQUEST))

    return result