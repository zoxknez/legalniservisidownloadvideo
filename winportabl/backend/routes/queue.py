from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.queue_manager import queue_manager

router = APIRouter()


class TaskIdRequest(BaseModel):
    id: str


@router.post("/cancel")
async def cancel_download(req: TaskIdRequest):
    await queue_manager.cancel_download(req.id)
    return {"success": True}


@router.post("/retry")
async def retry_download(req: TaskIdRequest):
    success = await queue_manager.retry_download(req.id)
    if not success:
        raise HTTPException(status_code=400, detail="Zadatak se ne može pokrenuti ponovo.")
    return {"success": True}


@router.post("/clear")
async def clear_completed():
    await queue_manager.clear_completed()
    return {"success": True}


@router.get("")
async def get_queue(
    limit: Optional[int] = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
):
    all_items = list(queue_manager.items.values())
    if status:
        valid = set(status.split(","))
        all_items = [i for i in all_items if i.status in valid]

    total = len(all_items)
    sliced = all_items[offset:offset + limit] if limit else all_items[offset:]
    return {
        "items": [item.to_dict() for item in sliced],
        "total": total,
        "offset": offset,
        "limit": limit,
    }
