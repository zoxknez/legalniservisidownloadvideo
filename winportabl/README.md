# Video Download Servisi

[![Preuzmi Prenosivu Verziju (ZIP)](https://img.shields.io/badge/Preuzmi_Portable-v2.7.5--Windows-orange?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/zoxknez/legalniservisidownloadvideo/releases/latest/download/VideoDownloadServisi-Portable.zip)

Lokalna aplikacija za preuzimanje video sadržaja s podržanih streaming servisa (Voyo, HRTi, EON, RTS Planeta, HBO Max) i univerzalni `yt-dlp` mod — **samo za sadržaj za koji imate pretplatu i pravo pristupa**.

## Brzi start

**Jedna komanda (preporučeno):**

```powershell
# Windows
.\scripts\setup.ps1
python run.py
```

```bash
# Linux / macOS
chmod +x scripts/setup.sh && ./scripts/setup.sh
python run.py
```

Ili ručno korak po korak:

### 1. Python zavisnosti

```bash
cd d:\ProjektiApp\videodownloadservisi
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Eksterni alati

Instalirajte i dodajte u PATH (ili u Podešavanjima u UI):

| Alat | Namjena |
|------|---------|
| ffmpeg | Spajanje / transkodiranje |
| mkvmerge | Multiplex |
| mp4decrypt | Widevine dekripcija segmenata |
| aria2c | Opcioni brži download |
| device.wvd | Widevine CDM (L3 na PC-u) |

### 3. Frontend build (UI za `python run.py`)

```bash
cd frontend
npm install
npm run build
cd ..
```

Build upisuje fajlove u `backend/static/` (nije u Git-u). `run.py` pokušava build automatski ako `index.html` nedostaje.

### 4. Pokretanje

```bash
python run.py
```

Otvara se `http://127.0.0.1:8200` (samo lokalno).

### 5. Frontend (razvoj sa hot-reload)

```bash
cd frontend
npm run dev
```

Vite proxy prosljeđuje `/api` i `/ws` na port **8200** (backend mora biti pokrenut).

## Sigurnost

- Server po defaultu sluša **127.0.0.1** — nije izložen internetu.
- Na prvom pokretanju generiše se **API ključ** u `~/.videodownload/config.json` (`server.api_key`).
- Za LAN pristup postavite `VIDEODOWNLOAD_API_KEY` ili unesite ključ u **Podešavanja → API ključ** u UI.
- Za RDP/LAN pristup možete u `.env` postaviti `VIDEODOWNLOAD_HOST=0.0.0.0` i `VIDEODOWNLOAD_PORT=8200`, uz API ključ i firewall pravila.
- Ako browser/Tampermonkey nije na istoj mašini kao backend, postavite `VIDEODOWNLOAD_PUBLIC_URL=http://IP-ILI-HOST:8200` da userscript šalje podatke na pravi server.
- Ako je server u drugoj državi i servisi odbijaju login/manifest/licencu zbog regiona, postavite regionalni `VIDEODOWNLOAD_PROXY_URL` u `.env`.
- `VIDEODOWNLOAD_LOCALHOST_BYPASS=true` (default) — localhost zahtjevi ne traže ključ.
- Izvoz DRM ključeva preko API-ja je **isključen** dok ne postavite `VIDEODOWNLOAD_ALLOW_DRM_KEY_EXPORT=true`.

### Lozinke i tokeni (plaćeni nalozi)

- **Lozinke** i **session tokeni** idu u **Windows Credential Manager** (Python `keyring`), ne u plain-text JSON.
- U `~/.videodownload/config.json` ostaju samo metapodaci (email, username, market, serial) — fajl ima chmod `600`.
- Pri startu aplikacija automatski **migrira** stare lozinke iz `config.json` i `~/.voyo`, `~/.hrti`, `~/.rtsplaneta` u keyring i briše ih s diska.
- HBO OAuth ostaje u `~/.hbomax/token.json` (tako i CLI); dodatno se može sačuvati u keyring.
- `/api/status` → `credentials_security` pokazuje da li je secret u keyringu (bez vraćanja vrijednosti).

### device.wvd (Widevine CDM)

U **Podešavanjima**:
- **Auto-instaliraj** — pronalazi validan `.wvd` na disku i kopira u `~/.videodownload/device.wvd`
- **Upload** ili **base64 paste** — nakon exporta iz vašeg alata, bez ručnog kopiranja putanje
- API: `GET /api/drm/wvd/discover`, `POST /api/drm/wvd/auto-install`, `POST /api/drm/wvd/upload`, `POST /api/drm/wvd/install-base64`

### Tampermonkey Bridge v2

1. Instalirajte Tampermonkey
2. Otvorite `http://127.0.0.1:8200/api/bridge/userscript.js`
3. Skripta automatski šalje sesije u app i snifuje `.mpd` / license URL-ove

API: `POST /api/bridge/session`, `POST /api/bridge/sniffer`, `GET /api/bridge/userscript.js`

Bookmarklet „Pošalji sesiju u app” radi isto bez Tampermonkey-a (1 klik na sajtu servisa).

Pri startu: migracija lozinki u keyring, auto-instalacija `device.wvd`, sinhronizacija browser kolačića.

### Sniffer auto-preuzimanje

Kad Tampermonkey uhvati **manifest + license**, aplikacija može automatski pokrenuti download (podešavanje u UI).
Ručno: toast **„Preuzmi odmah”** ili `POST /api/sniffer/download`.

Kopirajte `.env.example` u `.env` po potrebi.

## Struktura

```
backend/                    FastAPI API, red, DRM manager
backend/core/services/      Kanonski engine po servisu (jedan izvor istine)
backend/services/*_adapter.py  Most ka API-ju
backend/static/             Generisani UI (npm run build) — nije u Git-u
frontend/                   React + Vite izvor
binaries/                   Opciono mesto za device.wvd (vidi README u folderu)
userscripts/                Tampermonkey bridge
tests/                      pytest
*.py (root)                 Shim launcheri → backend.core.services.*
```

Detalji: [backend/core/services/SERVICES.md](backend/core/services/SERVICES.md) · [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)

Instalacija (alternativa): `pip install -e ".[dev]"` koristi `pyproject.toml`.

## Testovi

```bash
pip install -e ".[dev]"
python -m pytest tests/ -q
cd frontend && npm test
```

Vidi [CONTRIBUTING.md](CONTRIBUTING.md) za PR workflow.

## Pravna napomena

Korištenje je na vlastitu odgovornost i u skladu s uvjetima korištenja svakog servisa. Ne dijelite `device.wvd`, tokene ni dekripcijske ključeve.
