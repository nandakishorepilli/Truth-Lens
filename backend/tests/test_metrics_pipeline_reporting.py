import asyncio
import csv
import io
import json
import unittest

from app.core.config import parse_origins, provider_statuses
from app.core.redaction import mask_key, redact_headers, redact_secrets
from app.evaluation.metrics import compute_metrics
from app.evaluation.models import Classification, Evidence, InputError, Verification, VerificationStatus
from app.evaluation.pipeline import EvaluationConfig, run_evaluation
from app.evaluation.verify import RuleBasedVerifier
from app.reporting.export import CSV_COLUMNS, report_to_csv, report_to_dict, report_to_json
from tests.helpers import TOWER, run

OK = VerificationStatus.CLASSIFIED


def V(cls, ev=False, conflict=False):
    e = [Evidence("S1", "x", 0, 1)] if ev else []
    return Verification("C", OK, cls, e if cls == Classification.SUPPORTED else [],
                        e if cls == Classification.CONTRADICTED else [], conflict=conflict)


class MetricTests(unittest.TestCase):
    def test_zero_denominators_are_undefined_not_zero(self):
        m = compute_metrics(0, [])
        for r in (m.supported_claim_rate, m.evidence_coverage, m.verification_completion_rate):
            self.assertIsNone(r.value)

    def test_all_errors_leave_supported_rate_undefined(self):
        errs = [Verification("C", VerificationStatus.ERROR, error="x")] * 3
        m = compute_metrics(3, errs)
        self.assertEqual((m.errors, m.insufficient_evidence), (3, 0))
        self.assertIsNone(m.supported_claim_rate.value)
        self.assertEqual(m.verification_completion_rate.value, 0.0)

    def test_formulas_and_denominators(self):
        vs = [V(Classification.SUPPORTED, True), V(Classification.SUPPORTED, True), V(Classification.CONTRADICTED, True),
              V(Classification.INSUFFICIENT_EVIDENCE), Verification("C", VerificationStatus.ERROR, error="e")]
        m = compute_metrics(5, vs)
        self.assertEqual((m.supported_claim_rate.numerator, m.supported_claim_rate.denominator), (2, 4))
        self.assertEqual((m.evidence_coverage.numerator, m.evidence_coverage.denominator), (3, 5))
        self.assertEqual(m.verification_completion_rate.value, 0.8)


class PipelineTests(unittest.TestCase):
    ANSWER = "The Eiffel Tower was completed in 1889. It was completed in 1925? Not sure. The tower is 330 metres tall."

    def evaluate(self, answer, **kw):
        return run(run_evaluation("When was it built?", answer, [TOWER], verifier=RuleBasedVerifier(), **kw))

    def test_end_to_end_and_stage_order(self):
        seen = []
        r = self.evaluate("The Eiffel Tower was completed in 1925. The tower is 330 metres tall.",
                          on_stage=lambda s, st: seen.append((s, st)))
        self.assertEqual(r.status, "completed")
        self.assertEqual([v.classification for v in r.verifications],
                         [Classification.CONTRADICTED, Classification.SUPPORTED])
        self.assertEqual([s for s, st in seen if st == "done"],
                         ["input_preparation", "claim_extraction", "evidence_verification", "aggregation"])

    def test_invalid_input_raises_before_any_record(self):
        with self.assertRaises(InputError):
            run(run_evaluation("", "a b c", [TOWER], verifier=RuleBasedVerifier()))

    def test_crashing_verifier_yields_errors_and_honest_status(self):
        class Boom:
            name = "boom"
            async def verify(self, claim, sources):
                raise RuntimeError("kaput sk-abcdefghijklmnopqrstuvwxyz")
        r = run(run_evaluation("q", "The tower is 330 metres tall. It stands in Paris, France.", [TOWER], verifier=Boom()))
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.metrics.errors, 2)
        self.assertNotIn("sk-abcdefghijkl", r.verifications[0].error)

    def test_partial_failure_is_completed_with_errors(self):
        class Flaky:
            name = "flaky"
            async def verify(self, claim, sources):
                if claim.id == "C1":
                    raise RuntimeError("x")
                return await RuleBasedVerifier().verify(claim, sources)
        r = run(run_evaluation("q", "The tower is 330 metres tall. The Eiffel Tower was completed in 1889.", [TOWER], verifier=Flaky()))
        self.assertEqual((r.status, r.metrics.errors), ("completed_with_errors", 1))

    def test_concurrency_is_bounded(self):
        state = {"now": 0, "peak": 0}
        class Slow:
            name = "slow"
            async def verify(self, claim, sources):
                state["now"] += 1
                state["peak"] = max(state["peak"], state["now"])
                await asyncio.sleep(0.01)
                state["now"] -= 1
                return Verification(claim.id, OK, Classification.INSUFFICIENT_EVIDENCE)
        answer = " ".join(f"Statement number {i} is recorded here." for i in range(10))
        run(run_evaluation("q", answer, [TOWER], verifier=Slow(), config=EvaluationConfig(max_concurrency=2)))
        self.assertEqual(state["peak"], 2)


class ReportingAndSecurityTests(unittest.TestCase):
    def report(self, answer="The Eiffel Tower was completed in 1889. The tower is 330 metres tall."):
        return run(run_evaluation("q", answer, [TOWER], verifier=RuleBasedVerifier()))

    def test_csv_escapes_formulas_and_quotes(self):
        r = self.report()
        r.claims[1] = type(r.claims[1])("C2", '=HYPERLINK("http://evil"), "quoted"\nline', 50)
        rows = list(csv.reader(io.StringIO(report_to_csv(r))))
        self.assertEqual(rows[0], CSV_COLUMNS)
        self.assertTrue(rows[2][1].startswith("'="))
        self.assertIn('"quoted"\nline', rows[2][1])

    def test_json_has_definitions_limitations_and_config(self):
        d = json.loads(report_to_json(self.report()))
        self.assertIn("supported_claim_rate", d["metric_definitions"])
        self.assertTrue(d["limitations"])
        self.assertEqual(d["config"]["verifier"], "rule_based_baseline")
        self.assertEqual(d["verifications"][0]["classification"], "SUPPORTED")

    def test_exports_never_contain_secrets(self):
        r = self.report("My key is sk-abcdefghijklmnopqrstuvwxyz1234 and the tower is 330 metres tall.")
        for out in (report_to_json(r), report_to_csv(r)):
            self.assertNotIn("sk-abcdefghijkl", out)
        self.assertNotIn("sk-abcdefghijkl", json.dumps(report_to_dict(r)))

    def test_redaction_patterns_and_masking(self):
        text = "k1 sk-ant-abcdefgh12345 k2 AIzaSyA1234567890abcdefghij k3 gsk_abcdefghijklmnop1234 Bearer abc.def-ghi12345"
        self.assertEqual(redact_secrets(text).count("[REDACTED]"), 4)
        self.assertEqual(redact_headers({"Authorization": "Bearer x", "Accept": "json"})["Authorization"], "[REDACTED]")
        self.assertEqual(mask_key("sk-abcdefghijklmnop"), "••••mnop")
        self.assertEqual(mask_key("short"), "••••")
        self.assertIsNone(mask_key(None))

    def test_provider_status_never_exposes_raw_keys_and_app_starts_unconfigured(self):
        env = {"OPENAI_API_KEY": "sk-supersecretvalue1234567890", "OPENAI_MODEL": "m1"}
        statuses = provider_statuses(env)
        self.assertNotIn("supersecret", json.dumps(statuses))
        self.assertEqual({s["provider"]: s["configured"] for s in statuses}["openai"], True)
        self.assertFalse(any(s["configured"] for s in provider_statuses({})))

    def test_cors_wildcard_rejected(self):
        self.assertEqual(parse_origins("http://localhost:5173, https://a.example"), ["http://localhost:5173", "https://a.example"])
        with self.assertRaises(ValueError):
            parse_origins("*")


if __name__ == "__main__":
    unittest.main()
