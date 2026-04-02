# Hush — Python Backend Design Document

> **Purpose:** Living reference for the FastAPI backend. Explains every file, its role,
> and how it connects to the Flutter app. Updated automatically with every code change.
>
> **Important context:** The backend is ONLY used in Phase 4 (AI Mood Insights).
> Phases 1–3 of the app are 100% offline — this backend doesn't need to exist yet.
> The Flutter app works completely without it.

---

## Where the Backend Lives

```
hush-personal-diary/
└── backend/          ← All Python code lives here
    ├── main.py       ← FastAPI app entry point
    ├── routers/      ← API route handlers
    ├── services/     ← Business logic (AI calls, etc.)
    ├── models/       ← Pydantic request/response models
    ├── requirements.txt
    └── .env          ← API keys (never committed to git)
```

---

## What the Backend Does (and Doesn't Do)

**Does:**
- Receives a note's decrypted text from the Flutter app
- Sends it to the Claude or GPT-4o API for sentiment analysis
- Returns a mood score + keywords back to the app
- Signs and verifies requests using HMAC (so random people can't call your API)

**Does NOT:**
- Store any note content — stateless, no database
- Know who you are — no user accounts
- Persist anything between requests

---

## How Flutter Talks to the Backend

```
Flutter app (on phone)
    ↓  HTTP POST /analyze/mood
    ↓  Body: { "text": "had a great day today...", "date": "2026-03-28" }
    ↓  Header: X-Signature: HMAC-SHA256(body, sharedSecret)
FastAPI backend (on laptop/cloud)
    ↓  Verifies HMAC signature
    ↓  Calls Claude/OpenAI API
    ↓  Returns: { "mood": "positive", "score": 0.85, "keywords": ["great", "happy"] }
Flutter app
    ↓  Stores mood score locally in Isar
    ↓  Shows mood badge on NoteCard
```

---

## Files

### `backend/main.py`
**What it is:** The FastAPI application entry point.

**What it does:**
- Creates the `FastAPI()` app instance
- Registers routers (routes/endpoints)
- Adds CORS middleware (so the Flutter app on localhost can call it during dev)
- Run with: `uvicorn main:app --reload`

---

### `backend/routers/mood.py`
**What it is:** The single API endpoint: `POST /analyze/mood`

**What it does:**
1. Validates the HMAC signature on the request
2. Extracts the note text from the request body
3. Calls `MoodService.analyze(text)`
4. Returns `MoodResponse(mood, score, keywords)`

---

### `backend/services/mood_service.py`
**What it is:** The AI call logic.

**What it does:**
- Sends the note text to Claude API (or OpenAI) with a structured prompt
- Parses the response into a mood label (positive/neutral/negative), score (0.0–1.0), and keywords
- If the AI API is down or times out, raises an exception (Flutter handles this gracefully — shows "Pending")

---

### `backend/models/schemas.py`
**What it is:** Pydantic data models for request and response validation.

**Models:**
```python
class MoodRequest(BaseModel):
    text: str          # The note content
    date: str          # ISO date string

class MoodResponse(BaseModel):
    mood: str          # "positive" | "neutral" | "negative"
    score: float       # 0.0 to 1.0
    keywords: list[str]  # Up to 5 notable words
```
Pydantic automatically validates incoming JSON — if `text` is missing, FastAPI returns a 422 error.

---

### `backend/requirements.txt`
```
fastapi
uvicorn
anthropic      # Claude API client
pydantic
python-dotenv  # Load .env file
```

---

### `backend/.env` (NOT committed to git)
```
ANTHROPIC_API_KEY=sk-ant-...
HMAC_SECRET=your-random-secret-string-shared-with-flutter-app
```

---

## Running the Backend (Phase 4)

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate    # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn main:app --reload --port 8000

# The API is now at: http://localhost:8000
# Docs (auto-generated): http://localhost:8000/docs
```

---

## Security Model

**HMAC request signing:**
Both the Flutter app and the backend share a secret string (set in `.env` and hardcoded in the app).
Every request from Flutter includes a signature: `HMAC-SHA256(request_body, shared_secret)`.
The backend recomputes this signature and rejects requests where it doesn't match.
This prevents anyone else from sending fake mood analysis requests to your server.

**No content persistence:**
The backend is designed to be stateless. The note text is only in memory for the duration of
one request (~200ms). It is never logged, never written to disk, never stored in any database.

---

---

## Phase 6+7: Shared Notes Backend

The `backend/` folder contains a FastAPI service for collaborative shared notes.
Shared notes are **intentionally not encrypted** — users explicitly opt into sharing them.

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/notes` | List all notes owned by or shared with the authenticated user |
| `POST` | `/api/notes` | Create a new shared note |
| `PUT` | `/api/notes/{id}` | Update title/body/font/color (owner or editor) |
| `DELETE` | `/api/notes/{id}` | Permanently delete a note (owner only) |
| `POST` | `/api/notes/{id}/share` | Invite collaborators by email with `edit` or `view` permission |
| `DELETE` | `/api/notes/{id}/share/{shareId}` | Remove a collaborator (owner removes anyone; member removes self) |
| `GET` | `/api/invites` | List pending invites for the current user |
| `POST` | `/api/invites/{shareId}/accept` | Accept a share invite |
| `POST` | `/api/invites/{shareId}/decline` | Decline a share invite |

### Share Invite Flow

1. Owner calls `POST /api/notes/{id}/share` with `{"emails": ["..."], "permission": "edit"}`
2. Backend creates a `share` row with `status = 'pending'`
3. Recipient sees the invite via `GET /api/invites` (Flutter polls on app open)
4. Recipient accepts → `status = 'accepted'`, note appears in their shared list

**Offline handling (Flutter side):** If the backend is unreachable, the Flutter app shows "Could not reach server. Check your connection…" — does NOT silently queue invites.

**Local note guard (Flutter side):** If the note has a `local_` ID (not yet synced), the Flutter UI blocks the share attempt: "Sync note first — open it while online."

### Body storage

- Backend stores `body` as plain text (Quill Delta flattened before sending).
- Flutter client stores original Delta JSON locally for rich editing.
- On sync, Delta is sent as plain text; local cache keeps Delta.

*Last updated: Phase 6+7 — Shared notes backend, share invite UX improvements, activity logs.*
