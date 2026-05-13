"""Settings endpoints — provider config + auth token + logs + diagnostics."""

from __future__ import annotations

import json
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..auth import verify_token
from ..db import get_db
from ..log_buffer import (
    clear_ai_calls,
    clear_system_logs,
    get_ai_calls,
    get_system_logs,
    subscribe,
)
from ..providers import PROVIDER_PRESETS, ProviderError, build_provider
from ..schemas import (
    AiLogsOut,
    CurlIn,
    CurlOut,
    ModelListOut,
    SettingsIn,
    SettingsOut,
    SystemLogsOut,
    TestResultOut,
    TestResultV2,
)
from ..settings_store import get_settings, is_configured, mask_key, update_settings

# /api/settings is intentionally NOT behind verify_token for GET — otherwise a fresh
# install with no token couldn't bootstrap the UI. PUT/test/models DO require token.
router = APIRouter(prefix="/api/settings", tags=["settings"])


def _to_out(row) -> SettingsOut:
    return SettingsOut(
        provider_type=row.provider_type or "openai",
        base_url=row.base_url or "",
        api_key_set=bool(row.api_key),
        api_key_preview=mask_key(row.api_key or ""),
        model=row.model or "",
        auth_token_set=bool(row.auth_token),
        configured=is_configured(row),
    )


@router.get("", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db)):
    return _to_out(get_settings(db))


@router.get("/presets")
def list_presets():
    return {"presets": PROVIDER_PRESETS}


@router.put("", response_model=SettingsOut, dependencies=[Depends(verify_token)])
def write_settings(payload: SettingsIn, db: Session = Depends(get_db)):
    row = update_settings(
        db,
        provider_type=payload.provider_type,
        base_url=payload.base_url,
        api_key=payload.api_key,
        model=payload.model,
        auth_token=payload.auth_token,
    )
    return _to_out(row)


# ─── Test connection (classified) ─────────────────────────────────────────


def _classify(provider_err_msg: str) -> tuple[str, str]:
    """Map ProviderError text (HTTP status + body snippet) to (category, detail)."""
    msg = provider_err_msg.strip()
    if msg.startswith("401"):
        return "auth", "API key 无效或被吊销。检查 key 是否正确、是否过期。"
    if msg.startswith("403"):
        return "auth", "API key 权限不足。可能是没开通此模型的访问。"
    if msg.startswith("404"):
        return "not_found", "模型不存在或路径错。检查 model 名字和 base_url。"
    if msg.startswith("429"):
        return "rate_limit", "请求频率超限或余额不足。"
    if msg.startswith("5"):
        return "upstream", "上游服务异常。可能是 provider 自己故障，过一会再试。"
    return "unknown", msg[:200] if msg else "未知错误"


@router.post("/test", response_model=TestResultV2, dependencies=[Depends(verify_token)])
async def test_connection(payload: SettingsIn, db: Session = Depends(get_db)):
    row = get_settings(db)
    provider_type = (payload.provider_type or row.provider_type or "openai").lower()
    base_url = payload.base_url or row.base_url
    api_key = payload.api_key if payload.api_key else row.api_key
    model = payload.model or row.model

    t0 = time.monotonic()
    try:
        provider = build_provider(provider_type, base_url, api_key, model)
        text = await provider.chat("Reply with just: OK", "ping", max_tokens=10)
        ms = round((time.monotonic() - t0) * 1000, 1)
        return TestResultV2(
            ok=True,
            category="ok",
            detail=f"模型 {model} 回复: {text[:80]}",
            echo=text[:120],
            ms=ms,
        )
    except ProviderError as e:
        msg = str(e)
        category, detail = _classify(msg)
        return TestResultV2(
            ok=False,
            category=category,
            detail=detail,
            raw=msg[:400],
            ms=round((time.monotonic() - t0) * 1000, 1),
        )
    except httpx.ConnectTimeout:
        return TestResultV2(
            ok=False,
            category="timeout",
            detail="连接超时（>10s）。可能是 base_url 不可达，或 VPS 出口被限速。",
            ms=round((time.monotonic() - t0) * 1000, 1),
        )
    except httpx.ConnectError as e:
        if "Name or service not known" in str(e) or "nodename nor servname" in str(e):
            return TestResultV2(
                ok=False,
                category="dns",
                detail=f"DNS 解析失败 — 域名找不到。检查 base_url 拼写。\n{e}",
                raw=str(e)[:400],
                ms=round((time.monotonic() - t0) * 1000, 1),
            )
        return TestResultV2(
            ok=False,
            category="connect",
            detail=f"无法连接到目标。检查 base_url 域名 / 端口；本地服务先确认 systemctl 是 active。\n{e}",
            raw=str(e)[:400],
            ms=round((time.monotonic() - t0) * 1000, 1),
        )
    except httpx.TimeoutException:
        return TestResultV2(
            ok=False,
            category="timeout",
            detail="请求超时（>10s）。AI provider 可能很慢，或网络中断。",
            ms=round((time.monotonic() - t0) * 1000, 1),
        )
    except Exception as e:
        return TestResultV2(
            ok=False,
            category="unknown",
            detail=f"{type(e).__name__}: {e}",
            raw=str(e)[:400],
            ms=round((time.monotonic() - t0) * 1000, 1),
        )


@router.post("/test/legacy", response_model=TestResultOut, dependencies=[Depends(verify_token)])
async def test_connection_legacy(payload: SettingsIn, db: Session = Depends(get_db)):
    row = get_settings(db)
    provider_type = (payload.provider_type or row.provider_type or "openai").lower()
    base_url = payload.base_url or row.base_url
    api_key = payload.api_key if payload.api_key else row.api_key
    model = payload.model or row.model
    try:
        provider = build_provider(provider_type, base_url, api_key, model)
        result = await provider.test()
        return TestResultOut(ok=True, echo=result.get("echo", ""))
    except ProviderError as e:
        return TestResultOut(ok=False, error=str(e))
    except Exception as e:
        return TestResultOut(ok=False, error=f"{type(e).__name__}: {e}")


@router.post("/models", response_model=ModelListOut, dependencies=[Depends(verify_token)])
async def list_models(payload: SettingsIn, db: Session = Depends(get_db)):
    row = get_settings(db)
    provider_type = (payload.provider_type or row.provider_type or "openai").lower()
    base_url = payload.base_url or row.base_url
    api_key = payload.api_key if payload.api_key else row.api_key
    try:
        provider = build_provider(provider_type, base_url, api_key, "placeholder")
        models = await provider.list_models()
        return ModelListOut(models=models)
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ─── curl preview ─────────────────────────────────────────────────────────


def _mask_key(key: str) -> str:
    if len(key) <= 12:
        return "***"
    return key[:6] + "*" * 8 + key[-4:]


def _curl_openai(base_url: str, key: str, model: str) -> str:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "ping"}]})
    return (
        f"curl -X POST '{base_url.rstrip('/')}/chat/completions' \\\n"
        f"  -H 'Authorization: Bearer {key}' \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -d '{body}'"
    )


def _curl_anthropic(base_url: str, key: str, model: str) -> str:
    body = json.dumps({
        "model": model,
        "max_tokens": 16,
        "messages": [{"role": "user", "content": "ping"}],
    })
    return (
        f"curl -X POST '{base_url.rstrip('/')}/v1/messages' \\\n"
        f"  -H 'x-api-key: {key}' \\\n"
        f"  -H 'anthropic-version: 2023-06-01' \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -d '{body}'"
    )


def _curl_google(base_url: str, key: str, model: str) -> str:
    body = json.dumps({"contents": [{"parts": [{"text": "ping"}]}]})
    return (
        f"curl -X POST '{base_url.rstrip('/')}/v1beta/models/{model}:generateContent?key={key}' \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -d '{body}'"
    )


@router.post("/curl", response_model=CurlOut, dependencies=[Depends(verify_token)])
def generate_curl(payload: CurlIn, db: Session = Depends(get_db)):
    row = get_settings(db)
    raw_key = payload.api_key or row.api_key or ""
    key = raw_key if payload.reveal_key else _mask_key(raw_key)
    base_url = payload.base_url or row.base_url
    model = payload.model or row.model
    ptype = (payload.provider_type or row.provider_type or "openai").lower()
    if ptype == "anthropic":
        cmd = _curl_anthropic(base_url, key, model)
    elif ptype == "google":
        cmd = _curl_google(base_url, key, model)
    else:
        cmd = _curl_openai(base_url, key, model)
    return CurlOut(command=cmd)


# ─── Logs ─────────────────────────────────────────────────────────────────


@router.get("/logs/ai", response_model=AiLogsOut, dependencies=[Depends(verify_token)])
def ai_logs(
    kind: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=50),
):
    return AiLogsOut(items=get_ai_calls(limit=limit, kind=kind))


@router.post("/logs/ai/clear", dependencies=[Depends(verify_token)])
def ai_logs_clear():
    clear_ai_calls()
    return {"ok": True}


@router.get("/logs/system", response_model=SystemLogsOut, dependencies=[Depends(verify_token)])
def system_logs(
    event_prefix: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=200),
):
    return SystemLogsOut(items=get_system_logs(limit=limit, event_prefix=event_prefix))


@router.post("/logs/system/clear", dependencies=[Depends(verify_token)])
def system_logs_clear():
    clear_system_logs()
    return {"ok": True}


@router.post("/logs/system/stream", dependencies=[Depends(verify_token)])
async def stream_system_logs():
    """SSE stream of system logs as they happen. Replays current buffer first."""

    async def gen():
        async for rec in subscribe():
            yield f"data: {json.dumps(rec, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
