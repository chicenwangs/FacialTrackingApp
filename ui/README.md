# ui — SvelteKit 3 / Svelte 5 (adapter-static, hash router), shown in pywebview

- `npm ci` · `npm run build` → `build/` (loaded by `src/mcg/ui/shell.py`) · `npm run check` (svelte-check).
- Screens = wireframes: Home, Signs, Test mode, Macros, Settings, Setup (first run), Overlay (`#/overlay`).
- Bridge: `#lib/api.svelte.ts` → `window.pywebview.api.*` (`src/mcg/ui/bridge.py`). State push: `window.__sc.emit` 10/s.
- Tokens only (`src/lib/app.css`, docs/THEME.md). No raw hex in components. Details: ADR-011.
