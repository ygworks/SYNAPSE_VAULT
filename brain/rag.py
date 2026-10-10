import os
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
            f"[{r['code']}] {r['title']}\n"
            f"- 배우: {r['artist']}\n"
            f"- 스튜디오: {r['studio']} ({r['year']}년)\n"
            f"- 태그: {r['tags']}\n"
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
