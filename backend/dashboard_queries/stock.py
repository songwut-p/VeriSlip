"""
backend/dashboard_queries/stock.py

Per-symbol rollup for stock_confirmation docs.

Split out 18 Sep 2026 from the original single-file `dashboard_queries.py`
(see `dashboard_queries.py.bak_20260918` for the pre-split version used for
the regression check) — no logic changed, only moved.
"""

import json
from typing import Any

from ._shared import _connect


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
