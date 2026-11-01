# TruthLens System Audit Report

**Date**: 2026-10-27  
**Status**: Comprehensive Project Audit Completed  
**Repository Path**: `TruthLens/`  
**Test Suite Status**: 44 passed, 0 failed, 0 errors (0.17s runtime)  

---

## 1. Executive Summary

TruthLens is designed to evaluate whether AI-generated answers are factual and supported by supplied source documents claim-by-claim. 

The previous development phase produced a high-quality, dependency-free core engine (`backend/app/`) containing data models, text normalization, sentence segmentation, rule-based claim extraction, a baseline rule-based verifier, strict LLM output parsing, provider contracts with exponential backoff and error categorization, metrics calculation with explicit ratios, and security utilities (secret redaction, CSV formula injection defense, CORS origin validation).

This audit verified all existing code, executed the full offline test suite, audited the distinction between claim classifications and verification errors, identified architectural bottlenecks and security gaps, and defined the next smallest implementation milestone.

---

## 2. Test Execution & Empirical Results

### 2.1 Test Suite Run
The offline test suite was executed against Python 3.13:
```bash
python -m unittest discover -s tests -t . -v
```

**Actual Results**:
- **Total Tests Run**: 44
- **Passed**: 44
- **Failures**: 0
- **Errors**: 0
- **Execution Time**: 0.167s

### 2.2 Test Breakdown by Module
| Test Module | Tests | Result | Focus Areas |
|---|:---:|:---:|---|
| `tests.test_baseline_verifier` | 7 | PASS | Supported excerpts, number contradictions, negation contradictions, insufficient evidence, unstated numbers, conflict detection, delimiter neutrality |
| `tests.test_input_and_claims` | 7 | PASS | Input validation, character limits, URL validation, duplicate ID rejection, sentence boundary preservation, non-factual segment skipping |
| `tests.test_llm_verifier_and_providers` | 16 | PASS | Strict JSON parsing, fenced code block handling, whitespace-flexible excerpt matching, hallucinated excerpt rejection, rate limit retries, auth fast-failure, cost estimation |
| `tests.test_metrics_pipeline_reporting` | 14 | PASS | Explicit ratio denominators, zero-denominator safety, all-error undefined behavior, bounded concurrency, stage transitions, CSV escaping, secret redaction, key masking |

### 2.3 Sample Evaluation Demo
The offline sample evaluation demo was executed using `backend/sample_data/sample_eval.json`:
- Claim 1 ("The Eiffel Tower was completed in 1889."): `SUPPORTED` (matches S1)
- Claim 2 ("The tower is 330 metres tall."): `SUPPORTED` (matches S1)
- Claim 3 ("The Eiffel Tower was completed in 1925."): `CONTRADICTED` (conflicts with 1889 in S1)

### 2.4 Empirical Finding: Windows Sandbox Asyncio Loopback Isolation
During sandboxed test execution on Windows, `python -m unittest` hung on the very first async test. Investigation revealed:
- On Windows, Python's `asyncio` default event loop (`ProactorEventLoop` or `SelectorEventLoop`) initializes an internal loopback IPC/socket mechanism via `socket.socketpair()` or IOCP binding to `127.0.0.1`.
- In sandboxed environments where network access is isolated, loopback connect (`127.0.0.1`) fails with `PermissionError: [WinError 10013]` or blocks indefinitely on socket connection.
- When isolation is bypassed or proper loopback permissions are granted, all 44 tests pass instantly in 0.167s.
- **Action Item**: Document this Windows loopback quirk in the test runner instructions or configure an offline selector loop for headless test environments.

---

## 3. Evaluation Logic & Classification Correctness

A primary objective of TruthLens is ensuring that verification results remain strictly honest and transparent. We audited how the engine handles each classification and whether verification errors are ever conflated with evidence gaps.

```
                  ┌──────────────────────────────┐
                  │    Claim Verification        │
                  └──────────────┬───────────────┘
                                 │
         ┌───────────────────────┴───────────────────────┐
         ▼                                               ▼
  [Status: CLASSIFIED]                            [Status: ERROR]
         │                                               │
 ┌───────┼────────────────────────┐              (Network timeout,
 │       │                        │               bad JSON schema,
 ▼       ▼                        ▼               unknown source,
SUPPORTED CONTRADICTED  INSUFFICIENT_EVIDENCE     fabricated excerpt)
                                  │                      │
                         ┌────────┴────────┐             │
                         ▼                 ▼             ▼
                     No Passage        Conflict   Excluded from
                      Matches          Detected  completion rate
                                    (sup and con)
```

### 3.1 Four-Way Distinction Audit

1. **`SUPPORTED`**:
   - **Baseline**: Requires $\ge 60\%$ term overlap, matching polarity (`_negated(claim) == _negated(source)`), and all numbers in the claim must be present in the source passage.
   - **LLM Verifier**: Enforces that at least one valid supporting excerpt exists (`len(supporting) > 0`). If the model outputs `SUPPORTED` without excerpts, `parse_verifier_output` rejects it as a verification `ERROR`.
   - **Excerpt Validation**: Excerpts are verified against the cited source via `locate_excerpt`. Hallucinated or non-existent excerpts trigger an `ERROR`.

2. **`CONTRADICTED`**:
   - **Baseline**: Triggered when key-term overlap is met but numbers differ (`cn and sn and not (cn & sn)`) or polarity differs (`_negated(claim) != _negated(source)`).
   - **LLM Verifier**: Requires at least one valid contradicting excerpt (`len(contradicting) > 0`). A `CONTRADICTED` verdict without excerpts is rejected as an `ERROR`.

3. **`INSUFFICIENT_EVIDENCE`**:
   - Triggered when source passages lack sufficient overlap, or when claim numbers are unstated in the source.
   - **Source Conflict Handling**: When both supporting and contradicting evidence are found across sources, `conflict=True` is set, and the verdict is classified as `INSUFFICIENT_EVIDENCE` while preserving both sets of evidence.

4. **`ERROR` vs `INSUFFICIENT_EVIDENCE` (Crucial Guarantee)**:
   - System crashes, provider timeouts, HTTP 429/500/401 errors, JSON formatting errors, schema mismatches, unknown source IDs, and unlocatable excerpts are tagged as `VerificationStatus.ERROR` with `classification=None`.
   - **Under no circumstances is an ERROR classified as INSUFFICIENT_EVIDENCE**.
   - In `compute_metrics()`:
     - `errors` are counted in a separate metric.
     - `supported_claim_rate = supported / successfully_classified_claims`. Errors do not skew the numerator or denominator.
     - If all claims fail, `supported_claim_rate.value` is `None` (undefined), not 0%.
     - `verification_completion_rate = successfully_classified / total_claims`. Errors reduce this rate.

---

## 4. Prioritized Findings

### Priority 0: Critical Architecture & Resilience

#### Finding P0-1: Fragile Markdown Fencing Stripping in LLM Output Parser
- **Location**: [`app/evaluation/verify.py#L139`](file:///c:/projects/TruthLens/TruthLens/backend/app/evaluation/verify.py#L139)
- **Code**:
  ```python
  text = raw.strip()
  text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
  ```
- **Evidence & Impact**: The regex requires the string to begin exactly with ```` and end with ````. If the LLM generates any conversational preface (e.g. `Here is the verification result: ```json ... ``` Thank you!`), the regex fails, `json.loads` fails, and the claim is marked as an `ERROR`.
- **Recommendation**: Use a robust JSON extractor that searches for the first `{` and matching last `}` or extracts within the first ````json ... ```` code block.

#### Finding P0-2: Synchronous CPU-Bound Execution in Async Pipeline
- **Location**: [`app/evaluation/pipeline.py#L75-L83`](file:///c:/projects/TruthLens/TruthLens/backend/app/evaluation/pipeline.py#L75-L83)
- **Evidence & Impact**: `RuleBasedVerifier.verify` is declared `async def`, but contains purely CPU-bound string search and regex loops. Under concurrent multi-user load, running these in the main asyncio thread will block the event loop and freeze HTTP request handling.
- **Recommendation**: Wrap CPU-intensive rule-based verification and claim extraction with `asyncio.to_thread` when deploying inside the web application.

---

### Priority 1: High Priority Correctness & Adaptability

#### Finding P1-1: Exact Whitespace Regex in `locate_excerpt` Fails on Punctuation Normalization
- **Location**: [`app/evaluation/verify.py#L25-L32`](file:///c:/projects/TruthLens/TruthLens/backend/app/evaluation/verify.py#L25-L32)
- **Code**:
  ```python
  words = excerpt.split()
  pattern = r"\s+".join(re.escape(w) for w in words)
  m = re.search(pattern, source_text)
  ```
- **Evidence & Impact**: If an LLM normalizes typographical quotes (`“` to `"`), hyphens to en-dashes (`-` to `–`), or removes trailing periods, `locate_excerpt` fails. TruthLens then rejects the valid evidence and marks the entire claim as `ERROR`.
- **Recommendation**: Implement quote/dash/unicode normalization on both `source_text` and `excerpt` prior to span alignment, while retaining the true character slice of the raw source.

#### Finding P1-2: Lack of Overall Pipeline-Level Evaluation Timeout
- **Location**: [`app/evaluation/pipeline.py#L51-L84`](file:///c:/projects/TruthLens/TruthLens/backend/app/evaluation/pipeline.py#L51-L84)
- **Evidence & Impact**: While `Provider.generate_answer` enforces a per-call timeout (`timeout_s=30.0`), a pipeline evaluating 20 claims with retries (up to 3 attempts each) could take several minutes. There is no top-level timeout guarding `run_evaluation`.
- **Recommendation**: Add `pipeline_timeout_s` to `EvaluationConfig` and guard `asyncio.gather` with `asyncio.wait_for`.

#### Finding P1-3: Linear Token Inefficiency in Per-Claim Verification
- **Location**: [`app/evaluation/verify.py#L129-L134`](file:///c:/projects/TruthLens/TruthLens/backend/app/evaluation/verify.py#L129-L134)
- **Evidence & Impact**: Every claim prompts the provider with the full text of all sources (`build_prompt`). For an answer with 15 claims and 5 sources of 10,000 words, the same 10,000 words are re-sent 15 times (150,000 words). This introduces significant API latency and cost.
- **Recommendation**: Support batch verification where multiple claims are evaluated against the source documents in a single structured prompt when provider context limits allow.

---

### Priority 2: Security & Configuration

#### Finding P2-1: Generic API Key Redaction Limitations
- **Location**: [`app/core/redaction.py#L9-L17`](file:///c:/projects/TruthLens/TruthLens/backend/app/core/redaction.py#L9-L17)
- **Evidence & Impact**: `_SECRET_PATTERN` matches standard vendor key patterns (`sk-ant-`, `sk-or-`, `sk-`, `AIza`, `gsk_`, `xai-`, `Bearer`). Custom bearer tokens, basic auth passwords, or Ollama endpoint keys that do not follow these conventions will not be scrubbed if echoed in provider error messages.
- **Recommendation**: In addition to regex matching, dynamically register any environment variable containing `_KEY`, `_SECRET`, or `_TOKEN` into the redaction filter so exact configured secrets are always masked.

#### Finding P2-2: Incomplete Model Pricing Configuration
- **Location**: [`app/providers/base.py#L110-L115`](file:///c:/projects/TruthLens/TruthLens/backend/app/providers/base.py#L110-L115)
- **Evidence & Impact**: `estimate_cost` requires a tuple `(input_per_mtok, output_per_mtok)`. However, `PROVIDER_SPECS` in `config.py` does not specify pricing definitions or map model names to pricing structures. As a result, `estimated_cost_usd` is consistently `None`.
- **Recommendation**: Add an optional pricing catalog lookup based on `(provider, model)` in `config.py`.

---

### Priority 3: Code Cleanliness & Documentation

#### Finding P3-1: Rule-Based Negation in Unrelated Clauses
- **Location**: [`app/evaluation/verify.py#L70-L81`](file:///c:/projects/TruthLens/TruthLens/backend/app/evaluation/verify.py#L70-L81)
- **Evidence & Impact**: If a source sentence contains a negative word in a relative clause ("The tower, which is not in London, was built in 1889"), `_negated(sentence)` is `True`. A factual claim ("The tower was built in 1889") is falsely marked `CONTRADICTED` due to polarity mismatch.
- **Recommendation**: Document this prominently as a baseline heuristic limitation (already noted in `evaluation-methodology.md`), and refine clause extraction for compound sentences in Milestone 2.

---

## 5. Architectural Gap Analysis: Planned vs Current

| Component | Status | Existing Implementation | Missing Requirements |
|---|:---:|---|---|
| **Domain Models & Preprocessing** | Completed | `Source`, `Claim`, `Evidence`, `Verification`, `prepare_input` | None |
| **Claim Extraction** | Partial | Sentence-level rule splitter with skip tracking | Compound sentence splitting, coreference resolution, LLM extractor |
| **Verification Engine** | Completed (Core) | `RuleBasedVerifier`, `LLMVerifier`, strict parser | Batch verification, prompt-level caching |
| **Metrics & Aggregation** | Completed | `compute_metrics`, `Ratio`, zero-denominator safety | Trend metrics across multiple runs |
| **Reporting & Export** | Completed | `report_to_dict`, `report_to_json`, `report_to_csv` with formula protection | PDF export, database persistence |
| **Provider Abstraction** | Completed (Core) | `Provider`, `RetryPolicy`, `ErrorCategory`, `MockProvider` | Real HTTP adapters (OpenAI, Gemini, Groq, Ollama) |
| **API / Service Layer** | Not Started | None (`pyproject.toml` defines optional `[api]` dependencies) | FastAPI app, REST endpoints (`/health`, `/evaluations`), Pydantic request/response schemas |
| **Persistence Layer** | Not Started | None | SQLite/PostgreSQL schema, SQLAlchemy models, Alembic migrations |
| **Web Dashboard** | Not Started | None | React / Vite UI, claim breakdown view, source highlighter |

---

## 6. Recommended Next Implementation Milestone

### Milestone 1b: FastAPI Service & Persistence Layer

The evaluation core is robust, strictly tested, and decoupled from any framework. To make TruthLens operational as a service, the next smallest, highest-priority milestone is building the HTTP API wrapper and persistence layer.

#### Target Deliverables:
1. **FastAPI Application (`backend/app/main.py`)**:
   - `GET /api/health`: Health status, version, and environment check.
   - `GET /api/providers`: Configured provider statuses with masked key previews (via `provider_statuses()`).
   - `POST /api/evaluations`: Accepts `{question, answer, sources, verifier_config}`, validates input, executes `run_evaluation`, and returns the evaluation report.
   - `GET /api/evaluations/{run_id}`: Retrieves a previously stored evaluation report.
   - `GET /api/evaluations/{run_id}/export?format=csv|json`: Exports the evaluation report.
   - CORS middleware configured via `parse_origins(os.environ.get("CORS_ALLOWED_ORIGINS"))`.

2. **Persistence Layer (`backend/app/db/`)**:
   - SQLite database configuration (zero setup, ideal for development and offline testing).
   - SQLAlchemy 2.0 models for `EvaluationRecord`, `ClaimRecord`, and `VerificationRecord`.
   - CRUD repository functions for saving and loading `EvaluationReport` objects.

3. **API Integration Tests (`backend/tests/test_api.py`)**:
   - Offline FastAPI `TestClient` tests verifying endpoint status codes, validation errors, and report retrieval using `MockProvider` and `RuleBasedVerifier`.
