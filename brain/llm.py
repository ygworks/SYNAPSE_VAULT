import os
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
        context_str = "\n\n".join([f"[{m['code']}] {m['title']} (배우: {m['artist']}, {m['year']}년)\n{m['text']}" for m in matched])

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
