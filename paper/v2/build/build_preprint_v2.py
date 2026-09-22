"""Builds the v2 preprint PDF. Text and tables are inline below; figures come from ./figures
(copies of the repo outputs). Output: $DIST_DIR or ../dist/.

    pip install reportlab
    python3 build_preprint_v2.py
"""
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, KeepTogether)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping

import os, glob
from pathlib import Path
HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
DIST = Path(os.environ.get("DIST_DIR", HERE.parent / "dist"))
DIST.mkdir(parents=True, exist_ok=True)


def find_font(name):
    """Look for a TTF in the usual places (Linux, macOS, FONT_DIR)."""
    dirs = [os.environ.get("FONT_DIR", ""), "/usr/share/fonts", "/usr/local/share/fonts",
            "/Library/Fonts", "/System/Library/Fonts", str(Path.home() / "Library/Fonts")]
    for d in dirs:
        if d:
            hits = glob.glob(os.path.join(d, "**", name), recursive=True)
            if hits:
                return hits[0]
    return None


FONTS = {"LS": "LiberationSerif-Regular.ttf", "LSB": "LiberationSerif-Bold.ttf",
         "LSI": "LiberationSerif-Italic.ttf", "LSBI": "LiberationSerif-BoldItalic.ttf"}
paths = {k: find_font(v) for k, v in FONTS.items()}
if all(paths.values()):
    for k, v in paths.items():
        pdfmetrics.registerFont(TTFont(k, v))
    addMapping("LS", 0, 0, "LS"); addMapping("LS", 1, 0, "LSB"); addMapping("LS", 0, 1, "LSI"); addMapping("LS", 1, 1, "LSBI")
    FALLBACK = False
else:  # built-in Times; swap the one glyph it lacks
    print("Liberation Serif not found; falling back to Times (install fonts-liberation for the intended look)")
    for k, v in {"LS": "Times-Roman", "LSB": "Times-Bold", "LSI": "Times-Italic", "LSBI": "Times-BoldItalic"}.items():
        globals()[k] = v
    FALLBACK = True

GREY = colors.HexColor("#555555")
body = ParagraphStyle("b", fontName=("Times-Roman" if FALLBACK else "LS"), fontSize=10, leading=13.4, spaceAfter=6, alignment=TA_JUSTIFY)
bul = ParagraphStyle("bu", parent=body, leftIndent=12, bulletIndent=2, spaceAfter=3)
title = ParagraphStyle("t", fontName=("Times-Bold" if FALLBACK else "LSB"), fontSize=17, leading=21, alignment=TA_CENTER, spaceAfter=6)
sub = ParagraphStyle("s", fontName=("Times-Italic" if FALLBACK else "LSI"), fontSize=11.5, leading=14, alignment=TA_CENTER, spaceAfter=8)
auth = ParagraphStyle("a", fontName=("Times-Roman" if FALLBACK else "LS"), fontSize=11, leading=14, alignment=TA_CENTER, spaceAfter=2)
aff = ParagraphStyle("af", fontName=("Times-Roman" if FALLBACK else "LS"), fontSize=9, leading=12, alignment=TA_CENTER, spaceAfter=6)
note = ParagraphStyle("n", fontName=("Times-Italic" if FALLBACK else "LSI"), fontSize=8.5, leading=11, alignment=TA_CENTER, spaceAfter=10, textColor=GREY)
h1 = ParagraphStyle("h1", fontName=("Times-Bold" if FALLBACK else "LSB"), fontSize=12.5, leading=16, spaceBefore=10, spaceAfter=5, keepWithNext=1)
h2 = ParagraphStyle("h2", fontName=("Times-BoldItalic" if FALLBACK else "LSBI"), fontSize=10.5, leading=14, spaceBefore=7, spaceAfter=4, keepWithNext=1)
abs_h = ParagraphStyle("ah", fontName=("Times-Bold" if FALLBACK else "LSB"), fontSize=11, leading=14, spaceAfter=4)
cap = ParagraphStyle("c", fontName=("Times-Roman" if FALLBACK else "LS"), fontSize=8.8, leading=11.2, alignment=TA_JUSTIFY, spaceAfter=10)
tcap = ParagraphStyle("tc", fontName=("Times-Roman" if FALLBACK else "LS"), fontSize=9, leading=11.5, alignment=TA_JUSTIFY, spaceAfter=4, keepWithNext=1)
td = ParagraphStyle("td", fontName=("Times-Roman" if FALLBACK else "LS"), fontSize=8, leading=9.6)
th = ParagraphStyle("th", fontName=("Times-Bold" if FALLBACK else "LSB"), fontSize=8, leading=9.6)
ref = ParagraphStyle("r", fontName=("Times-Roman" if FALLBACK else "LS"), fontSize=8.8, leading=11.2, leftIndent=12, firstLineIndent=-12, spaceAfter=3)
kw = ParagraphStyle("k", parent=body, fontSize=9)

W = A4[0] - 44 * mm
P = lambda t, s=body: Paragraph(t.replace("\u2212", "-") if FALLBACK else t, s)
B = lambda items: [Paragraph(i, bul, bulletText="•") for i in items]
LINK = lambda u, t=None: f'<link href="{u}" color="#1a4f9c">{t or u}</link>'


def table(caption, rows, widths=None, head=1):
    n = len(rows[0])
    widths = widths or [W / n] * n
    data = [[Paragraph(str(c), th if i < head else td) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=head)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, head - 1), colors.HexColor("#e6e6e6")),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9a9a9a")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                           ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return [P(caption, tcap), t, Spacer(1, 10)]


def fig(path, ratio, caption, sc=1.0):
    return KeepTogether([Image(path, width=W * sc, height=W * sc * ratio), Spacer(1, 3), P(caption, cap)])


V1 = "https://doi.org/10.5281/zenodo.22879140"
GH = "https://github.com/tim2000s/llm-food-benchmark-2026-09"
s = []
s += [P("Carbohydrate estimates from food photographs by Claude Fable 5.1 and GPT-6 Astra: a September 2026 update to a reproducibility benchmark", title),
      P("Averaging repeated calls removes outlying estimates and leaves systematic error in place", sub),
      P("Tim Street", auth),
      P(f"Diabettech Ltd, United Kingdom. {LINK('https://www.diabettech.com')}", aff),
      P(f"Preprint. Data collection and analysis first published on github.com/tim2000s/llm-food-benchmark-2026-09 on 21 September 2026. "
        f"This version: v2, 22 September 2026. Version 1 (21 September 2026): {LINK(V1)}. Section 7 lists the changes. "
        "Licence: Creative Commons Attribution 4.0 International (CC BY 4.0).", note)]

s.append(P("Abstract", abs_h))
s.append(P(
    "In April 2026 a benchmark sent 13 food photographs about 500 times each to four vision-capable large language models (LLMs) at temperature 0.01 and reported median "
    "within-photograph coefficients of variation (CV) of 2.4% to 11.0%. Two newer models, Claude Fable 5.1 and GPT-6 Astra, accept no sampling parameter and cannot run "
    "without reasoning, so that condition can no longer be reproduced. This update sent the same photographs and prompt 50 times each to the two new models and to Claude "
    "Sonnet 4.6 and GPT-5.4 at provider-default sampling. An application can respond to the lost control by sending a photograph several times and taking the median answer. "
    "Simulated from the calls already made, the median of 20 calls cut the share of estimates more than 1 U (10 g) from the model's own typical answer from between 3.4% and "
    "17.5% to 1.5% or less. On the five photographs with packet-label or weighed references, no estimate implying an insulin overdose above 5 U remained in the resampled "
    "20-call medians, but the share implying an overdose above 2 U did not fall: 19.2% with one call and 20.0% with 20 for Astra, and 34.7% and 40.0% for GPT-5.4. Each "
    "photograph's rate moved towards 0% if the model's typical answer was within 20 g of the reference and towards 100% if it was not, so averaging removed outlying estimates "
    "and left systematic error in place. Underestimation followed the same pattern: no model was more than 20 g below any of the eight non-visual references, but Fable 5.1 "
    "and Sonnet 4.6 were more than 10 g low in 21.2% and 39.2% of single estimates and 20.0% and 40.0% of 20-call medians. Mean absolute error as a share of the reference was "
    "17.5% for Fable 5.1, 20.3% for Sonnet 4.6, 35.2% for Astra and 38.2% for GPT-5.4, against about 21% reported for adults with type 1 diabetes estimating their own, larger "
    "meals in a separate study. Compared across all ten 50-call blocks of the April runs, default sampling raised the median CV of Sonnet 4.6 from 2.3% (95% CI 1.8 to 3.2) to "
    "5.7% (4.2 to 7.1) and of GPT-5.4 from 7.8% (4.8 to 10.6) to 10.1% (7.8 to 17.4); Fable 5.1 and Astra had 6.3% (5.4 to 8.9) and 5.7% (3.3 to 9.8). Astra returned "
    "unparseable output in 40 of 50 calls on one photograph and in 1% elsewhere. Five strong-reference photographs did not resolve differences in accuracy between models; as a "
    "rough planning estimate, detecting a 5 g difference would need between 13 and 57 photographs depending on the pair. Overdose rates depend on the "
    "insulin-to-carbohydrate ratio assumed, and at 1 U per 5 g every model exceeded 2 U in at least 15% of estimates."))
s.append(P("<b>Keywords:</b> artificial intelligence, carbohydrate counting, large language models, reproducibility, food recognition, insulin dosing, type 1 diabetes, automated insulin delivery", kw))

# 1
s.append(P("1. Why an update", h1))
s += [P("The April 2026 preprint [1] asked how much a vision-capable LLM disagrees with itself when shown the same food photograph repeatedly, and how that disagreement "
        "relates to accuracy. Thirteen photographs were each sent between 495 and 561 times to GPT-5.4, Claude Sonnet 4.6, Gemini 2.5 Pro and Gemini 3.1 Pro Preview, using a "
        "food-analysis prompt adapted from the iAPS automated insulin delivery system [2], at temperature 0.01. The median within-photograph CV ranged from 2.4% for Sonnet 4.6 "
        "to 11.0% for Gemini 2.5 Pro. On the five photographs with the strongest reference values, Sonnet 4.6 had the lowest mean absolute error (MAE, 8.7 g) and none of its "
        "estimates implied an insulin overdose above 2 U."),
      P("Two things have changed since. Both providers have released new flagship models, Claude Fable 5.1 from Anthropic and GPT-6 Astra from OpenAI. Neither accepts "
        "temperature or top_p: Fable 5.1 rejects them with an error [3], and OpenAI's migration guide for Astra says to remove them [4]. Neither can be run without reasoning. "
        "The condition the April study held fixed is therefore no longer available on current models, and any application using them samples at whatever the provider does by default."),
      P("The April preprint anticipated both halves of this. Its limitations noted that deployments at higher temperatures \u201cwould experience greater variation still\u201d, "
        "and its recommendations proposed sending each photograph three to five times and presenting the median. This update measures the first and tests the second, extending "
        "the test to 20 calls.")]

# 2
s.append(P("2. Methods", h1))
s.append(P("2.1 Arms", h2))
s.append(P("Four arms were run on 21 September 2026 (Table 1). The two new models ran at the lowest reasoning effort each allows (low), matched between them; this is a "
           "modelling choice, made because it is the setting closest to deterministic that remains. The two April models were rerun with the temperature setting removed and "
           "everything else as in April, so that the only change for them is sampling. Sonnet 4.6 ran without extended thinking, as in April, and GPT-5.4 at its default reasoning "
           "setting, which used no reasoning tokens in either run."))
s += table("<b>Table 1.</b> Arms of the September 2026 run.", [
    ["Arm", "Model", "Sampling", "Reasoning", "Image long edge", "Calls per photograph"],
    ["Fable 5.1", "claude-fable-5-1", "provider default", "effort low (thinking always on)", "1,568 px", "50"],
    ["Astra", "gpt-6-astra", "provider default", "effort low", "2,048 px", "50"],
    ["Sonnet 4.6, default", "claude-sonnet-4-6", "provider default", "none", "1,568 px", "50"],
    ["GPT-5.4, default", "gpt-5.4", "provider default", "provider default", "2,048 px", "50"]],
    [W * x for x in (0.16, 0.18, 0.16, 0.22, 0.14, 0.14)])
s.append(P("The prompt and image preprocessing (per-provider maximum dimension, JPEG quality 85) were those of April, and the SHA-256 of the prompt recorded in every results "
           "file matches the April hash. The response parser was April's apart from the corrections in section 2.5. Each call was an independent request through the provider's "
           "batch API. Gemini models were not rerun."))
s.append(P("2.2 Comparison with April", h2))
s += [P("The April runs made about 500 calls per photograph and this run made 50. A within-photograph range grows with the number of calls, and the 5th to 95th percentile "
        "width does so to a lesser degree, so figures from 500 calls are not comparable with figures from 50. The April runs were therefore divided into their ten complete blocks "
        "of 50 calls per photograph (calls 1 to 50, 51 to 100, and so on to 500), each measure was computed within every block, and the April comparator is the median over the "
        "ten blocks. For the per-photograph CV used in paired tests, each photograph's April CV is the median of its ten block CVs."),
      P("This matters for GPT-5.4. Its median CV varies between blocks from 4.3% to 9.1%, against 8.4% over all calls pooled, because the April GPT-5.4 data were collected as "
        "many separately submitted sub-batches and part of the published spread comes from differences between them. For Sonnet 4.6 the block medians lie between 1.9% and 2.9%. "
        "The first 50 calls happen to form GPT-5.4's least variable block, and comparing against them alone would overstate the effect of default sampling; that comparison is "
        "reported as secondary. Accuracy for the April arms is computed on their first 50 calls, which reproduce the published values closely (MAE on the strong-reference "
        "photographs of 8.8 g for Sonnet 4.6 and 17.3 g for GPT-5.4, against 8.7 g and 17.4 g published).")]
s.append(P("2.3 Measures", h2))
s += [P("Total carbohydrate, CV, range, interquartile range, 5th to 95th percentile width, reference tiers and overdose thresholds follow the April definitions [1]. Intervals "
        "are 95% bootstrap intervals over photographs (5,000 resamples), because the photograph is the unit a reader would generalise over; April quoted per-query t intervals, "
        "which treat 500 calls about one photograph as 500 independent observations and are much narrower. Paired comparisons of per-photograph CV use the Wilcoxon signed-rank test."),
      P("Accuracy is reported primarily on the five photographs whose references come from a packet label or weighing. The set of all nine reference photographs adds three "
        "portioned references and one visual estimate (the churros, 80 g), and is reported as exploratory. Even the strong references carry uncertainty: packet labels have "
        "declared tolerances, and the weighed references combine a measured weight with typical composition for the food. They should be read as accurate to a few grams, which "
        "matters for photographs whose typical estimate lies near a threshold."),
      P("Insulin figures convert grams at 1 U per 10 g, as April did. That ratio is an illustration, not a property of any person; ratios vary several-fold between people. "
        "Throughout, \u201coverdose\u201d means an estimate which, if bolused for at the stated ratio, would give more than the stated amount of meal insulin above the dose for the "
        "reference. It is arithmetic on the estimate, not an observed dosing event, and takes no account of insulin on board, corrections, limits or an automated system's "
        "response. The overdose rates are also reported at 1 U per 5 g and 1 U per 20 g, at which a 2 U overdose corresponds to 10 g and 40 g above the reference."),
      P("Version 2 adds two measures. Underestimation is the share of estimates more than 10 g, 20 g or 40 g below the reference, computed in the same way as the overestimation "
        "thresholds. Error as a share of the meal is, for each reference photograph, the mean over answers of the absolute difference from the reference divided by the reference, "
        "averaged over photographs; this is the form in which studies of human carbohydrate counting commonly report error."),
      P("The number of photographs needed to rank two models by accuracy was estimated from the spread of their paired per-photograph MAE differences, for 80% power at a "
        "two-sided 5% level (normal approximation). Because that spread is itself estimated from five to nine photographs, these figures are rough planning estimates rather than "
        "required sample sizes.")]
s.append(P("2.4 Averaging", h2))
s += [P("The averaging analysis made no new calls. For each photograph, arm and number of calls k (1, 2, 3, 5, 10 and 20), 10,000 batches of k answers were drawn with "
        "replacement from that arm's answers for the photograph and the median of each batch taken; the same random draws were applied to every arm (seed 20260922). Drawing with "
        "replacement treats a photograph's answers as the model's distribution for it. Drawing 20 of 50 without replacement would make simulated batches share most of their "
        "answers and understate the spread of 20 fresh calls by about a fifth. Drawing without replacement, and the mean in place of the median, were run as sensitivity analyses. "
        "Rates are means over photographs, each photograph weighted equally."),
      P("Two kinds of risk are distinguished because they respond to averaging differently. Variability risk is the chance that an estimate lands more than 10 g (1 U) from the "
        "model's own typical answer for the photograph, the median of all its answers; it needs no reference. Accuracy risk is the chance that an estimate implies an overdose "
        "above 2 U against the reference.")]
s.append(P("2.5 Changes to the benchmark code", h2))
s.append(P("Three faults in the April code would have affected the new models and were corrected before or during the run. None changes any April result."))
s += B(["The Anthropic reader took the first content block as the answer. On a model that always thinks, the first block is the thinking block, so every Fable 5.1 answer "
        "would have been lost. The answer is now the concatenation of the text blocks.",
        "When a response was malformed JSON, the April extractor could fall back to a nested object (a single food item) and record a successful answer with no food items, which "
        "scores as 0 g. A response without a top-level list of food items is now a parse failure. This occurred in 2 Fable 5.1 responses; none of the 26,909 April answers had the pattern.",
        "Requests rejected by OpenAI at validation appear only in a batch's error file, which the April runner did not read. It now does."])
s.append(P("Both provider accounts ran out of credit during the run. The 190 requests affected were resubmitted and every photograph-and-call slot was settled once. The code "
           "and the raw responses are public [5], and section 3.6 gives the cost. The repository's 54 unit tests, which include tests that the text-block reader still reads a "
           "response without a thinking block and that malformed JSON is a failure rather than 0 g, pass on a fresh copy."))
s.append(P("2.6 Independence of the analysis", h2))
s += [P("The benchmark code, the analysis and the drafting of this paper were done with Claude Code, an Anthropic product, and Anthropic makes Fable 5.1 and Sonnet 4.6. The "
        "design limits what that relationship could influence in three ways. The prompt is April's, adapted from the iAPS codebase before this work began, and its hash is "
        "unchanged. Everything that turns a response into a number (JSON extraction, the total carbohydrate calculation and every measure) is the same code for every model and "
        "does not know which model produced the response; the provider-specific code only submits requests and reads the text back. The one provider-specific correction, the "
        "Anthropic text-block reader, restores answers that would otherwise have been lost and does not alter any answer that was read. The code, every raw response and the "
        "scripts behind each table are public [5], so each figure can be regenerated and checked. The analysis was not pre-registered and has not been independently audited."),
      P("The analyses added in version 2 (section 3.7, Figures 4 and 5 and Table 9) were computed with Claude, also an Anthropic product, from the public repository. The script "
        "that produces them, v2_analyses.py, calls the repository's existing loaders, response settling and resampling functions unchanged, with the same seed, and adds only the "
        "new thresholds, the share-of-meal calculation and the two figures.")]

# 3
s.append(P("3. Results", h1))
s.append(P("3.1 Completion", h2))
s += [P("Sonnet 4.6 and GPT-5.4 answered all 650 calls. Fable 5.1 answered 648; the other two were the malformed responses described above, both on the stuffed pork loin. "
        "Astra answered 604 (92.9%). All 46 of its failures had the same cause: a numeric field in the JSON was written as a word, always after a doubled space. On the churros "
        "photograph it wrote the carbohydrate content per 100 g as <i>forty</i> or <i>Forty</i> in 39 of 50 calls and as <i>progressively55.0</i> once. The six failures on three "
        "other photographs were similar (<i>fifty</i>, and in three cases unrelated words such as <i>skinless</i>)."),
      P("The failures were concentrated on one meal. On the other 12 photographs Astra failed in 1.0% of calls and Fable 5.1 in 0.3%, and a single retry would recover almost all "
        "of them. On the churros Astra failed in 80% of calls. If attempts were independent, an application would need five attempts on average to obtain an answer, and three "
        "attempts in a row would all fail 51% of the time; because the failures cluster on one photograph, retries may well be correlated and fare worse. Astra therefore has 10 "
        "answers for the churros, and measures that include that photograph rest on those 10.")]
s.append(P("3.2 Reproducibility", h2))
s.append(P("Default sampling increased the spread of both April models (Table 2, Figure 1). Against the April runs taken over all ten blocks, the median CV of Sonnet 4.6 rose "
           "from 2.3% to 5.7%, higher on 11 of 13 photographs (median difference 2.1 percentage points, p = 0.027), and that of GPT-5.4 from 7.8% to 10.1%, higher on 12 of 13 "
           "(median difference 3.1 points, p = 0.001). Against each April block separately, default sampling gave the higher CV on 10 to 13 photographs for GPT-5.4 (p from 0.0002 "
           "to 0.027) and on 10 to 12 for Sonnet 4.6 (p from 0.017 to 0.057). Against the first 50 April calls alone, GPT-5.4's rise appears as 4.3% to 10.1%, which overstates it "
           "for the reason given in section 2.2."))
s += table("<b>Table 2.</b> Reproducibility at 50 calls per photograph. The April columns are medians over the ten 50-call blocks of the April runs; CV and width medians take "
           "each photograph's median over blocks. Intervals are 95% bootstrap intervals over the 13 photographs.", [
    ["Measure", "Fable 5.1", "Astra", "Sonnet 4.6, default", "Sonnet 4.6, April 0.01", "GPT-5.4, default", "GPT-5.4, April 0.01"],
    ["Answers", "648 of 650", "604 of 650", "650 of 650", "650 per block", "650 of 650", "650 per block"],
    ["CV, median", "6.3% (5.4\u20138.9)", "5.7% (3.3\u20139.8)", "5.7% (4.2\u20137.1)", "2.3% (1.8\u20133.2)", "10.1% (7.8\u201317.4)", "7.8% (4.8\u201310.6)"],
    ["CV, maximum", "10.0%", "17.1%", "19.0%", "29.7%", "33.9%", "22.5%"],
    ["P5\u2013P95 width, median (g)", "11.9 (7.2\u201314.9)", "11.6 (8.2\u201320.0)", "7.1 (4.5\u201313.5)", "3.8 (2.0\u20136.8)", "19.1 (13.9\u201333.1)", "12.9 (8.3\u201321.3)"],
    ["Range, median (g)", "16.8", "17.0", "12.1", "7.3", "29.6", "18.4"],
    ["Insulin range, median (U)", "1.7", "1.7", "1.2", "0.7", "3.0", "1.8"],
    ["Photographs with range > 2 U", "5", "6", "4", "2", "10", "5"],
    ["Photographs with range > 5 U", "0", "0", "1", "1", "3", "2"]],
    [W * x for x in (0.19, 0.13, 0.13, 0.14, 0.14, 0.14, 0.13)])
s.append(fig(str(FIG / "fig1_cv_by_arm_blocks.png"), 720 / 1440, "<b>Figure 1.</b> Within-photograph CV of the carbohydrate estimate for each of the 13 photographs, by arm. Blue points are provider-default "
             "sampling at 50 calls per photograph; grey points are the April runs at temperature 0.01, each the median over the photograph's ten 50-call blocks. The black bar is the median."))
s.append(P("The two new models were close to Sonnet 4.6 at default sampling. Their median CVs, 6.3% for Fable 5.1 and 5.7% for Astra, were indistinguishable from each other "
           "(p = 0.95). Fable 5.1 did not differ detectably from Sonnet 4.6 at default sampling (p = 0.79). Astra's CV was lower than GPT-5.4 at default sampling on 10 of 13 "
           "photographs (median difference 4.7 points, p = 0.003). Fable 5.1 had the lowest maximum CV of any arm (10.0%), and neither new model had a photograph with a range above "
           "5 U. Figure 5 in section 3.7 shows the same comparison as the distribution of individual answers."))
s.append(P("3.3 Accuracy and insulin translation", h2))
s += table("<b>Table 3.</b> Accuracy against the five strong-reference photographs (packet label or weighed), the primary set, and against all nine reference photographs, "
           "exploratory. MAE intervals are 95% bootstrap intervals over photographs. Insulin figures use 1 U per 10 g; Table 4 gives other ratios. The rows for error as a share "
           "of the reference are new in version 2.", [
    ["Measure", "Fable 5.1", "Astra", "Sonnet 4.6, default", "Sonnet 4.6, April 0.01", "GPT-5.4, default", "GPT-5.4, April 0.01"],
    ["Strong: MAE (g)", "7.0 (3.6\u201310.3)", "13.2 (4.7\u201325.7)", "8.8 (5.9\u201311.6)", "8.8 (4.8\u201312.0)", "14.7 (4.2\u201325.4)", "17.3 (7.0\u201328.1)"],
    ["Strong: MAE as share of reference", "17.5% (7.4\u201327.8)", "35.2% (9.4\u201373.9)", "20.3% (13.8\u201325.7)", "20.2% (11.5\u201326.8)", "38.2% (8.8\u201368.7)", "44.6% (14.1\u201378.4)"],
    ["Strong: mean bias (g)", "+0.3", "+8.8", "\u22120.6", "\u22121.1", "+9.9", "+11.5"],
    ["Strong: within 20 g", "100%", "80.7%", "100%", "100%", "65.2%", "61.6%"],
    ["Strong: > 2 U overdose", "0.0%", "19.3%", "0.0%", "0.0%", "34.8%", "38.4%"],
    ["Strong: > 5 U overdose", "0.0%", "2.0%", "0.0%", "0.0%", "0.4%", "0.0%"],
    ["Strong: worst overdose (U)", "1.7", "5.9", "1.6", "1.2", "5.9", "4.3"],
    ["All nine (exploratory): MAE (g)", "8.9 (5.9\u201311.8)", "15.1 (7.5\u201322.4)", "10.7 (7.2\u201314.6)", "11.4 (7.3\u201316.2)", "16.6 (8.9\u201324.0)", "20.4 (12.6\u201328.3)"],
    ["All nine (exploratory): MAE as share of reference", "18.8% (12.0\u201325.9)", "33.0% (15.7\u201355.9)", "21.1% (15.4\u201327.0)", "22.4% (15.4\u201329.3)", "35.9% (18.8\u201354.4)", "45.8% (24.2\u201369.1)"],
    ["All nine (exploratory): mean bias (g)", "\u22121.5", "+10.6", "+1.6", "+1.8", "+7.8", "+12.7"]],
    [W * x for x in (0.19, 0.13, 0.13, 0.14, 0.14, 0.14, 0.13)])
s += [P("Astra and GPT-5.4 overestimated the strong-reference photographs, with mean biases of +8.8 g and +9.9 g, and 19.3% and 34.8% of their estimates implied an overdose "
        "above 2 U. Fable 5.1 and Sonnet 4.6 had biases within 1 g of zero and no such estimate. Their near-zero bias is partly errors in opposite directions cancelling; "
        "section 3.7 gives the underestimates."),
      P("These differences between models are not established by the data. Compared photograph by photograph over the nine reference photographs, Fable 5.1's MAE was lower than "
        "Sonnet 4.6's at default sampling by a mean of 1.8 g (95% CI \u22125.3 to +2.2), and lower than Astra's by 5.5 g (\u221213.1 to +1.6); Astra against GPT-5.4 at default "
        "sampling was \u22122.2 g (\u221210.6 to +5.7). Every interval includes zero. As rough planning estimates from the spread of these paired differences, detecting a 5 g "
        "difference in MAE with 80% power would need about 13 photographs for Fable 5.1 against Sonnet 4.6, 46 for Fable 5.1 against Astra and 57 for Astra against GPT-5.4. "
        "Detecting the 1.8 g difference observed between Fable 5.1 and Sonnet 4.6 would need about 94."),
      P("Default sampling did not make either April model less accurate. The MAE of Sonnet 4.6 changed by \u22120.7 g (\u22121.6 to +0.2) and that of GPT-5.4 by \u22123.7 g "
        "(\u22129.2 to +0.3).")]
s += table("<b>Table 4.</b> Share of estimates implying an overdose above 2 U on the five strong-reference photographs, at three insulin-to-carbohydrate ratios, for one call and "
           "for the median of 20 calls. Rates are from the simulation of section 2.4 and differ from the observed rates in Table 3 by up to 0.1 percentage point.", [
    ["Arm", "1 U/5 g, 1 call", "20 calls", "1 U/10 g, 1 call", "20 calls", "1 U/20 g, 1 call", "20 calls"],
    ["Fable 5.1", "16.0%", "19.4%", "0.0%", "0.0%", "0.0%", "0.0%"],
    ["Astra", "35.9%", "40.0%", "19.2%", "20.0%", "8.4%", "5.0%"],
    ["Sonnet 4.6, default", "15.2%", "16.6%", "0.0%", "0.0%", "0.0%", "0.0%"],
    ["GPT-5.4, default", "37.6%", "40.0%", "34.8%", "40.0%", "3.2%", "0.0%"]],
    [W * x for x in (0.22, 0.13, 0.13, 0.13, 0.13, 0.13, 0.13)])
s.append(P("The overdose rates depend on the ratio (Table 4). For a person who takes 1 U per 5 g, a 10 g overestimate is a 2 U overdose, and every model exceeded that in at "
           "least 15% of single estimates, including Fable 5.1 and Sonnet 4.6, whose rate at 1 U per 10 g was zero. For a person who takes 1 U per 20 g, only Astra retained a material rate."))
s.append(P("3.4 Averaging up to 20 calls", h2))
s += table("<b>Table 5.</b> Averaging and variability over the 12 photographs other than the churros, where Astra has too few answers to resample. Width is the 5th to 95th "
           "percentile of the estimate in grams, median over photographs. \u201cMore than 1 U off\u201d is the share of estimates more than 10 g from the model's typical answer, "
           "mean over photographs. 95% bootstrap intervals over photographs.", [
    ["Arm", "Width, 1 call", "Width, 5 calls", "Width, 20 calls", "More than 1 U off, 1 call", "5 calls", "20 calls"],
    ["Fable 5.1", "11.7 (6.7\u201315.4)", "5.1 (2.6\u20138.0)", "3.2 (2.1\u20134.5)", "3.4% (1.5\u20135.8)", "0.1% (0.0\u20130.2)", "0.0% (0.0\u20130.0)"],
    ["Astra", "10.9 (7.3\u201319.6)", "7.0 (4.4\u201312.4)", "3.4 (2.1\u20135.1)", "10.2% (2.7\u201319.3)", "3.1% (0.3\u20137.2)", "0.3% (0.0\u20130.9)"],
    ["Sonnet 4.6, default", "8.5 (3.9\u201315.6)", "5.1 (3.4\u20139.0)", "2.9 (1.7\u20135.3)", "4.3% (0.7\u20139.9)", "0.8% (0.0\u20132.4)", "0.0% (0.0\u20130.1)"],
    ["GPT-5.4, default", "19.8 (14.8\u201336.3)", "9.6 (7.7\u201318.8)", "4.9 (2.9\u201310.1)", "17.5% (8.6\u201327.3)", "6.0% (0.9\u201312.2)", "1.5% (0.0\u20133.7)"]],
    [W * x for x in (0.17, 0.14, 0.13, 0.13, 0.15, 0.14, 0.14)])
s.append(P("Averaging removed variability risk (Table 5, Figure 2). With 20 calls the share of estimates more than 1 U from the model's typical answer was 0.3% or less in every "
           "arm except GPT-5.4, where it was 1.5%, and five calls achieved most of the reduction for Fable 5.1 and Sonnet 4.6. Against the April baselines, five default-sampling "
           "calls brought GPT-5.4's width below that of one April call (9.6 g against 12.9 g), while Sonnet 4.6 needed more than five (5.1 g against 3.8 g) and was below it at 20 (2.9 g)."))
s += table("<b>Table 6.</b> Averaging and accuracy risk: share of estimates implying an overdose above 2 U at 1 U per 10 g, mean over photographs, with 95% bootstrap intervals. "
           "The last column counts, of the eight reference photographs other than the churros, those on which 20 calls raised or lowered the rate relative to one call. "
           "Single-call rates are simulated and differ from Table 3 by up to 0.1 percentage point.", [
    ["Arm", "Strong reference, 1 call", "5 calls", "20 calls", "All 8 references, 1 call", "20 calls", "Raised / lowered"],
    ["Fable 5.1", "0.0%", "0.0%", "0.0%", "0.0%", "0.0%", "0 / 0"],
    ["Astra", "19.2% (0.0\u201356.8)", "20.0%", "20.0% (0.0\u201360.0)", "33.6% (9.9\u201366.8)", "37.5% (12.5\u201375.0)", "3 / 1"],
    ["Sonnet 4.6, default", "0.0%", "0.0%", "0.0%", "10.8% (0.0\u201327.9)", "11.8% (0.0\u201335.3)", "1 / 1"],
    ["GPT-5.4, default", "34.7% (0.0\u201369.8)", "39.3%", "40.0% (0.0\u201380.0)", "37.2% (10.7\u201365.8)", "38.1% (12.5\u201375.0)", "3 / 1"]],
    [W * x for x in (0.17, 0.15, 0.10, 0.15, 0.16, 0.15, 0.12)])
s.append(fig(str(FIG / "fig3_risk_by_k.png"), 660 / 1480, "<b>Figure 2.</b> Effect of averaging on the two kinds of risk. Left: share of estimates more than 1 U from the model's typical answer, over the "
             "12 photographs other than the churros. Right: share of estimates implying an overdose above 2 U, over the five strong-reference photographs; Fable 5.1 and Sonnet 4.6 "
             "lie together at zero. The horizontal axis is the number of calls whose median is taken, on a logarithmic scale."))
s.append(P("Averaging did not reduce accuracy risk (Table 6). The changes in the pooled rates are small against their intervals, which rest on five photographs, and the mechanism "
           "is clearer photograph by photograph (Figure 3). As calls are added the estimate converges on the model's typical answer for the photograph, so the overdose rate for that "
           "photograph converges on 0% if the typical answer is less than 20 g above the reference and on 100% if it is more. Where a model's single calls overdosed a photograph "
           "most of the time, 20 calls made it nearly every time. Astra's typical answer for the breakfast burrito was 37 g above the reference, and its overdose rate went from 94.0% "
           "to 100%; for the chilli, 25 g above, from 80.7% to 99.9%. Sonnet 4.6 at default sampling was 21 g above on the chilli and went from 68.4% to 94.2%. Where the typical "
           "answer was close and the overdoses came from scatter, averaging removed them: GPT-5.4 at default sampling on the stuffed pork loin, 4 g above, went from 34.5% to 5.0%, "
           "and Sonnet 4.6 at default sampling on the roast dinner, 7 g above, from 17.8% to 0%."))
s.append(fig(str(FIG / "fig4_overdose_by_photo.png"), 660 / 1440, "<b>Figure 3.</b> Each point is one model on one of the eight reference photographs other than the churros, placed by the model's typical error "
             "for that photograph (its median answer minus the reference). Light points give the share of single calls implying an overdose above 2 U, dark points the share for the "
             "median of 20 calls. Fable 5.1, Astra, Sonnet 4.6 and GPT-5.4 at default sampling are shown."))
s += [P("The largest overdoses did not survive averaging in these data. Astra's estimates implying more than 5 U fell from 2.1% of strong-reference estimates to 0% of resampled "
        "medians by ten calls, and GPT-5.4's from 0.4% to 0% by five. A zero among resampled medians of 50 answers per photograph shows that such estimates became rare, not that "
        "they cannot occur. The mean absolute error barely moved: on the strong-reference photographs, Fable 5.1 went from 7.0 g to 6.1 g, Astra from 13.2 g to 12.5 g, and "
        "GPT-5.4 stayed at 14.7 g. The same convergence operates below the reference (section 3.7). At other insulin-to-carbohydrate ratios the pattern holds (Table 4): at 1 U per "
        "5 g, 20 calls raised Fable 5.1's rate from 16.0% to 19.4%, and at 1 U per 20 g they lowered Astra's from 8.4% to 5.0%, each according to where the typical answers lay "
        "relative to the threshold."),
      P("The median was the better statistic. With the mean, rare outlying answers pulled the estimate away from the typical answer as calls were added; for Sonnet 4.6 at "
        "temperature 0.01 the share more than 1 U off rose from 4.2% with one call to 5.2% with 20. Drawing without replacement gave the same conclusions. The median of two calls "
        "is their mean, which is why some arms are slightly more variable at three calls than at two.")]
s.append(P("3.5 Identification", h2))
s.append(P("The April preprint documented systematic misidentifications. Table 7 repeats those checks as the percentage of answers naming each item, with the difference in mean "
           "estimated carbohydrate between answers that name the item and answers that do not, where both occur."))
s += table("<b>Table 7.</b> Identification on the photographs the April preprint discussed. Figures in brackets are the difference in mean carbohydrate estimate (g) between "
           "answers naming the item and the rest.", [
    ["Photograph and item named", "Fable 5.1", "Astra", "Sonnet 4.6, default", "Sonnet 4.6, April 0.01", "GPT-5.4, default", "GPT-5.4, April 0.01"],
    ["Bakewell tart: \u201cBakewell\u201d", "100%", "73% (\u22121.4)", "0%", "0%", "0%", "0%"],
    ["Bakewell tart: \u201cLinzer\u201d", "0%", "0%", "100%", "100%", "0%", "0%"],
    ["Crema catalana: \u201ccrema catalana\u201d", "76% (+0.6)", "100%", "0%", "0%", "0%", "0%"],
    ["Stuffed pork loin: \u201cpork\u201d", "54% (\u22120.4)", "58% (\u22128.9)", "100%", "100%", "0%", "0%"],
    ["Stuffed pork loin: \u201cchicken\u201d", "46% (+0.4)", "0%", "2% (+0.9)", "26% (\u22120.6)", "100%", "100%"],
    ["Pizza: \u201cburrata\u201d from the adjacent plate", "0%", "96% (+2.8)", "0%", "18% (+5.6)", "34% (+4.4)", "0%"]],
    [W * x for x in (0.22, 0.12, 0.12, 0.13, 0.14, 0.13, 0.14)])
s.append(P("Both new models named the Bakewell tart and the crema catalana, which no April model other than Gemini 3.1 Pro did. Fable 5.1 named chicken in 46% of answers on the "
           "stuffed pork loin, and Astra included the burrata salad from the neighbouring plate in the pizza photograph in 96%. In this set, misidentification moved the carbohydrate "
           "estimate little: the meat in the pork loin carries almost no carbohydrate, and the burrata salad added 3 g to 6 g where it was counted. The exception was Astra on the pork "
           "loin, whose answers that named pork were 8.9 g lower than those that did not. The identification errors checked here explain little of the accuracy differences in Table 3."))
s.append(P("3.6 Tokens and cost", h2))
s += table("<b>Table 8.</b> Mean tokens per answered call and cost at batch prices on 21 September 2026, with the annual cost in US dollars for one person logging three meals a "
           "day. The 3-call and 5-call columns are new in version 2 and are the per-answer cost multiplied accordingly.", [
    ["Arm", "Input tokens", "Output tokens", "Of which reasoning", "USD per 1,000 answers", "Per year, 1 call", "3 calls", "5 calls", "20 calls"],
    ["Fable 5.1", "4,918", "1,434", "not reported separately", "60.63", "66", "199", "332", "1,328"],
    ["Astra", "5,291", "1,258", "37", "62.38", "68", "205", "342", "1,366"],
    ["Sonnet 4.6, default", "3,371", "1,703", "none", "17.83", "20", "59", "98", "390"],
    ["GPT-5.4, default", "4,502", "818", "0", "11.76", "13", "39", "64", "258"]],
    [W * x for x in (0.16, 0.10, 0.10, 0.13, 0.12, 0.10, 0.09, 0.09, 0.11)])
s.append(P("At low effort both new models reasoned little: Astra averaged 37 reasoning tokens, and Fable 5.1's output, which includes its thinking, was shorter than Sonnet 4.6's. "
           "Per answer, the two new models cost 3.4 to 5.3 times as much as the two April models. At batch prices, five-call averaging with either new model costs about 330 US "
           "dollars a year for three meals a day and 20-call averaging about 1,300; an application that needs the answer immediately pays real-time prices, which both providers set "
           "at twice the batch rate. The run itself cost 96.20 US dollars."))

s.append(P("3.7 Underestimation and error as a share of the meal (added in version 2)", h2))
s.append(P("Figure 4 shows every arm's answers for every photograph in grams, with the reference where there is one. It makes visible what the pooled measures average over. "
           "GPT-5.4 put the cheese sandwich, a packet-label reference, about 33 g high; Astra was well above the breakfast burrito; Fable 5.1 and Sonnet 4.6 both put the cheese "
           "sandwich about 12 g low; and every arm was above the chilli."))
s.append(fig(str(FIG / "v2_fig4_meals.png"), 1848 / 1584, "<b>Figure 4.</b> Each row is a photograph. For each arm the circle is its median answer, the thick bar the interquartile range and the thin "
             "line the 5th to 95th percentile. The black line is the reference: solid for packet label or weighed, dashed for portioned or visual. The five photographs in bold carry "
             "the primary accuracy analysis. Astra has 10 answers for the churros.", 0.78))
s += table("<b>Table 9.</b> Share of estimates more than 10 g and more than 20 g below the reference on the five strong-reference photographs, for one call and for the medians of "
           "5 and 20 calls, simulated as in section 2.4. At 1 U per 10 g these are shortfalls of more than 1 U and 2 U; at 1 U per 5 g, more than 2 U and 4 U. 95% bootstrap "
           "intervals over photographs.", [
    ["Arm", "> 10 g low, 1 call", "5 calls", "20 calls", "> 20 g low, 1 call", "20 calls"],
    ["Fable 5.1", "21.2% (0.4\u201360.8)", "20.0% (0.0\u201360.0)", "20.0% (0.0\u201360.0)", "0.0%", "0.0%"],
    ["Astra", "2.8% (0.0\u20138.3)", "0.4% (0.0\u20131.2)", "0.0%", "0.0%", "0.0%"],
    ["Sonnet 4.6, default", "39.2% (0.0\u201379.2)", "40.0% (0.0\u201380.0)", "40.0% (0.0\u201380.0)", "0.0%", "0.0%"],
    ["Sonnet 4.6, April 0.01", "40.0% (0.0\u201380.0)", "40.0% (0.0\u201380.0)", "40.0% (0.0\u201380.0)", "0.0%", "0.0%"],
    ["GPT-5.4, default", "3.2% (0.4\u20137.6)", "0.3% (0.0\u20130.9)", "0.0%", "0.0%", "0.0%"],
    ["GPT-5.4, April 0.01", "0.0%", "0.0%", "0.0%", "0.0%", "0.0%"]],
    [W * x for x in (0.2, 0.17, 0.16, 0.16, 0.16, 0.15)])
s += [P("No arm produced an estimate more than 20 g below any of the eight reference photographs other than the churros, in any call. At 10 g the picture is the reverse of "
        "overestimation (Table 9). Fable 5.1 and Sonnet 4.6, which never overestimated a strong reference by 20 g, were more than 10 g low in 21.2% and 39.2% of single estimates, "
        "almost entirely on the cheese sandwich and, for Sonnet 4.6, the soup and bread. Averaging converged on the typical answer here too: 20 calls gave 20.0% and 40.0%. Astra "
        "and GPT-5.4, which overestimated, were rarely low, and averaging took their small rates to zero."),
      P("The churros, whose 80 g reference is a visual estimate, were the one photograph where large underestimates were common. GPT-5.4 at default sampling was more than 20 g "
        "low in 74.0% of calls and in 99.3% of 20-call medians, and at temperature 0.01 in 54.0% and 65.8%. Fable 5.1 was more than 20 g low in 12.0% of calls and Sonnet 4.6 at "
        "default sampling in 8.0%, and neither in any 20-call median. Astra's 10 answers were none more than 20 g low."),
      P("As a share of the reference (Table 3), mean absolute error on the five strong-reference photographs was 17.5% for Fable 5.1, 20.3% for Sonnet 4.6 at default sampling, "
        "35.2% for Astra and 38.2% for GPT-5.4 at default sampling. The strong references averaged 44.3 g, so an error of a given size in grams is a larger share here than it "
        "would be on a larger meal."),
      P("Figure 5 shows the within-photograph spread of section 3.2 as the distribution of individual answers relative to each arm's median for the photograph. It pools "
        "answers across photographs and is descriptive; the per-photograph CVs of Figure 1 remain the basis for the statistical comparisons.")]
s.append(fig(str(FIG / "v2_fig5_violin.png"), 858 / 1584, "<b>Figure 5.</b> Every answer as a percentage above or below the arm's median answer for the same photograph, pooled over the 13 "
             "photographs. Filled violins are provider-default sampling (50 calls per photograph); hatched violins are the April runs at temperature 0.01, each answer taken relative "
             "to the median of its own 50-call block and pooled over the ten blocks. Bars show the interquartile range and the 5th to 95th percentile. The axis is cut at \u00b150%; "
             "the share of answers beyond it is printed beneath each violin."))

# 4
s.append(P("4. Discussion", h1))
s += [P("Averaging repeated calls, the mitigation the April preprint proposed, deals with one of the two risks that preprint described and not the other. The acute risk, a single "
        "outlying estimate, falls quickly: five calls remove most of it for Fable 5.1 and Sonnet 4.6, twenty for every arm, and in these data no estimate implying an overdose "
        "above 5 U survived. The chronic risk, a model that overestimates a meal, does not fall and can rise. With one call, a model whose typical answer for a meal is 25 g too high "
        "overdoses most of the time and occasionally does not; with twenty, it overdoses on nearly every attempt, and the number the person sees is close to the same each time. "
        "Consistency of that kind is easily taken for correctness. The same holds in the other direction for a model that underestimates a meal. An application that averages calls "
        "therefore needs the confirmation step as much as one that does not, and it pays about twenty times as much for each answer."),
      P("At the sampling applications now receive by default, both April models became more variable, Sonnet 4.6 from 2.3% to 5.7% and GPT-5.4 from 7.8% to 10.1%, and the two new "
        "models sit close to Sonnet 4.6 at default sampling. The April figure of 2.4% for Sonnet 4.6 describes a configuration a developer can still choose for that model, but not "
        "for its successor. The block analysis adds a caution about the April data themselves: GPT-5.4's spread differed between separately submitted batches, so reproducibility "
        "measured in one session can understate what a user meets across sessions. The same caution applies to the averaging analysis, which resamples within one session."),
      P("Accuracy did not separate the models reliably. Fable 5.1 and Sonnet 4.6 were unbiased on average on the strong-reference photographs and Astra and GPT-5.4 overestimated them, "
        "but no paired comparison of MAE was resolved, and a ranking would need a test set of weighed references several times larger than the five photographs that carry the "
        "primary analysis here. The overdose rates also rest on the ratio used to convert grams to units. At 1 U per 5 g every model produced a 2 U overdose in at least 15% of "
        "estimates, so an estimate that is harmless for one person is not harmless for another."),
      P("Human carbohydrate counting gives a point of reference, though not a controlled comparison. In a study of 50 adults with type 1 diabetes estimating their own meals, the mean "
        "difference from a dietitian's assessment was 15.4 g, or 20.9% of meals averaging 72.4 g, and 63% of meals were underestimated [7]. In a study of hospital meals weighed "
        "against a nutrient database, participants' mean absolute error was 27.9 g, against 12.3 g for a purpose-built smartphone system [8]. The models' errors in grams were "
        "smaller than both human figures, but on smaller meals: as a share of the reference, Fable 5.1 and Sonnet 4.6 were close to the 21% reported for people and Astra and "
        "GPT-5.4 were larger. The meals, references and methods differ, and five photographs cannot place any model above or below a person who counts carbohydrate daily. What "
        "differs clearly is the character of the error: people in that study mostly underestimated, while two of the four models mostly overestimated, and averaging makes a "
        "model's error more consistent rather than smaller."),
      P("Astra's parse failures are a separate safety property. Across most meals they were rare and a retry would recover them, but on one photograph Astra failed four times in five, "
        "so for that meal an application would usually have no answer at all. A carbohydrate value written as a word is caught by a strict parser and becomes no answer; a lenient "
        "parser that coerced or skipped the field would produce a wrong one. The benchmark's April parser had a comparable weakness for malformed JSON, now corrected. Applications "
        "should reject any response that fails strict validation instead of repairing it, and should tell the person when a photograph has not produced an answer.")]
s.append(P("Limitations", h2))
s.append(P("Each arm made 50 calls per photograph on one day, and the April block analysis shows that a single session can understate variation that appears across sessions. The "
           "averaging analysis resamples the 50 calls made per photograph and assumes an application's repeated calls behave like independent draws from the same distribution, "
           "which cannot represent variation between sessions; a prospective test with fresh calls on different days would be needed to confirm it. Thirteen photographs, five with "
           "strong references, give wide intervals, and no accuracy ranking between arms is supported; the rates in Tables 4, 6 and 9 rest on five photographs however many answers "
           "they summarise. The references themselves carry uncertainty of a few grams, one is a visual estimate, and estimates near a threshold could change classification within "
           "that uncertainty. The sample-size figures are rough, being derived from variances estimated on five to nine photographs. Insulin figures depend on an illustrative ratio, "
           "and Table 4 shows how much; they are translations of carbohydrate error, not dosing events. The comparison with human carbohydrate counting draws on separate studies with "
           "different meals and references. Reasoning effort was fixed at the lowest level, and higher settings may change both spread and accuracy. Image sizes differ by provider as "
           "they did in April. Only the Anthropic and OpenAI models were run, and the prompt was not varied. Fable 5.1 does not report its thinking tokens separately, so its "
           "reasoning cost is not isolated. The analysis was not pre-registered, and although the code and data are public it has not been audited by anyone independent of the tools "
           "used to write it (section 2.6)."))

# 5
s.append(P("5. Conclusions", h1))
s += [P("Taking the median of up to 20 calls removed nearly all carbohydrate estimates more than 1 U from a model's typical answer, and left no strong-reference estimate implying "
        "an overdose above 5 U in these data, but did not reduce the rate of 2 U overdoses: on photographs a model systematically overestimated, that rate rose towards 100%, and "
        "the same convergence held for underestimates. Averaging is worth using against outlying answers and cannot substitute for confirmation by the person."),
      P("Without a fixed low temperature, Sonnet 4.6 and GPT-5.4 became more variable, and Claude Fable 5.1 and GPT-6 Astra, which cannot be run at a fixed temperature, had median "
        "CVs of 6.3% and 5.7%. Astra failed to produce any answer for one photograph in four calls out of five. Differences in accuracy between models were not resolved by this "
        "test set, and as a share of the meal no model's error was clearly smaller than that reported for people counting their own meals. On these photographs, neither new model "
        "is a basis for insulin dosing without confirmation by the person using it.")]

s.append(P("6. Data availability", h1))
s.append(P(f"Raw responses, results, analysis code and the scripts that produced every table and figure are public in the repository for this update [5]. The April data and code "
           f"are in the companion repository of the original preprint [6]. The reproducibility and accuracy tables are regenerated by update_analysis.py and review_analyses.py, the "
           f"averaging tables and figures by averaging_risk.py, and the version 2 additions (Table 9, the share-of-reference rows of Table 3, and Figures 4 and 5) by v2_analyses.py."))

s.append(P("7. Changes in version 2", h1))
s += B(["Added section 3.7, Table 9 and Figures 4 and 5: underestimation at 10 g and 20 g with averaging, the churros underestimates, error as a share of the reference, a "
        "per-photograph chart in grams, and the distribution of individual answers.",
        "Added error as a share of the reference to Table 3, 3-call and 5-call columns to Table 8, and a comparison with published human carbohydrate-counting error to the "
        "Discussion, with references 7 and 8.",
        "Defined \u201coverdose\u201d as arithmetic on the estimate (section 2.3), described the uncertainty of the references, and described the sample-size figures as rough planning estimates.",
        "Reworded the finding on overdoses above 5 U in the abstract, section 3.4, Discussion and Conclusions: none remained in the resampled data, which does not show they cannot occur.",
        "Noted that Astra's retries on the churros may not be independent (section 3.1), and extended the Limitations.",
        "Described the version 2 analyses and the unit tests in sections 2.5 and 2.6.",
        "No result reported in version 1 has changed."])

s.append(P("Funding, relationships and acknowledgements", h1))
s.append(P("This work received no specific funding; API costs were paid by the author. The author has used open-source automated insulin delivery since 2016, has contributed to AID "
           "systems in the oref family and maintains a fork of AndroidAPS; the author has no affiliation with the iAPS project. Claude Code (Anthropic) was used for the benchmark "
           "code, the analysis and drafting, and Claude (Anthropic) for the version 2 analyses and revisions; the author reviewed the analysis and is responsible for the "
           "conclusions. Anthropic makes two of the models evaluated, and section 2.6 describes how the design limits the influence of that relationship. The manuscript was revised "
           "after a critical review, which led to the ten-block April comparison, the strong-reference primary analysis, the ratio sensitivity, the failure and identification "
           "analyses, and section 2.6. Version 2 was revised after a second critical review, which led to the changes listed in section 7."))

s.append(P("References", h1))
refs = [
    f"Street T (2026) Reproducibility and accuracy of large language model vision APIs for carbohydrate estimation from food photographs: a four-model batch comparison with implications for automated insulin dosing. SSRN preprint. {LINK('https://doi.org/10.2139/ssrn.6577780')}. Also published at {LINK('https://www.diabettech.com/i-asked-ai-to-count-my-carbs-27000-times-it-couldnt-give-me-the-same-answer-twice/')}",
    f"iAPS Project (2026) iAPS: open-source automated insulin delivery system. {LINK('https://github.com/Artificial-Pancreas/iAPS')}",
    f"Anthropic (2026) Migrating to Claude Fable 5.1: sampling parameters and thinking. Claude API documentation. {LINK('https://docs.claude.com')}",
    f"OpenAI (2026) GPT-6 Astra model guide. {LINK('https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra')}",
    f"Street T (2026) llm-food-benchmark-2026-09: September 2026 rerun. {LINK(GH)}",
    f"Street T (2026) llm-food-benchmark-academic: companion repository. {LINK('https://github.com/tim2000s/llm-food-benchmark-academic')}",
    f"Brazeau AS, Mircescu H, Desjardins K, et al. (2013) Carbohydrate counting accuracy and blood glucose variability in adults with type 1 diabetes. Diabetes Research and Clinical Practice 99(1):19\u201323. {LINK('https://pubmed.ncbi.nlm.nih.gov/23146371/')}",
    f"Rhyner D, Loher H, Dehais J, et al. (2016) Carbohydrate estimation by a mobile phone-based system versus self-estimations of individuals with type 1 diabetes mellitus: a comparative study. Journal of Medical Internet Research 18(5):e101. {LINK('https://doi.org/10.2196/jmir.5567')}",
]
for i, r in enumerate(refs, 1):
    s.append(P(f"{i}&nbsp;&nbsp;{r}", ref))


def footer(c, d):
    c.saveState()
    c.setFont("Times-Roman" if FALLBACK else "LS", 8.5)
    c.setFillColor(GREY)
    c.drawString(22 * mm, 12 * mm, "Tim Street / Diabettech preprint, version 2")
    c.drawRightString(A4[0] - 22 * mm, 12 * mm, str(d.page))
    c.restoreState()


out = str(DIST / "Street_2026_LLM_Carbohydrate_Reproducibility_Update_preprint_v2.pdf")
doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=18 * mm, bottomMargin=20 * mm,
                        title="Carbohydrate estimates from food photographs by Claude Fable 5.1 and GPT-6 Astra: a September 2026 update to a reproducibility benchmark (v2)",
                        author="Tim Street")
doc.build(s, onFirstPage=footer, onLaterPages=footer)
print(out)
