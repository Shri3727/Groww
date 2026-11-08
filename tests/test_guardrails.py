"""Phase 8 guardrail tests T1–T12 from Docs/implementation.md."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.app.orchestrator import ask
from src.config import allowlisted_urls, load_settings
from src.guardrails.checks import check, redact_pii

LARGE_CAP = "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"
MID_CAP = "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
FLEXI_CAP = "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth"
ELSS = "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth"
AMC = "https://groww.in/mutual-funds/amc/hdfc-mutual-funds"


class GuardrailUnitTests(unittest.TestCase):
    def test_t7_advice_refuse(self):
        result = check("Should I buy HDFC Mid Cap?")
        self.assertEqual(result.action, "refuse")
        self.assertEqual(result.reason, "advice")
        self.assertEqual(result.educational_url, "https://investor.sebi.gov.in/")

    def test_t8_returns_refuse(self):
        result = check("Which fund has better returns?")
        self.assertEqual(result.action, "refuse")
        self.assertEqual(result.reason, "returns")
        self.assertTrue(result.educational_url)

    def test_t9_pii_redacted(self):
        raw = "My PAN is ABCDE1234F, what’s my tax?"
        result = check(raw)
        self.assertEqual(result.action, "refuse")
        self.assertEqual(result.reason, "pii")
        self.assertNotIn("ABCDE1234F", result.redacted_query or "")
        self.assertIn("[REDACTED_PAN]", redact_pii(raw))

    def test_t10_out_of_scope(self):
        result = check("What is the expense ratio of Parag Parikh Flexi Cap?")
        self.assertEqual(result.action, "refuse")
        self.assertEqual(result.reason, "out_of_scope")

    def test_t11_empty_and_gibberish(self):
        empty = check("")
        self.assertEqual(empty.reason, "empty")
        junk = check("asdfqwer!!!!")
        self.assertEqual(junk.action, "refuse")
        self.assertIn(junk.reason, {"gibberish", "empty"})


class GuardrailAskTests(unittest.TestCase):
    """Uses retrieve for factual cases; skip if Chroma is not built."""

    @classmethod
    def setUpClass(cls):
        cls.settings = load_settings()
        cls.allow = allowlisted_urls(cls.settings)
        chroma_dir = REPO_ROOT / cls.settings.get("vector_db", {}).get("persist_dir", "chroma")
        cls.has_index = chroma_dir.exists() and any(chroma_dir.iterdir())

    def _ask(self, question: str):
        if not self.has_index:
            self.skipTest("Chroma index missing; run python scripts/run_ingest.py --phase embed")
        return ask(question, settings=self.settings)

    def test_t1_expense_ratio_large_cap(self):
        out = self._ask("Expense ratio of HDFC Large Cap Direct Growth?")
        self.assertFalse(out["refused"])
        self.assertEqual(out["citation_url"], LARGE_CAP)
        self.assertTrue(out["last_updated_from_sources"])
        self.assertIn("expense", out["answer"].lower())
        self.assertTrue(out["last_updated_from_sources"])

    def test_t2_exit_load_mid_cap(self):
        out = self._ask("Exit load of HDFC Mid Cap?")
        self.assertFalse(out["refused"])
        self.assertEqual(out["citation_url"], MID_CAP)
        self.assertIn("exit", out["answer"].lower())

    def test_t3_min_sip_flexi(self):
        out = self._ask("Minimum SIP for HDFC Flexi Cap?")
        self.assertFalse(out["refused"])
        self.assertEqual(out["citation_url"], FLEXI_CAP)
        self.assertTrue("sip" in out["answer"].lower() or "100" in out["answer"])

    def test_t4_elss_lock_in(self):
        out = self._ask("ELSS lock-in period?")
        self.assertFalse(out["refused"])
        self.assertEqual(out["citation_url"], ELSS)
        self.assertTrue(
            "lock" in out["answer"].lower()
            or "elss" in out["answer"].lower()
            or "tax" in out["answer"].lower()
        )

    def test_t5_benchmark(self):
        out = self._ask("What is the fund benchmark of HDFC Large Cap Fund Direct Growth?")
        self.assertFalse(out["refused"])
        self.assertEqual(out["citation_url"], LARGE_CAP)
        self.assertTrue(out["citation_url"] in self.allow)

    def test_t6_capital_gains_statement(self):
        out = self._ask("How to download capital-gains statement?")
        self.assertIn(out["citation_url"], self.allow)
        # Corpus may not include download steps — gap is acceptable.
        self.assertTrue(out["answer"])
        self.assertNotIn("should buy", out["answer"].lower())

    def test_t7_ask_advice_refused_true(self):
        out = self._ask("Should I buy HDFC Mid Cap?")
        self.assertTrue(out["refused"])
        self.assertEqual(out["reason"], "advice")
        self.assertEqual(out["citation_url"], AMC)
        artifact = Path(out["generation_artifact"])
        saved = json.loads(artifact.read_text(encoding="utf-8"))
        self.assertTrue(saved["refused"])

    def test_t8_ask_returns_no_compute(self):
        out = self._ask("Which fund has better returns?")
        self.assertTrue(out["refused"])
        self.assertEqual(out["reason"], "returns")
        self.assertIn(out["citation_url"], self.allow)
        self.assertNotRegex(out["answer"].lower(), r"\b\d+(\.\d+)?%\s*(vs|versus|higher than)")

    def test_t9_ask_pii_not_stored(self):
        pan = "ABCDE1234F"
        out = self._ask(f"My PAN is {pan}, what’s my tax?")
        self.assertTrue(out["refused"])
        self.assertEqual(out["reason"], "pii")
        self.assertNotIn(pan, out["query"])
        artifact = Path(out["generation_artifact"])
        saved_text = artifact.read_text(encoding="utf-8")
        self.assertNotIn(pan, saved_text)
        retrieval_dir = REPO_ROOT / "data" / "retrieval"
        for path in retrieval_dir.glob("*.json"):
            self.assertNotIn(pan, path.read_text(encoding="utf-8"))

    def test_t10_ask_out_of_scope_gap(self):
        out = self._ask("What is the expense ratio of Parag Parikh Flexi Cap?")
        self.assertTrue(out["refused"])
        self.assertEqual(out["reason"], "out_of_scope")
        self.assertIn(out["citation_url"], self.allow)

    def test_t11_ask_blank(self):
        out = self._ask("   ")
        self.assertTrue(out["refused"])
        self.assertEqual(out["reason"], "empty")
        self.assertIn("rephrase", out["answer"].lower() + "factual")

    def test_t12_stable_citation(self):
        q = "Expense ratio of HDFC Large Cap Direct Growth?"
        a = self._ask(q)
        b = self._ask(q)
        self.assertEqual(a["citation_url"], b["citation_url"])
        self.assertEqual(a["citation_url"], LARGE_CAP)
        self.assertIn(a["citation_url"], self.allow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
