#!/usr/bin/env python3
"""Analyses added in version 2 of the September 2026 preprint.

1. Underestimation. The same resampling as averaging_risk.py (same seed, draws
   and k), with the share of k-call medians more than 10, 20 and 40 g BELOW
   the reference alongside the same thresholds above it. At 1 U per 10 g,
   20 g is 2 U; at 1 U per 5 g, 10 g is 2 U.
2. Error as a share of the meal: for each photograph with a reference, the
   mean over answers of |estimate - reference| / reference, then the mean over
   photographs with a 95% bootstrap interval over photographs. This is the
   form in which studies of human carbohydrate counting report error.
3. Figure 4: every arm's answers for every photograph, in grams.
4. Figure 5: each answer as a percentage of that arm's median for the
   photograph, pooled over photographs. April arms are taken relative to the
   median of each 50-call block, pooled over the ten blocks.

No new API calls. The loaders, the response settling and the resampling are
the unchanged functions of update_analysis.py, averaging_check.py and
averaging_risk.py.

    APRIL_RESULTS_DIR=../llm-food-benchmark-academic/results python3 v2_analyses.py

Writes output/v2_analyses.json, output/V2_ANALYSES.md,
output/v2_fig4_meals.png and output/v2_fig5_violin.png.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import averaging_check as avg
import averaging_risk as ar
from update_analysis import APRIL_DIR, ARMS, CHURROS, load_rows, settled

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "output"
KS = (1, 5, 20)
THRESH_G = (10, 20, 40)
N_BOOT = 5000
SEED_BOOT = 20260923
STRONG = {1, 2}
COLOURS = {"fable": "#2a78d6", "gpt-6": "#eb6834", "sonnet": "#1baf7a", "gpt-5": "#eda100"}
NAMES = {
    "IMG-20260410-WA0016.jpg": "Breakfast burrito", "IMG_20250915_112359.jpg": "Bakewell tart",
    "IMG_20260209_192318.jpg": "Soup and bread", "IMG_20260210_142258.jpg": "Cheese sandwich",
    "MVIMG_20260304_120022.jpg": "Bakery cookie", "IMG_20200412_154249.jpg": "Roast dinner",
    "MVIMG_20260303_200132.jpg": "Chilli and rice", "MVIMG_20260308_142023.jpg": "Stuffed pork loin",
    "MVIMG_20260222_204918.jpg": "Churros", "IMG-20260410-WA0017.jpg": "Pizza",
    "IMG-20260410-WA0018.jpg": "Eggs benedict", "IMG-20260410-WA0019.jpg": "Crema catalana",
    "IMG-20260410-WA0020.jpg": "Paella",
}
TIER = {1: "packet label", 2: "weighed", 3: "portioned", 4: "visual estimate"}


def colour(arm: str) -> str:
    return next(c for k, c in COLOURS.items() if arm.startswith(k))


def with_under(base):
    """Extend averaging_risk.photo_metrics with over/under thresholds."""
    def pm(est, own, ref):
        m = base(est, own, ref)
        if ref is not None:
            e = est - ref
            for g in THRESH_G:
                m[f"over_{g}"] = float(np.mean(e > g))
                m[f"under_{g}"] = float(np.mean(e < -g))
        return m
    return pm


def boot_mean(vals, rng):
    v = np.asarray(vals, dtype=float)
    b = [v[rng.integers(0, len(v), len(v))].mean() for _ in range(N_BOOT)]
    return [float(v.mean()), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]


def main():
    ref = json.load(open(BASE_DIR / "usda_reference.json"))
    rows = load_rows()
    arms = [a for a, _ in ARMS]
    labels = dict(ARMS)
    totals = {a: avg.totals_by_image(settled(rows[a])) for a in arms}
    q = lambda p: (ref.get(p) or {}).get("reference_quality")
    rv = lambda p: (ref.get(p) or {}).get("total_portion_carbs_g")
    rng = np.random.default_rng(SEED_BOOT)
    out = {"seed_resample": ar.SEED, "seed_bootstrap": SEED_BOOT}

    # 1. Under- and overestimation with averaging, excluding the churros as averaging_risk does.
    ar.photo_metrics = with_under(ar.photo_metrics)
    res = ar.run(totals, ref, np.median, replace=True, seed=ar.SEED)  # all of ar.KS, so draws match averaging_risk.py
    strong = [p for p in res["photos"] if q(p) in STRONG]
    anyref = [p for p in res["photos"] if rv(p) is not None]
    rates = {}
    for a in arms:
        for set_name, ps in (("strong", strong), ("all8", anyref)):
            for side in ("over", "under"):
                for g in THRESH_G:
                    for k in KS:
                        rates[f"{a}|{set_name}|{side}_{g}|{k}"] = boot_mean(
                            [res["per_photo"][a][p][k][f"{side}_{g}"] for p in ps], rng)
    out["rates"] = rates
    out["typical_error_g"] = {a: {p: res["per_photo"][a][p][1]["typical_error_g"] for p in anyref} for a in arms}

    # Churros: single calls observed; 20-call medians resampled (Astra has 10 answers, single calls only).
    churros = {}
    ref_c = rv(CHURROS)
    for a in arms:
        v = np.asarray(totals[a][CHURROS], dtype=float)
        row = {"n": int(len(v)), "under_20_1": float(np.mean(v < ref_c - 20)),
               "under_10_1": float(np.mean(v < ref_c - 10))}
        if a != "gpt-6-astra":
            r2 = np.random.default_rng(ar.SEED)
            med = np.median(v[r2.integers(0, len(v), size=(ar.DRAWS, 20))], axis=1)
            row["under_20_20"] = float(np.mean(med < ref_c - 20))
        churros[a] = row
    out["churros"] = churros

    # 2. Error as a share of the meal, every answer, all photographs with a reference.
    share = {}
    for a in arms:
        for set_name, sel in (("strong", lambda p: q(p) in STRONG), ("all9", lambda p: rv(p) is not None)):
            ps = [p for p in totals[a] if sel(p)]
            per = [float(np.mean(np.abs(np.asarray(totals[a][p]) - rv(p)) / rv(p))) for p in ps]
            share[f"{a}|{set_name}"] = boot_mean(per, rng)
    out["share_of_meal"] = share
    out["mean_reference_g"] = {"strong": float(np.mean([rv(p) for p in totals[arms[0]] if q(p) in STRONG]))}

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "v2_analyses.json").write_text(json.dumps(out, indent=1))
    figure_meals(totals, ref, labels, OUT_DIR / "v2_fig4_meals.png")
    figure_violin(OUT_DIR / "v2_fig5_violin.png")
    write_report(out, labels, OUT_DIR / "V2_ANALYSES.md")
    print((OUT_DIR / "V2_ANALYSES.md").read_text())


def figure_meals(totals, ref, labels, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    ink, muted, grid = "#0b0b0b", "#52514e", "#e4e3dd"
    arms = ["fable-5-1", "gpt-6-astra", "sonnet-4-6-default", "gpt-5-4-default"]
    q = lambda p: (ref.get(p) or {}).get("reference_quality", 9)
    order = sorted(NAMES, key=lambda p: (0 if q(p) <= 2 else 1 if q(p) <= 4 else 2, q(p), NAMES[p]))
    n = len(order)
    fig, ax = plt.subplots(figsize=(7.2, 8.4), dpi=220)
    for i, p in enumerate(order):
        y = n - 1 - i
        if i % 2 == 0:
            ax.axhspan(y - 0.5, y + 0.5, color="#f6f6f3", zorder=0)
        r = (ref.get(p) or {}).get("total_portion_carbs_g")
        if r is not None:
            s = q(p) <= 2
            ax.plot([r, r], [y - 0.42, y + 0.42], color=ink, lw=2.2 if s else 1.2,
                    ls="-" if s else (0, (2, 1.5)), zorder=2)
        for j, a in enumerate(arms):
            v = np.asarray(totals[a].get(p, []), dtype=float)
            if not len(v):
                continue
            yy, c = y + 0.27 - j * 0.18, colour(a)
            q1, med, q3 = np.percentile(v, [25, 50, 75])
            p5, p95 = np.percentile(v, [5, 95])
            ax.plot([p5, p95], [yy, yy], color=c, lw=0.9, alpha=0.8, zorder=3)
            ax.plot([q1, q3], [yy, yy], color=c, lw=3.2, solid_capstyle="butt", zorder=3)
            ax.scatter([med], [yy], s=16, color="white", edgecolor=c, linewidth=1.2, zorder=4)
            if a == "gpt-6-astra" and p == CHURROS:
                ax.annotate(f"n = {len(v)}", (p95 + 3, yy), fontsize=5.5, va="center", color=c)
    ax.set_yticks(range(n), [f"{NAMES[p]}\n{TIER.get(q(p), 'no reference')}" for p in order][::-1],
                  fontsize=7, color=ink)
    for k, t in enumerate(ax.get_yticklabels()[::-1]):
        if q(order[k]) <= 2:
            t.set_fontweight("bold")
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xlabel("Estimated carbohydrate (g)", fontsize=8, color=muted)
    ax.tick_params(axis="x", labelsize=7.5, colors=muted)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=grid, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(grid)
    for yb in (n - 5.5, n - 9.5):
        ax.axhline(yb, color=muted, lw=0.8)
    h = [Line2D([], [], color=colour(a), lw=3.2, label=labels[a]) for a in arms]
    h += [Line2D([], [], color=ink, lw=2.2, label="reference: label or weighed"),
          Line2D([], [], color=ink, lw=1.2, ls=(0, (2, 1.5)), label="reference: portioned or visual")]
    ax.legend(handles=h, fontsize=6.5, frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.06), ncol=3)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def figure_violin(path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    rows = load_rows()
    april = avg.load_april(APRIL_DIR)
    devs = {}
    for arm, _ in ARMS:
        if arm.endswith("-april"):
            blocks = [[r for r in april[arm] if lo <= r["iteration"] < lo + 50] for lo in range(1, 501, 50)]
        else:
            blocks = [settled(rows[arm])]
        d = []
        for b in blocks:
            for v in avg.totals_by_image([r for r in b if r["success"]]).values():
                v = np.asarray(v, dtype=float)
                m = np.median(v)
                if m > 0:
                    d += list((v - m) / m * 100)
        devs[arm] = np.asarray(d)
    ink, muted, grid, lim = "#0b0b0b", "#52514e", "#e4e3dd", 50
    mpl.rcParams["hatch.linewidth"] = 0.7
    fig, ax = plt.subplots(figsize=(7.2, 3.9), dpi=220)
    for x, (a, label) in enumerate(ARMS):
        v, c, apr = devs[a], colour(a), a.endswith("-april")
        p = ax.violinplot([v[np.abs(v) <= lim * 3]], positions=[x], widths=0.8, showextrema=False,
                          bw_method=0.25, points=400)
        for b in p["bodies"]:
            b.set_edgecolor(c)
            b.set_linewidth(1.1)
            if apr:
                b.set_facecolor("none")
                b.set_hatch("////")
            else:
                b.set_facecolor(c)
                b.set_alpha(0.6)
        q1, q3, p5, p95 = np.percentile(v, [25, 75, 5, 95])
        ax.plot([x, x], [p5, p95], color=ink, lw=0.9, zorder=3)
        ax.plot([x, x], [q1, q3], color=ink, lw=4, solid_capstyle="butt", zorder=3)
        ax.scatter([x], [0], s=14, color="white", edgecolor=ink, zorder=4, linewidth=0.8)
        out = np.mean(np.abs(v) > lim) * 100
        if out:
            ax.annotate(f"{out:.1f}% beyond ±{lim}%", (x, -lim - 7), ha="center", fontsize=6, color=muted)
    ax.set_ylim(-lim - 10, lim + 9)
    ax.set_yticks([-40, -20, 0, 20, 40])
    ax.axhline(0, color=grid, lw=0.8, zorder=0)
    ax.set_xticks(range(len(ARMS)), [l.replace(", ", "\n") for _, l in ARMS], fontsize=7.5, color=ink)
    ax.set_ylabel("Answer relative to the arm's median\nfor the photograph (%)", fontsize=8, color=muted)
    ax.tick_params(axis="y", labelsize=7.5, colors=muted)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color=grid, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(grid)
    ax.legend(handles=[Patch(facecolor="#9a9994", alpha=0.6, label="filled: provider default (50 calls)"),
                       Patch(facecolor="none", edgecolor=muted, hatch="////",
                             label="hatched: April, temperature 0.01 (ten 50-call blocks)"),
                       Line2D([], [], color=ink, lw=4, label="middle 50%"),
                       Line2D([], [], color=ink, lw=0.9, label="5th to 95th percentile")],
              fontsize=6.5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def write_report(out, labels, path):
    f = lambda t: f"{t[0]*100:.1f}% ({t[1]*100:.1f} to {t[2]*100:.1f})"
    L = ["# Version 2 analyses", "",
         "## Estimates below and above the reference, five strong-reference photographs", "",
         "| Arm | >10 g low, 1 | 5 | 20 | >20 g low, 1 | 20 | >10 g high, 1 | 20 | >20 g high, 1 | 20 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    r = out["rates"]
    for a, l in labels.items():
        g = lambda key, k: f(r[f"{a}|strong|{key}|{k}"])
        L.append(f"| {l} | {g('under_10',1)} | {g('under_10',5)} | {g('under_10',20)} | {g('under_20',1)} | "
                 f"{g('under_20',20)} | {g('over_10',1)} | {g('over_10',20)} | {g('over_20',1)} | {g('over_20',20)} |")
    L += ["", "## Eight reference photographs other than the churros, more than 20 g low", ""]
    for a, l in labels.items():
        L.append(f"- {l}: 1 call {f(r[f'{a}|all8|under_20|1'])}, 20 calls {f(r[f'{a}|all8|under_20|20'])}")
    L += ["", "## Churros (reference 80 g, visual estimate)", ""]
    for a, c in out["churros"].items():
        extra = f", 20-call medians {c['under_20_20']*100:.1f}%" if "under_20_20" in c else ""
        L.append(f"- {labels[a]} (n = {c['n']}): more than 20 g low in {c['under_20_1']*100:.1f}% of calls{extra}")
    L += ["", "## Mean absolute error as a share of the reference", "",
          "| Arm | Five strong-reference | All nine reference |", "|---|---|---|"]
    for a, l in labels.items():
        s = out["share_of_meal"]
        L.append(f"| {l} | {f(s[f'{a}|strong'])} | {f(s[f'{a}|all9'])} |")
    L += ["", f"Mean strong-reference value: {out['mean_reference_g']['strong']:.1f} g."]
    path.write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
