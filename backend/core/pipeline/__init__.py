"""
Unified media download pipeline (shared across services).

Stages:
  resolve → keys → fragments → decrypt → mux → done

Resume is stage-based (and segment-based when native URL lists are used).
Service engines stay thin: auth + license headers + TrackPolicy.
"""
from .checkpoint import (
    JobCheckpoint,
    cleanup_old_jobs,
    jobs_root,
    make_job_id,
    purge_job_segments,
)
from .models import PipelineResult, Stage, TrackPolicy
from .orchestrator import MediaPipeline
from .resolve import (
    StreamResolve,
    resolve_stream_ladder,
    sniffer_resolve,
    with_api_refresh_sniffer,
)
from .segments import download_segments_resumable, merge_segment_files

__all__ = [
    "JobCheckpoint",
    "MediaPipeline",
    "PipelineResult",
    "Stage",
    "StreamResolve",
    "TrackPolicy",
    "cleanup_old_jobs",
    "download_segments_resumable",
    "jobs_root",
    "make_job_id",
    "merge_segment_files",
    "purge_job_segments",
    "resolve_stream_ladder",
    "sniffer_resolve",
    "with_api_refresh_sniffer",
]
