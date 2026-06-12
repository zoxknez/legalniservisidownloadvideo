import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path as ApiPath, Query
from pydantic import BaseModel, Field

from backend.queue_manager import queue_manager
from backend.services.hrti_adapter import HrtiAdapter
from ._schemas import LoginRequest

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_HRTI_REF_LEN = 512
MAX_HRTI_TITLE_LEN = 240
MAX_HRTI_BATCH_ITEMS = 500
MAX_HRTI_QUERY_LEN = 120
MAX_HRTI_CATEGORY_LEN = 128


def _raise_if_failed(result, status_code: int = 503):
    if isinstance(result, dict) and result.get("success") is False:
        raise HTTPException(status_code=status_code, detail=result.get("error") or "HRTi zahtev nije uspeo.")
    return result


def _require_hrti_auth() -> None:
    auth = HrtiAdapter.get_auth_status()
    if not auth.get("authenticated"):
        raise HTTPException(
            status_code=401,
            detail="Niste prijavljeni na HRTi. Unesite kredencijale u Postavkama.",
        )


@router.post("/login")
def hrti_login(req: LoginRequest):
    res = HrtiAdapter.save_credentials(req.email, req.password)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.get("/status")
def hrti_status():
    return HrtiAdapter.get_auth_status()


@router.get("/categories")
def hrti_categories():
    _require_hrti_auth()
    try:
        return HrtiAdapter.list_categories()
    except Exception as e:
        logger.exception("Failed to list HRTi categories")
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/category-items")
def hrti_category_items(
    category: str = Query(..., min_length=1, max_length=MAX_HRTI_CATEGORY_LEN),
    page: int = Query(1, ge=1, le=1000),
):
    _require_hrti_auth()
    if not category.strip():
        raise HTTPException(status_code=400, detail="Kategorija je obavezna.")
    try:
        return _raise_if_failed(HrtiAdapter.get_category_items(category.strip(), page))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch HRTi category items")
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/search")
def hrti_search(query: str = Query(..., min_length=1, max_length=MAX_HRTI_QUERY_LEN)):
    _require_hrti_auth()
    if not query.strip():
        raise HTTPException(status_code=400, detail="Upit za pretragu je obavezan.")
    try:
        return _raise_if_failed(HrtiAdapter.search_items(query.strip()))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to search HRTi")
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/preview")
def hrti_preview(ref_id: str = Query(..., min_length=1, max_length=MAX_HRTI_REF_LEN)):
    _require_hrti_auth()
    if not ref_id.strip():
        raise HTTPException(status_code=400, detail="Reference ID je obavezan.")
    try:
        return _raise_if_failed(HrtiAdapter.preview_ref(ref_id.strip()), status_code=404)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to preview HRTi ref")
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/series/{series_uuid}")
def hrti_series_episodes(
    series_uuid: str = ApiPath(..., min_length=1, max_length=MAX_HRTI_REF_LEN),
):
    _require_hrti_auth()
    if not series_uuid.strip():
        raise HTTPException(status_code=400, detail="Series UUID je obavezan.")
    try:
        return _raise_if_failed(HrtiAdapter.get_series_episodes(series_uuid.strip()), status_code=404)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch HRTi series episodes")
        raise HTTPException(status_code=503, detail=str(e))


class HrtiDownloadItem(BaseModel):
    ref_id: str = Field(min_length=1, max_length=MAX_HRTI_REF_LEN)
    title: str = Field(default="", max_length=MAX_HRTI_TITLE_LEN)


class HrtiDownloadRequest(BaseModel):
    ref_id: str = Field(default="", max_length=MAX_HRTI_REF_LEN)
    title: str = Field(default="", max_length=MAX_HRTI_TITLE_LEN)
    workers: int = Field(default=16, ge=1, le=64)
    items: Optional[List[HrtiDownloadItem]] = Field(default=None, max_length=MAX_HRTI_BATCH_ITEMS)


@router.post("/download")
async def hrti_download(req: HrtiDownloadRequest):
    _require_hrti_auth()
    if req.items:
        items = [
            {"ref_id": item.ref_id.strip(), "title": item.title.strip()}
            for item in req.items
            if item.ref_id.strip()
        ]
        if not items:
            raise HTTPException(status_code=400, detail="Lista HRTi epizoda je prazna.")
        cmd = HrtiAdapter.make_download_batch_cmd(items, req.workers)
        title = f"HRTi: {len(items)} epizoda"
        task_id = await queue_manager.add_download("hrti", title, cmd)
        return {"success": True, "queued": len(items), "task_id": task_id}

    if not req.ref_id.strip():
        raise HTTPException(status_code=400, detail="HRTi ref_id je obavezan.")

    cmd = HrtiAdapter.make_download_cmd(req.ref_id.strip(), req.title.strip(), req.workers)
    title = f"HRTi: {req.title.strip() or req.ref_id.strip()}"
    task_id = await queue_manager.add_download("hrti", title, cmd)
    return {"success": True, "task_id": task_id}
