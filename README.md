# TruthLens
*Measure what AI gets right, expose what it gets wrong.*

TruthLens tests whether an AI answer is supported by the evidence you supply, claim by claim.

---

## Status

Milestones 1a, 1b, and 3A are complete and tested.

| Area | State |
|---|---|
| Input validation, claim extraction, baseline + LLM verifier, strict output parsing, metrics, pipeline | Done, tested |
| Provider contract: timeouts, bounded retries/backoff, 429/5xx/auth handling, normalized results, mock provider | Done, tested |
| Secret redaction, key masking, env-based provider status, CORS origin parsing | Done, tested |
| JSON/CSV export (formula-injection-safe, redacted) | Done, tested |
| FastAPI app (`/api/health`, `/api/providers`, `/api/evaluations`), SQLAlchemy 2.x SQLite persistence | Done, tested |
| **Gemini adapter** (real HTTP, `httpx`, retry, token usage) | **Done, tested** |
| **Groq adapter** (real HTTP, OpenAI-compatible, retry, token usage) | **Done, tested** |
| **OpenRouter adapter** (real HTTP, OpenAI-compatible, identification headers) | **Done, tested** |
| **Ollama adapter** (real HTTP, keyless local, connection failure reporting) | **Done, tested** |
| **Provider registry** (build from env, get by ID, is_configured, status flags) | **Done, tested** |
| **LLM verifier_type in API** (`POST /api/evaluations` with `provider_id`) | **Done, tested** |
| **React/Vite dark mode dashboard and all 6 pages (Milestone 4)** | **Done, tested** |
| OpenAI, Anthropic, xAI adapters | Not started (Milestone 3B) |
| Comparison, datasets, Docker | Not started |

---

## Supported Providers (Milestone 3A)

| Provider | Auth | Env Vars | Notes |
|---|---|---|---|
| **Gemini** | API key | `GEMINI_API_KEY`, `GEMINI_MODEL` | Google Generative Language API (v1beta) |
| **Groq** | API key | `GROQ_API_KEY`, `GROQ_MODEL` | OpenAI-compatible; ultra-fast LLM inference |
| **OpenRouter** | API key | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Routes to 300+ models from a single endpoint |
| **Ollama** | None (keyless) | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Local inference; default `http://localhost:11434` |

---

## Configuration

Copy `.env.example` to `backend/.env` and fill in what you are authorized to use.

```bash
cp .env.example backend/.env
# Edit backend/.env with your keys
```

**Model IDs are NOT defaulted** — you must set them explicitly.

### Gemini
```
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-1.5-flash
```
Get an API key at: https://aistudio.google.com/app/apikey

### Groq
```
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.1-8b-instant
```
Popular models: `llama-3.1-8b-instant`, `llama-3.3-70b-versatile`, `mixtral-8x7b-32768`  
Get an API key at: https://console.groq.com

### OpenRouter
```
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-4o-mini
```
Model format: `provider/model-name`, e.g. `anthropic/claude-3-5-sonnet`, `google/gemini-flash-1.5`  
Get an API key at: https://openrouter.ai/settings/keys

### Ollama (local)
```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
```
Install Ollama: https://ollama.ai  
Pull a model first: `ollama pull llama3.1`

---

## API Endpoints

### `GET /api/health`
Health status and database connectivity check.

### `GET /api/providers`
Returns all configured providers with masked key previews and `adapter_available` flags.

```json
{
  "providers": [
    {
      "provider": "gemini",
      "configured": true,
      "key_preview": "••••abc1",
      "model": "gemini-1.5-flash",
      "adapter_available": true,
      "setup_hint": "Set GEMINI_API_KEY and GEMINI_MODEL in backend/.env"
    }
  ]
}
```

### `POST /api/evaluations`
Run an evaluation against supplied sources and persist the report.

**Rule-based (offline, no API key needed):**
```json
{
  "question": "When was the Eiffel Tower built?",
  "answer": "The Eiffel Tower was completed in 1889.",
  "sources": [{"id": "S1", "text": "The Eiffel Tower was completed in 1889."}],
  "config": {"verifier_type": "rule_based"}
}
```

**LLM verifier (requires a configured provider):**
```json
{
  "question": "When was the Eiffel Tower built?",
  "answer": "The Eiffel Tower was completed in 1889.",
  "sources": [{"id": "S1", "text": "The Eiffel Tower was completed in 1889."}],
  "config": {
    "verifier_type": "llm",
    "provider_id": "gemini",
    "model_id": "gemini-1.5-flash"
  }
}
```

`provider_id` options: `gemini`, `groq`, `openrouter`, `ollama`  
`model_id` is optional — omit to use the model from your `.env` file.

If the requested provider is not configured, the API returns **400 Bad Request**
with a clear explanation. It never silently falls back to another provider.

### `GET /api/evaluations/{run_id}`
Retrieve a stored evaluation report after restart.

### `GET /api/evaluations/{run_id}/export?format=json|csv`
Export reports to JSON or formula-injection-safe CSV.

---

## Run the service

```bash
cd backend
pip install -e ".[api]"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## Run the tests

```bash
cd backend
python -m unittest discover -s tests -t . -v
# 126 tests, no network or real API keys needed
```

Or with pytest:
```bash
pytest -v
```

All 126 tests run entirely offline using `httpx.MockTransport`. No real API keys or network access are required.

---

## Demo — offline rule-based evaluation

```bash
cd backend
python -c "
import json, asyncio
from app.evaluation.pipeline import run_evaluation
from app.evaluation.verify import RuleBasedVerifier
d = json.load(open('sample_data/sample_eval.json'))
r = asyncio.run(run_evaluation(d['question'], d['answer'], d['sources'], verifier=RuleBasedVerifier()))
print(r.status, [(v.claim_id, v.classification) for v in r.verifications])
"
```

---

## Known Limitations

- **Claim extraction** uses sentence-boundary heuristics, not semantic NLP. It can split or miss claims.
- **Rule-based verifier** uses term overlap, numbers, and negation. It is not a semantic entailment detector.
- **LLM verifier** output is strictly validated (every excerpt must be verbatim in the cited source). Hallucinated excerpts become `ERROR` results.
- **Ollama** requires the server to be running locally before making requests. A connection failure is reported as `PROVIDER_OUTAGE`, not silently ignored.
- **OpenAI, Anthropic, xAI** adapters are planned for Milestone 3B and are not implemented yet. Requesting them via `provider_id` returns a 400 error.
- **Windows asyncio**: On Windows in sandboxed environments, the asyncio event loop may block on loopback socket initialization. Run tests outside the sandbox if they hang.
- **Model IDs** are not defaulted. If `GEMINI_MODEL` (or equivalent) is not set, the provider reports as unconfigured.

---

## Security

- API keys are read from environment variables; they are never returned in API responses.
- Error messages pass through secret redaction (`redact_secrets`) before being stored or returned.
- CSV exports are formula-injection-safe (Excel/Sheets formula prefixes are escaped).
- `.env` files are in `.gitignore` and must never be committed.
- CORS wildcard (`*`) is rejected; only explicit origins are allowed.
- Source text is treated as untrusted input in the LLM prompt; delimiter forgery attempts are neutralized.

---

## Frontend Dashboard (Milestone 4)

TruthLens features a dark-mode SaaS dashboard designed for AI observability and fact-checking.

### Quick Start

**Terminal 1 — Backend API:**
```bash
cd backend
pip install -e ".[api]"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — Frontend Application:**
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

### Production Build

```bash
cd frontend
npm run build
```

### Dashboard Pages

| Page | Route | Description |
|---|---|---|
| **Overview** | `overview` | Key verification metrics, claim status distribution chart, and recent evaluations. |
| **New Evaluation** | `new-evaluation` | Submit prompt, answer, and evidence sources for claim-by-claim evaluation using rule-based or LLM verifiers. Includes 1-click sample loader. |
| **Evaluation Result** | `result` | Detailed audit report with expandable claim cards, verbatim evidence quotes, conflict flags, and JSON/CSV export. |
| **Evaluation History** | `history` | Searchable, filterable audit log of past evaluations with pagination. |
| **Analytics** | `analytics` | Macro metrics and visualizations (Recharts donut & bar charts) derived from real SQLite data. |
| **Providers** | `providers` | LLM provider adapter readiness, environment credential status, and setup hints. |

---

## Environment Variables Reference

| Variable | Provider | Required | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Gemini | Yes | Google AI Studio API key (`AIza...`) |
| `GEMINI_MODEL` | Gemini | Yes | Model ID, e.g. `gemini-1.5-flash` |
| `GROQ_API_KEY` | Groq | Yes | Groq console API key (`gsk_...`) |
| `GROQ_MODEL` | Groq | Yes | Model ID, e.g. `llama-3.1-8b-instant` |
| `OPENROUTER_API_KEY` | OpenRouter | Yes | OpenRouter API key (`sk-or-...`) |
| `OPENROUTER_MODEL` | OpenRouter | Yes | Model ID, e.g. `openai/gpt-4o-mini` |
| `OLLAMA_BASE_URL` | Ollama | No | Server URL (default `http://localhost:11434`) |
| `OLLAMA_MODEL` | Ollama | Yes | Model ID, e.g. `llama3.1` |
| `CORS_ALLOWED_ORIGINS` | API | No | Comma-separated origins (no wildcard) |
| `DATABASE_URL` | DB | No | SQLite path (default `sqlite:///./truthlens.db`) |
