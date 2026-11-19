# FaceCam web UI

SvelteKit 3 / Svelte 5 static build, shown in pywebview when FaceCam is run with `--web`. The default UI is a native Tkinter window in `facecam/ui/native_shell.py`.

- `npm ci` then `npm run build` produces `build/`, which is loaded by `facecam/ui/shell.py`. `npm run check` runs svelte-check.
- Screens: Home (preview and status), Settings, Setup (only when the camera is not registered).
- Bridge: `src/lib/api.svelte.ts` talks to `window.pywebview.api.*` from `facecam/ui/bridge.py`. State is pushed at 10 Hz with `window.__sc.emit`.
- Design tokens live in `src/lib/app.css`; components use those variables rather than raw colours.
