# ContentMind — Run Doc

Two processes: FastAPI backend (port 8000) + Vite frontend (port 5173, proxies `/api` to the backend).

## Reproduce artifacts (fresh checkout)

1. Backend deps (Python 3.11+):
   ```
   python -m pip install -r requirements.txt
   ```
2. Frontend deps (Node 18+):
   ```
   cd frontend && npm install
   ```
3. Env config: copy `.env.example` to `.env` (no secrets committed; the app runs fully without keys — Hindsight falls back to an in-process store, LLM uses deterministic fallbacks).
4. Database: `contentmind.db` is created automatically on backend startup. For demo data, either click **Run Before / After Demo** on the Memory Demo page or:
   ```
   curl -X POST -H "Content-Type: application/json" -d '{"count":64}' http://127.0.0.1:8000/api/demo/seed
   ```

## Run the servers

Backend (from repo root):
```
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
Frontend (from `frontend/`, uses the project default port 5173):
```
npm run dev
```
App URL: http://localhost:5173 (Vite proxies `/api` and `/health` to http://localhost:8000).

Backend tests: `python -m pytest backend/tests -q` (22 tests).
