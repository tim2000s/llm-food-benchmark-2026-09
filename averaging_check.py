#!/usr/bin/env python3
"""How much does taking the median of k calls narrow the spread of estimates?

An app can send the same photograph k times and use the median answer. This
measures what that buys without any new API calls, by resampling the calls
already made: for each photograph, R random subsets of k calls are drawn, the
median total carbohydrate of each subset is taken, and the spread of those
medians is compared with the spread of single calls (k = 1).

The subsets are drawn once per photograph and k, as positions in the list of
calls, and the same positions are used for every arm. Each arm contributes its
first n successful calls by iteration number, where n is the smallest count of
successful calls any arm has for that photograph, so the positions mean the
same thing in every arm. Differences between arms then come from the models
and not from which draws each happened to get.

Total carbohydrate is the April definition (deep_dive_batch.total_carbs_g):
the sum over food items of carbs_per_100 x portion_estimate_size / 100.

    python3 averaging_check.py                   # the rerun arms
    python3 averaging_check.py --april           # plus the April runs at temperature 0.01
    python3 averaging_check.py --exclude MVIMG_20260222_204918.jpg --tag no_churros

A photograph on which one arm mostly fails to parse still enters the table,
but every arm is cut to that arm's few successes there; --exclude drops it
so the other photographs keep their full count, and --tag keeps the two
outputs apart.

Writes output/averaging_check.json and output/AVERAGING_CHECK.md.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
OUT_DIR = BASE_DIR / "output"
SEED = 20260921
DEFAULT_KS = (1, 3, 5)
DEFAULT_DRAWS = 2000

APRIL_FILES = {
    "sonnet-4-6-april": "results_anthropic_batch_consolidated.json",
    "gpt-5-4-april": "results_openai_batch_consolidated_final.json",
}


def total_carbs_g(food_items: list[dict]) -> float:
    return sum((fi.get("carbs_per_100") or 0) * (fi.get("portion_estimate_size") or 0) / 100
               for fi in (food_items or []))


def load_rerun_arm(arm: str) -> list[dict]:
    rows = []
    for f in sorted((RESULTS_DIR / arm).glob("results_*.json")):
        rows += json.load(open(f))["results"]
    return rows


def load_april(root: Path) -> dict[str, list[dict]]:
    return {label: json.load(open(root / name))["results"] for label, name in APRIL_FILES.items()}


def totals_by_image(rows: list[dict]) -> dict[str, list[float]]:
    """Successful totals per image, ordered by iteration, one per iteration."""
    by = defaultdict(dict)
    for r in rows:
        if r.get("success"):
            by[r["image_file"]].setdefault(r["iteration"], total_carbs_g(r.get("food_items")))
    return {img: [v for _, v in sorted(its.items())] for img, its in by.items()}


def draw_positions(n: int, k: int, draws: int, rng: np.random.Generator) -> np.ndarray:
    """`draws` subsets of k distinct positions out of n, shape (draws, k)."""
    return np.argsort(rng.random((draws, n)), axis=1)[:, :k]


def analyse(arm_totals: dict[str, dict[str, list[float]]], reference: dict,
            ks=DEFAULT_KS, draws=DEFAULT_DRAWS, seed=SEED) -> dict:
    rng = np.random.default_rng(seed)
    arms = sorted(arm_totals)
    images = sorted(set.intersection(*(set(t) for t in arm_totals.values())))
    per_image = {}
    for img in images:
        n = min(len(arm_totals[a][img]) for a in arms)
        ref = (reference.get(img) or {}).get("total_portion_carbs_g")
        entry = {"n_common": n, "reference_g": ref, "k": {}}
        for k in ks:
            if k > n:
                continue
            pos = draw_positions(n, k, draws, rng)
            entry["k"][k] = {}
            for a in arms:
                vals = np.asarray(arm_totals[a][img][:n])
                medians = np.median(vals[pos], axis=1)
                p5, p95 = np.percentile(medians, [5, 95])
                entry["k"][k][a] = {
                    "sd_g": float(np.std(medians, ddof=1)),
                    "p5_p95_width_g": float(p95 - p5),
                    "mae_g": float(np.mean(np.abs(medians - ref))) if ref is not None else None,
                }
        per_image[img] = entry

    summary = {}
    for k in ks:
        summary[k] = {}
        for a in arms:
            cells = [per_image[i]["k"][k][a] for i in images if k in per_image[i]["k"]]
            maes = [c["mae_g"] for c in cells if c["mae_g"] is not None]
            summary[k][a] = {
                "median_sd_g": float(np.median([c["sd_g"] for c in cells])),
                "median_width_g": float(np.median([c["p5_p95_width_g"] for c in cells])),
                "mean_mae_g": float(np.mean(maes)) if maes else None,
                "n_images": len(cells),
            }
    return {"seed": seed, "draws": draws, "ks": list(ks), "arms": arms,
            "summary": summary, "per_image": per_image}


def write_report(res: dict, path: Path) -> None:
    arms, ks = res["arms"], res["ks"]
    lines = [
        "# Median of k calls against a single call",
        "",
        f"Resampled from the calls already made: {res['draws']} subsets of k calls per photograph, "
        f"the same subsets for every arm, seed {res['seed']}. Each cell is the median across "
        "photographs of the spread of the k-call median, in grams of carbohydrate. The width is "
        "the distance between the 5th and 95th percentiles, so nine answers in ten fall inside it. "
        "Mean absolute error is against the reference values in usda_reference.json."
        + (f" Excluded: {', '.join(res['excluded'])}." if res.get("excluded") else ""),
        "",
        "| arm | k | SD (g) | 5-95% width (g) | mean abs. error (g) |",
        "|---|---|---|---|---|",
    ]
    for a in arms:
        for k in ks:
            s = res["summary"][k][a]
            mae = f"{s['mean_mae_g']:.1f}" if s["mean_mae_g"] is not None else "n/a"
            lines.append(f"| {a} | {k} | {s['median_sd_g']:.1f} | {s['median_width_g']:.1f} | {mae} |")
    lines += ["", "## By photograph, 5-95% width (g)", "",
              "| photograph | n | ref (g) | " + " | ".join(f"{a} k={k}" for a in arms for k in ks) + " |",
              "|---|---|---|" + "---|" * (len(arms) * len(ks))]
    for img, e in res["per_image"].items():
        cells = [f"{e['k'][k][a]['p5_p95_width_g']:.1f}" if k in e["k"] else "" for a in arms for k in ks]
        ref = f"{e['reference_g']}" if e["reference_g"] is not None else "n/a"
        lines.append(f"| {img} | {e['n_common']} | {ref} | " + " | ".join(cells) + " |")
    path.write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arms", nargs="*",
                    default=sorted(p.name for p in RESULTS_DIR.glob("*") if p.is_dir()))
    ap.add_argument("--april", action="store_true", help="include the April runs at temperature 0.01")
    ap.add_argument("--april-dir", type=Path, default=Path(os.environ.get(
        "APRIL_RESULTS_DIR", Path.home() / "LLM-API-Tests" / "batch_analysis" / "results")))
    ap.add_argument("--draws", type=int, default=DEFAULT_DRAWS)
    ap.add_argument("--exclude", nargs="*", default=[], help="photographs to leave out")
    ap.add_argument("--tag", default="", help="suffix for the output file names")
    args = ap.parse_args()

    arm_totals = {a: totals_by_image(load_rerun_arm(a)) for a in args.arms}
    if args.april:
        arm_totals.update({a: totals_by_image(rows) for a, rows in load_april(args.april_dir).items()})
    arm_totals = {a: {img: v for img, v in t.items() if img not in args.exclude}
                  for a, t in arm_totals.items() if t}
    if not arm_totals:
        raise SystemExit("no results found")

    reference = json.load(open(BASE_DIR / "usda_reference.json"))
    res = analyse(arm_totals, reference, draws=args.draws)
    OUT_DIR.mkdir(exist_ok=True)
    res["excluded"] = args.exclude
    suffix = f"_{args.tag}" if args.tag else ""
    (OUT_DIR / f"averaging_check{suffix}.json").write_text(json.dumps(res, indent=1))
    report = OUT_DIR / f"AVERAGING_CHECK{suffix.upper()}.md"
    write_report(res, report)
    print(report.read_text())


if __name__ == "__main__":
    main()
