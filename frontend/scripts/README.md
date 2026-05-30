# Frontend maintenance scripts

Not used at runtime. See [../../docs/FRONTEND_MAINTENANCE.md](../../docs/FRONTEND_MAINTENANCE.md).

| Script | Purpose |
|--------|---------|
| `split_app.py` | Split monolithic App into tab modules |
| `regenerate_frontend_chunks.py` | Regenerate chunks from backup |
| `cleanup_split.py` / `post_regen_patch.py` / `fix_style_any.py` | Post-regen fixes |
| `generate_app_context_type.py` | Regenerate TS context types |

Run via: `npm run regen:tabs` (from `frontend/`).
