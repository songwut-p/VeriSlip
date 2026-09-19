"""
backend/dashboard_queries/_shared.py

Internal helpers shared by every submodule in this package: the read-only DB
connection, the issue-detection SQL fragment, and the date-range filter
builder. Nothing here is part of the public API — submodules import from
this file, but external code should only ever import from
`backend.dashboard_queries` (the package's `__init__.py` re-exports
everything public).

Split out 18 Sep 2026 from the original single-file `dashboard_queries.py`
(see `dashboard_queries.py.bak_20260918` for the pre-split version used for
the regression check) — no logic changed, only moved.
"""

import sqlite3
from typing import Any

DB_PATH = "db/slips.db"

# issue columns that only mean something for bank_slip rows
BANK_SLIP_ISSUE_COLS = [
    "bank_name_issue",
    "amount_issue",
    "sender_name_issue",
    "sender_account_issue",
    "recipient_name_issue",
    "recipient_account_issue",
    "datetime_issue",
]

# issue columns that apply to stock_confirmation rows
# (bank_name_issue/sender_*/recipient_* are hardcoded "not applicable..." on
# these rows -- not a real signal, so they're excluded here)
STOCK_ISSUE_COLS = [
    "amount_issue",
    "datetime_issue",
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _has_issue_case_sql() -> str:
    """
    SQL CASE expression: 1 if the row has a genuine extraction issue, 0 if not --
    branches on doc_type so stock rows aren't penalized for bank-slip-only columns.
    """
    bank_clause = " OR ".join(f"{c} IS NOT NULL" for c in BANK_SLIP_ISSUE_COLS)
    stock_clause = " OR ".join(f"{c} IS NOT NULL" for c in STOCK_ISSUE_COLS)
    return f"""
        CASE
            WHEN doc_type = 'stock_confirmation' THEN CASE WHEN ({stock_clause}) THEN 1 ELSE 0 END
            ELSE CASE WHEN ({bank_clause}) THEN 1 ELSE 0 END
        END
    """


def _date_filter_clause(start_date: str | None, end_date: str | None) -> tuple[str, list[Any]]:
    """
    Build a SQL fragment (leading " AND ...", or "" if no filter requested) plus
    its bound params, for filtering rows by datetime_year/month/day against an
    inclusive [start_date, end_date] range of ISO date strings.

    Added 31 Aug 2026 for the Dashboard Item 2 redesign's date-range filter.
    When start_date/end_date are both None (the default -- no filter applied),
    returns ("", []) so every existing call site that doesn't pass these
    arguments keeps its exact previous behavior unchanged.
    """
    if not start_date and not end_date:
        return "", []
    date_expr = "printf('%04d-%02d-%02d', datetime_year, datetime_month, datetime_day)"
    clauses = ["datetime_year IS NOT NULL", "datetime_month IS NOT NULL", "datetime_day IS NOT NULL"]
    params: list[Any] = []
    if start_date:
        clauses.append(f"{date_expr} >= ?")
        params.append(start_date)
    if end_date:
        clauses.append(f"{date_expr} <= ?")
        params.append(end_date)
    return " AND " + " AND ".join(clauses), params
