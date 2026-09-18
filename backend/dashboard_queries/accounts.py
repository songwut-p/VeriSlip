"""
backend/dashboard_queries/accounts.py

Account-number-keyed views: activity for one account, and the distinct set
of known accounts. (Not currently wired into main.py's imports, but kept
here as prepared-but-unused backend support.)

Split out 18 Sep 2026 from the original single-file `dashboard_queries.py`
(see `dashboard_queries.py.bak_20260918` for the pre-split version used for
the regression check) — no logic changed, only moved.
"""

from typing import Any

from ._shared import _connect


def get_activity_by_account(account_number: str, user_id: str) -> dict[str, Any]:
    """
    All bank_slip activity where the given account appears as sender OR recipient.
    Keyed by account number (not name) -- stock rows have no account columns
    populated so they never show up here, which is correct (Item 1/2 scope).

    user_id filter here matters MORE than on the filename-keyed queries above:
    without it, one user could discover another user's counterparties (who they
    sent money to / received money from) purely via account number, without ever
    knowing the other user's filenames.
    """
    with _connect() as conn:
        sent = conn.execute(
            """
            SELECT id, filename, datetime_year, datetime_month, datetime_day,
                   amount, recipient_name, recipient_account
            FROM slips
            WHERE doc_type = 'bank_slip' AND sender_account = ? AND user_id = ?
            ORDER BY datetime_year DESC, datetime_month DESC, datetime_day DESC
            """,
            (account_number, user_id),
        ).fetchall()

        received = conn.execute(
            """
            SELECT id, filename, datetime_year, datetime_month, datetime_day,
                   amount, sender_name, sender_account
            FROM slips
            WHERE doc_type = 'bank_slip' AND recipient_account = ? AND user_id = ?
            ORDER BY datetime_year DESC, datetime_month DESC, datetime_day DESC
            """,
            (account_number, user_id),
        ).fetchall()

        return {
            "account_number": account_number,
            "sent": [dict(r) for r in sent],
            "received": [dict(r) for r in received],
        }


def list_known_accounts(user_id: str) -> list[dict[str, Any]]:
    """
    Distinct account numbers seen as sender or recipient (bank_slip only), with a
    best-effort display name -- used to populate a person-picker without trusting
    name-matching across rows.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT sender_account AS account_number, sender_name AS display_name
            FROM slips WHERE doc_type = 'bank_slip' AND sender_account IS NOT NULL AND user_id = ?
            UNION
            SELECT recipient_account AS account_number, recipient_name AS display_name
            FROM slips WHERE doc_type = 'bank_slip' AND recipient_account IS NOT NULL AND user_id = ?
            """,
            (user_id, user_id),
        ).fetchall()
        seen: dict[str, str | None] = {}
        for r in rows:
            acc = r["account_number"]
            if acc not in seen or seen[acc] is None:
                seen[acc] = r["display_name"]
        return [{"account_number": k, "display_name": v} for k, v in seen.items()]
