"""
backend/dashboard_queries/summary.py

Overall dashboard summary numbers: total/complete/has-issue counts and the
income vs. expense net card.

Split out 18 Sep 2026 from the original single-file `dashboard_queries.py`
(see `dashboard_queries.py.bak_20260918` for the pre-split version used for
the regression check) — no logic changed, only moved.
"""

from typing import Any

from ._shared import _connect, _date_filter_clause, _has_issue_case_sql


def get_summary_stats(
    user_id: str,
    doc_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """
    Overall counts: total docs, complete vs has-issue (doc_type-aware), by doc_type.

    doc_type is optional (default None = all doc types combined, unchanged from
    the original behavior) -- Dashboard Item 2 (31 Aug 2026) passes doc_type=
    "bank_slip" explicitly to scope the summary cards to bank_slip only, since
    stock_confirmation was dropped from the Dashboard display entirely (backend
    support for stock_confirmation itself is untouched).
    """
    doc_clause = ""
    doc_params: list[Any] = []
    if doc_type:
        doc_clause = " AND doc_type = ?"
        doc_params = [doc_type]
    date_clause, date_params = _date_filter_clause(start_date, end_date)

    with _connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS n FROM slips WHERE user_id = ?{doc_clause}{date_clause}",
            (user_id, *doc_params, *date_params),
        ).fetchone()["n"]

        by_doc_type = conn.execute(
            f"SELECT doc_type, COUNT(*) AS n FROM slips WHERE user_id = ?{doc_clause}{date_clause} "
            f"GROUP BY doc_type",
            (user_id, *doc_params, *date_params),
        ).fetchall()

        has_issue_case = _has_issue_case_sql()
        issue_counts = conn.execute(
            f"SELECT doc_type, SUM({has_issue_case}) AS n_issue, COUNT(*) AS n_total "
            f"FROM slips WHERE user_id = ?{doc_clause}{date_clause} GROUP BY doc_type",
            (user_id, *doc_params, *date_params),
        ).fetchall()

        total_issue = sum(r["n_issue"] or 0 for r in issue_counts)

        return {
            "total": total,
            "complete": total - total_issue,
            "has_issue": total_issue,
            "by_doc_type": {r["doc_type"]: r["n"] for r in by_doc_type},
            "issues_by_doc_type": {
                r["doc_type"]: {"has_issue": r["n_issue"] or 0, "total": r["n_total"]}
                for r in issue_counts
            },
        }


def get_income_expense_summary(
    user_id: str,
    doc_type: str = "bank_slip",
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """
    Sum of amounts split by transaction_type ("income"/"expense"), for the
    Dashboard's net-amount card (13 ก.ย. 2026).

    Rows with transaction_type IS NULL (rows saved before this feature
    existed, or never classified for any other reason) are silently
    excluded from both sums -- there is no way to know their direction, so
    they don't contribute to net/income/expense rather than being guessed
    into either bucket (same "don't guess" principle as _date_filter_clause
    dropping undated rows).

    amount_issue IS NULL mirrors get_totals_by_app()'s exclusion of rows
    with a flagged amount extraction issue -- a garbled amount shouldn't
    silently skew the net total.
    """
    date_clause, date_params = _date_filter_clause(start_date, end_date)
    with _connect() as conn:
        row = conn.execute(
            f"""
            SELECT
                COALESCE(SUM(CASE WHEN transaction_type = 'income' THEN amount ELSE 0 END), 0) AS income,
                COALESCE(SUM(CASE WHEN transaction_type = 'expense' THEN amount ELSE 0 END), 0) AS expense
            FROM slips
            WHERE doc_type = ? AND amount_issue IS NULL AND user_id = ?{date_clause}
            """,
            (doc_type, user_id, *date_params),
        ).fetchone()
        income = row["income"] or 0
        expense = row["expense"] or 0
        return {"income": income, "expense": expense, "net": income - expense}
