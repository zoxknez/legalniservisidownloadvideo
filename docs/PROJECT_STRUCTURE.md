# Struktura projekta

## Ulazne tačke

| Putanja | Uloga |
|---------|--------|
| `run.py` | Pokreće Uvicorn (`backend.main:app`) na `127.0.0.1:8000`, po potrebi gradi frontend |
| `backend/main.py` | FastAPI aplikacija, statički UI iz `backend/static/` |
| `frontend/` | React + Vite izvor; `npm run build` → `backend/static/` |

## Backend

```
backend/
├── main.py              # App factory, lifespan, static mount
├── config.py            # ~/.videodownload/config.json
├── queue_manager.py     # Red preuzimanja (SQLite)
├── credentials_store.py # Keyring + config metadata
├── session_import.py    # Uvoz tokena / kolačića
├── bridge.py            # Tampermonkey payload
├── routes/              # HTTP API po domenu
├── jobs/                # Izvršavanje download zadataka
├── services/            # Adapteri (voyo, hrti, eon, rts, hbo, drm, …)
└── core/services/       # Kanonski engine moduli (jedan izvor istine)
```

Detalji servisa: [backend/core/services/SERVICES.md](../backend/core/services/SERVICES.md)

## Root `*_auth.py` / `*_downloader.py`

Kratki **CLI shim** fajlovi (`runpy` → `backend.core.services.*`). Nisu duplikati logike — pogodni za `python voyo_downloader.py` iz navike.

## Frontend

```
frontend/src/
├── components/     # Tabovi, layout, settings, drm
├── hooks/domains/  # Po servisu + useAppConfig
├── context/        # Slice store (AppProvider)
├── lib/            # api, bridge, session skripte
└── types/
```

`frontend/scripts/` — alati za održavanje (split/regen); nisu potrebni za runtime.

## Šta ne ide u Git

- `backend/static/assets/`, `index.html` — generiše `npm run build`
- `.videodownload/` — config, baza reda, device.wvd kopija
- `device.wvd`, `eon_*.json` (osim `*.example.json`)
- `scratch/`, `output/`, `temp/`, `*.bak`

## Lokalni šabloni (EON)

Pri startu servera, ako nedostaju `eon_*.json` u root-u, kopiraju se iz `eon_*.example.json` (`backend/bootstrap_local_files.py`).

## Setup skripte

- `scripts/setup.ps1` — Windows
- `scripts/setup.sh` — Linux / macOS

## Testovi

```bash
python -m pytest tests/ -q
cd frontend && npm test && npm run build
```
