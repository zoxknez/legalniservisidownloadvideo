from fastapi import APIRouter

router = APIRouter()


@router.get("/diagnose")
def transcoder_diagnose():
    from backend.services.transcoder import get_transcode_diagnostics

    return get_transcode_diagnostics()
