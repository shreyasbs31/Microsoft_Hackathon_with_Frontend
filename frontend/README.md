# Frontend — Honeypot dashboard

React (Vite) UI for the honeypot system. Root project documentation is in the [../README.md](../README.md).

## Commands

```bash
npm ci
npm run dev
```

Development proxies `/api` to `http://localhost:8000` (see `vite.config.js`).

```bash
npm run build
```

Writes production files to `../static/` (configured in `vite.config.js`). Run the FastAPI app from the repository root to serve `static/`.
