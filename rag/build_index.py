"""
Phase 2 - Step 4a: สร้าง/อัปเดต Chroma vector index จาก slips.db
สำหรับคำถามเชิงความหมาย (semantic) ที่ pattern/SQL จัดการไม่ได้ เช่น "สลิปที่เกี่ยวกับร้านกาแฟ"

ติดตั้งก่อน: pip install chromadb sentence-transformers

รัน: python build_index.py
     (เรียกซ้ำได้ปลอดภัย — upsert ตาม filename เหมือน import_slips.py)

หมายเหตุ: ใช้ multilingual-e5-small ซึ่ง "ต้อง" ใส่ prefix "passage: " นำหน้าข้อความตอน index
และ "query: " นำหน้าคำถามตอนค้นเสมอ (ทำอัตโนมัติในไฟล์นี้และ semantic_search.py แล้ว
ไม่ต้องจำเอง — แต่ถ้าจะเขียนเพิ่มเติมเองต้องระวังจุดนี้ ไม่งั้นคุณภาพผลลัพธ์จะตกฮวบ)
"""

import json
import sqlite3

import chromadb
from sentence_transformers import SentenceTransformer

DB_PATH = "db/slips.db"
CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "slips"
EMBED_MODEL_NAME = "intfloat/multilingual-e5-small"


def build_document_text(row: dict) -> str:
    """
    รวม field ที่มีความหมายเชิงเนื้อหาของสลิปเป็นข้อความเดียว สำหรับ embed
    (ไม่รวม field เชิงเทคนิคเช่น transaction_id/account number ที่ไม่ช่วย semantic search)
    """
    if row.get("doc_type") == "stock_confirmation":
        # field แบบ bank slip (recipient_name, sender_name, bank_name) เป็น null
        # สำหรับแถว stock -- symbol/exchange/order_type อยู่ใน raw_json เท่านั้น
        # เพราะไม่มีคอลัมน์แยก (ดู extract_record())
        extra = {}
        if row.get("raw_json"):
            try:
                extra = json.loads(row["raw_json"])
            except (TypeError, ValueError):
                extra = {}
        parts = []
        if extra.get("symbol"):
            parts.append(f"ซื้อหุ้น {extra['symbol']}")
        if extra.get("exchange"):
            parts.append(f"ตลาด {extra['exchange']}")
        if row.get("amount") is not None:
            parts.append(f"จำนวน {row['amount']:.2f} บาท")
        if extra.get("order_type"):
            parts.append(f"ประเภทคำสั่ง {extra['order_type']}")
        if row.get("source_app") and row["source_app"] != "unknown":
            parts.append(f"ผ่านแอป {row['source_app']}")
        return " ".join(parts) if parts else row.get("filename", "")

    parts = []
    if row.get("recipient_name"):
        parts.append(f"โอนเงินให้ {row['recipient_name']}")
    if row.get("sender_name"):
        parts.append(f"จาก {row['sender_name']}")
    if row.get("amount") is not None:
        parts.append(f"จำนวน {row['amount']:.2f} บาท")
    if row.get("source_app") and row["source_app"] != "unknown":
        parts.append(f"ผ่านแอป {row['source_app']}")
    if row.get("bank_name"):
        parts.append(f"({row['bank_name']})")
    if row.get("datetime_raw"):
        parts.append(f"วันที่ {row['datetime_raw']}")

    return " ".join(parts) if parts else row.get("filename", "")


def load_rows():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM slips")]
    conn.close()
    return rows


_model = None  # lazy-loaded singleton — โหลดโมเดลครั้งเดียวตอน request แรก ไม่ใช่ทุกครั้งที่เรียก


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL_NAME)
    return _model


def index_row(row: dict, chroma_path: str = CHROMA_PATH) -> str:
    """
    Embed + upsert record เดียวเข้า Chroma (ใช้ตอน save ทีละสลิปจาก API
    แทนที่จะ re-embed ทั้ง collection ทุกครั้งเหมือน main() ที่ออกแบบมาสำหรับ batch)
    คืนค่า document text ที่ index ไป (เผื่อ debug/แสดงผล)
    """
    model = _get_model()
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    doc_text = build_document_text(row)
    embedding = model.encode([f"passage: {doc_text}"], normalize_embeddings=True).tolist()

    # id ต้องผูกกับ user_id ด้วย ไม่ใช่ filename เฉยๆ — คนละ user อัปโหลดไฟล์ชื่อซ้ำกันได้
    # (เช่น IMG_001.jpg) ถ้าใช้ filename ตรงๆ เป็น id, embedding ของอีกคนจะถูกทับ
    user_id = row.get("user_id") or "default"
    chroma_id = f"{user_id}:{row['filename']}"

    collection.upsert(
        ids=[chroma_id],
        embeddings=embedding,
        documents=[doc_text],
        metadatas=[{
            "filename": row["filename"],
            "user_id": user_id,
            "amount": row.get("amount") or 0.0,
            "source_app": row.get("source_app") or "unknown",
            "datetime_year": row.get("datetime_year") or 0,
            "datetime_month": row.get("datetime_month") or 0,
            "recipient_name": row.get("recipient_name") or "",
            "sender_name": row.get("sender_name") or "",
        }],
    )
    return doc_text


def delete_row(filename: str, user_id: str, chroma_path: str = CHROMA_PATH) -> None:
    """ลบ embedding ของสลิป 1 ไฟล์ออกจาก Chroma -- เพิ่ม 23 Aug 2026 คู่กับ
    db/import_slips.py's delete_slip() ต้องเรียกคู่กันเสมอตอนลบสลิป ไม่งั้น
    สลิปที่ลบไปแล้วจากฝั่ง SQLite อาจยังโผล่มาในคำตอบหน้า "Ask" (semantic
    search) ได้อยู่ เพราะ Chroma ไม่รู้ว่าแถวนั้นถูกลบไปแล้ว

    id ต้องประกอบด้วย user_id เหมือนตอน index_row() เป๊ะ ("{user_id}:{filename}")
    ไม่งั้นจะลบผิด id หรือลบไม่ออกเลย เงียบๆ (Chroma .delete() ไม่ error ถ้า id
    ไม่มีอยู่จริง จึงต้องระวังเรื่อง id format ให้ตรงกันเป็นพิเศษ)"""
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_or_create_collection(COLLECTION_NAME)
    chroma_id = f"{user_id}:{filename}"
    collection.delete(ids=[chroma_id])


def main():
    rows = load_rows()
    if not rows:
        print(f"ไม่พบข้อมูลใน {DB_PATH} — รัน import_slips.py ก่อน")
        return

    print(f"โหลด embedding model ({EMBED_MODEL_NAME})... (ครั้งแรกจะดาวน์โหลดโมเดล อาจใช้เวลาสักครู่)")
    model = SentenceTransformer(EMBED_MODEL_NAME)

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    ids, documents, metadatas = [], [], []
    for row in rows:
        doc_text = build_document_text(row)
        user_id = row.get("user_id") or "default"
        ids.append(f"{user_id}:{row['filename']}")
        documents.append(doc_text)
        # metadata เก็บไว้ใช้ตอนแสดงผล/กรองเพิ่มเติม — Chroma metadata ต้องเป็น str/int/float/bool เท่านั้น
        metadatas.append({
            "filename": row["filename"],
            "user_id": user_id,
            "amount": row.get("amount") or 0.0,
            "source_app": row.get("source_app") or "unknown",
            "datetime_year": row.get("datetime_year") or 0,
            "datetime_month": row.get("datetime_month") or 0,
            "recipient_name": row.get("recipient_name") or "",
            "sender_name": row.get("sender_name") or "",
        })

    # e5 ต้องมี prefix "passage: " นำหน้าเอกสารที่จะเก็บ (คนละ prefix กับตอน query)
    embeddings = model.encode([f"passage: {d}" for d in documents], normalize_embeddings=True).tolist()

    collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

    print(f"Index เสร็จ: {len(ids)} รายการ เก็บไว้ที่ {CHROMA_PATH}/ (collection: {COLLECTION_NAME})")
    print("\nตัวอย่างข้อความที่ index (3 รายการแรก):")
    for doc_id, doc in list(zip(ids, documents))[:3]:
        print(f"  [{doc_id}] {doc}")


if __name__ == "__main__":
    main()