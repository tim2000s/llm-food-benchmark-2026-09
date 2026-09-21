#!/usr/bin/env python3
"""Token usage per request in the April 2026 batch run, by model.

The April results are in the public companion repository
tim2000s/llm-food-benchmark-academic under results/. Point APRIL_RESULTS_DIR
at that directory. The figures printed here are the ones written into
TOKEN_ASSUMPTIONS in rerun.py for the two April models.
"""
import json
import os
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

FILES = [
    "results_anthropic_batch_consolidated.json",
    "results_openai_batch_consolidated_final.json",
]


def main():
    root = Path(os.environ.get(
        "APRIL_RESULTS_DIR",
        Path.home() / "LLM-API-Tests" / "batch_analysis" / "results"))
    if not root.is_dir():
        sys.exit(f"April results not found at {root}; set APRIL_RESULTS_DIR")
    usage = defaultdict(lambda: {"in": [], "out": []})
    for name in FILES:
        for r in json.load(open(root / name))["results"]:
            if r.get("input_tokens"):
                usage[r["model"]]["in"].append(r["input_tokens"])
            if r.get("output_tokens"):
                usage[r["model"]]["out"].append(r["output_tokens"])
    for model, u in sorted(usage.items()):
        out = sorted(u["out"])
        print(f"{model}: n={len(out)}  input median {st.median(u['in']):.0f} max {max(u['in'])}  "
              f"output mean {st.mean(out):.0f} median {st.median(out):.0f} "
              f"p90 {out[int(0.9 * len(out))]} max {out[-1]}")


if __name__ == "__main__":
    main()
