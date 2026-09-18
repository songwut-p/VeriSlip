"""
Dashboard query layer for VeriSlip.

Split 18 Sep 2026 from a single `dashboard_queries.py` file into this
package, one submodule per dashboard section (see `_shared.py` for the
DB connection/issue/date-filter helpers all of them share). This
`__init__.py` re-exports every public function so existing imports like
`from backend.dashboard_queries import get_summary_stats, ...` keep working
unchanged -- external code should always import from here, never reach
into a submodule directly.

The pre-split version is kept as `dashboard_queries.py.bak_20260918` for
the regression check comparing old vs. new output.

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

NOTE (23 Aug 2026): this package is READ-ONLY by design (_connect() opens
SQLite in mode=ro). Do NOT add write operations (INSERT/UPDATE/DELETE) here --
writes belong in db/import_slips.py, which already owns the read-write
connection used by save_record(). Keeping writes in one place avoids two
modules disagreeing about schema/locking behavior.
"""

from .accounts import get_activity_by_account, list_known_accounts
from .recent import get_recent_slips, search_slips
from .stock import get_stock_summary
from .summary import get_income_expense_summary, get_summary_stats
from .trends import get_totals_by_app, get_trend_by_month

__all__ = [
    "get_summary_stats",
    "get_income_expense_summary",
    "get_totals_by_app",
    "get_trend_by_month",
    "get_recent_slips",
    "search_slips",
    "get_activity_by_account",
    "list_known_accounts",
    "get_stock_summary",
]
