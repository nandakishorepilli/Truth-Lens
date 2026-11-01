# TruthLens
*Measure what AI gets right, expose what it gets wrong.*

TruthLens tests whether an AI answer is supported by the evidence you supply, claim by claim.

## Status (honest report)

Milestone 1a (Evaluation Core) and Milestone 1b (FastAPI Service + SQLite Persistence) are complete and tested.

| Area | State |
|---|---|
| Input validation, claim extraction, baseline + LLM verifier, strict output parsing, metrics, pipeline | Done, tested |
| Provider contract: timeouts, bounded retries/backoff, 429/5xx/auth handling, normalized results, mock provider | Done, tested |
| Secret redaction, key masking, env-based provider status, CORS origin parsing | Done, tested |
| JSON/CSV export (formula-injection-safe, redacted) | Done, tested |
| FastAPI app (`/api/health`, `/api/providers`, `/api/evaluations`), SQLAlchemy 2.x SQLite persistence | Done, tested |
| React/Vite dashboard and all pages | **Not started** |
| Real adapters (Gemini, Groq, OpenRouter, OpenAI, Anthropic, xAI, Ollama) | **Not started** (Milestone 3) |
| Comparison, datasets, Docker | **Not started** (Docker not available here) |

## API Endpoints

- `GET /api/health`: Health status and database connectivity check.
- `GET /api/providers`: Configured provider statuses with masked key previews.
- `POST /api/evaluations`: Run an evaluation against supplied sources and persist the report.
- `GET /api/evaluations/{run_id}`: Retrieve a stored evaluation report after restart.
- `GET /api/evaluations/{run_id}/export?format=json|csv`: Export reports to JSON or formula-injection-safe CSV.

## Run the service
```bash
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Run the tests
```bash
cd backend
python -m unittest discover -s tests -t . -v      # 53 tests, no network or external API keys needed
# or with pytest:
pytest -v
```

Demo with the sample data:
```
cd backend && python3 -c "
import json, asyncio
from app.evaluation.pipeline import run_evaluation
from app.evaluation.verify import RuleBasedVerifier
d = json.load(open('sample_data/sample_eval.json'))
r = asyncio.run(run_evaluation(d['question'], d['answer'], d['sources'], verifier=RuleBasedVerifier()))
for c, v in zip(r.claims, r.verifications): print(v.classification.value, '|', c.text)"
```

## Configuration
Copy `.env.example` to `backend/.env`. Keys are read from the environment only, are never returned by any function
(`provider_statuses` returns a masked suffix), and are redacted from errors and exports. With no keys set, everything
above still runs. Model IDs have no defaults; set the ones your account can access.

## Limits
Results show support **from the supplied sources**, not truth. Both extraction and verification can be wrong. See
`docs/evaluation-methodology.md`.

## Next step
In a networked environment: `cd backend && pip install -e ".[api,dev]"`, run `pytest`, then add `app/main.py`
(FastAPI: `/api/health`, `/api/providers`, `/api/evaluations`) wrapping `run_evaluation`, plus SQLAlchemy persistence.
