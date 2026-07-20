# Streaming services — arhitektura

## Jedan izvor istine

| Servis | Kanonski modul (preuzimanje) | Auth / browse |
|--------|------------------------------|---------------|
| Voyo (RS / HR) | `backend.core.services.voyo.downloader` | `voyo.auth` + `stream_probe` (videoUrlV2); katalog `drmProtected` je samo hint |
| HRTi | `backend.core.services.hrti.hrti_downloader` | `hrti.HRTIBrowser` (in-process) |
| EON | `backend.core.services.eon.eon_downloader` | `eon.engine.EONEngine` (in-process browse/API) |
| RTS Planeta | `backend.core.services.rtsplaneta.rtsplaneta_downloader` | `rtsplaneta_auth` (in-process) |
| HBO Max | `backend.core.services.hbomax.hbomax_downloader` | `hbomax_auth` |
| SkyShowtime | `backend.core.services.skyshowtime.skyshowtime_downloader` | `skyshowtime.skyshowtime_auth` |
| Univerzalno (yt-dlp) | `backend.services.ytdlp_command_builder` + yt-dlp CLI | `backend.services.ytdlp_adapter` |

Red preuzimanja pokreće **in-process** poslove preko `backend/jobs/` (bez subprocessa za glavne servise):

- **In-process**: Voyo, HBO Max, HRTi, EON, RTS, SkyShowtime — vidi `backend/jobs/*_job.py` i `build_job()` u adapterima
- **Subprocess** yt-dlp: `backend/routes/ytdlp.py` → `YtdlpAdapter` → `queue_manager` (Pametno preuzimanje)
- **CLI shim**: `ytdlp_downloader.py` → `backend.core.services.ytdlp.cli`

## Root skripte

Fajlovi u rootu (`voyo_downloader.py`, `hrti_*.py`, …) su **tanke shim launcher** skripte koje delegiraju na `python -m backend.core.services...`.

## DRM

`backend.services.drm_manager` koriste engine moduli u core-u:

- `hrti.hrti_downloader`
- `eon.eon_downloader`

## Shared pipeline (Faza 2)

`backend/core/pipeline/` — zajednički stage pipeline sa checkpoint resume-om:

| Modul | Uloga |
|-------|--------|
| `orchestrator.MediaPipeline` | keys → fragments → decrypt → mux |
| `checkpoint.JobCheckpoint` | `~/.videodownload/jobs/<id>/checkpoint.json` |
| `segments` | native URL-list resume (po segmentu) |
| `decrypt` / `mux` | mp4decrypt + mkvmerge/ffmpeg |

| Servis | MediaPipeline | Segment resume | Multi-path ladder |
|--------|---------------|----------------|-------------------|
| EON | da | stage | api → catalog → sniffer |
| HRTi | da | stage | api → re-login → sniffer |
| SkyShowtime | da + finalize | stage | api → re-auth → sniffer |
| RTS Planeta | da + keys_after_fragments | stage | api → re-login → sniffer |
| HBO Max | partial | **segment** | api → refresh → sniffer |
| Voyo | native HLS | **segment** | api → re-link → sniffer |

`pipeline.resolve.with_api_refresh_sniffer` / `resolve_stream_ladder` — standardni ladder.

Checkpoints: `~/.videodownload/jobs/<id>/`  
- TTL cleanup pri startu: DONE posle 3 dana, ostalo posle 7 dana (`cleanup_old_jobs`)  
  (podešava se u `config.pipeline.checkpoint_done_days` / `checkpoint_stale_days`)  
- WS `resolve_fallback` → UI toast kad resolve ide preko sniffer/refresh/catalog  

### Batch / serije

Delimičan uspeh (**neke** epizode OK) = job **finished** sa WARNING logom (Sky, HRTi, Voyo, EON).  
Fail samo ako **nijedna** epizoda nije preuzeta.

## Zastarjelo

- `Eon/` — uklonjen legacy engine (vidi `Eon/README.md`)
- `backend/core/services/rts/` — alias; pravi kod je u `rtsplaneta/`
