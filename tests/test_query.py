from rag.query_router import answer_question
from rag.llm_sql import call_ollama_for_sql
from rag.semantic_search import semantic_search

# คำถามเชิงตัวเลข -> pattern
print(answer_question("เดือนนี้โอนไปทั้งหมดเท่าไหร่"))

# คำถามเชิงความหมาย มีคำตอบจริง -> semantic
print(answer_question("มีสลิปที่เกี่ยวกับแท็กซี่ไหม", semantic_search_fn=semantic_search))

# คำถามเชิงความหมาย ไม่มีคำตอบจริง -> no_confident_match
print(answer_question("มีสลิปที่เกี่ยวกับร้านกาแฟไหม", semantic_search_fn=semantic_search))

# ครบทุกทาง
print(answer_question(
    "มีสลิปกี่ใบที่เกี่ยวกับร้านกาแฟ",
    llm_call_fn=call_ollama_for_sql,
    semantic_search_fn=semantic_search,
))