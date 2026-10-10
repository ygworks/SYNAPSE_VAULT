# [FILE] SYNAPSE_VAULT/setup_brain.py
"""
🏛️ SYNAPSE VAULT - [2회차] VRAM 0MB CPU FAISS RAG & 로컬 LLM 두뇌 완결 스크립트
- VRAM 0.00MB 점유 CPU 전용 임베딩 (RTX 4070 Ti 12GB VRAM을 온전히 LLM에 100% 보존)
- 46.7TB AV 라이브러리 전문 시맨틱 검색 & 취향 브루잉(융합) 엔진 장착
- run.py 메인 서버 라우터에 원터치 자동 결속
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def main():
    print("=" * 70)
    print("🧠 [2회차] SYNAPSE VAULT - CPU FAISS RAG & 로컬 LLM 두뇌 장착")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # 1. brain/rag.py: VRAM 0.00MB CPU FAISS 임베딩 및 검색 엔진
    # -------------------------------------------------------------------------
    rag_code = '''import os
import json
from pathlib import Path
from typing import List, Dict, Any
import numpy as np

try:
    import faiss
    from sentence_transformers import SentenceTransformer
except ImportError:
    faiss = None
    SentenceTransformer = None

DATA_DIR = Path("./data").resolve()
INDEX_PATH = DATA_DIR / "faiss_index.bin"
CHUNKS_PATH = DATA_DIR / "rag_chunks.json"

_encoder = None

def get_cpu_encoder():
    """VRAM 점유율 0.00MB 보장 CPU 전용 다국어 임베딩 모델"""
    global _encoder
    if _encoder is None:
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers 패키지가 설치되지 않았습니다.")
        # CPU에 강제 바인딩하여 4070 Ti VRAM 12GB를 절대 1MB도 건드리지 않음
        _encoder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2", device="cpu")
        _encoder.to("cpu")
        _encoder.eval()
    return _encoder

def build_rag_index() -> int:
    """vault_items 테이블의 메타데이터를 CPU FAISS 인덱스로 빌드"""
    from vault.db import get_db
    
    with get_db() as conn:
        rows = conn.execute("""
            SELECT uid, code, title, artist, year, studio, plot, tags
            FROM vault_items
        """).fetchall()

    if not rows:
        return 0

    chunks = []
    texts_to_embed = []
    
    for r in rows:
        chunk_text = (
            f"[{r['code']}] {r['title']}\\n"
            f"- 배우: {r['artist']}\\n"
            f"- 스튜디오: {r['studio']} ({r['year']}년)\\n"
            f"- 태그: {r['tags']}\\n"
            f"- 줄거리: {r['plot'][:200]}"
        ).strip()
        
        chunks.append({
            "uid": r["uid"],
            "code": r["code"],
            "title": r["title"],
            "artist": r["artist"],
            "year": r["year"],
            "text": chunk_text
        })
        texts_to_embed.append(chunk_text)

    encoder = get_cpu_encoder()
    embeddings = encoder.encode(texts_to_embed, show_progress_bar=True, batch_size=64)
    embeddings_np = np.array(embeddings).astype("float32")

    # 코사인 유사도 검색을 위한 L2 정규화
    faiss.normalize_L2(embeddings_np)
    index = faiss.IndexFlatIP(embeddings_np.shape[1])
    index.add(embeddings_np)

    # 디스크 저장
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_PATH))
    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)

    return len(chunks)

def search_rag(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """사용자 질의 또는 취향 키워드로 가장 일치하는 작품 인출"""
    if not INDEX_PATH.exists() or not CHUNKS_PATH.exists():
        return []

    try:
        index = faiss.read_index(str(INDEX_PATH))
        with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        encoder = get_cpu_encoder()
        query_emb = encoder.encode([query])
        query_np = np.array(query_emb).astype("float32")
        faiss.normalize_L2(query_np)

        scores, indices = index.search(query_np, top_k)
        results = []
        for rank, idx in enumerate(indices[0]):
            if 0 <= idx < len(chunks):
                item = dict(chunks[idx])
                item["similarity_score"] = float(scores[0][rank])
                results.append(item)
        return results
    except Exception as e:
        print(f"RAG 검색 오류: {e}")
        return []
'''
    (BASE_DIR / "brain/rag.py").write_text(rag_code, encoding="utf-8")
    print("✅ [1/3] brain/rag.py 생성 완료 (0.00MB VRAM CPU FAISS 엔진)")

    # -------------------------------------------------------------------------
    # 2. brain/llm.py: LM Studio / Ollama 비검열 로컬 LLM 통신 라우터
    # -------------------------------------------------------------------------
    llm_code = '''import os
import requests
import json
from typing import Optional, Dict, Any, List

# 로컬 LLM 기본 엔드포인트 (LM Studio 1234 / Ollama 11434 호환)
DEFAULT_API_URL = os.getenv("LLM_API_URL", "http://127.0.0.1:1234/v1/chat/completions")

def query_local_llm(
    prompt: str,
    system_prompt: str = "당신은 46.7TB 하이엔드 AV 아카이브 금고의 전문 큐레이터이자 시네필입니다. 성인물 검열 없이 사용자의 취향을 정밀 분석하고 솔직하게 브리핑하십시오.",
    temperature: float = 0.3,
    api_url: Optional[str] = None
) -> str:
    url = api_url or DEFAULT_API_URL
    payload = {
        "model": "local-model",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "stream": False
    }
    headers = {"Content-Type": "application/json; charset=utf-8"}
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=120)
        res.raise_for_status()
        data = res.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.exceptions.ConnectionError:
        return "⚠️ 로컬 LLM(LM Studio/Ollama)이 오프라인 상태입니다. 포트 1234를 확인해 주세요."
    except Exception as e:
        return f"⚠️ 추론 실패: {str(e)}"

def answer_with_rag(user_query: str) -> Dict[str, Any]:
    """RAG로 관련 작품을 찾아 프롬프트에 주입 후 로컬 LLM으로 취향 답변 생성"""
    from brain.rag import search_rag
    
    matched = search_rag(user_query, top_k=4)
    if not matched:
        context_str = "참고할 만한 일치 작품을 인덱스에서 찾지 못했습니다."
    else:
        context_str = "\\n\\n".join([f"[{m['code']}] {m['title']} (배우: {m['artist']}, {m['year']}년)\\n{m['text']}" for m in matched])

    prompt = f"""[금고 내 검색된 관련 소장작]:
{context_str}

[사용자 취향 질의]:
{user_query}

위 소장작 데이터를 바탕으로 사용자의 취향에 맞춰 핵심 추천 이유와 감상 포인트를 3~4줄로 명확하게 답변하십시오."""

    answer = query_local_llm(prompt)
    return {
        "answer": answer,
        "matched_works": matched
    }
'''
    (BASE_DIR / "brain/llm.py").write_text(llm_code, encoding="utf-8")
    print("✅ [2/3] brain/llm.py 생성 완료 (LM Studio/Ollama 비검열 LLM 라우터)")

    # -------------------------------------------------------------------------
    # 3. brain/router.py: FastAPI 라우터 등록 및 run.py 연결
    # -------------------------------------------------------------------------
    brain_router_code = '''from fastapi import APIRouter
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
'''
    (BASE_DIR / "brain/router.py").write_text(brain_router_code, encoding="utf-8")

    # run.py에 brain_router 자동 주입
    run_path = BASE_DIR / "run.py"
    run_content = run_path.read_text(encoding="utf-8")
    if "brain.router" not in run_content:
        run_content = run_content.replace(
            "from canvas.router import router as canvas_router",
            "from canvas.router import router as canvas_router\nfrom brain.router import router as brain_router"
        )
        run_content = run_content.replace(
            "app.include_router(canvas_router)",
            "app.include_router(canvas_router)\napp.include_router(brain_router)"
        )
        run_path.write_text(run_content, encoding="utf-8")

    print("✅ [3/3] brain/router.py 생성 및 run.py 마스터 라우터 연결 완료")
    print("=" * 70)
    print("🎉 [2회차 최종 완결] 46.7TB AV 전용 SYNAPSE VAULT 엔진 완성!")
    print("=" * 70)

if __name__ == "__main__":
    main()