"""Tests for the September 2026 rerun: arm-specific requests, result reading
for reasoning models, resume bookkeeping and the averaging check."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic_batch_runner as ant
import openai_batch_runner as oai
import averaging_check as avg
import rerun
from arms import ARMS, get_arm
from batch_common import build_result_dicts, make_id_mapping

GOOD_JSON = json.dumps({
    "image_type": "food_photo",
    "brief_description": "toast",
    "food_items": [{"name": "toast", "portion_estimate_size": 50, "carbs_per_100": 40}],
})


class TestArmRequests(unittest.TestCase):
    def test_no_arm_sends_temperature(self):
        # Every arm runs at the provider default; fable-5-1 and gpt-6-astra reject it outright.
        for name, arm in ARMS.items():
            mod = ant if arm["provider"] == "claude" else oai
            req = mod.build_request(get_arm(name), "idx0", "AAAA")
            body = req.get("params") or req.get("body")
            self.assertNotIn("temperature", body, name)

    def test_fable_request(self):
        p = ant.build_request(get_arm("fable-5-1"), "idx0", "AAAA")["params"]
        self.assertEqual(p["model"], "claude-fable-5-1")
        self.assertEqual(p["output_config"], {"effort": "low"})
        self.assertNotIn("thinking", p)
        self.assertEqual([c["type"] for c in p["messages"][0]["content"]], ["text", "image"])

    def test_sonnet_default_matches_april_except_temperature(self):
        p = ant.build_request(get_arm("sonnet-4-6-default"), "idx0", "AAAA")["params"]
        self.assertEqual(p["max_tokens"], 8000)
        self.assertNotIn("output_config", p)
        self.assertNotIn("thinking", p)

    def test_astra_request(self):
        b = oai.build_request(get_arm("gpt-6-astra"), "idx0", "AAAA")["body"]
        self.assertEqual(b["model"], "gpt-6-astra")
        self.assertEqual(b["reasoning"], {"effort": "low"})
        self.assertFalse(b["store"])

    def test_gpt54_default_has_no_reasoning_override(self):
        b = oai.build_request(get_arm("gpt-5-4-default"), "idx0", "AAAA")["body"]
        self.assertNotIn("reasoning", b)
        self.assertEqual(b["max_output_tokens"], 6000)

    def test_explicit_temperature_is_passed_through(self):
        arm = dict(get_arm("sonnet-4-6-default"), temperature=0.01)
        self.assertEqual(ant.build_request(arm, "idx0", "AAAA")["params"]["temperature"], 0.01)


def _ant_result(content, stop_reason="end_turn", rtype="succeeded", stop_details=None):
    msg = NS(content=content, stop_reason=stop_reason, stop_details=stop_details,
             usage=NS(input_tokens=3000, output_tokens=900), model="claude-fable-5-1")
    return NS(custom_id="idx0", result=NS(type=rtype, message=msg, error="boom"))


class TestAnthropicResults(unittest.TestCase):
    def test_text_after_thinking_block_is_read(self):
        r = _ant_result([NS(type="thinking", thinking=""), NS(type="text", text=GOOD_JSON)])
        item = ant.item_from_result(r)
        self.assertEqual(item["raw_text"], GOOD_JSON)
        self.assertIsNone(item["api_error"])

    def test_refusal_is_a_failure_not_a_parse(self):
        r = _ant_result([], stop_reason="refusal", stop_details=NS(category="bio"))
        item = ant.item_from_result(r)
        self.assertEqual(item["api_error_class"], "refusal")
        self.assertIn("bio", item["api_error"])

    def test_errored_result(self):
        item = ant.item_from_result(_ant_result([], rtype="errored"))
        self.assertEqual(item["api_error_class"], "api")

    def test_max_tokens_stop_is_recorded(self):
        r = _ant_result([NS(type="text", text="{\"food_items\": [")], stop_reason="max_tokens")
        self.assertEqual(ant.item_from_result(r)["extra"]["stop_reason"], "max_tokens")


class TestOpenAIResults(unittest.TestCase):
    def _line(self, output, status="completed", usage=None, status_code=200):
        return {"custom_id": "idx0", "response": {"status_code": status_code, "body": {
            "status": status, "model": "gpt-6-astra-2026-09-03", "output": output,
            "usage": usage or {"input_tokens": 4500, "output_tokens": 1200,
                               "output_tokens_details": {"reasoning_tokens": 400}},
        }}}

    def test_text_and_reasoning_tokens(self):
        line = self._line([
            {"type": "reasoning", "summary": []},
            {"type": "message", "content": [{"type": "output_text", "text": GOOD_JSON}]},
        ])
        item = oai.item_from_line(line)
        self.assertEqual(item["raw_text"], GOOD_JSON)
        self.assertEqual(item["extra"]["reasoning_tokens"], 400)
        self.assertEqual(item["usage"]["output_tokens"], 1200)

    def test_refusal(self):
        line = self._line([{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}])
        self.assertEqual(oai.item_from_line(line)["api_error_class"], "refusal")

    def test_error_file_line(self):
        line = {"custom_id": "idx3", "response": None,
                "error": {"code": "invalid_request", "message": "temperature not supported"}}
        item = oai.item_from_line(line)
        self.assertEqual(item["api_error_class"], "api")
        self.assertIn("temperature", item["api_error"])

    def test_incomplete_is_recorded(self):
        line = self._line([], status="incomplete")
        line["response"]["body"]["incomplete_details"] = {"reason": "max_output_tokens"}
        item = oai.item_from_line(line)
        self.assertEqual(item["extra"]["stop_reason"], "incomplete")
        self.assertEqual(item["extra"]["incomplete_reason"], "max_output_tokens")


class TestParser(unittest.TestCase):
    def test_malformed_json_is_a_parse_failure_not_zero_grams(self):
        # Fable 5.1 dropped a key's opening quote; the brace scan then found a
        # single food item and the April parser scored it as an empty success.
        raw = ('{"image_type": "food_photo", "food_items": [{"name": "stuffing", '
               '"carbs_per_100": 20, "portion_estimate_size": 130},\n'
               '{"name": "pork",\nassessment_notes": "x"}]}').replace("\\n", "\n")
        from food_nutrition_benchmark import parse_response
        qr = parse_response(raw, "m", "claude", "a.jpg", 1, 0.0)
        self.assertFalse(qr.success)
        self.assertEqual(qr.error_class, "parse")

    def test_valid_response_still_parses(self):
        from food_nutrition_benchmark import parse_response
        qr = parse_response(GOOD_JSON, "m", "claude", "a.jpg", 1, 0.0)
        self.assertTrue(qr.success)
        self.assertEqual(len(qr.food_items), 1)


class TestResultRows(unittest.TestCase):
    def test_extras_reach_the_row(self):
        _, id_map = make_id_mapping([(1, "a.jpg")])
        items = [{"custom_id": "idx0", "raw_text": GOOD_JSON, "usage": None,
                  "api_error": None, "api_error_class": None,
                  "extra": {"stop_reason": "end_turn", "reasoning_tokens": 7}}]
        row = build_result_dicts(items, "m", "openai", id_map)[0]
        self.assertTrue(row["success"])
        self.assertEqual(row["stop_reason"], "end_turn")
        self.assertEqual(row["reasoning_tokens"], 7)
        self.assertEqual(row["raw_response"], GOOD_JSON)

    def test_refusal_row_is_unsuccessful(self):
        _, id_map = make_id_mapping([(1, "a.jpg")])
        items = [{"custom_id": "idx0", "raw_text": None, "usage": None,
                  "api_error": "refusal: category=None", "api_error_class": "refusal"}]
        row = build_result_dicts(items, "m", "claude", id_map)[0]
        self.assertFalse(row["success"])
        self.assertEqual(row["error_class"], "refusal")


class TestResume(unittest.TestCase):
    def test_abandoned_chunks_do_not_count_as_covered(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(rerun, "RESULTS_DIR", Path(d)):
                sdir = rerun.state_dir("x")
                sdir.mkdir(parents=True)
                _, live = make_id_mapping([(1, "a.jpg"), (1, "b.jpg")])
                _, dead = make_id_mapping([(2, "a.jpg")])
                (sdir / "chunk_1.json").write_text(json.dumps({"status": "submitted", "batch_id": "b1", "id_map": live}))
                (sdir / "chunk_2.json").write_text(json.dumps({"status": "abandoned", "batch_id": "b2", "id_map": dead}))
                self.assertEqual(rerun.covered_pairs("x"), {(1, "a.jpg"), (1, "b.jpg")})

    def _downloaded(self, d, rows_by_batch):
        """Write downloaded chunks and their results files; rows are (it, img, success, error_class)."""
        sdir = rerun.state_dir("x")
        sdir.mkdir(parents=True, exist_ok=True)
        for bid, rows in rows_by_batch.items():
            _, id_map = make_id_mapping([(it, img) for it, img, *_ in rows])
            (sdir / f"chunk_{bid}.json").write_text(json.dumps(
                {"status": "downloaded", "batch_id": bid, "id_map": id_map}))
            (rerun.arm_dir("x") / f"results_{bid}.json").write_text(json.dumps({"results": [
                {"iteration": it, "image_file": img, "success": ok, "error_class": ec}
                for it, img, ok, ec in rows]}))

    def test_api_errors_are_retried_but_refusals_and_parse_failures_are_not(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(rerun, "RESULTS_DIR", Path(d)):
            self._downloaded(d, {"b1": [(1, "a.jpg", True, None), (2, "a.jpg", False, "api"),
                                        (3, "a.jpg", False, "refusal"), (4, "a.jpg", False, "parse")]})
            self.assertEqual(rerun.covered_pairs("x"), {(1, "a.jpg"), (3, "a.jpg"), (4, "a.jpg")})

    def test_api_error_that_later_succeeded_is_covered(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(rerun, "RESULTS_DIR", Path(d)):
            self._downloaded(d, {"b1": [(2, "a.jpg", False, "api")], "b2": [(2, "a.jpg", True, None)]})
            self.assertEqual(rerun.covered_pairs("x"), {(2, "a.jpg")})

    def test_chunk_size_respects_cap_and_payload(self):
        arm = get_arm("fable-5-1")
        small = rerun.chunk_size(ant, arm, {"a": "A" * 1000}, cap=50)
        self.assertEqual(small, 50)
        big = rerun.chunk_size(ant, arm, {"a": "A" * 10_000_000}, cap=1000)
        self.assertEqual(big, 15)


class TestAveraging(unittest.TestCase):
    def _totals(self, values):
        return {"img.jpg": list(values)}

    def test_identical_arms_get_identical_results(self):
        rng = np.random.default_rng(0)
        vals = rng.normal(40, 8, 50)
        res = avg.analyse({"a": self._totals(vals), "b": self._totals(vals)}, {})
        for k in res["ks"]:
            self.assertEqual(res["per_image"]["img.jpg"]["k"][k]["a"],
                             res["per_image"]["img.jpg"]["k"][k]["b"])

    def test_draws_are_shared_across_arms(self):
        # b is a shifted by a constant, so with shared draws its spread is identical.
        vals = np.random.default_rng(1).normal(40, 8, 50)
        res = avg.analyse({"a": self._totals(vals), "b": self._totals(vals + 10)}, {})
        for k in res["ks"]:
            cell = res["per_image"]["img.jpg"]["k"][k]
            self.assertAlmostEqual(cell["a"]["sd_g"], cell["b"]["sd_g"], places=9)

    def test_median_of_more_calls_narrows_spread(self):
        vals = np.random.default_rng(2).normal(40, 8, 50)
        res = avg.analyse({"a": self._totals(vals)}, {})
        sds = [res["per_image"]["img.jpg"]["k"][k]["a"]["sd_g"] for k in res["ks"]]
        self.assertGreater(sds[0], sds[1])
        self.assertGreater(sds[1], sds[2])

    def test_common_n_truncates_to_first_calls(self):
        # b succeeded only 5 times, so a contributes its first 5 calls and not the later 99s.
        res = avg.analyse({"a": self._totals([10.0] * 5 + [99.0] * 45), "b": self._totals([10.0] * 5)},
                          {"img.jpg": {"total_portion_carbs_g": 10}})
        self.assertEqual(res["summary"][1]["a"]["mean_mae_g"], 0.0)
        self.assertEqual(res["per_image"]["img.jpg"]["n_common"], 5)
        self.assertEqual(res["per_image"]["img.jpg"]["k"][5]["a"]["sd_g"], 0.0)
        self.assertEqual(res["per_image"]["img.jpg"]["k"][3]["a"]["p5_p95_width_g"], 0.0)

    def test_mae_against_reference(self):
        res = avg.analyse({"a": self._totals([30.0] * 10)}, {"img.jpg": {"total_portion_carbs_g": 40}})
        self.assertAlmostEqual(res["summary"][1]["a"]["mean_mae_g"], 10.0)

    def test_total_carbs_definition(self):
        self.assertAlmostEqual(avg.total_carbs_g([
            {"carbs_per_100": 40, "portion_estimate_size": 50},
            {"carbs_per_100": None, "portion_estimate_size": 100},
        ]), 20.0)

    def test_totals_skip_failures_and_order_by_iteration(self):
        rows = [
            {"image_file": "i", "iteration": 2, "success": True,
             "food_items": [{"carbs_per_100": 100, "portion_estimate_size": 20}]},
            {"image_file": "i", "iteration": 1, "success": True,
             "food_items": [{"carbs_per_100": 100, "portion_estimate_size": 10}]},
            {"image_file": "i", "iteration": 3, "success": False, "food_items": []},
        ]
        self.assertEqual(avg.totals_by_image(rows), {"i": [10.0, 20.0]})


if __name__ == "__main__":
    unittest.main()


class FakeProvider:
    """Stands in for a provider module's Provider. The first batch can be made
    to fail on the enqueued-token limit, as an OpenAI organisation limit would."""

    def __init__(self, fail_first_on_token_limit=False):
        self.batches = {}
        self.fail_next = fail_first_on_token_limit

    def submit(self, requests, state_dir, label):
        bid = f"b{len(self.batches)}"
        self.batches[bid] = {"requests": requests, "token_limit": self.fail_next}
        self.fail_next = False
        return {"batch_id": bid}

    def poll(self, batch_id):
        tl = self.batches[batch_id]["token_limit"]
        return {"finished": True, "text": "done", "token_limit": tl, "failed": tl}

    def fetch(self, batch_id):
        return [{"custom_id": r["custom_id"], "raw_text": GOOD_JSON, "usage": None,
                 "api_error": None, "api_error_class": None, "extra": {"stop_reason": "end_turn"}}
                for r in self.batches[batch_id]["requests"]]


class TestRunArm(unittest.TestCase):
    def _run(self, arm, provider, iterations=3, cap=1000):
        mod = ant if get_arm(arm)["provider"] == "claude" else oai
        with mock.patch.object(mod, "Provider", lambda key: provider), \
             mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "x", "OPENAI_API_KEY": "x"}), \
             mock.patch.object(rerun, "preload_image_data", lambda imgs, p, q: {i.name: "AAAA" for i in imgs}), \
             mock.patch.object(rerun, "TOKEN_LIMIT_BACKOFF_SEC", 0):
            rerun.run_arm(arm, iterations, cap)

    def _rows(self, arm):
        rows = []
        for f in (rerun.RESULTS_DIR / arm).glob("results_*.json"):
            rows += json.load(open(f))["results"]
        return rows

    def test_every_pair_once_and_rerun_submits_nothing(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(rerun, "RESULTS_DIR", Path(d)):
            fake = FakeProvider()
            self._run("fable-5-1", fake, iterations=3, cap=10)
            rows = self._rows("fable-5-1")
            n_images = len(rerun.discover_images())
            self.assertEqual(len(rows), 3 * n_images)
            self.assertEqual(len({(r["iteration"], r["image_file"]) for r in rows}), 3 * n_images)
            self.assertTrue(all(r["success"] for r in rows))
            n_batches = len(fake.batches)
            self._run("fable-5-1", fake, iterations=3, cap=10)
            self.assertEqual(len(fake.batches), n_batches)
            meta = json.load(open(next((rerun.RESULTS_DIR / "fable-5-1").glob("results_*.json"))))["meta"]
            self.assertEqual(meta["arm"]["model"], "claude-fable-5-1")

    def test_token_limit_resubmits_smaller_and_loses_nothing(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(rerun, "RESULTS_DIR", Path(d)):
            fake = FakeProvider(fail_first_on_token_limit=True)
            self._run("gpt-6-astra", fake, iterations=2, cap=26)
            rows = self._rows("gpt-6-astra")
            n_images = len(rerun.discover_images())
            self.assertEqual(sorted((r["iteration"], r["image_file"]) for r in rows),
                             sorted(rerun.all_pairs(2, rerun.discover_images())))
            self.assertEqual(len(rows), 2 * n_images)
            sizes = [len(b["requests"]) for b in fake.batches.values()]
            self.assertEqual(sizes[0], 26)
            self.assertLessEqual(max(sizes[1:]), 13)
            states = [json.load(open(f))["status"] for f in rerun.state_dir("gpt-6-astra").glob("chunk_*.json")]
            self.assertEqual(states.count("abandoned"), 1)
