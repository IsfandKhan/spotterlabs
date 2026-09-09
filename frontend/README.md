# Frontend — ELD Trip Planner

React + Vite + Tailwind + shadcn/ui. See the [root README](../README.md) for the
full picture.

```bash
pnpm install
pnpm dev        # http://localhost:5173
pnpm build      # -> dist/
```

`.env` → `VITE_API_BASE_URL=http://localhost:8000` (no trailing slash).

Deploys to Vercel with root directory `frontend`; `vercel.json` handles SPA
rewrites. Set `VITE_API_BASE_URL` to the deployed API URL.
