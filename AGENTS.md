# Agent notes (Cursor / AI)

## Architecture

- **Engines:** `backend/core/services/<service>/` — single source of truth.
- **API:** `backend/routes/` + `backend/services/*_adapter.py`.
- **UI:** React slices in `frontend/src/hooks/domains/`, state in `AppProvider` / `appStore`.
- **Root `*_downloader.py`:** CLI shims only (`runpy`), not duplicate logic.

## Commands

```bash
python -m pytest tests/ -q
cd frontend && npm run build && npm test
python run.py
```

## Do not commit

`backend/static/assets/`, `.videodownload/`, `device.wvd`, `eon_*.json` (except `*.example.json`), `scratch/`, `output/`.

## Docs

- [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [backend/core/services/SERVICES.md](backend/core/services/SERVICES.md)

## Conventions

- Match existing adapter/route patterns per service.
- Secrets → `credentials_store` (keyring), never plain passwords in `config.json`.
- User-facing strings: Serbian (latinica) unless the file is English-only.
- Minimal diffs; no drive-by refactors.
