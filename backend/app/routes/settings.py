"""Settings endpoints — provider config + auth token, all editable via UI."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import verify_token
from ..db import get_db
from ..providers import PROVIDER_PRESETS, ProviderError, build_provider
from ..schemas import ModelListOut, SettingsIn, SettingsOut, TestResultOut
from ..settings_store import get_settings, is_configured, mask_key, update_settings

# /api/settings is intentionally NOT behind verify_token for GET — otherwise a fresh
# install with no token couldn't bootstrap the UI. PUT/test/models DO require token
# (once one is set).
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


@router.post("/test", response_model=TestResultOut, dependencies=[Depends(verify_token)])
async def test_connection(payload: SettingsIn, db: Session = Depends(get_db)):
    """Test using the values from the request body, falling back to stored
    values when a field is omitted. Useful for 'test before save'."""
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
    """List available models. Uses request-body values if provided, else stored."""
    row = get_settings(db)
    provider_type = (payload.provider_type or row.provider_type or "openai").lower()
    base_url = payload.base_url or row.base_url
    api_key = payload.api_key if payload.api_key else row.api_key
    # model is unused for listing — pass placeholder
    try:
        provider = build_provider(provider_type, base_url, api_key, "placeholder")
        models = await provider.list_models()
        return ModelListOut(models=models)
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))
