from fastapi import APIRouter
from pydantic import BaseModel
from brain.llm import answer_with_rag, query_local_llm
from brain.rag import build_rag_index

router = APIRouter(prefix="/api/brain", tags=["Brain & RAG"])

class ChatPayload(BaseModel):
    query: str

class BrewPayload(BaseModel):
    title_a: str
    content_a: str
    title_b: str
    content_b: str

@router.post("/chat")
async def chat_with_vault(payload: ChatPayload):
    """소장작 RAG 기반 지능형 취향 문답"""
    return answer_with_rag(payload.query)

@router.post("/brew")
async def brew_insight(payload: BrewPayload):
    """캔버스에서 두 작품/배우 노드를 연결했을 때의 취향 융합 브루잉"""
    prompt = f"""사용자가 다음 두 AV 작품을 '연결선'으로 이었습니다.
[작품 A]: {payload.title_a}
내용: {payload.content_a}

[작품 B]: {payload.title_b}
내용: {payload.content_b}

이 두 작품의 장르와 연출적 시너지, 공통된 페티시즘/취향 포인트, 그리고 연계 감상 팁을 3줄로 명확하게 브리핑하십시오."""
    insight = query_local_llm(prompt)
    return {"insight": insight}

@router.post("/build-index")
async def trigger_rag_rebuild():
    """DB에 새로 들어온 작품들을 CPU FAISS 벡터 인덱스로 재색인"""
    total = build_rag_index()
    return {"status": "ok", "indexed_count": total}
