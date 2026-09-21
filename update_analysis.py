#!/usr/bin/env python3
"""The measures of the April preprint, recomputed for the September 2026 rerun.

Six arms: the four rerun arms (50 calls per photograph) and the two April arms
at temperature 0.01, truncated to their first 50 calls per photograph. The
truncation matters for the spread measures: a within-image range, and to a
lesser degree the 5th-95th percentile width, grow with the number of calls,
so the April figures published from about 500 calls per photograph are not
comparable with 50-call figures. The coefficient of variation is not
systematically affected by n, but is recomputed on the same 50 for symmetry.

Every measure follows the April definitions (deep_dive_batch.py in the
academic repository): total carbohydrate is the sum over food items of
carbs_per_100 x portion_estimate_size / 100; CV is SD/mean per photograph;
insulin figures use an insulin-to-carbohydrate ratio of 1 U per 10 g; accuracy
is against usda_reference.json, split into the strong-reference tiers (1-2),
the weaker tiers (3-4) and all nine.

One change from April: intervals are bootstrapped over photographs (5,000
resamples), because the photograph is the unit a reader would generalise
over. April quoted per-query t intervals, which treat 500 calls about one
photograph as 500 independent observations and are far narrower.

Each arm's per-photograph measures use every successful answer that arm has.
Parse failures are counted and reported, not imputed.

    APRIL_RESULTS_DIR=~/LLM-API-Tests/batch_analysis/results python3 update_analysis.py

Writes output/update_analysis.json, output/UPDATE_TABLES.md and two figures.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

import averaging_check as avg

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
OUT_DIR = BASE_DIR / "output"
APRIL_DIR = Path(os.environ.get("APRIL_RESULTS_DIR",
                                Path.home() / "LLM-API-Tests" / "batch_analysis" / "results"))
SEED = 20260921
N_BOOT = 5000
N_CALLS = 50
ICR_G_PER_U = 10
CHURROS = "MVIMG_20260222_204918.jpg"

# Display order: the new models, then each April model at default sampling
# next to its own temperature-0.01 run.
ARMS = [
    ("fable-5-1", "Claude Fable 5.1"),
    ("gpt-6-astra", "GPT-6 Astra"),
    ("sonnet-4-6-default", "Sonnet 4.6, default"),
    ("sonnet-4-6-april", "Sonnet 4.6, April 0.01"),
    ("gpt-5-4-default", "GPT-5.4, default"),
    ("gpt-5-4-april", "GPT-5.4, April 0.01"),
]
PRICES = {  # batch USD per million tokens, input and output
    "fable-5-1": (5.00, 25.00), "gpt-6-astra": (5.00, 25.00),
    "sonnet-4-6-default": (1.50, 7.50), "gpt-5-4-default": (1.25, 7.50),
}
PAIRS = [  # paired comparisons of per-photograph CV
    ("sonnet-4-6-default", "sonnet-4-6-april"),
    ("gpt-5-4-default", "gpt-5-4-april"),
    ("fable-5-1", "sonnet-4-6-default"),
    ("gpt-6-astra", "gpt-5-4-default"),
    ("fable-5-1", "gpt-6-astra"),
]


def april_blocks() -> dict[str, list[list[dict]]]:
    """The ten complete 50-call blocks of each April arm (calls 1-50, 51-100, ...
    451-500). The April GPT-5.4 run was submitted as many sequential batches and
    its median CV differs between blocks (4.3% to 9.1%), so a single block is
    one draw from a spread of possible 50-call baselines."""
    out = {}
    for arm, rs in avg.load_april(APRIL_DIR).items():
        out[arm] = [[r for r in rs if lo <= r["iteration"] < lo + N_CALLS]
                    for lo in range(1, 501, N_CALLS)]
    return out


def load_rows() -> dict[str, list[dict]]:
    rows = {}
    for arm, _ in ARMS:
        if arm.endswith("-april"):
            continue
        rows[arm] = [r for f in sorted((RESULTS_DIR / arm).glob("results_*.json"))
                     for r in json.load(open(f))["results"]]
    for arm, rs in avg.load_april(APRIL_DIR).items():
        rows[arm] = [r for r in rs if r["iteration"] <= N_CALLS]
    return rows


def settled(rows: list[dict]) -> list[dict]:
    """One row per (iteration, photograph): the answer if there is one, else the
    parse or refusal failure. API-error rows were resubmitted and are dropped."""
    best = {}
    for r in rows:
        key = (r["iteration"], r["image_file"])
        if r["success"]:
            best[key] = r
        elif r.get("error_class") != "api":
            best.setdefault(key, r)
    return list(best.values())


def boot_ci(values_by_image: dict[str, float], stat=np.median, rng=None) -> tuple[float, float, float]:
    imgs = sorted(values_by_image)
    v = np.array([values_by_image[i] for i in imgs], dtype=float)
    idx = rng.integers(0, len(v), size=(N_BOOT, len(v)))
    boots = np.array([stat(v[row]) for row in idx])
    return float(stat(v)), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def per_image(totals: dict[str, list[float]]) -> dict[str, dict]:
    out = {}
    for img, vals in totals.items():
        v = np.asarray(vals)
        p5, p25, p75, p95 = np.percentile(v, [5, 25, 75, 95])
        out[img] = {
            "n": len(v), "mean": float(v.mean()), "sd": float(v.std(ddof=1)),
            "cv_pct": float(100 * v.std(ddof=1) / v.mean()) if v.mean() else float("nan"),
            "range_g": float(v.max() - v.min()), "iqr_g": float(p75 - p25),
            "p5_p95_g": float(p95 - p5),
            "shapiro_p": float(stats.shapiro(v).pvalue) if len(v) >= 3 and v.std() > 0 else 0.0,
        }
    return out


def accuracy(totals: dict[str, list[float]], reference: dict, tiers: set[int], rng) -> dict:
    per_img_mae, errors = {}, []
    for img, vals in totals.items():
        ref = reference.get(img) or {}
        if ref.get("reference_quality") not in tiers:
            continue
        e = np.asarray(vals) - ref["total_portion_carbs_g"]
        errors.append((e, ref["total_portion_carbs_g"]))
        per_img_mae[img] = float(np.mean(np.abs(e)))
    all_e = np.concatenate([e for e, _ in errors])
    all_ref = np.concatenate([np.full(len(e), r) for e, r in errors])
    # Pooled over queries, as April did, so photographs weigh by their call count.
    mae = float(np.mean(np.abs(all_e)))
    _, lo, hi = boot_ci(per_img_mae, stat=np.mean, rng=rng)
    return {
        "n_queries": int(len(all_e)), "n_images": len(per_img_mae),
        "mae_g": mae, "mae_ci_images": (lo, hi),
        "mape_pct": float(np.mean(np.abs(all_e) / all_ref) * 100),
        "bias_g": float(np.mean(all_e)),
        "within_10_pct": float(np.mean(np.abs(all_e) <= 10) * 100),
        "within_20_pct": float(np.mean(np.abs(all_e) <= 20) * 100),
        "overdose_2u_pct": float(np.mean(all_e > 2 * ICR_G_PER_U) * 100),
        "overdose_5u_pct": float(np.mean(all_e > 5 * ICR_G_PER_U) * 100),
        "worst_overdose_u": float(max(all_e.max(), 0) / ICR_G_PER_U),
        "worst_underdose_u": float(max(-all_e.min(), 0) / ICR_G_PER_U),
        "mean_insulin_error_u": float(np.mean(all_e) / ICR_G_PER_U),
    }


def usage(rows: list[dict], arm: str) -> dict | None:
    if arm not in PRICES:
        return None
    pi, po = PRICES[arm]
    billed = [r for r in rows if r.get("input_tokens")]
    ok = [r for r in rows if r["success"] and r.get("output_tokens")]
    cost = sum(r["input_tokens"] * pi + (r.get("output_tokens") or 0) * po for r in billed) / 1e6
    return {
        "input_mean": float(np.mean([r["input_tokens"] for r in ok])),
        "output_mean": float(np.mean([r["output_tokens"] for r in ok])),
        "reasoning_mean": (float(np.mean([r["reasoning_tokens"] or 0 for r in ok]))
                           if any("reasoning_tokens" in r for r in ok) else None),
        "billed_usd": float(cost),
        "usd_per_1000_answers": float(1000 * cost / len(ok)),
    }


# Identification checks on the photographs April singled out. Each pattern is
# tested against the lower-cased name of every food item in an answer.
ID_CHECKS = {
    "IMG_20250915_112359.jpg": [("Bakewell", r"bakewell"), ("Linzer", r"linzer")],
    "IMG-20260410-WA0019.jpg": [("crema catalana", r"catalan"), ("creme brulee only", r"^(?!.*catalan).*br[uû]l[eé]e")],
    "MVIMG_20260308_142023.jpg": [("pork", r"pork"), ("chicken", r"chicken")],
    "IMG-20260410-WA0017.jpg": [("burrata", r"burrata")],
    "IMG_20260210_142258.jpg": [("deli meat or ham", r"deli|ham\b|turkey")],
}


def identification(rows: list[dict]) -> dict:
    out = {}
    for img, checks in ID_CHECKS.items():
        answers = [r for r in rows if r["success"] and r["image_file"] == img]
        out[img] = {"n": len(answers)}
        for label, pat in checks:
            hit = sum(1 for r in answers if any(re.search(pat, (fi.get("name") or "").lower())
                                                for fi in r["food_items"]))
            out[img][label] = 100 * hit / len(answers) if answers else float("nan")
    return out


def averaging_with_ci(arm_totals: dict, reference: dict, exclude: set[str], rng) -> dict:
    trimmed = {a: {i: v for i, v in t.items() if i not in exclude} for a, t in arm_totals.items()}
    res = avg.analyse(trimmed, reference)
    out = {}
    for k in res["ks"]:
        out[k] = {}
        for a in res["arms"]:
            widths = {i: e["k"][k][a]["p5_p95_width_g"] for i, e in res["per_image"].items() if k in e["k"]}
            out[k][a] = boot_ci(widths, rng=rng)
    return {"widths": out, "n_images": len(res["per_image"])}


def fig_cv(summary: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ink, muted, grid, surface = "#0b0b0b", "#52514e", "#e4e3dd", "#ffffff"
    blue, grey = "#2a78d6", "#8d8c85"
    fig, ax = plt.subplots(figsize=(7.2, 3.6), dpi=200)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)
    rng = np.random.default_rng(3)
    for x, (arm, label) in enumerate(ARMS):
        cvs = [v["cv_pct"] for v in summary[arm]["per_image"].values()]
        colour = grey if arm.endswith("-april") else blue
        jitter = rng.uniform(-0.12, 0.12, len(cvs))
        ax.scatter(x + jitter, cvs, s=22, color=colour, edgecolor=surface, linewidth=1, zorder=3)
        med = np.median(cvs)
        ax.plot([x - 0.28, x + 0.28], [med, med], color=ink, linewidth=2, zorder=4, solid_capstyle="round")
        ax.annotate(f"{med:.1f}%", (x + 0.3, med), va="center", fontsize=7.5, color=ink)
    ax.set_xticks(range(len(ARMS)), [l.replace(", ", "\n") for _, l in ARMS], fontsize=7.5, color=ink)
    ax.set_ylabel("Within-photograph CV (%)", fontsize=8, color=muted)
    ax.tick_params(axis="y", labelsize=7.5, colors=muted)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color=grid, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(grid)
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker="o", ls="", color=blue, label="provider default sampling"),
                       Line2D([], [], marker="o", ls="", color=grey, label="temperature 0.01 (April)"),
                       Line2D([], [], color=ink, lw=2, label="median")],
              fontsize=7, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, facecolor=surface)
    plt.close(fig)


def fig_averaging(widths: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ink, muted, grid, surface = "#0b0b0b", "#52514e", "#e4e3dd", "#ffffff"
    ramp = {1: "#9ec5f4", 3: "#3987e5", 5: "#184f95"}
    fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=200)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)
    for y, (arm, label) in enumerate(ARMS):
        pts = [widths[k][arm][0] for k in (1, 3, 5)]
        ax.plot([min(pts), max(pts)], [y, y], color=grid, linewidth=2, zorder=2)
        for k in (1, 3, 5):
            ax.scatter(widths[k][arm][0], y, s=46, color=ramp[k], edgecolor=surface, linewidth=2,
                       zorder=3, label=f"median of {k} call{'s' if k > 1 else ''}" if y == 0 else None)
        ax.annotate(f"{pts[0]:.1f} g", (pts[0] + 0.4, y + 0.18), fontsize=7, color=muted)
    ax.set_yticks(range(len(ARMS)), [l for _, l in ARMS], fontsize=7.5, color=ink)
    ax.invert_yaxis()
    ax.set_xlabel("5th to 95th percentile width of the estimate (g), median over photographs",
                  fontsize=8, color=muted)
    ax.tick_params(axis="x", labelsize=7.5, colors=muted)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=grid, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(grid)
    ax.set_xlim(left=0)
    ax.legend(fontsize=7, frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3)
    fig.tight_layout()
    fig.savefig(path, facecolor=surface)
    plt.close(fig)


def main():
    rng = np.random.default_rng(SEED)
    reference = json.load(open(BASE_DIR / "usda_reference.json"))
    rows = load_rows()
    summary = {}
    for arm, label in ARMS:
        s = settled(rows[arm])
        totals = avg.totals_by_image(s)
        pim = per_image(totals)
        cvs = {i: v["cv_pct"] for i, v in pim.items()}
        summary[arm] = {
            "label": label,
            "n_settled": len(s),
            "n_answers": sum(r["success"] for r in s),
            "parse_failures": dict(Counter(r["image_file"] for r in s if not r["success"])),
            "per_image": pim,
            "cv_median": boot_ci(cvs, rng=rng),
            "cv_mean": float(np.mean(list(cvs.values()))),
            "cv_max": float(max(cvs.values())),
            "range_median_g": float(np.median([v["range_g"] for v in pim.values()])),
            "iqr_median_g": float(np.median([v["iqr_g"] for v in pim.values()])),
            "p5_p95_median_g": boot_ci({i: v["p5_p95_g"] for i, v in pim.items()}, rng=rng),
            "insulin_range_median_u": float(np.median([v["range_g"] for v in pim.values()]) / ICR_G_PER_U),
            "images_range_over_2u": sum(v["range_g"] > 20 for v in pim.values()),
            "images_range_over_5u": sum(v["range_g"] > 50 for v in pim.values()),
            "non_normal": sum(v["shapiro_p"] < 0.05 for v in pim.values()),
            "accuracy": {name: accuracy(totals, reference, tiers, rng)
                         for name, tiers in (("strong", {1, 2}), ("all", {1, 2, 3, 4}), ("weak", {3, 4}))},
            "usage": usage(rows[arm], arm),
            "identification": identification(s),
        }

    comparisons = []
    for a, b in PAIRS:
        ca = {i: v["cv_pct"] for i, v in summary[a]["per_image"].items()}
        cb = {i: v["cv_pct"] for i, v in summary[b]["per_image"].items()}
        imgs = sorted(set(ca) & set(cb))
        diff = np.array([ca[i] - cb[i] for i in imgs])
        w = stats.wilcoxon([ca[i] for i in imgs], [cb[i] for i in imgs])
        comparisons.append({"a": a, "b": b, "n_images": len(imgs),
                            "median_diff_pct_points": float(np.median(diff)),
                            "a_higher_in": int((diff > 0).sum()), "wilcoxon_p": float(w.pvalue)})

    # Paired accuracy: per-photograph MAE differences over the reference
    # photographs both arms answered, with a bootstrap interval over photographs.
    mae_pairs = []
    for a, b in [("fable-5-1", "sonnet-4-6-default"), ("gpt-6-astra", "gpt-5-4-default"),
                 ("fable-5-1", "gpt-6-astra"), ("sonnet-4-6-default", "sonnet-4-6-april"),
                 ("gpt-5-4-default", "gpt-5-4-april")]:
        ta, tb = (avg.totals_by_image(settled(rows[x])) for x in (a, b))
        d = {}
        for img in sorted(set(ta) & set(tb)):
            ref = (reference.get(img) or {}).get("total_portion_carbs_g")
            if ref is not None:
                d[img] = (np.mean(np.abs(np.asarray(ta[img]) - ref))
                          - np.mean(np.abs(np.asarray(tb[img]) - ref)))
        est, lo, hi = boot_ci(d, stat=np.mean, rng=rng)
        mae_pairs.append({"a": a, "b": b, "n_images": len(d), "mean_diff_g": est, "ci": (lo, hi),
                          "a_lower_in": int(sum(v < 0 for v in d.values()))})

    block_sensitivity = {}
    for april_arm, blocks in april_blocks().items():
        default_arm = april_arm.replace("-april", "-default")
        cd = {i: v["cv_pct"] for i, v in summary[default_arm]["per_image"].items()}
        per_block = []
        for b in blocks:
            pim = per_image(avg.totals_by_image(settled(b)))
            cb = {i: v["cv_pct"] for i, v in pim.items()}
            imgs = sorted(set(cd) & set(cb))
            diff = np.array([cd[i] - cb[i] for i in imgs])
            per_block.append({
                "cv_median": float(np.median(list(cb.values()))),
                "p5_p95_median_g": float(np.median([v["p5_p95_g"] for v in pim.values()])),
                "default_higher_in": int((diff > 0).sum()),
                "wilcoxon_p": float(stats.wilcoxon([cd[i] for i in imgs], [cb[i] for i in imgs]).pvalue),
            })
        block_sensitivity[april_arm] = per_block

    arm_totals = {arm: avg.totals_by_image(settled(rows[arm])) for arm, _ in ARMS}
    averaging = {
        "without_churros": averaging_with_ci(arm_totals, reference, {CHURROS}, rng),
        "with_churros": averaging_with_ci(arm_totals, reference, set(), rng),
    }

    OUT_DIR.mkdir(exist_ok=True)
    result = {"seed": SEED, "n_boot": N_BOOT, "n_calls": N_CALLS, "arms": summary,
              "cv_comparisons": comparisons, "mae_comparisons": mae_pairs,
              "april_block_sensitivity": block_sensitivity,
              "averaging": averaging}
    (OUT_DIR / "update_analysis.json").write_text(json.dumps(result, indent=1, default=float))
    fig_cv(summary, OUT_DIR / "fig1_cv_by_arm.png")
    fig_averaging(averaging["without_churros"]["widths"], OUT_DIR / "fig2_median_of_k.png")
    write_tables(result, OUT_DIR / "UPDATE_TABLES.md")
    print((OUT_DIR / "UPDATE_TABLES.md").read_text())


def write_tables(res: dict, path: Path) -> None:
    A = res["arms"]
    arms = [a for a, _ in ARMS]
    head = "| measure | " + " | ".join(A[a]["label"] for a in arms) + " |"
    sep = "|---|" + "---|" * len(arms)
    L = ["# Tables for the September 2026 update", "",
         "Generated by update_analysis.py. Intervals are 95% bootstrap intervals over photographs.", "",
         "## Reproducibility", "", head, sep]

    def row(name, f):
        L.append(f"| {name} | " + " | ".join(f(A[a]) for a in arms) + " |")

    row("answers / settled calls", lambda s: f"{s['n_answers']} / {s['n_settled']}")
    row("CV, median (95% CI)", lambda s: f"{s['cv_median'][0]:.1f}% ({s['cv_median'][1]:.1f}-{s['cv_median'][2]:.1f})")
    row("CV, mean", lambda s: f"{s['cv_mean']:.1f}%")
    row("CV, max", lambda s: f"{s['cv_max']:.1f}%")
    row("range, median (g)", lambda s: f"{s['range_median_g']:.1f}")
    row("IQR, median (g)", lambda s: f"{s['iqr_median_g']:.1f}")
    row("P5-P95, median (g) (95% CI)", lambda s: f"{s['p5_p95_median_g'][0]:.1f} ({s['p5_p95_median_g'][1]:.1f}-{s['p5_p95_median_g'][2]:.1f})")
    row("insulin range, median (U)", lambda s: f"{s['insulin_range_median_u']:.1f}")
    row("photographs with range > 2 U", lambda s: f"{s['images_range_over_2u']}/13")
    row("photographs with range > 5 U", lambda s: f"{s['images_range_over_5u']}/13")
    row("non-normal (Shapiro-Wilk p<0.05)", lambda s: f"{s['non_normal']}/13")

    for name, title in (("strong", "Accuracy, strong reference (tiers 1-2, 5 photographs)"),
                        ("all", "Accuracy, all nine reference photographs"),
                        ("weak", "Accuracy, weaker reference (tiers 3-4, 4 photographs)")):
        L += ["", f"## {title}", "", head, sep]
        row("queries", lambda s: f"{s['accuracy'][name]['n_queries']}")
        row("MAE, g (95% CI)", lambda s: (f"{s['accuracy'][name]['mae_g']:.1f} "
                                          f"({s['accuracy'][name]['mae_ci_images'][0]:.1f}-{s['accuracy'][name]['mae_ci_images'][1]:.1f})"))
        row("MAPE, %", lambda s: f"{s['accuracy'][name]['mape_pct']:.1f}")
        row("mean bias, g", lambda s: f"{s['accuracy'][name]['bias_g']:+.1f}")
        row("within 10 g, %", lambda s: f"{s['accuracy'][name]['within_10_pct']:.1f}")
        row("within 20 g, %", lambda s: f"{s['accuracy'][name]['within_20_pct']:.1f}")
        if name == "strong":
            row("mean insulin error (U)", lambda s: f"{s['accuracy'][name]['mean_insulin_error_u']:+.1f}")
            row("queries > 2 U overdose, %", lambda s: f"{s['accuracy'][name]['overdose_2u_pct']:.1f}")
            row("queries > 5 U overdose, %", lambda s: f"{s['accuracy'][name]['overdose_5u_pct']:.1f}")
            row("worst overdose (U)", lambda s: f"{s['accuracy'][name]['worst_overdose_u']:.1f}")
            row("worst underdose (U)", lambda s: f"{s['accuracy'][name]['worst_underdose_u']:.1f}")

    L += ["", "## Per-photograph CV (%)", "", "| photograph | " + " | ".join(A[a]["label"] for a in arms) + " |", sep]
    for img in sorted(A[arms[0]]["per_image"]):
        L.append(f"| {img} | " + " | ".join(
            f"{A[a]['per_image'][img]['cv_pct']:.1f} (n={A[a]['per_image'][img]['n']})" if img in A[a]["per_image"] else ""
            for a in arms) + " |")

    L += ["", "## Paired comparisons of per-photograph CV (Wilcoxon signed-rank)", "",
          "| comparison | photographs | median difference (points) | first higher in | p |", "|---|---|---|---|---|"]
    for c in res["cv_comparisons"]:
        L.append(f"| {A[c['a']]['label']} vs {A[c['b']]['label']} | {c['n_images']} | "
                 f"{c['median_diff_pct_points']:+.1f} | {c['a_higher_in']} | {c['wilcoxon_p']:.3f} |")

    L += ["", "## Paired per-photograph MAE differences (reference photographs)", "",
          "| comparison | photographs | mean difference, g (95% CI) | first lower in |", "|---|---|---|---|"]
    for c in res["mae_comparisons"]:
        L.append(f"| {A[c['a']]['label']} vs {A[c['b']]['label']} | {c['n_images']} | "
                 f"{c['mean_diff_g']:+.1f} ({c['ci'][0]:+.1f} to {c['ci'][1]:+.1f}) | {c['a_lower_in']} |")

    L += ["", "## Sensitivity: default sampling against each complete 50-call April block", "",
          "| April arm | block median CV, range | block P5-P95 median (g), range | "
          "default higher in (photographs), range | Wilcoxon p, range |", "|---|---|---|---|---|"]
    for arm, blocks in res["april_block_sensitivity"].items():
        f = lambda key: (min(b[key] for b in blocks), max(b[key] for b in blocks))
        cv, w, h, p = f("cv_median"), f("p5_p95_median_g"), f("default_higher_in"), f("wilcoxon_p")
        L.append(f"| {A[arm]['label']} | {cv[0]:.1f}-{cv[1]:.1f}% | {w[0]:.1f}-{w[1]:.1f} | "
                 f"{h[0]}-{h[1]} of 13 | {p[0]:.4f}-{p[1]:.3f} |")

    for key, title in (("without_churros", "Median of k calls, churros excluded"),
                       ("with_churros", "Median of k calls, all photographs")):
        W = res["averaging"][key]["widths"]
        L += ["", f"## {title} ({res['averaging'][key]['n_images']} photographs)", "",
              "5th-95th percentile width of the k-call median (g), median over photographs (95% CI).", "",
              "| arm | k = 1 | k = 3 | k = 5 |", "|---|---|---|---|"]
        for a in arms:
            L.append(f"| {A[a]['label']} | " + " | ".join(
                f"{W[k][a][0]:.1f} ({W[k][a][1]:.1f}-{W[k][a][2]:.1f})" for k in (1, 3, 5)) + " |")

    L += ["", "## Parse failures by photograph", ""]
    for a in arms:
        L.append(f"- {A[a]['label']}: {A[a]['parse_failures'] or 'none'}")

    L += ["", "## Tokens and cost (rerun arms)", "",
          "| arm | input tokens | output tokens | of which reasoning | billed (USD) | USD per 1,000 answers |",
          "|---|---|---|---|---|---|"]
    for a in arms:
        u = A[a]["usage"]
        if u:
            r = f"{u['reasoning_mean']:.0f}" if u["reasoning_mean"] is not None else "not reported"
            L.append(f"| {A[a]['label']} | {u['input_mean']:.0f} | {u['output_mean']:.0f} | {r} | "
                     f"{u['billed_usd']:.2f} | {u['usd_per_1000_answers']:.2f} |")

    L += ["", "## Identification (% of answers naming the item)", ""]
    for img, checks in ID_CHECKS.items():
        labels = [l for l, _ in checks]
        L.append(f"- {img}: " + "; ".join(
            f"{A[a]['label']} " + ", ".join(f"{l} {A[a]['identification'][img][l]:.0f}" for l in labels)
            for a in arms))
    path.write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
