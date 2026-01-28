from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
import logging
import re
import json
from pydantic import BaseModel
from typing import List, Literal, Optional, Any, Dict
import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import get_db
from app.schemas.agent import AgentRequest, AgentResponse
from app.services.agent_runtime import run_agent
router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)


class Msg(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatReq(BaseModel):
    messages: List[Msg]
    stream: Optional[bool] = False
    temperature: Optional[float] = 0.2
    max_tokens: Optional[int] = 1024
    # 你想加 repo/time_window 等上下文也可以加在这里
    # repo: Optional[str] = None
    # time_window: Optional[int] = 90


def _build_endpoint() -> str:
    # 简化：仅拼接 /chat/completions，要求 BASE/CHAT URL 为应用根路径
    base = settings.MAXKB_CHAT_URL or settings.MAXKB_BASE_URL
    if not base:
        raise HTTPException(status_code=500, detail="MAXKB_BASE_URL or MAXKB_CHAT_URL not set")
    return base.rstrip("/") + "/chat/completions"


def _infer_model_from_base() -> Optional[str]:
    """从 MAXKB_BASE_URL 抽取 app_id 作为 model（若未显式配置）。"""
    if settings.MAXKB_MODEL:
        return settings.MAXKB_MODEL
    base = settings.MAXKB_BASE_URL or ""
    match = re.search(r"/api/([0-9a-fA-F-]{12,})", base)
    return match.group(1) if match else None


def _extract_piece(obj: Dict[str, Any]) -> str:
    """兼容 MaxKB/OpenAI 流式/非流式的内容提取。"""
    ch = (obj.get("choices") or [{}])[0]
    delta = ch.get("delta") or {}
    msg = ch.get("message") or {}
    piece = delta.get("content") or msg.get("content")

    if not piece:
        ans = ch.get("answer_list") or obj.get("answer") or obj.get("content")
        if isinstance(ans, str):
            piece = ans
        elif isinstance(ans, list):
            buf: List[str] = []
            for it in ans:
                if isinstance(it, str):
                    buf.append(it)
                elif isinstance(it, dict):
                    buf.append(it.get("content") or it.get("text") or "")
            piece = "".join(buf)

    return piece or ""


@router.post("/chat")
async def chat(req: ChatReq):
    api_key = settings.MAXKB_API_KEY
    if not api_key:
        raise HTTPException(status_code=500, detail="MAXKB_API_KEY not set")

    url = _build_endpoint()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: Dict[str, Any] = {
        "messages": [m.model_dump() for m in req.messages],
        # MaxKB 对 stream=false 有已知 bug，强制开启流式规避
        "stream": True,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
    }

    inferred_model = _infer_model_from_base()
    payload["model"] = inferred_model

    try:
        logger.info("MaxKB req url=%s payload_keys=%s", url, list(payload.keys()))
        content_parts: List[str] = []
        raw_lines: List[str] = []
        raw_json_text: str = ""
        first_id: Optional[str] = None

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise HTTPException(status_code=resp.status_code, detail=body.decode("utf-8", "ignore"))

                ct = (resp.headers.get("content-type") or "").lower()
                logger.info("MaxKB resp content-type=%s", ct)

                # 情况 1：直接返回 JSON（非 SSE）
                if "application/json" in ct:
                    raw_body = await resp.aread()
                    raw_text = raw_body.decode("utf-8", "ignore")
                    raw_json_text = raw_text
                    try:
                        obj = json.loads(raw_text)
                    except Exception:
                        raise HTTPException(status_code=500, detail=raw_text)

                    if isinstance(obj, dict) and "code" in obj and "message" in obj:
                        # MaxKB 业务错误包，直接抛出
                        raise HTTPException(status_code=502, detail=obj.get("message") or raw_text)

                    piece = _extract_piece(obj)
                    if piece:
                        content_parts.append(piece)
                    first_id = obj.get("id") or first_id
                    if not piece:
                        logger.warning("MaxKB json has no piece. raw=%s", raw_text[:500])
                else:
                    # 情况 2：SSE 或 chunked，每行尝试解析 JSON
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        s = line.strip()
                        if s.startswith("event:") or s.startswith(":"):
                            continue
                        if s.startswith("data:"):
                            s = s[5:].strip()
                        if not s:
                            continue
                        if s == "[DONE]":
                            break

                        raw_lines.append(s)
                        try:
                            obj = json.loads(s)
                        except Exception:
                            continue

                        if first_id is None:
                            first_id = obj.get("id")

                        piece = _extract_piece(obj)
                        if piece:
                            content_parts.append(piece)

        final_text = "".join(content_parts).strip()
        if not final_text:
            # 如果前面没解析到内容，尝试把原始行或原始 JSON 拼起来以便前端至少看到信息
            raw_hint = "".join(raw_lines).strip()
            if not raw_hint and raw_json_text:
                raw_hint = raw_json_text
            if raw_hint:
                final_text = raw_hint
        logger.info("MaxKB stream aggregated text len=%s", len(final_text))
        if not final_text and raw_lines:
            logger.warning("MaxKB got empty text. first_lines=%s", raw_lines[:3])

        return JSONResponse(
            {
                "id": first_id or "maxkb-local",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": final_text},
                    }
                ],
            }
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"MaxKB request failed: {e}")


@router.post("/run", response_model=AgentResponse)
async def run(req: AgentRequest, db: Session = Depends(get_db)) -> AgentResponse:
    """Two-phase agent call: Router -> Orchestrator -> Report."""
    return await run_agent(req, db)

