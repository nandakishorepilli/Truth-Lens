# Evaluation methodology

TruthLens checks whether **supplied sources** support each claim in an answer. It does not decide what is
objectively true, and an LLM agreeing with an answer is never treated as proof.

## Pipeline
1. **Input preparation**: Unicode/newline normalization, size limits, http(s)-only URLs. URLs are stored, never fetched.
2. **Claim extraction**: the baseline splits sentences (line- and bullet-aware) and records every skipped segment with a reason
   (question, instruction, opinion, filler, too short). It does not split compound sentences or resolve pronouns.
3. **Verification**: each claim is classified `SUPPORTED`, `CONTRADICTED` or `INSUFFICIENT_EVIDENCE`, with verbatim excerpts.
   - `RuleBasedVerifier` is a **baseline**: term overlap (>= 60%, >= 2 shared terms), then number and negation checks.
     Differing numbers or polarity => contradicted; claim numbers not stated => insufficient. Known blind spots:
     paraphrase, pronouns ("It is located in Paris"), negation in unrelated clauses, units, "U.S." at sentence end.
   - `LLMVerifier` asks a provider for JSON, then validates it strictly. Excerpts must exist in the cited source
     (whitespace-flexible match; the stored excerpt is the real source span). Fabricated excerpts, unknown sources,
     SUPPORTED without evidence, bad confidence values or malformed JSON => verification **ERROR**.
4. **Aggregation**: see metric definitions below. Every ratio keeps its numerator and denominator; a zero denominator is
   `undefined` (None), not 0%.

## Rules
- Conflicting sources are exposed: both evidence lists are kept, `conflict=true`, classification `INSUFFICIENT_EVIDENCE`.
- Verification errors are never folded into `INSUFFICIENT_EVIDENCE`.
- `confidence` is `None` for the baseline; an LLM-supplied value is the model's self-report, not a calibrated probability.
- Sources and model output are untrusted data: sources sit inside delimiters (forged delimiters are neutralized), and the
  system prompt tells the model not to follow instructions inside them. This reduces, but cannot eliminate, injection risk.
- Using different models for extraction and verification does not guarantee statistical independence.

## Metrics
- `supported_claim_rate = supported / successfully_classified` (not the probability the answer is true)
- `evidence_coverage = claims_with_supporting_or_contradicting_evidence / factual_claims`
- `verification_completion_rate = successfully_classified / factual_claims`
