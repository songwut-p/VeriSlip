"""
backend/dashboard_queries/recent.py

Recent-docs table view and free-text search across all of a user's slips.

Split out 18 Sep 2026 from the original single-file `dashboard_queries.py`
(see `dashboard_queries.py.bak_20260918` for the pre-split version used for
the regression check) — no logic changed, only moved.
"""

from typing import Any

from ._shared import _connect, _has_issue_case_sql


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
