"""Tests for the PTO rule engine."""

from datetime import date

from app.rule_engine import (
    INSUFFICIENT_BALANCE,
    INVALID_DATE_RANGE,
    LONG_REQUEST,
    NO_WORKDAYS,
    OVERLAPPING_REQUEST,
    SHORT_NOTICE,
    START_DATE_IN_PAST,
    ExistingRequest,
    calculate_hours,
    count_workdays,
    evaluate_request,
)

# A fixed "today" so tests don't depend on the real date.
TODAY = date(2026, 11, 2)  # Monday


def codes(items: list[dict[str, str]]) -> list[str]:
    return [item["code"] for item in items]


# ---------------------------------------------------------------------------
# Hours calculation
# ---------------------------------------------------------------------------


def test_single_weekday_is_8_hours():
    assert calculate_hours(date(2026, 12, 7), date(2026, 12, 7)) == 8


def test_full_week_is_40_hours():
    # Monday Dec 7 – Friday Dec 11, 2026
    assert calculate_hours(date(2026, 12, 7), date(2026, 12, 11)) == 40


def test_weekends_are_not_counted():
    # Friday Dec 11 – Monday Dec 14, 2026: Fri + Mon only
    assert count_workdays(date(2026, 12, 11), date(2026, 12, 14)) == 2


def test_holidays_are_not_counted():
    # Thanksgiving week 2026: Thu and Fri are holidays, so Mon–Wed only
    assert calculate_hours(date(2026, 11, 23), date(2026, 11, 27)) == 24


def test_policy_example_week_with_one_holiday_is_32_hours():
    # Policy Section 3: a Mon–Fri week with one holiday uses 32 hours.
    # Week of Labor Day 2027 (Mon Sep 6 is a holiday).
    assert calculate_hours(date(2027, 9, 6), date(2027, 9, 10)) == 32


# ---------------------------------------------------------------------------
# Errors (request rejected)
# ---------------------------------------------------------------------------


def test_end_before_start_is_rejected():
    result = evaluate_request(date(2026, 12, 10), date(2026, 12, 8), 120, today=TODAY)

    assert not result.is_valid
    assert codes(result.errors) == [INVALID_DATE_RANGE]


def test_start_in_past_is_rejected():
    result = evaluate_request(date(2026, 10, 30), date(2026, 11, 3), 120, today=TODAY)

    assert codes(result.errors) == [START_DATE_IN_PAST]


def test_starting_today_is_allowed():
    result = evaluate_request(TODAY, TODAY, 120, today=TODAY)

    assert result.is_valid


def test_weekend_only_request_is_rejected():
    # Saturday Dec 12 – Sunday Dec 13, 2026
    result = evaluate_request(date(2026, 12, 12), date(2026, 12, 13), 120, today=TODAY)

    assert codes(result.errors) == [NO_WORKDAYS]


def test_holiday_only_request_is_rejected():
    # Christmas Eve and Christmas Day 2026
    result = evaluate_request(date(2026, 12, 24), date(2026, 12, 25), 120, today=TODAY)

    assert codes(result.errors) == [NO_WORKDAYS]


def test_overlap_with_pending_request_is_rejected():
    existing = [ExistingRequest(date(2026, 12, 9), date(2026, 12, 11), "pending")]

    result = evaluate_request(date(2026, 12, 7), date(2026, 12, 9), 120, existing, today=TODAY)

    assert codes(result.errors) == [OVERLAPPING_REQUEST]


def test_overlap_with_approved_request_is_rejected():
    existing = [ExistingRequest(date(2026, 12, 7), date(2026, 12, 7), "approved")]

    result = evaluate_request(date(2026, 12, 7), date(2026, 12, 8), 120, existing, today=TODAY)

    assert codes(result.errors) == [OVERLAPPING_REQUEST]

def test_overlap_check_ignores_status_case():
    # A status stored as "Pending" must still block overlapping requests.
    existing = [ExistingRequest(date(2026, 12, 7), date(2026, 12, 8), "Pending")]

    result = evaluate_request(date(2026, 12, 8), date(2026, 12, 9), 120, existing, today=TODAY)

    assert codes(result.errors) == [OVERLAPPING_REQUEST]


def test_overlap_with_denied_request_is_allowed():
    existing = [ExistingRequest(date(2026, 12, 7), date(2026, 12, 11), "denied")]

    result = evaluate_request(date(2026, 12, 7), date(2026, 12, 8), 120, existing, today=TODAY)

    assert result.is_valid


def test_back_to_back_requests_do_not_overlap():
    existing = [ExistingRequest(date(2026, 12, 7), date(2026, 12, 8), "approved")]

    result = evaluate_request(date(2026, 12, 9), date(2026, 12, 10), 120, existing, today=TODAY)

    assert result.is_valid


# ---------------------------------------------------------------------------
# Flags (request saved for manager review)
# ---------------------------------------------------------------------------


def test_clean_request_has_hours_and_no_flags():
    result = evaluate_request(date(2026, 12, 7), date(2026, 12, 11), 120, today=TODAY)

    assert result.is_valid
    assert result.hours == 40
    assert result.flags == []


def test_insufficient_balance_is_flagged_not_rejected():
    result = evaluate_request(date(2026, 12, 7), date(2026, 12, 11), 32, today=TODAY)

    assert result.is_valid
    assert codes(result.flags) == [INSUFFICIENT_BALANCE]


def test_exact_balance_is_not_flagged():
    result = evaluate_request(date(2026, 12, 7), date(2026, 12, 11), 40, today=TODAY)

    assert result.flags == []


def test_short_notice_is_flagged():
    # Starts 6 days from today
    result = evaluate_request(date(2026, 11, 8), date(2026, 11, 9), 120, today=TODAY)

    assert codes(result.flags) == [SHORT_NOTICE]


def test_exactly_seven_days_notice_is_not_flagged():
    result = evaluate_request(date(2026, 11, 9), date(2026, 11, 9), 120, today=TODAY)

    assert result.flags == []


def test_more_than_ten_workdays_is_flagged():
    # Mon Dec 7 – Mon Dec 21, 2026: 11 workdays
    result = evaluate_request(date(2026, 12, 7), date(2026, 12, 21), 120, today=TODAY)

    assert result.hours == 88
    assert codes(result.flags) == [LONG_REQUEST]


def test_exactly_ten_workdays_is_not_flagged():
    # Mon Dec 7 – Fri Dec 18, 2026: 10 workdays
    result = evaluate_request(date(2026, 12, 7), date(2026, 12, 18), 120, today=TODAY)

    assert result.hours == 80
    assert result.flags == []


def test_multiple_flags_can_apply():
    # Short notice + long + more hours than available
    result = evaluate_request(date(2026, 11, 4), date(2026, 11, 20), 40, today=TODAY)

    assert codes(result.flags) == [INSUFFICIENT_BALANCE, SHORT_NOTICE, LONG_REQUEST]


def test_every_result_has_a_message():
    result = evaluate_request(date(2026, 11, 4), date(2026, 11, 20), 40, today=TODAY)

    assert all(flag["message"] for flag in result.flags)
