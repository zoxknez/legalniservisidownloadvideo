# Streaming services — arhitektura

## Jedan izvor istine

| Servis | Kanonski modul (preuzimanje) | Auth / browse |
|--------|------------------------------|---------------|
| Voyo | `backend.core.services.voyo.downloader` | `voyo.auth` (in-process u adapteru) |
| HRTi | `backend.core.services.hrti.hrti_downloader` | `hrti.HRTIBrowser` (in-process) |
| EON | `backend.core.services.eon.eon_downloader` | `eon.engine.EONEngine` (in-process browse/API) |
| RTS Planeta | `backend.core.services.rtsplaneta.rtsplaneta_downloader` | `rtsplaneta_auth` (in-process) |
| HBO Max | `backend.core.services.hbomax.hbomax_downloader` | `hbomax_auth` |

Red preuzimanja pokreće:

- **In-process** (bez subprocessa): Voyo, HBO Max — vidi `backend/jobs/`
- **Subprocess** `python -m <modul>`: HRTi, EON, RTS, yt-dlp

## Root skripte

Fajlovi u rootu (`voyo_downloader.py`, `hrti_*.py`, …) su **tanke shim launcher** skripte koje delegiraju na `python -m backend.core.services...`.

## DRM

`backend.services.drm_manager` koriste engine moduli u core-u:

- `hrti.hrti_downloader`
- `eon.eon_downloader`

## Zastarjelo

- `Eon/` — uklonjen legacy engine (vidi `Eon/README.md`)
- `backend/core/services/rts/` — alias; pravi kod je u `rtsplaneta/`
