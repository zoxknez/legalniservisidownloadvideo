# Streaming services — arhitektura

## Jedan izvor istine

| Servis | Kanonski modul (preuzimanje) | Auth / browse |
|--------|------------------------------|---------------|
| Voyo (RS / HR) | `backend.core.services.voyo.downloader` | `voyo.auth` — varijante `rs` (voyo.rs) i `hr` (voyo.hr) |
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

## Zastarjelo

- `Eon/` — uklonjen legacy engine (vidi `Eon/README.md`)
- `backend/core/services/rts/` — alias; pravi kod je u `rtsplaneta/`
