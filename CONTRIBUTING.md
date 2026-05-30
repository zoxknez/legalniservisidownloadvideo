# Doprinos / razvoj

Hvala što radite na projektu. Kratak vodič za lokalni rad i PR-ove.

## Prvi setup

**Windows (PowerShell):**

```powershell
.\scripts\setup.ps1
python run.py
```

**Linux / macOS:**

```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
python run.py
```

Ručno: vidi [README.md](README.md) (venv, `pip install -r requirements.txt`, `cd frontend && npm ci && npm run build`).

## Šta menjati gde

| Promena | Gde |
|---------|-----|
| Logika preuzimanja servisa | `backend/core/services/<servis>/` |
| HTTP API | `backend/routes/` + `backend/services/*_adapter.py` |
| UI tab / postavke | `frontend/src/components/`, `frontend/src/hooks/domains/` |
| Sesije / bridge | `userscripts/`, `backend/bridge.py`, `backend/session_import.py` |

Ne duplirajte engine u root `*_downloader.py` — to su samo CLI shimovi.

## Testovi pre PR-a

```bash
python -m pytest tests/ -q
cd frontend && npm run build && npm run lint && npm test
```

## Git higijena

Ne commit-ujte:

- `backend/static/assets/`, `backend/static/index.html` (build)
- `.videodownload/`, `output/`, `device.wvd`, `eon_*.json` (osim `*.example.json`)
- `scratch/`, `*.bak`, `frontend/lint-out.txt`

Detalji: [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)

## Frontend održavanje (retko)

Alati u `frontend/scripts/` — vidi [docs/FRONTEND_MAINTENANCE.md](docs/FRONTEND_MAINTENANCE.md).
