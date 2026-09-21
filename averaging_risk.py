#!/usr/bin/env python3
"""Does averaging many calls reduce the risk in a carbohydrate estimate?

An application can send one photograph k times and use the median (or mean) of
the k answers. This script simulates that for k = 1, 2, 3, 5, 10 and 20 from the
50 answers per photograph already collected, with no further API calls, and
measures two kinds of risk.

Variability risk, on all 13 photographs: how often the k-call estimate lands more
than 10 g (1 U at 1 U per 10 g) or 20 g (2 U) from that model's own typical answer
for the photograph, the median of all its answers. This is the risk of an unlucky
draw, and it needs no reference value.

Accuracy risk, on the photographs with reference values: how often the k-call
estimate implies an insulin overdose above 2 U or 5 U, or an underdose above 2 U,
against the reference. These are the April preprint's thresholds.

Resampling is with replacement: each photograph's answers are treated as that
model's distribution for that photograph, and each simulated call is a draw from
it. Drawing 20 of 50 without replacement would share most answers between
simulated batches and understate the spread of 20 fresh calls by about a fifth
(finite-population factor sqrt(30/49) = 0.78). The without-replacement result is
computed as a sensitivity check. Every arm receives the same random draw
positions for a photograph, and draws are indexed into each arm's own answers.

As k grows the k-call estimate converges on the model's typical answer, so a
photograph's overdose rate converges on 0% or 100% according to whether that
typical answer is more or less than 20 g above the reference. Averaging can
therefore raise an accuracy risk as well as lower it; the script counts both.

The churros photograph is excluded from the primary tables because GPT-6 Astra
has 10 parsable answers for it, too few to resample 20 from; it is reported
separately for the arms that answered it.

    APRIL_RESULTS_DIR=~/LLM-API-Tests/batch_analysis/results python3 averaging_risk.py

Writes output/averaging_risk.json, output/AVERAGING_RISK.md and two figures.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import averaging_check as avg
from update_analysis import ARMS, CHURROS, ICR_G_PER_U, load_rows, settled

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "output"
SEED = 20260922
DRAWS = 10000
KS = (1, 2, 3, 5, 10, 20)
N_BOOT = 5000
STRONG = {1, 2}


def simulate(values: np.ndarray, positions: np.ndarray, stat) -> np.ndarray:
    """k-call estimates: stat over each row of values[positions]."""
    return stat(values[positions], axis=1)


def draw_positions(rng, n: int, k: int, draws: int, replace: bool) -> np.ndarray:
    if replace:
        return rng.integers(0, n, size=(draws, k))
    return np.argsort(rng.random((draws, n)), axis=1)[:, :k]


def photo_metrics(est: np.ndarray, own_median: float, ref: float | None) -> dict:
    p5, p95 = np.percentile(est, [5, 95])
    dev = np.abs(est - own_median)
    m = {
        "width_g": float(p95 - p5),
        "p_off_own_10g": float(np.mean(dev > 10)),
        "p_off_own_20g": float(np.mean(dev > 20)),
    }
    if ref is not None:
        err = est - ref
        m.update({
            "p_over_2u": float(np.mean(err > 2 * ICR_G_PER_U)),
            "p_over_5u": float(np.mean(err > 5 * ICR_G_PER_U)),
            "p_under_2u": float(np.mean(err < -2 * ICR_G_PER_U)),
            "mae_g": float(np.mean(np.abs(err))),
            "typical_error_g": float(own_median - ref),
        })
    return m


def run(arm_totals: dict, reference: dict, stat, replace: bool, seed: int, ks=KS,
        draws=DRAWS, exclude=frozenset({CHURROS})) -> dict:
    """Per-arm, per-photograph, per-k metrics. Positions are shared across arms:
    for with-replacement draws they are generated on [0, n_min) then scaled into
    each arm's own n, so arms with more answers are not disadvantaged."""
    rng = np.random.default_rng(seed)
    arms = list(arm_totals)
    photos = sorted(set.intersection(*(set(t) for t in arm_totals.values())) - set(exclude))
    out = {a: {} for a in arms}
    for img in photos:
        ref = (reference.get(img) or {}).get("total_portion_carbs_g")
        n_min = min(len(arm_totals[a][img]) for a in arms)
        for k in ks:
            if not replace and k > n_min:
                continue
            u = rng.random((draws, k))  # shared uniform draws, mapped into each arm's n
            shared = draw_positions(rng, n_min, k, draws, replace=False) if not replace else None
            for a in arms:
                vals = np.asarray(arm_totals[a][img], dtype=float)
                pos = (np.floor(u * len(vals)).astype(int) if replace else shared)
                est = simulate(vals, pos, stat)
                out[a].setdefault(img, {})[k] = photo_metrics(est, float(np.median(vals)), ref)
    return {"photos": photos, "per_photo": out}


def summarise(per_photo: dict, reference: dict, rng) -> dict:
    """Mean over photographs of each per-photograph rate, with a bootstrap
    interval over photographs. Photographs are weighted equally."""
    summary = {}
    for a, photos in per_photo.items():
        summary[a] = {}
        ks = sorted({k for p in photos.values() for k in p})
        for k in ks:
            row = {}
            for key, subset in (("p_off_own_10g", "all"), ("p_off_own_20g", "all"), ("width_g", "all"),
                                ("p_over_2u", "strong"), ("p_over_5u", "strong"), ("p_under_2u", "strong"),
                                ("mae_g", "strong"), ("p_over_2u", "ref"), ("mae_g", "ref")):
                vals = []
                for img, byk in photos.items():
                    q = (reference.get(img) or {}).get("reference_quality")
                    if subset == "strong" and q not in STRONG:
                        continue
                    if subset == "ref" and q is None:
                        continue
                    if k in byk and key in byk[k]:
                        vals.append(byk[k][key])
                if not vals:
                    continue
                v = np.asarray(vals)
                stat = np.median if key == "width_g" else np.mean
                boots = [stat(v[rng.integers(0, len(v), len(v))]) for _ in range(N_BOOT)]
                row[f"{key}_{subset}"] = (float(stat(v)), float(np.percentile(boots, 2.5)),
                                          float(np.percentile(boots, 97.5)), len(v))
            summary[a][k] = row
    return summary


def direction_counts(per_photo: dict, reference: dict, k_hi: int = 20) -> dict:
    """For each arm, on the reference photographs: in how many did the 2 U
    overdose rate fall, rise or stay at zero between one call and k_hi calls."""
    out = {}
    for a, photos in per_photo.items():
        fell = rose = zero = same = 0
        detail = []
        for img, byk in photos.items():
            if "p_over_2u" not in byk[1]:
                continue
            p1, pk = byk[1]["p_over_2u"], byk[k_hi]["p_over_2u"]
            detail.append({"photo": img, "p1": p1, f"p{k_hi}": pk, "typical_error_g": byk[1]["typical_error_g"]})
            if p1 == 0 and pk == 0:
                zero += 1
            elif pk < p1:
                fell += 1
            elif pk > p1:
                rose += 1
            else:
                same += 1
        out[a] = {"fell": fell, "rose": rose, "zero_throughout": zero, "unchanged_nonzero": same,
                  "detail": detail}
    return out


def figure(summary: dict, labels: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ink, muted, grid, surface = "#0b0b0b", "#52514e", "#e4e3dd", "#ffffff"
    colours = {"fable-5-1": "#2a78d6", "gpt-6-astra": "#eb6834", "sonnet-4-6-default": "#1baf7a",
               "gpt-5-4-default": "#eda100"}
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.3), dpi=200)
    fig.patch.set_facecolor(surface)
    panels = (("p_off_own_10g_all", "More than 1 U from the model's\ntypical answer (12 photographs)"),
              ("p_over_2u_strong", "Overdose above 2 U against the\nreference (5 strong-reference photographs)"))
    for ax, (key, title) in zip(axes, panels):
        ax.set_facecolor(surface)
        for a, col in colours.items():
            ks = sorted(summary[a])
            y = [100 * summary[a][k][key][0] for k in ks]
            ax.plot(ks, y, color=col, lw=2, marker="o", ms=4, label=labels[a])
        ax.set_xscale("log")
        ax.set_xticks(list(KS), [str(k) for k in KS])
        ax.minorticks_off()
        ax.set_xlim(0.85, 24)
        ax.set_xlabel("Calls averaged (median)", fontsize=7.5, color=muted)
        ax.set_ylabel("% of estimates", fontsize=7.5, color=muted)
        ax.set_title(title, fontsize=7.5, color=ink, loc="left")
        ax.tick_params(labelsize=7, colors=muted)
        ax.grid(axis="y", color=grid, lw=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(grid)
        ax.set_ylim(bottom=0)
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, fontsize=6.5, frameon=False, loc="lower center", ncol=4)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(path, facecolor=surface)
    plt.close(fig)


def figure_photos(per_photo: dict, reference: dict, labels: dict, path: Path) -> None:
    """Each point is one arm on one reference photograph: the arm's typical error
    for it (median answer minus reference) against its 2 U overdose rate, at 1 call
    and at 20 calls. Above +20 g, 20 calls push the rate to 100%; below, to 0%."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ink, muted, grid, surface = "#0b0b0b", "#52514e", "#e4e3dd", "#ffffff"
    light, dark = "#9ec5f4", "#184f95"
    fig, ax = plt.subplots(figsize=(7.2, 3.3), dpi=200)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)
    arms = ["fable-5-1", "gpt-6-astra", "sonnet-4-6-default", "gpt-5-4-default"]
    for a in arms:
        for img, byk in per_photo[a].items():
            if "p_over_2u" not in byk[1]:
                continue
            x = byk[1]["typical_error_g"]
            y1, y20 = 100 * byk[1]["p_over_2u"], 100 * byk[20]["p_over_2u"]
            ax.plot([x, x], [y1, y20], color=grid, lw=1.5, zorder=1)
            ax.scatter(x, y1, s=22, color=light, edgecolor=surface, lw=1, zorder=3)
            ax.scatter(x, y20, s=22, color=dark, edgecolor=surface, lw=1, zorder=3)
    ax.axvline(20, color=muted, lw=1, ls="--", zorder=0)
    ax.annotate("typical answer 20 g (2 U) above the reference", (20, 50), xytext=(-6, 0),
                textcoords="offset points", rotation=90, fontsize=6.5, color=muted, ha="right", va="center")
    ax.scatter([], [], s=22, color=light, label="1 call")
    ax.scatter([], [], s=22, color=dark, label="median of 20 calls")
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    ax.set_xlabel("Model's typical error for the photograph (g, median answer minus reference)", fontsize=7.5, color=muted)
    ax.set_ylabel("% of estimates above 2 U overdose", fontsize=7.5, color=muted)
    ax.tick_params(labelsize=7, colors=muted)
    ax.grid(axis="y", color=grid, lw=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(grid)
    fig.tight_layout()
    fig.savefig(path, facecolor=surface)
    plt.close(fig)


def main():
    reference = json.load(open(BASE_DIR / "usda_reference.json"))
    rows = load_rows()
    arm_totals = {a: avg.totals_by_image(settled(rows[a])) for a, _ in ARMS}
    labels = dict(ARMS)
    rng = np.random.default_rng(SEED)

    primary = run(arm_totals, reference, np.median, replace=True, seed=SEED)
    variants = {
        "mean_with_replacement": run(arm_totals, reference, np.mean, replace=True, seed=SEED),
        "median_without_replacement": run(arm_totals, reference, np.median, replace=False, seed=SEED),
    }
    churros_arms = {a: t for a, t in arm_totals.items() if a != "gpt-6-astra"}
    churros = run({a: {CHURROS: t[CHURROS]} for a, t in churros_arms.items()}, reference,
                  np.median, replace=True, seed=SEED, exclude=frozenset())

    result = {
        "seed": SEED, "draws": DRAWS, "ks": list(KS), "photos": primary["photos"],
        "summary": summarise(primary["per_photo"], reference, rng),
        "direction": direction_counts(primary["per_photo"], reference),
        "per_photo": primary["per_photo"],
        "variants": {name: summarise(v["per_photo"], reference, rng) for name, v in variants.items()},
        "churros": churros["per_photo"],
    }
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "averaging_risk.json").write_text(json.dumps(result, indent=1))
    figure(result["summary"], labels, OUT_DIR / "fig3_risk_by_k.png")
    figure_photos(primary["per_photo"], reference, labels, OUT_DIR / "fig4_overdose_by_photo.png")
    write_report(result, labels, OUT_DIR / "AVERAGING_RISK.md")
    print((OUT_DIR / "AVERAGING_RISK.md").read_text())


def write_report(res: dict, labels: dict, path: Path) -> None:
    S = res["summary"]
    arms = list(S)
    fmt = lambda t, pct=True: (f"{100*t[0]:.1f}% ({100*t[1]:.1f}-{100*t[2]:.1f})" if pct
                               else f"{t[0]:.1f} ({t[1]:.1f}-{t[2]:.1f})")
    L = ["# Averaging and risk", "",
         f"Generated by averaging_risk.py. {res['draws']:,} simulated batches per arm, photograph and k, "
         f"drawn with replacement from each arm's answers (seed {res['seed']}). Median of k calls. "
         "Rates are the mean over photographs, each weighted equally; widths are the median over "
         "photographs. Intervals are 95% bootstrap intervals over photographs. The churros photograph "
         "is excluded (see the end).", ""]
    tables = (("p_off_own_10g_all", "More than 1 U (10 g) from the model's typical answer, 12 photographs", True),
              ("p_off_own_20g_all", "More than 2 U (20 g) from the model's typical answer, 12 photographs", True),
              ("width_g_all", "5th-95th percentile width of the estimate (g), 12 photographs", False),
              ("p_over_2u_strong", "Overdose above 2 U against the reference, 5 strong-reference photographs", True),
              ("p_over_5u_strong", "Overdose above 5 U against the reference, 5 strong-reference photographs", True),
              ("p_under_2u_strong", "Underdose above 2 U against the reference, 5 strong-reference photographs", True),
              ("mae_g_strong", "Mean absolute error (g), 5 strong-reference photographs", False),
              ("p_over_2u_ref", "Overdose above 2 U, all 8 reference photographs other than the churros", True))
    for key, title, pct in tables:
        L += [f"## {title}", "", "| arm | " + " | ".join(f"k = {k}" for k in res["ks"]) + " |",
              "|---|" + "---|" * len(res["ks"])]
        for a in arms:
            L.append(f"| {labels[a]} | " + " | ".join(fmt(S[a][k][key], pct) if key in S[a][k] else ""
                                                    for k in res["ks"]) + " |")
        L.append("")

    L += ["## Direction of change in the 2 U overdose rate, 1 call to 20 calls (8 reference photographs)", "",
          "| arm | fell | rose | unchanged, above zero | zero throughout |", "|---|---|---|---|---|"]
    for a in arms:
        d = res["direction"][a]
        L.append(f"| {labels[a]} | {d['fell']} | {d['rose']} | {d['unchanged_nonzero']} | {d['zero_throughout']} |")
    L += ["", "### Photographs with any 2 U overdose risk", "",
          "| arm | photograph | typical error (g) | 1 call | 20 calls |", "|---|---|---|---|---|"]
    for a in arms:
        for d in res["direction"][a]["detail"]:
            if d["p1"] > 0 or d["p20"] > 0:
                L.append(f"| {labels[a]} | {d['photo']} | {d['typical_error_g']:+.1f} | "
                         f"{100*d['p1']:.1f}% | {100*d['p20']:.1f}% |")

    L += ["", "## Sensitivity: mean instead of median, and median without replacement", ""]
    for name, V in res["variants"].items():
        L += [f"### {name.replace('_', ' ')}", "", "| arm | measure | " +
              " | ".join(f"k = {k}" for k in res["ks"]) + " |", "|---|---|" + "---|" * len(res["ks"])]
        for a in arms:
            for key in ("p_off_own_10g_all", "p_over_2u_strong"):
                L.append(f"| {labels[a]} | {key} | " + " | ".join(
                    fmt(V[a][k][key]) if k in V[a] and key in V[a][k] else "n/a" for k in res["ks"]) + " |")
        L.append("")

    L += ["## Churros (reference 80 g, tier 4), arms other than Astra", "",
          "| arm | k | more than 1 U from typical | overdose above 2 U | underdose above 2 U |", "|---|---|---|---|---|"]
    for a, photos in res["churros"].items():
        for k, m in photos[CHURROS].items():
            if k in (1, 5, 20):
                L.append(f"| {labels[a]} | {k} | {100*m['p_off_own_10g']:.1f}% | {100*m['p_over_2u']:.1f}% | "
                         f"{100*m['p_under_2u']:.1f}% |")
    path.write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
