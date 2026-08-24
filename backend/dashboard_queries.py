"""
Dashboard query layer for ai-document-assistant.

Verified against the real slips.db schema (19 Aug 2026):
  id, filename, bank_name, amount, currency,
  sender_name, sender_account, recipient_name, recipient_account,
  transaction_id, datetime_raw, datetime_year, datetime_month, datetime_day,
  bank_name_issue, amount_issue, sender_name_issue, sender_account_issue,
  recipient_name_issue, recipient_account_issue, transaction_id_issue, datetime_issue,
  source_app, raw_json, created_at, updated_at, doc_type

Design principles (agreed with Songwut, 19 Aug 2026):
- Query SQLite directly with hand-written SQL (deterministic, not via query_router/LLM).
- One function per dashboard section — isolated scope.
- Group/key by account number (sender_account / recipient_account), NOT by name —
  names come from OCR and have documented failure modes (missing labels, garbled
  icons, app-specific formats); account numbers are more stable even when masked.
- Completeness ("has_issue") is checked per doc_type, using only the columns that
  are meaningful for that type. Bank-slip-shaped issue columns
  (sender_name_issue, recipient_name_issue, etc.) are hardcoded to the string
  "not applicable for stock_confirmation" on stock rows (see db/import_slips.py
  extract_record()) — treating that as a real issue would flag every stock row
  as broken. Only amount_issue / transaction_id_issue / datetime_issue apply to
  stock rows.
- No single query mixes bank_slip and stock_confirmation amounts unless the
  caller explicitly asks for combined totals (mirrors the same bug we just fixed
  in rag/query_router.py's /ask intents).

NOTE (23 Aug 2026): this module is READ-ONLY by design (_connect() opens SQLite
in mode=ro). Do NOT add write operations (INSERT/UPDATE/DELETE) here -- writes
belong in db/import_slips.py, which already owns the read-write connection used
by save_record(). Keeping writes in one place avoids two modules disagreeing
about schema/locking behavior.
"""

import json
import sqlite3
from pathlib import Path
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
    "transaction_id_issue",
    "datetime_issue",
]

# issue columns that apply to stock_confirmation rows
# (bank_name_issue/sender_*/recipient_* are hardcoded "not applicable..." on
# these rows -- not a real signal, so they're excluded here)
STOCK_ISSUE_COLS = [
    "amount_issue",
    "transaction_id_issue",
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


def get_summary_stats(user_id: str) -> dict[str, Any]:
    """Overall counts: total docs, complete vs has-issue (doc_type-aware), by doc_type."""
    with _connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM slips WHERE user_id = ?", (user_id,)
        ).fetchone()["n"]

        by_doc_type = conn.execute(
            "SELECT doc_type, COUNT(*) AS n FROM slips WHERE user_id = ? GROUP BY doc_type",
            (user_id,),
        ).fetchall()

        has_issue_case = _has_issue_case_sql()
        issue_counts = conn.execute(
            f"SELECT doc_type, SUM({has_issue_case}) AS n_issue, COUNT(*) AS n_total "
            f"FROM slips WHERE user_id = ? GROUP BY doc_type",
            (user_id,),
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


def get_totals_by_app(user_id: str, doc_type: str = "bank_slip") -> list[dict[str, Any]]:
    """
    Sum of amounts grouped by source_app, complete-amount rows only.
    Uses source_app (K+/Make/Dime/TrueMoney/unknown) instead of bank_name --
    bank_name is free OCR text and frequently captures status lines or app
    names instead of a real bank identifier on slips with no clean label
    (see known_limitations.md), so grouping by it produces meaningless,
    fragmented buckets. source_app comes from guess_source_app()'s controlled
    vocabulary and is reliable for this purpose.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT source_app, COUNT(*) AS count, SUM(amount) AS total_amount
            FROM slips
            WHERE doc_type = ? AND amount_issue IS NULL AND user_id = ?
            GROUP BY source_app
            ORDER BY total_amount DESC
            """,
            (doc_type, user_id),
        ).fetchall()
        return [dict(r) for r in rows]


def get_trend_by_month(user_id: str, doc_type: str = "bank_slip") -> list[dict[str, Any]]:
    """
    Doc count + total amount per (year, month), for a time-series chart.
    doc_type is required (not optional/'all') to avoid silently mixing THB
    bank transfers with THB stock purchase amounts in one trend line --
    pass doc_type='stock_confirmation' explicitly for a separate stock chart.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT datetime_year AS year, datetime_month AS month,
                   COUNT(*) AS count,
                   SUM(amount) AS total_amount
            FROM slips
            WHERE doc_type = ? AND datetime_issue IS NULL AND user_id = ?
              AND datetime_year IS NOT NULL AND datetime_month IS NOT NULL
            GROUP BY datetime_year, datetime_month
            ORDER BY datetime_year, datetime_month
            """,
            (doc_type, user_id),
        ).fetchall()
        return [dict(r) for r in rows]


def get_recent_slips(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Most recent docs (both types) with extraction status, for a table view."""
    has_issue_case = _has_issue_case_sql()
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, doc_type, filename, image_path, datetime_year, datetime_month, datetime_day,
                   amount, currency, bank_name, sender_name, recipient_name, source_app,
                   ({has_issue_case}) AS has_issue
            FROM slips
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def search_slips(user_id: str, query: str, limit: int = 20) -> list[dict[str, Any]]:
    """
    ค้นหาสลิปจาก filename/ชื่อผู้โอน/ชื่อผู้รับ/ชื่อธนาคาร-แอป -- ค้นทั่วทั้ง DB
    ของ user นี้ (ไม่จำกัดแค่รายการล่าสุด) เพิ่ม 23 Aug 2026 ตามคำขอ: ไฟล์ที่
    อัปโหลดผิดแล้วอยากลบทิ้ง อาจหลุดออกจากรายการ "ล่าสุด" (ตอนนี้ตั้ง limit
    ไว้แค่ 5) ไปแล้วก็ได้ ถ้า search แค่ในรายการที่แสดงอยู่จะหาไม่เจอ

    ใช้ LIKE แบบ case-insensitive (SQLite ทำ case-insensitive ให้อัตโนมัติ
    สำหรับ ASCII แต่ไม่ครอบคลุมภาษาไทย -- ยอมรับข้อจำกัดนี้ไปก่อน เพราะ user
    ส่วนใหญ่มักจำได้แค่บางส่วนของชื่อไฟล์/ชื่อคนอยู่แล้ว ไม่ต้องพิมพ์ให้ตรง
    case เป๊ะ)
    """
    has_issue_case = _has_issue_case_sql()
    like_pattern = f"%{query}%"
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, doc_type, filename, image_path, datetime_year, datetime_month, datetime_day,
                   amount, currency, bank_name, sender_name, recipient_name, source_app,
                   ({has_issue_case}) AS has_issue
            FROM slips
            WHERE user_id = ?
              AND (
                    filename LIKE ? OR
                    sender_name LIKE ? OR
                    recipient_name LIKE ? OR
                    bank_name LIKE ? OR
                    source_app LIKE ?
                  )
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, like_pattern, like_pattern, like_pattern, like_pattern, like_pattern, limit),
        ).fetchall()
        return [dict(r) for r in rows]


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


def get_stock_summary(user_id: str) -> list[dict[str, Any]]:
    """
    Per-symbol rollup for stock_confirmation rows. symbol/exchange/order_type
    have no dedicated columns (see extract_record()) -- they live in raw_json,
    so this pulls it out in Python rather than SQL.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT filename, amount, currency, transaction_id, source_app, raw_json
            FROM slips
            WHERE doc_type = 'stock_confirmation' AND user_id = ?
            """,
            (user_id,),
        ).fetchall()

    by_symbol: dict[str, dict[str, Any]] = {}
    for r in rows:
        extra = {}
        if r["raw_json"]:
            try:
                extra = json.loads(r["raw_json"])
            except (TypeError, ValueError):
                extra = {}
        symbol = extra.get("symbol") or "unknown"
        entry = by_symbol.setdefault(symbol, {"symbol": symbol, "count": 0, "total_amount": 0.0})
        entry["count"] += 1
        entry["total_amount"] += r["amount"] or 0.0

    return sorted(by_symbol.values(), key=lambda e: e["total_amount"], reverse=True)
