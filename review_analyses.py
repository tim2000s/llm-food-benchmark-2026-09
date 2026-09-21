#!/usr/bin/env python3
"""Analyses added in response to peer review of the September 2026 update.

1. April baseline over all ten 50-call blocks. The reproducibility measures of
   each April arm are computed in each complete 50-call block (calls 1-50 ...
   451-500) and summarised by the median over blocks, which becomes the primary
   April comparator. The first 50 calls are the least variable GPT-5.4 block, so
   using them alone would overstate the effect of default sampling.
2. Parse failures by photograph, and the retries an application would need.
3. Sensitivity of the overdose rates to the insulin-to-carbohydrate ratio:
   1 U per 5 g, 10 g and 20 g, for one call and for the median of 20 calls.
4. The effect on the carbohydrate estimate of the misidentifications in the
   identification table: mean estimate in answers that name the item against
   answers that do not.
5. How many photographs a ranking of models by accuracy would need, from the
   spread of paired per-photograph MAE differences observed here.
6. Annual cost of k-call averaging for one person logging three meals a day.

    APRIL_RESULTS_DIR=~/LLM-API-Tests/batch_analysis/results python3 review_analyses.py

Writes output/review_analyses.json and output/REVIEW_ANALYSES.md.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from scipy import stats

import averaging_check as avg
from update_analysis import (ARMS, CHURROS, ID_CHECKS, ICR_G_PER_U, april_blocks, boot_ci,
                             load_rows, per_image, settled)

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "output"
SEED = 20260923
DRAWS = 10000
STRONG = {1, 2}
USD_PER_ANSWER = {"fable-5-1": 0.06063, "gpt-6-astra": 0.06238,
                  "sonnet-4-6-default": 0.01783, "gpt-5-4-default": 0.01176}


def block_measures(pim: dict) -> dict:
    cvs = [v["cv_pct"] for v in pim.values()]
    return {
        "cv_median": float(np.median(cvs)), "cv_mean": float(np.mean(cvs)), "cv_max": float(max(cvs)),
        "p5_p95_median_g": float(np.median([v["p5_p95_g"] for v in pim.values()])),
        "range_median_g": float(np.median([v["range_g"] for v in pim.values()])),
        "insulin_range_median_u": float(np.median([v["range_g"] for v in pim.values()]) / ICR_G_PER_U),
        "images_range_over_2u": int(sum(v["range_g"] > 20 for v in pim.values())),
        "images_range_over_5u": int(sum(v["range_g"] > 50 for v in pim.values())),
    }


def april_over_blocks(rows: dict, rng) -> dict:
    """Median over the ten April blocks of each reproducibility measure, the range
    over blocks, and a per-photograph CV (median over blocks) for paired tests."""
    out = {}
    for arm, blocks in april_blocks().items():
        pims = [per_image(avg.totals_by_image(settled(b))) for b in blocks]
        measures = [block_measures(p) for p in pims]
        keys = measures[0].keys()
        per_photo_cv = {img: float(np.median([p[img]["cv_pct"] for p in pims])) for img in pims[0]}
        per_photo_w = {img: float(np.median([p[img]["p5_p95_g"] for p in pims])) for img in pims[0]}
        out[arm] = {
            "median_over_blocks": {k: float(np.median([m[k] for m in measures])) for k in keys},
            "range_over_blocks": {k: (float(min(m[k] for m in measures)), float(max(m[k] for m in measures)))
                                  for k in keys},
            "per_photo_cv": per_photo_cv,
            "cv_median_ci": boot_ci(per_photo_cv, rng=rng),
            "p5_p95_median_ci": boot_ci(per_photo_w, rng=rng),
        }
        default_arm = arm.replace("-april", "-default")
        cd = {i: v["cv_pct"] for i, v in per_image(avg.totals_by_image(settled(rows[default_arm]))).items()}
        imgs = sorted(set(cd) & set(per_photo_cv))
        diff = np.array([cd[i] - per_photo_cv[i] for i in imgs])
        out[arm]["vs_default"] = {
            "median_diff_points": float(np.median(diff)), "default_higher_in": int((diff > 0).sum()),
            "n": len(imgs),
            "wilcoxon_p": float(stats.wilcoxon([cd[i] for i in imgs], [per_photo_cv[i] for i in imgs]).pvalue),
        }
    return out


def failures(rows: dict) -> dict:
    out = {}
    for arm, _ in ARMS:
        s = settled(rows[arm])
        by = {}
        for r in s:
            d = by.setdefault(r["image_file"], [0, 0])
            d[0] += 1
            d[1] += 0 if r["success"] else 1
        per = {img: {"calls": n, "failed": f, "rate": f / n,
                     "expected_attempts": (1 / (1 - f / n)) if f < n else float("inf"),
                     "p_none_after_3": (f / n) ** 3}
               for img, (n, f) in by.items() if f}
        rest = [(n, f) for img, (n, f) in by.items() if img != CHURROS]
        out[arm] = {"per_photo": per,
                    "rate_excluding_churros": (sum(f for _, f in rest) / sum(n for n, _ in rest)
                                               if rest else float("nan"))}
    return out


def icr_sensitivity(arm_totals: dict, reference: dict, rng) -> dict:
    """Share of estimates implying an overdose above 2 U at 1 U per 5, 10 and 20 g,
    mean over the five strong-reference photographs, for 1 call and a 20-call median."""
    out = {}
    photos = [p for p, r in reference.items()
              if isinstance(r, dict) and r.get("reference_quality") in STRONG]
    for arm, totals in arm_totals.items():
        out[arm] = {}
        for g in (5, 10, 20):
            one, twenty = [], []
            for img in photos:
                vals = np.asarray(totals[img], dtype=float)
                err1 = vals - reference[img]["total_portion_carbs_g"]
                med20 = np.median(vals[rng.integers(0, len(vals), size=(DRAWS, 20))], axis=1)
                err20 = med20 - reference[img]["total_portion_carbs_g"]
                one.append(float(np.mean(err1 > 2 * g)))
                twenty.append(float(np.mean(err20 > 2 * g)))
            out[arm][g] = {"one_call": float(np.mean(one)), "twenty_calls": float(np.mean(twenty))}
    return out


def identification_effect(rows: dict, reference: dict) -> dict:
    out = {}
    for arm, _ in ARMS:
        answers = [r for r in settled(rows[arm]) if r["success"]]
        out[arm] = {}
        for img, checks in ID_CHECKS.items():
            ref = (reference.get(img) or {}).get("total_portion_carbs_g")
            for label, pat in checks:
                named, other = [], []
                for r in answers:
                    if r["image_file"] != img:
                        continue
                    total = avg.total_carbs_g(r["food_items"])
                    hit = any(re.search(pat, (fi.get("name") or "").lower()) for fi in r["food_items"])
                    (named if hit else other).append(total)
                if named and other:
                    out[arm][f"{img}|{label}"] = {
                        "n_named": len(named), "n_other": len(other),
                        "mean_named_g": float(np.mean(named)), "mean_other_g": float(np.mean(other)),
                        "difference_g": float(np.mean(named) - np.mean(other)), "reference_g": ref,
                    }
    return out


def photographs_needed(res_update: dict) -> dict:
    """Photographs needed for 80% power (two-sided alpha 0.05, paired) to detect a
    5 g or 10 g difference in per-photograph MAE, from the observed SD of paired
    differences. Normal approximation: n = ((z_a + z_b) * sd / delta)^2."""
    out = {}
    z = stats.norm.ppf(0.975) + stats.norm.ppf(0.80)
    for c in res_update["mae_pairs_detail"]:
        sd = float(np.std(c["diffs"], ddof=1))
        out[f"{c['a']} vs {c['b']}"] = {"sd_g": sd, "n_images": len(c["diffs"]),
                                        "n_for_5g": int(np.ceil((z * sd / 5) ** 2)),
                                        "n_for_10g": int(np.ceil((z * sd / 10) ** 2))}
    return out


def mae_pair_diffs(arm_totals: dict, reference: dict) -> dict:
    pairs = [("fable-5-1", "sonnet-4-6-default"), ("gpt-6-astra", "gpt-5-4-default"), ("fable-5-1", "gpt-6-astra")]
    detail = []
    for a, b in pairs:
        diffs = []
        for img in sorted(set(arm_totals[a]) & set(arm_totals[b])):
            ref = (reference.get(img) or {}).get("total_portion_carbs_g")
            if ref is None:
                continue
            diffs.append(float(np.mean(np.abs(np.asarray(arm_totals[a][img]) - ref))
                               - np.mean(np.abs(np.asarray(arm_totals[b][img]) - ref))))
        detail.append({"a": a, "b": b, "diffs": diffs})
    return {"mae_pairs_detail": detail}


def annual_cost() -> dict:
    meals = 3 * 365
    return {arm: {k: {"batch_usd": meals * k * usd, "realtime_usd": meals * k * usd * 2} for k in (1, 5, 20)}
            for arm, usd in USD_PER_ANSWER.items()}


def main():
    rng = np.random.default_rng(SEED)
    reference = json.load(open(BASE_DIR / "usda_reference.json"))
    rows = load_rows()
    labels = dict(ARMS)
    arm_totals = {a: avg.totals_by_image(settled(rows[a])) for a, _ in ARMS}
    res = {
        "april_blocks": april_over_blocks(rows, rng),
        "failures": failures(rows),
        "icr": icr_sensitivity(arm_totals, reference, rng),
        "identification_effect": identification_effect(rows, reference),
        "photographs_needed": photographs_needed(mae_pair_diffs(arm_totals, reference)),
        "annual_cost": annual_cost(),
    }
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "review_analyses.json").write_text(json.dumps(res, indent=1, default=float))
    # Figure 1 with the April arms as the median over their ten blocks per photograph.
    from update_analysis import fig_cv
    upd = json.load(open(OUT_DIR / "update_analysis.json"))["arms"]
    for arm, d in res["april_blocks"].items():
        for img, cv in d["per_photo_cv"].items():
            upd[arm]["per_image"][img]["cv_pct"] = cv
    fig_cv(upd, OUT_DIR / "fig1_cv_by_arm_blocks.png")
    write_report(res, labels, OUT_DIR / "REVIEW_ANALYSES.md")
    print((OUT_DIR / "REVIEW_ANALYSES.md").read_text())


def write_report(res: dict, labels: dict, path: Path) -> None:
    L = ["# Analyses added in response to review", "", "Generated by review_analyses.py.", "",
         "## 1. April arms over all ten 50-call blocks (median over blocks; range)", "",
         "| April arm | CV median | CV mean | CV max | P5-P95 median (g) | range median (g) | "
         "insulin range (U) | photos range > 2 U | > 5 U |", "|---|---|---|---|---|---|---|---|---|"]
    for arm, d in res["april_blocks"].items():
        m, r = d["median_over_blocks"], d["range_over_blocks"]
        f = lambda k, fmt="{:.1f}": f"{fmt.format(m[k])} ({fmt.format(r[k][0])}-{fmt.format(r[k][1])})"
        L.append(f"| {labels[arm]} | {f('cv_median')}% | {f('cv_mean')}% | {f('cv_max')}% | {f('p5_p95_median_g')} | "
                 f"{f('range_median_g')} | {f('insulin_range_median_u')} | {f('images_range_over_2u', '{:.0f}')} | "
                 f"{f('images_range_over_5u', '{:.0f}')} |")
    L += ["", "Per-photograph CV as the median over blocks: CV median with 95% bootstrap CI over photographs, "
          "and paired comparison with the same model at default sampling.", "",
          "| April arm | CV median (95% CI) | P5-P95 median (95% CI) | default higher in | median difference | Wilcoxon p |",
          "|---|---|---|---|---|---|"]
    for arm, d in res["april_blocks"].items():
        c, w, v = d["cv_median_ci"], d["p5_p95_median_ci"], d["vs_default"]
        L.append(f"| {labels[arm]} | {c[0]:.1f}% ({c[1]:.1f}-{c[2]:.1f}) | {w[0]:.1f} ({w[1]:.1f}-{w[2]:.1f}) | "
                 f"{v['default_higher_in']} of {v['n']} | {v['median_diff_points']:+.1f} | {v['wilcoxon_p']:.4f} |")

    L += ["", "## 2. Parse failures by photograph", "",
          "| arm | photograph | failed / calls | expected attempts per answer | P(no answer after 3 attempts) |",
          "|---|---|---|---|---|"]
    for arm, d in res["failures"].items():
        for img, p in d["per_photo"].items():
            L.append(f"| {labels[arm]} | {img} | {p['failed']}/{p['calls']} | {p['expected_attempts']:.2f} | "
                     f"{100*p['p_none_after_3']:.2f}% |")
    L += [""] + [f"- {labels[a]}: failure rate on the other 12 photographs {100*d['rate_excluding_churros']:.2f}%"
                 for a, d in res["failures"].items()]

    L += ["", "## 3. Overdose above 2 U at different insulin-to-carbohydrate ratios (5 strong-reference photographs)", "",
          "| arm | 1 U/5 g, 1 call | 20 calls | 1 U/10 g, 1 call | 20 calls | 1 U/20 g, 1 call | 20 calls |",
          "|---|---|---|---|---|---|---|"]
    for arm, d in res["icr"].items():
        L.append(f"| {labels[arm]} | " + " | ".join(f"{100*d[g]['one_call']:.1f}% | {100*d[g]['twenty_calls']:.1f}%"
                                                    for g in (5, 10, 20)) + " |")

    L += ["", "## 4. Effect of misidentification on the estimate", "",
          "| arm | photograph and item | named (n) | not named (n) | mean if named (g) | mean if not (g) | difference (g) | reference (g) |",
          "|---|---|---|---|---|---|---|---|"]
    for arm, d in res["identification_effect"].items():
        for key, e in d.items():
            img, label = key.split("|")
            ref = f"{e['reference_g']}" if e["reference_g"] is not None else "none"
            L.append(f"| {labels[arm]} | {img}: {label} | {e['n_named']} | {e['n_other']} | {e['mean_named_g']:.1f} | "
                     f"{e['mean_other_g']:.1f} | {e['difference_g']:+.1f} | {ref} |")

    L += ["", "## 5. Photographs needed to rank models by MAE (80% power, two-sided 5%)", "",
          "| comparison | SD of paired differences (g) | photographs used | needed for 5 g | needed for 10 g |",
          "|---|---|---|---|---|"]
    for k, d in res["photographs_needed"].items():
        a, b = k.split(" vs ")
        L.append(f"| {labels[a]} vs {labels[b]} | {d['sd_g']:.1f} | {d['n_images']} | {d['n_for_5g']} | {d['n_for_10g']} |")

    L += ["", "## 6. Annual cost, three meals a day (USD)", "",
          "| arm | 1 call, batch | 5 calls, batch | 20 calls, batch | 20 calls, real time |", "|---|---|---|---|---|"]
    for arm, d in res["annual_cost"].items():
        L.append(f"| {labels[arm]} | {d[1]['batch_usd']:.0f} | {d[5]['batch_usd']:.0f} | {d[20]['batch_usd']:.0f} | "
                 f"{d[20]['realtime_usd']:.0f} |")
    path.write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
