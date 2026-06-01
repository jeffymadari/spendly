"""
Tests for Step 6: Date Filter for Profile Page
Spec: .claude/specs/06-date-filter-profile-page.md

Coverage
--------
- GET /profile (no params)           → All Time unfiltered, filter-btn--active on "All Time"
- GET /profile?date_from=X&date_to=Y → all three sections filtered to that range
- "This Month" preset                → first/last day of current month, preset highlighted
- "Last 3 Months" preset             → window start computed correctly, preset highlighted
- "Last 6 Months" preset             → window start computed correctly, preset highlighted
- "All Time" (clean URL)             → active_preset == all_time, no query params needed
- Malformed date string              → 200, silent fallback to unfiltered, no crash
- date_from > date_to                → 200, flash "Start date must be before end date.", unfiltered
- filter-btn--active on active button
- Empty range                        → ₹0.00, 0 transactions, empty breakdown, no crash
- User with no expenses in range     → ₹0.00, no errors
- ₹ symbol always present in response
- get_filtered_stats DB helper       → in-range, out-of-range, empty, None/None
- get_filtered_transactions DB helper→ ordering, formatting, None/None
- get_filtered_breakdown DB helper   → categories, pct sum, empty, None/None
- _compute_preset_dates unit tests   → this_month, last_3, last_6, cross-year boundary
"""

import datetime
import calendar
import pytest
import database.db as db_module
import database.queries as queries
from app import app as flask_app, _compute_preset_dates


# ---------------------------------------------------------------------------
# Helpers shared across test classes
# ---------------------------------------------------------------------------

def _get_user_id(app, email):
    """Return the integer user id for a given email within an app context."""
    with app.app_context():
        row = db_module.get_user_by_email(email)
    return row["id"]


def _preset_dates_for_today():
    """Return the same preset dict the route computes for the real today."""
    today = datetime.date.today()
    return _compute_preset_dates(today)


# ===========================================================================
# Route tests — GET /profile
# ===========================================================================

class TestProfileNoParams:
    """GET /profile with no query params → All Time, unfiltered."""

    def test_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile")
        assert response.status_code == 200, "Expected 200 for authenticated /profile"

    def test_all_expenses_visible_including_old_dates(
        self, logged_in_client, test_user, insert_expense, app
    ):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 99.00, "Bills", "2015-06-15", "Very old expense")
        response = logged_in_client.get("/profile")
        assert b"Very old expense" in response.data, (
            "Unfiltered /profile should show expenses from any date"
        )

    def test_all_time_button_has_active_class(self, logged_in_client):
        response = logged_in_client.get("/profile")
        assert b"filter-btn--active" in response.data, (
            "filter-btn--active class must be present when no filter is active"
        )

    def test_rupee_symbol_present(self, logged_in_client):
        response = logged_in_client.get("/profile")
        assert "₹".encode() in response.data, (
            "₹ symbol must appear on the profile page regardless of filter"
        )

    def test_filter_bar_rendered(self, logged_in_client):
        response = logged_in_client.get("/profile")
        assert b"filter-btn" in response.data, "Filter bar must be rendered on the page"

    def test_all_time_preset_links_have_no_date_params(self, logged_in_client):
        """The All Time button must link to the clean /profile URL."""
        response = logged_in_client.get("/profile")
        # The anchor for All Time links to /profile with no date query params
        assert b'href="/profile"' in response.data, (
            "All Time button must link to /profile with no date query params"
        )


class TestCustomDateRangeFilter:
    """GET /profile?date_from=X&date_to=Y filters all three sections."""

    def test_in_range_expense_visible(
        self, logged_in_client, test_user, insert_expense, app
    ):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 25.00, "Food", "2026-03-15", "March meal")
        response = logged_in_client.get(
            "/profile?date_from=2026-03-01&date_to=2026-03-31"
        )
        assert response.status_code == 200
        assert b"March meal" in response.data, (
            "Expense inside the requested range must appear in response"
        )

    def test_out_of_range_expense_hidden(
        self, logged_in_client, test_user, insert_expense, app
    ):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 30.00, "Transport", "2026-01-05", "January trip")
        insert_expense(user_id, 15.00, "Food", "2026-03-20", "March snack")
        response = logged_in_client.get(
            "/profile?date_from=2026-03-01&date_to=2026-03-31"
        )
        assert b"January trip" not in response.data, (
            "Expense outside the requested range must NOT appear in response"
        )
        assert b"March snack" in response.data

    def test_boundary_date_inclusive_date_from(
        self, logged_in_client, test_user, insert_expense, app
    ):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 10.00, "Food", "2026-04-01", "On start boundary")
        response = logged_in_client.get(
            "/profile?date_from=2026-04-01&date_to=2026-04-30"
        )
        assert b"On start boundary" in response.data, (
            "Expense on date_from must be included (inclusive lower bound)"
        )

    def test_boundary_date_inclusive_date_to(
        self, logged_in_client, test_user, insert_expense, app
    ):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 10.00, "Food", "2026-04-30", "On end boundary")
        response = logged_in_client.get(
            "/profile?date_from=2026-04-01&date_to=2026-04-30"
        )
        assert b"On end boundary" in response.data, (
            "Expense on date_to must be included (inclusive upper bound)"
        )

    def test_stats_section_reflects_filter(
        self, logged_in_client, test_user, insert_expense, app
    ):
        """Total spent must reflect only in-range expenses."""
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 50.00, "Bills", "2026-04-10", "In range bill")
        insert_expense(user_id, 200.00, "Bills", "2026-01-01", "Out of range bill")
        response = logged_in_client.get(
            "/profile?date_from=2026-04-01&date_to=2026-04-30"
        )
        assert b"50.00" in response.data, (
            "Stats total should include the in-range expense amount"
        )
        assert b"200.00" not in response.data, (
            "Stats total must not include out-of-range expense amount"
        )

    def test_custom_preset_when_range_does_not_match_preset(
        self, logged_in_client
    ):
        """A range that doesn't match any preset should not highlight a preset button
        with the preset's class — the custom button carries filter-btn--active."""
        response = logged_in_client.get(
            "/profile?date_from=2026-01-15&date_to=2026-02-15"
        )
        assert response.status_code == 200
        assert b"filter-btn--active" in response.data, (
            "filter-btn--active must still appear when a custom range is active"
        )

    def test_rupee_symbol_present_with_filter(
        self, logged_in_client, test_user, insert_expense, app
    ):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 42.00, "Food", "2026-04-05", "Filtered expense")
        response = logged_in_client.get(
            "/profile?date_from=2026-04-01&date_to=2026-04-30"
        )
        assert "₹".encode() in response.data, (
            "₹ symbol must appear in response regardless of active filter"
        )


class TestPresetThisMonth:
    """'This Month' preset filters to current calendar month."""

    def test_this_month_preset_activates_correct_button(self, logged_in_client):
        presets = _preset_dates_for_today()
        date_from, date_to = presets["this_month"]
        response = logged_in_client.get(
            f"/profile?date_from={date_from}&date_to={date_to}"
        )
        assert response.status_code == 200
        assert b"filter-btn--active" in response.data, (
            "The 'This Month' preset button must carry filter-btn--active"
        )

    def test_this_month_shows_current_month_expense(
        self, logged_in_client, test_user, insert_expense, app
    ):
        today = datetime.date.today()
        expense_date = today.replace(day=1).isoformat()
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 10.00, "Food", expense_date, "Current month expense")
        presets = _preset_dates_for_today()
        date_from, date_to = presets["this_month"]
        response = logged_in_client.get(
            f"/profile?date_from={date_from}&date_to={date_to}"
        )
        assert b"Current month expense" in response.data, (
            "Expense in current month must appear under 'This Month' filter"
        )

    def test_this_month_excludes_last_month_expense(
        self, logged_in_client, test_user, insert_expense, app
    ):
        today = datetime.date.today()
        first_of_this_month = today.replace(day=1)
        # Put expense one day before the first of this month
        last_month_last_day = first_of_this_month - datetime.timedelta(days=1)
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(
            user_id, 50.00, "Bills",
            last_month_last_day.isoformat(),
            "Last month expense"
        )
        presets = _preset_dates_for_today()
        date_from, date_to = presets["this_month"]
        response = logged_in_client.get(
            f"/profile?date_from={date_from}&date_to={date_to}"
        )
        assert b"Last month expense" not in response.data, (
            "Expense from last month must NOT appear under 'This Month' filter"
        )


class TestPresetLast3Months:
    """'Last 3 Months' preset filters to a 3-month window ending today."""

    def test_last_3_months_preset_activates_correct_button(self, logged_in_client):
        presets = _preset_dates_for_today()
        date_from, date_to = presets["last_3_months"]
        response = logged_in_client.get(
            f"/profile?date_from={date_from}&date_to={date_to}"
        )
        assert response.status_code == 200
        assert b"filter-btn--active" in response.data, (
            "The 'Last 3 Months' preset button must carry filter-btn--active"
        )

    def test_last_3_months_shows_expense_in_window(
        self, logged_in_client, test_user, insert_expense, app
    ):
        presets = _preset_dates_for_today()
        date_from, date_to = presets["last_3_months"]
        user_id = _get_user_id(app, test_user["email"])
        # Use the start date of the window itself — should be included
        insert_expense(user_id, 15.00, "Food", date_from, "Start of window expense")
        response = logged_in_client.get(
            f"/profile?date_from={date_from}&date_to={date_to}"
        )
        assert b"Start of window expense" in response.data, (
            "Expense on the first day of the 3-month window must appear"
        )

    def test_last_3_months_excludes_expense_before_window(
        self, logged_in_client, test_user, insert_expense, app
    ):
        presets = _preset_dates_for_today()
        date_from_str, date_to = presets["last_3_months"]
        date_from = datetime.date.fromisoformat(date_from_str)
        before_window = (date_from - datetime.timedelta(days=1)).isoformat()
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 75.00, "Bills", before_window, "Before 3 months")
        response = logged_in_client.get(
            f"/profile?date_from={date_from_str}&date_to={date_to}"
        )
        assert b"Before 3 months" not in response.data, (
            "Expense before the 3-month window must NOT appear"
        )


class TestPresetLast6Months:
    """'Last 6 Months' preset filters to a 6-month window ending today."""

    def test_last_6_months_preset_activates_correct_button(self, logged_in_client):
        presets = _preset_dates_for_today()
        date_from, date_to = presets["last_6_months"]
        response = logged_in_client.get(
            f"/profile?date_from={date_from}&date_to={date_to}"
        )
        assert response.status_code == 200
        assert b"filter-btn--active" in response.data, (
            "The 'Last 6 Months' preset button must carry filter-btn--active"
        )

    def test_last_6_months_shows_expense_in_window(
        self, logged_in_client, test_user, insert_expense, app
    ):
        presets = _preset_dates_for_today()
        date_from, date_to = presets["last_6_months"]
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 20.00, "Transport", date_from, "6-month window start")
        response = logged_in_client.get(
            f"/profile?date_from={date_from}&date_to={date_to}"
        )
        assert b"6-month window start" in response.data, (
            "Expense on the first day of the 6-month window must appear"
        )

    def test_last_6_months_excludes_expense_before_window(
        self, logged_in_client, test_user, insert_expense, app
    ):
        presets = _preset_dates_for_today()
        date_from_str, date_to = presets["last_6_months"]
        date_from = datetime.date.fromisoformat(date_from_str)
        before_window = (date_from - datetime.timedelta(days=1)).isoformat()
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 100.00, "Shopping", before_window, "Before 6 months")
        response = logged_in_client.get(
            f"/profile?date_from={date_from_str}&date_to={date_to}"
        )
        assert b"Before 6 months" not in response.data, (
            "Expense before the 6-month window must NOT appear"
        )


class TestMalformedDateFallback:
    """Malformed date strings must not crash the app — silent fallback to unfiltered."""

    def test_malformed_date_from_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?date_from=not-a-date")
        assert response.status_code == 200, (
            "Malformed date_from must not crash the app"
        )

    def test_malformed_date_to_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?date_to=also-bad")
        assert response.status_code == 200, (
            "Malformed date_to must not crash the app"
        )

    def test_both_malformed_return_200(self, logged_in_client):
        response = logged_in_client.get(
            "/profile?date_from=not-a-date&date_to=also-bad"
        )
        assert response.status_code == 200, (
            "Both malformed date params must not crash the app"
        )

    def test_malformed_dates_fall_back_to_unfiltered(
        self, logged_in_client, test_user, insert_expense, app
    ):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 10.00, "Food", "2019-07-04", "Old visible expense")
        response = logged_in_client.get(
            "/profile?date_from=not-a-date&date_to=also-bad"
        )
        assert b"Old visible expense" in response.data, (
            "Malformed date params must fall back to unfiltered — all expenses visible"
        )

    def test_malformed_date_from_only_falls_back(
        self, logged_in_client, test_user, insert_expense, app
    ):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 10.00, "Food", "2010-01-01", "Ancient expense")
        response = logged_in_client.get("/profile?date_from=NOTADATE&date_to=2026-12-31")
        assert b"Ancient expense" in response.data, (
            "When only date_from is malformed, both params are discarded — unfiltered"
        )

    def test_partial_date_string_falls_back(self, logged_in_client):
        """A string like '2026-13' (invalid month) must be rejected silently."""
        response = logged_in_client.get(
            "/profile?date_from=2026-13-01&date_to=2026-12-31"
        )
        assert response.status_code == 200, (
            "Invalid date value (month 13) must not crash the app"
        )


class TestInvertedDateRange:
    """date_from > date_to must flash an error and fall back to unfiltered."""

    def test_returns_200(self, logged_in_client):
        response = logged_in_client.get(
            "/profile?date_from=2026-06-01&date_to=2026-05-01"
        )
        assert response.status_code == 200, (
            "Inverted date range must return 200, not an error status"
        )

    def test_flash_message_visible(self, logged_in_client):
        response = logged_in_client.get(
            "/profile?date_from=2026-06-01&date_to=2026-05-01"
        )
        assert b"Start date must be before end date" in response.data, (
            "Flash message 'Start date must be before end date.' must appear in page"
        )

    def test_falls_back_to_unfiltered(
        self, logged_in_client, test_user, insert_expense, app
    ):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 20.00, "Food", "2010-03-01", "Ancient fallback")
        response = logged_in_client.get(
            "/profile?date_from=2026-06-01&date_to=2026-05-01"
        )
        assert b"Ancient fallback" in response.data, (
            "After inverted-range error, page must show all expenses (unfiltered)"
        )

    def test_same_day_is_valid_not_inverted(
        self, logged_in_client, test_user, insert_expense, app
    ):
        """date_from == date_to is a valid single-day range, not an error."""
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 5.00, "Food", "2026-04-15", "Same day expense")
        response = logged_in_client.get(
            "/profile?date_from=2026-04-15&date_to=2026-04-15"
        )
        assert b"Start date must be before end date" not in response.data, (
            "Same-day range must not trigger the error flash"
        )
        assert b"Same day expense" in response.data


class TestEmptyRangeAndNoExpenses:
    """Ranges or users with no matching expenses must show zeros gracefully."""

    def test_empty_range_shows_zero_total(self, logged_in_client):
        response = logged_in_client.get(
            "/profile?date_from=2000-01-01&date_to=2000-01-31"
        )
        assert response.status_code == 200
        assert "₹0.00".encode() in response.data, (
            "Empty range must display ₹0.00 total spent"
        )

    def test_empty_range_shows_no_transactions_found(self, logged_in_client):
        response = logged_in_client.get(
            "/profile?date_from=2000-01-01&date_to=2000-01-31"
        )
        assert b"No transactions found" in response.data, (
            "Empty range transaction table must display 'No transactions found.' row"
        )

    def test_empty_range_shows_empty_breakdown(self, logged_in_client):
        response = logged_in_client.get(
            "/profile?date_from=2000-01-01&date_to=2000-01-31"
        )
        assert b"No spending data" in response.data, (
            "Empty range must show empty-state message in category breakdown"
        )

    def test_user_with_no_expenses_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile")
        assert response.status_code == 200

    def test_user_with_no_expenses_shows_zero_total(self, logged_in_client):
        response = logged_in_client.get("/profile")
        assert "₹0.00".encode() in response.data, (
            "User with no expenses must see ₹0.00 on the unfiltered profile"
        )

    def test_user_with_no_expenses_no_crash_with_filter(self, logged_in_client):
        response = logged_in_client.get(
            "/profile?date_from=2026-01-01&date_to=2026-12-31"
        )
        assert response.status_code == 200, (
            "User with no expenses must not crash when a date filter is applied"
        )

    def test_rupee_symbol_present_on_empty_range(self, logged_in_client):
        response = logged_in_client.get(
            "/profile?date_from=2000-01-01&date_to=2000-01-31"
        )
        assert "₹".encode() in response.data, (
            "₹ symbol must be present even when the range returns no expenses"
        )


class TestActivePresetHighlighting:
    """The active filter button must carry the filter-btn--active CSS class."""

    def test_all_time_button_active_on_clean_url(self, logged_in_client):
        response = logged_in_client.get("/profile")
        data = response.data.decode("utf-8")
        # The All Time anchor must carry the active class
        assert "filter-btn--active" in data, (
            "filter-btn--active must be present when /profile is loaded clean"
        )

    def test_this_month_button_active_with_this_month_params(self, logged_in_client):
        presets = _preset_dates_for_today()
        df, dt = presets["this_month"]
        response = logged_in_client.get(f"/profile?date_from={df}&date_to={dt}")
        assert b"filter-btn--active" in response.data

    def test_last_3_months_button_active_with_correct_params(self, logged_in_client):
        presets = _preset_dates_for_today()
        df, dt = presets["last_3_months"]
        response = logged_in_client.get(f"/profile?date_from={df}&date_to={dt}")
        assert b"filter-btn--active" in response.data

    def test_last_6_months_button_active_with_correct_params(self, logged_in_client):
        presets = _preset_dates_for_today()
        df, dt = presets["last_6_months"]
        response = logged_in_client.get(f"/profile?date_from={df}&date_to={dt}")
        assert b"filter-btn--active" in response.data


# ===========================================================================
# Unit tests for _compute_preset_dates (app.py helper)
# ===========================================================================

class TestComputePresetDates:
    """_compute_preset_dates(today) must return correct date windows."""

    def test_this_month_starts_on_first_of_month(self):
        today = datetime.date(2026, 5, 15)
        presets = _compute_preset_dates(today)
        date_from, _ = presets["this_month"]
        assert date_from == "2026-05-01", (
            "'This Month' date_from must be the first day of the current month"
        )

    def test_this_month_ends_on_last_day_of_month(self):
        today = datetime.date(2026, 5, 15)
        presets = _compute_preset_dates(today)
        _, date_to = presets["this_month"]
        assert date_to == "2026-05-31", (
            "'This Month' date_to must be the last day of the current month"
        )

    def test_this_month_february_non_leap_year(self):
        today = datetime.date(2025, 2, 10)
        presets = _compute_preset_dates(today)
        df, dt = presets["this_month"]
        assert df == "2025-02-01"
        assert dt == "2025-02-28", "February in non-leap year must end on the 28th"

    def test_this_month_february_leap_year(self):
        today = datetime.date(2024, 2, 14)
        presets = _compute_preset_dates(today)
        df, dt = presets["this_month"]
        assert df == "2024-02-01"
        assert dt == "2024-02-29", "February in a leap year must end on the 29th"

    def test_last_3_months_start_is_first_of_month_3_ago(self):
        today = datetime.date(2026, 5, 20)
        presets = _compute_preset_dates(today)
        date_from, _ = presets["last_3_months"]
        # 3 months back from May: March (month 3) → start on 2026-03-01
        assert date_from == "2026-03-01", (
            "'Last 3 Months' date_from must be the first of the month 3 months ago"
        )

    def test_last_3_months_end_is_last_day_of_current_month(self):
        today = datetime.date(2026, 5, 20)
        presets = _compute_preset_dates(today)
        _, date_to = presets["last_3_months"]
        assert date_to == "2026-05-31", (
            "'Last 3 Months' date_to must be the last day of the current month"
        )

    def test_last_3_months_crosses_year_boundary(self):
        today = datetime.date(2026, 1, 15)
        presets = _compute_preset_dates(today)
        date_from, _ = presets["last_3_months"]
        # 3 months back from January: month 1 - 2 = month -1 → wrap to November prev year
        assert date_from == "2025-11-01", (
            "'Last 3 Months' must correctly cross into the previous year"
        )

    def test_last_6_months_start_is_first_of_month_6_ago(self):
        today = datetime.date(2026, 8, 10)
        presets = _compute_preset_dates(today)
        date_from, _ = presets["last_6_months"]
        # 6 months back from August: month 8 - 5 = month 3 → 2026-03-01
        assert date_from == "2026-03-01", (
            "'Last 6 Months' date_from must be the first of the month 6 months ago"
        )

    def test_last_6_months_end_is_last_day_of_current_month(self):
        today = datetime.date(2026, 8, 10)
        presets = _compute_preset_dates(today)
        _, date_to = presets["last_6_months"]
        assert date_to == "2026-08-31", (
            "'Last 6 Months' date_to must be the last day of the current month"
        )

    def test_last_6_months_crosses_year_boundary(self):
        today = datetime.date(2026, 3, 5)
        presets = _compute_preset_dates(today)
        date_from, _ = presets["last_6_months"]
        # 6 months back from March: month 3 - 5 = month -2 → wrap to October prev year
        assert date_from == "2025-10-01", (
            "'Last 6 Months' must correctly cross into the previous year"
        )

    def test_all_preset_end_dates_equal(self):
        """this_month, last_3_months, last_6_months all share the same end date."""
        today = datetime.date(2026, 5, 20)
        presets = _compute_preset_dates(today)
        assert presets["this_month"][1] == presets["last_3_months"][1], (
            "this_month and last_3_months must share the same end date"
        )
        assert presets["this_month"][1] == presets["last_6_months"][1], (
            "this_month and last_6_months must share the same end date"
        )

    def test_preset_dates_are_iso_strings(self):
        today = datetime.date(2026, 5, 20)
        presets = _compute_preset_dates(today)
        for key, (df, dt) in presets.items():
            # Validate that both strings are parseable ISO dates
            try:
                datetime.date.fromisoformat(df)
                datetime.date.fromisoformat(dt)
            except ValueError:
                pytest.fail(
                    f"Preset '{key}' returned non-ISO date string: ({df!r}, {dt!r})"
                )

    def test_preset_start_before_end_for_all_presets(self):
        today = datetime.date(2026, 5, 20)
        presets = _compute_preset_dates(today)
        for key, (df, dt) in presets.items():
            assert df <= dt, (
                f"Preset '{key}' date_from ({df}) must be <= date_to ({dt})"
            )


# ===========================================================================
# DB helper tests — get_filtered_stats
# ===========================================================================

class TestGetFilteredStats:
    """get_filtered_stats(user_id, date_from, date_to) contract."""

    def test_returns_correct_total_for_range(self, app, test_user, insert_expense):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 40.00, "Food", "2026-04-10", "In range a")
        insert_expense(user_id, 60.00, "Bills", "2026-04-20", "In range b")
        with app.app_context():
            result = queries.get_summary_stats(user_id, "2026-04-01", "2026-04-30")
        assert result["total_spent"] == pytest.approx(100.00), (
            "total_spent must sum only the in-range expenses"
        )
        assert result["transaction_count"] == 2

    def test_excludes_expense_before_date_from(self, app, test_user, insert_expense):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 50.00, "Food", "2026-03-31", "Day before range")
        with app.app_context():
            result = queries.get_summary_stats(user_id, "2026-04-01", "2026-04-30")
        assert result["total_spent"] == 0
        assert result["transaction_count"] == 0

    def test_excludes_expense_after_date_to(self, app, test_user, insert_expense):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 50.00, "Food", "2026-05-01", "Day after range")
        with app.app_context():
            result = queries.get_summary_stats(user_id, "2026-04-01", "2026-04-30")
        assert result["total_spent"] == 0

    def test_returns_zero_struct_when_no_expenses_in_range(
        self, app, test_user
    ):
        user_id = _get_user_id(app, test_user["email"])
        with app.app_context():
            result = queries.get_summary_stats(user_id, "2026-04-01", "2026-04-30")
        assert result == {"total_spent": 0, "transaction_count": 0, "top_category": "—"}, (
            "Empty range must return the zero sentinel struct"
        )

    def test_top_category_reflects_range_only(self, app, test_user, insert_expense):
        user_id = _get_user_id(app, test_user["email"])
        # Out of range: large Shopping amount
        insert_expense(user_id, 500.00, "Shopping", "2026-03-01", "Big shop")
        # In range: Food dominates
        insert_expense(user_id, 100.00, "Food", "2026-04-05", "Food a")
        insert_expense(user_id, 80.00, "Food", "2026-04-10", "Food b")
        insert_expense(user_id, 20.00, "Bills", "2026-04-15", "Small bill")
        with app.app_context():
            result = queries.get_summary_stats(user_id, "2026-04-01", "2026-04-30")
        assert result["top_category"] == "Food", (
            "top_category must reflect only in-range expenses"
        )

    def test_none_params_return_all_expenses(self, app, test_user, insert_expense):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 10.00, "Food", "2010-01-01", "Very old")
        insert_expense(user_id, 20.00, "Bills", "2026-05-01", "Recent")
        with app.app_context():
            result = queries.get_summary_stats(user_id, None, None)
        assert result["transaction_count"] == 2, (
            "None params must behave like unfiltered — return all expenses"
        )
        assert result["total_spent"] == pytest.approx(30.00)

    def test_boundary_dates_inclusive(self, app, test_user, insert_expense):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 10.00, "Food", "2026-04-01", "On date_from")
        insert_expense(user_id, 20.00, "Food", "2026-04-30", "On date_to")
        with app.app_context():
            result = queries.get_summary_stats(user_id, "2026-04-01", "2026-04-30")
        assert result["transaction_count"] == 2, (
            "Expenses exactly on date_from and date_to must be included"
        )


# ===========================================================================
# DB helper tests — get_filtered_transactions
# ===========================================================================

class TestGetFilteredTransactions:
    """get_filtered_transactions(user_id, date_from, date_to) contract."""

    def test_returns_only_in_range_transactions(
        self, app, test_user, insert_expense
    ):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 10.00, "Food", "2026-04-15", "In range")
        insert_expense(user_id, 20.00, "Bills", "2026-03-01", "Out of range")
        with app.app_context():
            result = queries.get_recent_transactions(
                user_id, date_from="2026-04-01", date_to="2026-04-30"
            )
        assert len(result) == 1
        assert result[0]["description"] == "In range"

    def test_ordered_newest_first(self, app, test_user, insert_expense):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 10.00, "Food", "2026-04-01", "Earlier")
        insert_expense(user_id, 20.00, "Bills", "2026-04-25", "Later")
        with app.app_context():
            result = queries.get_recent_transactions(
                user_id, date_from="2026-04-01", date_to="2026-04-30"
            )
        assert result[0]["description"] == "Later", (
            "Transactions must be ordered newest-first"
        )
        assert result[1]["description"] == "Earlier"

    def test_date_formatted_as_mon_dd_yyyy(self, app, test_user, insert_expense):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 10.00, "Food", "2026-04-05", "Formatted date")
        with app.app_context():
            result = queries.get_recent_transactions(
                user_id, date_from="2026-04-01", date_to="2026-04-30"
            )
        assert result[0]["date"] == "Apr 05, 2026", (
            "Transaction date must be formatted as 'Mon DD, YYYY'"
        )

    def test_returns_empty_list_when_no_matches(self, app, test_user):
        user_id = _get_user_id(app, test_user["email"])
        with app.app_context():
            result = queries.get_recent_transactions(
                user_id, date_from="2026-04-01", date_to="2026-04-30"
            )
        assert result == [], "Empty range must return an empty list"

    def test_none_params_return_all_transactions(self, app, test_user, insert_expense):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 10.00, "Food", "2010-01-01", "Old tx")
        insert_expense(user_id, 20.00, "Bills", "2026-05-01", "New tx")
        with app.app_context():
            result = queries.get_recent_transactions(user_id, date_from=None, date_to=None)
        assert len(result) == 2, "None params must return all transactions"

    def test_amount_field_present(self, app, test_user, insert_expense):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 42.50, "Food", "2026-04-10", "Amount check")
        with app.app_context():
            result = queries.get_recent_transactions(
                user_id, date_from="2026-04-01", date_to="2026-04-30"
            )
        assert result[0]["amount"] == pytest.approx(42.50), (
            "Transaction record must include the amount field"
        )

    def test_category_field_present(self, app, test_user, insert_expense):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 10.00, "Transport", "2026-04-10", "Bus")
        with app.app_context():
            result = queries.get_recent_transactions(
                user_id, date_from="2026-04-01", date_to="2026-04-30"
            )
        assert result[0]["category"] == "Transport", (
            "Transaction record must include the category field"
        )


# ===========================================================================
# DB helper tests — get_filtered_breakdown
# ===========================================================================

class TestGetFilteredBreakdown:
    """get_filtered_breakdown(user_id, date_from, date_to) contract."""

    def test_returns_only_in_range_categories(
        self, app, test_user, insert_expense
    ):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 80.00, "Bills", "2026-04-01", "In range bill")
        insert_expense(user_id, 20.00, "Food", "2026-03-01", "Out of range food")
        with app.app_context():
            result = queries.get_category_breakdown(
                user_id, "2026-04-01", "2026-04-30"
            )
        assert len(result) == 1
        assert result[0]["name"] == "Bills"

    def test_pct_values_sum_to_100(self, app, test_user, insert_expense):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 30.00, "Food", "2026-04-01", "f")
        insert_expense(user_id, 20.00, "Transport", "2026-04-02", "t")
        insert_expense(user_id, 50.00, "Bills", "2026-04-03", "b")
        with app.app_context():
            result = queries.get_category_breakdown(
                user_id, "2026-04-01", "2026-04-30"
            )
        total_pct = sum(item["pct"] for item in result)
        assert total_pct == 100, (
            "Percentage values in category breakdown must sum to exactly 100"
        )

    def test_returns_empty_list_when_no_expenses_in_range(self, app, test_user):
        user_id = _get_user_id(app, test_user["email"])
        with app.app_context():
            result = queries.get_category_breakdown(
                user_id, "2026-04-01", "2026-04-30"
            )
        assert result == [], "Empty range must return an empty list"

    def test_none_params_return_full_breakdown(self, app, test_user, insert_expense):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 50.00, "Food", "2010-01-01", "Old food")
        insert_expense(user_id, 50.00, "Bills", "2026-05-01", "New bills")
        with app.app_context():
            result = queries.get_category_breakdown(user_id, None, None)
        assert len(result) == 2, "None params must return breakdown for all expenses"

    def test_breakdown_includes_amount_field(self, app, test_user, insert_expense):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 75.00, "Shopping", "2026-04-05", "Clothes")
        with app.app_context():
            result = queries.get_category_breakdown(
                user_id, "2026-04-01", "2026-04-30"
            )
        assert result[0]["amount"] == pytest.approx(75.00), (
            "Breakdown record must include the amount field"
        )

    def test_breakdown_ordered_by_amount_descending(
        self, app, test_user, insert_expense
    ):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 10.00, "Food", "2026-04-01", "Small")
        insert_expense(user_id, 90.00, "Bills", "2026-04-02", "Large")
        with app.app_context():
            result = queries.get_category_breakdown(
                user_id, "2026-04-01", "2026-04-30"
            )
        assert result[0]["name"] == "Bills", (
            "Category breakdown must be ordered highest-amount first"
        )

    def test_breakdown_aggregates_multiple_expenses_same_category(
        self, app, test_user, insert_expense
    ):
        user_id = _get_user_id(app, test_user["email"])
        insert_expense(user_id, 30.00, "Food", "2026-04-01", "Food a")
        insert_expense(user_id, 20.00, "Food", "2026-04-10", "Food b")
        with app.app_context():
            result = queries.get_category_breakdown(
                user_id, "2026-04-01", "2026-04-30"
            )
        assert len(result) == 1, "Multiple expenses in same category must be aggregated"
        assert result[0]["amount"] == pytest.approx(50.00)


# ===========================================================================
# Parametrized edge-case tests
# ===========================================================================

@pytest.mark.parametrize("date_from,date_to", [
    ("not-a-date", "2026-12-31"),
    ("2026-01-01", "not-a-date"),
    ("not-a-date", "not-a-date"),
    ("2026-13-01", "2026-12-31"),   # invalid month
    ("2026-00-01", "2026-12-31"),   # invalid month 0
    ("2026-04-31", "2026-12-31"),   # April has 30 days
    ("",           "2026-12-31"),   # empty string
    ("2026-01-01", ""),             # empty string
])
def test_malformed_date_param_returns_200(logged_in_client, date_from, date_to):
    """All malformed or empty date combinations must return 200 without crashing."""
    url = f"/profile?date_from={date_from}&date_to={date_to}"
    response = logged_in_client.get(url)
    assert response.status_code == 200, (
        f"Expected 200 for malformed params date_from={date_from!r}, date_to={date_to!r}"
    )


@pytest.mark.parametrize("date_from,date_to", [
    ("2026-05-01", "2026-04-01"),   # inverted by 1 month
    ("2026-12-31", "2026-01-01"),   # inverted by 1 year
    ("2027-01-01", "2026-12-31"),   # inverted by 1 day across year boundary
])
def test_inverted_range_shows_flash_message(logged_in_client, date_from, date_to):
    """All inverted date ranges must produce the flash error message."""
    url = f"/profile?date_from={date_from}&date_to={date_to}"
    response = logged_in_client.get(url)
    assert response.status_code == 200
    assert b"Start date must be before end date" in response.data, (
        f"Expected flash error for date_from={date_from}, date_to={date_to}"
    )
