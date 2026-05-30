from fastapi import APIRouter
from pydantic import BaseModel

from backend.queue_manager import queue_manager

router = APIRouter()


class ScheduledRecordingRequest(BaseModel):
    channel_name: str
    title: str
    start_time: str
    duration: int


@router.post("/schedule")
async def schedule_recording(req: ScheduledRecordingRequest):
    task_id = await queue_manager.add_scheduled_recording(
        channel_name=req.channel_name,
        title=req.title,
        start_time=req.start_time,
        duration=req.duration,
    )
    return {"success": True, "task_id": task_id}


@router.get("/list")
def list_scheduled():
    return queue_manager.list_scheduled_recordings()


class CancelScheduledRequest(BaseModel):
    id: str


@router.post("/cancel")
async def cancel_scheduled(req: CancelScheduledRequest):
    await queue_manager.cancel_scheduled_recording(req.id)
    return {"success": True}
