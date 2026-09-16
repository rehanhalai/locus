# LOCUS Forensic Copilot (Local Qwen2.5-1.5B ONNX) Walkthrough

## Summary of Accomplishments

We implemented the complete offline, local Small Language Model (SLM) Forensic Copilot powered by **Qwen2.5-1.5B-Instruct ONNX** across both the backend (`api/locusAI`) and frontend (`web/locusAI`), using small, atomic commits for version control and safety.

---

## 1. Backend Architecture (`api/locusAI`)

### Commits on `api/locusAI`:
1. `f8304f0` — `feat(copilot): setup onnx model engine and verify token generation`
   - Generated and validated `genai_config.json` for INT4 ONNX Qwen2.5-1.5B.
   - Built and verified standalone token generator in `backend/scripts/verify_onnx_genai.py`.
2. `1b39ef7` — `feat(copilot): define chat schemas and forensic tool registry`
   - Created Pydantic schemas in `backend/app/modules/copilot/schemas.py`.
   - Created forensic tool registry and DB query handlers in `backend/app/modules/copilot/tools.py` (`get_case_summary`, `search_detections`, `seek_player`, `prepare_export`).
3. `ad48770` — `feat(copilot): implement copilot service with tool extraction and fallback`
   - ChatML prompt constructor (`<|im_start|>system...`).
   - Singleton model manager with worker-thread non-blocking token streamer.
   - JSON tool call parser and deterministic heuristic intent matcher.
4. `7e14c89` — `feat(copilot): add streaming chat router and automated tests`
   - Mounted `GET /api/v1/copilot/status` and `POST /api/v1/copilot/chat` (SSE & sync).
   - Wrote 6 automated tests in `backend/tests/test_copilot_api.py`.
   - All 140/140 backend pytest tests pass.

---

## 2. Frontend Architecture (`web/locusAI`)

### Commits on `web/locusAI`:
1. `50c05c5` — `feat(ui): add shadcn chat components`
   - Built modern Shadcn chat primitives:
     - `ChatBubble.tsx`: Author avatar, glowing AI pulse badge, formatted narrative, embedded action badges, copy button, and timestamp.
     - `ChatInput.tsx`: Auto-resizing textarea, Enter to submit, Shift+Enter for newline, streaming stop button, and quick prompt chips.
     - `MessageScroller.tsx`: Smooth auto-scroll with floating bottom scroll pill.
     - `ActionBadge.tsx`: Interactive badges with icons for `seek_player`, `search_detections`, `get_case_summary`, and `prepare_export`.
     - Types in `frontend/src/types/copilot.ts`.
2. `35d2d65` — `feat(copilot): add copilot state store and streaming client`
   - Implemented SSE POST stream reader and sync client in `frontend/src/api/copilot.ts`.
   - Built Zustand store `frontend/src/stores/useCopilotStore.ts` managing message history, streaming tokens, model status, and action dispatching.
3. `0cf834a` — `feat(ui): implement slide-over copilot drawer`
   - Created `CopilotDrawer.tsx` slide-over panel with active case context banner, CPU status pill, and hotkey listener (`Ctrl+Space`, `Alt+C`, `Esc`).
   - Integrated Copilot trigger button into `frontend/src/components/layout/Topbar.tsx`.
   - Mounted `<CopilotDrawer />` globally in `frontend/src/components/layout/AppLayout.tsx`.
4. `709ad85` — `feat(copilot): connect tool actions to video player and workspace`
   - Connected agentic tools to real workspace navigation:
     - `seek_player`: sets `focusedCameraId`, sets `masterPlayheadTime`, and jumps to `/investigate` (Room 1).
     - `search_detections`: jumps to `/search` (Room 2).
     - `prepare_export`: jumps to `/export` (Room 3).
     - `get_case_summary`: jumps to `/cases`.

---

## 3. Verification & Validation Results

### Backend Automated Test Suite
```bash
uv run pytest
```
- **Result:** `140 passed, 1 warning in 18.81s`
- **Coverage:** All 6 copilot API tests passed (`test_copilot_status_endpoint`, `test_copilot_chat_summary_action`, `test_copilot_chat_search_detections`, `test_copilot_chat_seek_player`, `test_copilot_chat_prepare_export`, `test_copilot_streaming_chat_sse`).
- **Linter:** `uv run ruff check .` passed with 0 errors.

### Frontend TypeScript & Production Build
```bash
pnpm --filter frontend build
```
- **Result:** `tsc -b && vite build` succeeded in `1.36s` with 0 type errors.
- **Bundle output:** Clean production bundle ready for Electron / Web deployment.

---

## 4. Remote Branches Pushed

- **Backend:** `api/locusAI` (pushed to origin)
- **Merged to:** `main` (pushed to origin)
- **Frontend:** `web/locusAI` (pushed to origin)
