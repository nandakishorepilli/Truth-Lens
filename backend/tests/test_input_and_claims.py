import unittest

from app.evaluation.claims import extract_claims
from app.evaluation.models import InputError, Source, prepare_input


class InputTests(unittest.TestCase):
    def test_empty_inputs_rejected(self):
        src = [{"text": "x y z"}]
        for q, a, s in [("", "a b c", src), ("q", "  ", src), ("q", "a b c", []), ("q", "a b c", [{"text": " "}])]:
            with self.assertRaises(InputError):
                prepare_input(q, a, s)

    def test_limits_urls_and_duplicate_ids(self):
        with self.assertRaises(InputError):
            prepare_input("q" * 2001, "a b c", [{"text": "t"}])
        with self.assertRaises(InputError):
            prepare_input("q", "a b c", [{"text": "t", "url": "javascript:alert(1)"}])
        with self.assertRaises(InputError):
            prepare_input("q", "a b c", [{"id": "A", "text": "t"}, {"id": "A", "text": "u"}])

    def test_normalization_and_default_ids(self):
        p = prepare_input(" q ", "a\r\nb c\x00", [Source("X", "t"), {"text": "u", "url": "https://e.com"}])
        self.assertEqual((p.question, p.answer), ("q", "a\nb c"))
        self.assertEqual([s.id for s in p.sources], ["X", "S2"])


class ClaimTests(unittest.TestCase):
    def test_positions_map_back_and_wording_is_preserved(self):
        ans = "The bridge, which may have opened in 1932, carries 3.5 million cars. It is likely safe."
        r = extract_claims(ans)
        self.assertEqual(len(r.claims), 2)
        for c in r.claims:
            self.assertEqual(ans[c.position:c.position + len(c.text)], c.text)
        self.assertIn("may have opened in 1932", r.claims[0].text)
        self.assertIn("3.5 million", r.claims[0].text)

    def test_non_factual_segments_are_skipped_with_reasons(self):
        r = extract_claims("Is it tall? Please check the height.\n- I think it is lovely.\n- It is 330 metres tall.")
        self.assertEqual([c.text for c in r.claims], ["It is 330 metres tall."])
        reasons = {s.text: s.reason for s in r.skipped}
        self.assertIn("Question", reasons["Is it tall?"])
        self.assertIn("Instruction", reasons["Please check the height."])
        self.assertIn("Opinion", reasons["I think it is lovely."])

    def test_abbreviations_do_not_split(self):
        r = extract_claims("Dr. Smith measured 3.5 metres. The U.S. team agreed with him.")
        self.assertEqual([c.text for c in r.claims],
                         ["Dr. Smith measured 3.5 metres.", "The U.S. team agreed with him."])

    def test_empty_answer_has_no_claims(self):
        r = extract_claims("")
        self.assertEqual((r.claims, r.skipped), ([], []))


if __name__ == "__main__":
    unittest.main()
