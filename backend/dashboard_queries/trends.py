"""
backend/dashboard_queries/trends.py

Amount breakdowns over time / by source app, for the Dashboard's charts.

Split out 18 Sep 2026 from the original single-file `dashboard_queries.py`
(see `dashboard_queries.py.bak_20260918` for the pre-split version used for
the regression check) — no logic changed, only moved.
"""

from typing import Any

from ._shared import _connect, _date_filter_clause


def get_totals_by_app(
    user_id: str,
    doc_type: str = "bank_slip",
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """
    Sum of amounts grouped by source_app, complete-amount rows only.
    Uses source_app (K+/Make/Dime/TrueMoney/unknown) instead of bank_name --
    bank_name is free OCR text and frequently captures status lines or app
    names instead of a real bank identifier on slips with no clean label
    (see known_limitations.md), so grouping by it produces meaningless,
    fragmented buckets. source_app comes from guess_source_app()'s controlled
    vocabulary and is reliable for this purpose.
    """
    date_clause, date_params = _date_filter_clause(start_date, end_date)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT source_app, COUNT(*) AS count, SUM(amount) AS total_amount
            FROM slips
            WHERE doc_type = ? AND amount_issue IS NULL AND user_id = ?{date_clause}
            GROUP BY source_app
            ORDER BY total_amount DESC
            """,
            (doc_type, user_id, *date_params),
        ).fetchall()
        return [dict(r) for r in rows]


def get_trend_by_month(
    user_id: str,
    doc_type: str = "bank_slip",
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """
    Doc count + total amount per (year, month), for a time-series chart.
    doc_type is required (not optional/'all') to avoid silently mixing THB
    bank transfers with THB stock purchase amounts in one trend line --
    pass doc_type='stock_confirmation' explicitly for a separate stock chart.

    income_total / expense_total (10 ต.ค. 2026): the chart used total_amount,
    which adds income and expense into one meaningless number (Aug 2026 for
    Ronova = 31,250 = income 30,000 + expense 1,250). Split the same way as
    get_income_expense_summary(): untyped rows and amount_issue rows go into
    neither bucket. count/total_amount are kept unchanged.
    """
    date_clause, date_params = _date_filter_clause(start_date, end_date)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT datetime_year AS year, datetime_month AS month,
                   COUNT(*) AS count,
                   SUM(amount) AS total_amount,
                   COALESCE(SUM(CASE WHEN transaction_type = 'income' AND amount_issue IS NULL
                                     THEN amount END), 0) AS income_total,
                   COALESCE(SUM(CASE WHEN transaction_type = 'expense' AND amount_issue IS NULL
                                     THEN amount END), 0) AS expense_total
            FROM slips
            WHERE doc_type = ? AND datetime_issue IS NULL AND user_id = ?
              AND datetime_year IS NOT NULL AND datetime_month IS NOT NULL{date_clause}
            GROUP BY datetime_year, datetime_month
            ORDER BY datetime_year, datetime_month
            """,
            (doc_type, user_id, *date_params),
        ).fetchall()
        return [dict(r) for r in rows]
