"""
Phase 2 - Step 4b: semantic search ผ่าน Chroma สำหรับคำถามเชิงความหมาย

วิธีใช้:
    from rag.semantic_search import semantic_search
    results = semantic_search("สลิปที่เกี่ยวกับร้านกาแฟ", top_k=5)

ต้องรัน build_index.py ให้เสร็จก่อนอย่างน้อย 1 ครั้ง ไม่งั้น collection จะว่าง
"""

import chromadb
from sentence_transformers import SentenceTransformer

CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "slips"
EMBED_MODEL_NAME = "intfloat/multilingual-e5-small"

_model = None  # โหลดครั้งเดียวแล้ว cache ไว้ (โหลดโมเดลใหม่ทุกครั้งช้าโดยไม่จำเป็น)


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL_NAME)
    return _model


def semantic_search(question: str, top_k: int = 5):
    """
    คืน list ของ dict: [{"filename", "document", "distance", "metadata"}, ...]
    เรียงจากใกล้เคียงที่สุดก่อน (distance ยิ่งน้อยยิ่งใกล้เคียง)
    """
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    if collection.count() == 0:
        return []

    model = _get_model()
    # e5 ต้องมี prefix "query: " นำหน้าคำถามตอนค้นเสมอ (คนละ prefix กับตอน index เอกสาร)
    query_embedding = model.encode([f"query: {question}"], normalize_embeddings=True).tolist()

    result = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count()),
    )

    matches = []
    for i in range(len(result["ids"][0])):
        matches.append({
            "filename": result["ids"][0][i],
            "document": result["documents"][0][i],
            "distance": result["distances"][0][i],
            "metadata": result["metadatas"][0][i],
        })
    return matches


if __name__ == "__main__":
    import sys

    question = sys.argv[1] if len(sys.argv) > 1 else "สลิปที่เกี่ยวกับร้านกาแฟ"
    print(f"คำถาม: {question}\n")
    for m in semantic_search(question):
        print(f"[{m['distance']:.4f}] {m['filename']}: {m['document']}")
