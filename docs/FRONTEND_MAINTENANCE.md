# Održavanje frontenda

Runtime aplikacija koristi samo `frontend/src/`. Folder `frontend/scripts/` je za **refaktoring / regeneraciju** — ne pokrećite ga u produkciji.

## Build

```bash
cd frontend
npm run build   # → ../backend/static/ (Vite outDir)
```

`base: '/static/'` u `vite.config.ts` mora ostati usklađen sa FastAPI mount-om u `backend/main.py`.

## Regen pipeline (samo ako monolit vraćate)

```bash
cd frontend
npm run regen:tabs
```

Redosled skripti (definisano u `package.json`):

1. `regenerate_frontend_chunks.py` — čita `App.tsx.bak` (ne drži se u Git-u)
2. `cleanup_split.py`
3. `post_regen_patch.py`
4. `fix_style_any.py`
5. `generate_app_context_type.py`

Posle regen-a uvek: `npm run build`, `npm run lint`, `npm test`.

## Test store

Mockovi za Vitest: `frontend/src/test/createTestStore.ts` — ažurirajte kada `use*Slice` hookovi dobiju nova polja.
