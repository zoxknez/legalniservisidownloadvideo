from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.queue_manager import queue_manager
from backend.services.hrti_adapter import HrtiAdapter
from ._schemas import LoginRequest

router = APIRouter()


@router.post("/login")
def hrti_login(req: LoginRequest):
    res = HrtiAdapter.save_credentials(req.email, req.password)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.get("/categories")
def hrti_categories():
    return HrtiAdapter.list_categories()


@router.get("/category-items")
def hrti_category_items(category: str, page: int = 1):
    return HrtiAdapter.get_category_items(category, page)


@router.get("/search")
def hrti_search(query: str):
    return HrtiAdapter.search_items(query)


@router.get("/series/{series_uuid}")
def hrti_series_episodes(series_uuid: str):
    return HrtiAdapter.get_series_episodes(series_uuid)


class HrtiDownloadRequest(BaseModel):
    ref_id: str
    title: str = ""
    workers: int = 16


@router.post("/download")
async def hrti_download(req: HrtiDownloadRequest):
    cmd = HrtiAdapter.make_download_cmd(req.ref_id, req.title, req.workers)
    title = f"HRTi: {req.title or req.ref_id}"
    task_id = await queue_manager.add_download("hrti", title, cmd)
    return {"success": True, "task_id": task_id}
