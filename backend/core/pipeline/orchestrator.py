"""
MediaPipeline — stage-resumable DASH/CENC orchestration.

Service engines provide keys + fragment download callbacks; this module
owns checkpoint transitions, decrypt, fix, and mux.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .checkpoint import JobCheckpoint
from .decrypt import decrypt_cenc
from .models import PipelineResult, Stage, TrackPolicy
from .mux import fix_container, mux_av

logger = logging.getLogger("pipeline.orchestrator")

# acquire_keys() -> list of kid:key
KeysFn = Callable[[], List[str]]
# download_fragments(continuedl: bool) -> (enc_video, enc_audio)
FragmentsFn = Callable[[bool], Tuple[Path, Path]]
# optional custom finalize after decrypt/fix (e.g. multi-audio + subs)
FinalizeFn = Callable[[Path, Path, List[str], JobCheckpoint], Path]


class MediaPipeline:
    """
    Resumable post-auth pipeline:

      keys → fragments → decrypt → mux → done
    """

    def __init__(
        self,
        *,
        service: str,
        mpd_url: str,
        title: str,
        output_dir: Path | str,
        bins: Dict[str, str],
        license_url: str = "",
        policy: Optional[TrackPolicy] = None,
        job_id: Optional[str] = None,
        resume: bool = True,
        min_fragment_bytes: int = 50_000,
    ):
        self.service = (service or "").strip().lower() or "unknown"
        self.mpd_url = mpd_url
        self.license_url = license_url or ""
        self.title = title
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.bins = bins
        self.policy = policy or TrackPolicy()
        self.resume = resume
        self.min_fragment_bytes = min_fragment_bytes

        if resume:
            self.checkpoint = JobCheckpoint.open(
                service=self.service,
                mpd_url=mpd_url,
                title=title,
                license_url=license_url,
                job_id=job_id,
            )
        else:
            jid = job_id or "noreuse"
            self.checkpoint = JobCheckpoint(jid)
            self.checkpoint.data.update(
                {
                    "service": self.service,
                    "mpd_url": mpd_url,
                    "license_url": license_url,
                    "title": title,
                }
            )

    def _load_or_download_fragments(
        self,
        cp: JobCheckpoint,
        download_fragments: FragmentsFn,
    ) -> Tuple[Path, Path]:
        if self.resume and cp.can_resume_fragments():
            enc_video = Path(cp.data["enc_video"])
            enc_audio = Path(cp.data["enc_audio"] or cp.data["enc_video"])
            if not enc_audio.exists():
                enc_audio = enc_video
            logger.info("[pipeline] fragments from checkpoint")
            print("[pipeline] Fragmenti iz checkpointa (preskačem download)")
            return enc_video, enc_audio

        continuedl = bool(self.resume and cp.stage == Stage.FRAGMENTS)
        print("[pipeline] Preuzimam enkriptovane fragmente…")
        enc_video, enc_audio = download_fragments(continuedl)
        enc_video = Path(enc_video)
        enc_audio = Path(enc_audio)
        if enc_video.stat().st_size < self.min_fragment_bytes:
            raise RuntimeError(f"Video fragment too small: {enc_video}")
        cp.set_fragments(enc_video, enc_audio)
        return enc_video, enc_audio

    def _load_or_acquire_keys(
        self,
        cp: JobCheckpoint,
        acquire_keys: KeysFn,
        skip_decrypt: bool,
    ) -> List[str]:
        if skip_decrypt:
            return []
        if self.resume and cp.keys and cp.stage.reached(Stage.KEYS):
            keys = cp.keys
            logger.info("[pipeline] keys from checkpoint (%s)", len(keys))
            print(f"[pipeline] Ključevi iz checkpointa ({len(keys)})")
            return keys
        print("[pipeline] Dobavljam Widevine ključeve…")
        keys = acquire_keys()
        if not keys:
            raise RuntimeError("No CONTENT keys returned")
        cp.set_keys(keys)
        print(f"[pipeline] Gotovih {len(keys)} ključ(eva)")
        return keys

    def run(
        self,
        *,
        acquire_keys: KeysFn,
        download_fragments: FragmentsFn,
        output_name: str,
        skip_decrypt: bool = False,
        keys_after_fragments: bool = False,
        finalize: Optional[FinalizeFn] = None,
        fix_before_finalize: bool = True,
    ) -> PipelineResult:
        """
        Execute or resume the pipeline.

        skip_decrypt: non-DRM path (fragments already clear).
        keys_after_fragments: download fragments before license (PSSH from init).
        finalize: custom post-decrypt step (multi-audio, subs, naming); skips default mux.
        """
        cp = self.checkpoint
        resumed = cp.stage != Stage.INIT and self.resume
        if resumed:
            logger.info(
                "[pipeline] RESUME service=%s job=%s stage=%s",
                self.service,
                cp.job_id,
                cp.stage.value,
            )
            print(f"[pipeline] Nastavljam job {cp.job_id} od stage={cp.stage.value}")
        else:
            logger.info("[pipeline] START service=%s job=%s", self.service, cp.job_id)

        # Already finished successfully — skip full re-download
        if self.resume and cp.stage == Stage.DONE:
            out = Path(cp.data.get("output_path") or "")
            if out.is_file() and out.stat().st_size > 50_000:
                logger.info("[pipeline] output already exists: %s", out.name)
                print(f"[pipeline] Već gotovo: {out.name}")
                return PipelineResult(
                    output_path=out,
                    stage=Stage.DONE,
                    job_id=cp.job_id,
                    resumed=True,
                    keys_count=len(cp.keys),
                    meta={"service": self.service, "title": self.title, "skipped": True},
                )

        keys: List[str] = []
        if keys_after_fragments:
            enc_video, enc_audio = self._load_or_download_fragments(cp, download_fragments)
            keys = self._load_or_acquire_keys(cp, acquire_keys, skip_decrypt)
        else:
            keys = self._load_or_acquire_keys(cp, acquire_keys, skip_decrypt)
            enc_video, enc_audio = self._load_or_download_fragments(cp, download_fragments)

        # ── DECRYPT ─────────────────────────────────────────────────────────
        if skip_decrypt:
            dec_video, dec_audio = enc_video, enc_audio
            cp.set_decrypted(dec_video, dec_audio)
        elif self.resume and cp.can_resume_decrypt():
            dec_video = Path(cp.data["dec_video"])
            dec_audio = Path(cp.data["dec_audio"] or cp.data["dec_video"])
            if not dec_audio.exists():
                dec_audio = dec_video
            logger.info("[pipeline] decrypted files from checkpoint")
            print("[pipeline] Dekriptovani fajlovi iz checkpointa")
        else:
            mp4decrypt = self.bins.get("mp4decrypt") or "mp4decrypt"
            print("[pipeline] Dekripcija videa…")
            dec_video = decrypt_cenc(enc_video, keys, mp4decrypt)
            if enc_audio.resolve() != enc_video.resolve() and enc_audio.exists():
                print("[pipeline] Dekripcija audia…")
                dec_audio = decrypt_cenc(enc_audio, keys, mp4decrypt)
            else:
                dec_audio = dec_video
            cp.set_decrypted(dec_video, dec_audio)

        # ── FIX (+ default MUX or custom finalize) ──────────────────────────
        ffmpeg = self.bins.get("ffmpeg")
        mkvmerge = self.bins.get("mkvmerge")
        if fix_before_finalize:
            dec_video = fix_container(Path(dec_video), ffmpeg)
            if Path(dec_audio).resolve() != Path(dec_video).resolve():
                dec_audio = fix_container(Path(dec_audio), ffmpeg)

        if finalize is not None:
            print("[pipeline] Custom finalize…")
            result_path = Path(finalize(Path(dec_video), Path(dec_audio), keys, cp))
        else:
            output_path = self.output_dir / f"{output_name}.mkv"
            print("[pipeline] Mux…")
            result_path = mux_av(
                Path(dec_video),
                Path(dec_audio),
                output_path,
                mkvmerge=mkvmerge,
                ffmpeg=ffmpeg,
            )
        cp.set_output(result_path)

        # Free disk: native segment stores no longer needed after successful output
        try:
            from .checkpoint import purge_job_segments

            purge_job_segments(cp.job_id)
        except Exception:
            pass

        return PipelineResult(
            output_path=result_path,
            stage=Stage.DONE,
            job_id=cp.job_id,
            resumed=resumed,
            keys_count=len(keys),
            meta={"service": self.service, "title": self.title},
        )

    def cleanup_temp_patterns(self, temp_dir: Path, name: str) -> None:
        """Remove common enc/dec temp files for *name* (same as EON cleanup)."""
        temp_dir = Path(temp_dir)
        for pattern in [f"{name}_enc*", f"{name}_dec*", f"{name}_fixed*"]:
            for f in temp_dir.glob(pattern):
                try:
                    f.unlink()
                except OSError:
                    pass
