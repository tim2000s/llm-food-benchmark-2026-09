# Handover: LLM carbohydrate benchmark, September 2026 update (preprint v2 + Diabettech article)

Prepared 22 September 2026 by Claude (claude.ai chat) for Tim Street, to be picked up in Claude Code.

## 1. Where things stand

Version 1 of the preprint is on Zenodo (record 22879140, DOI 10.5281/zenodo.22879140, published 21 Sept 2026).
In chat we:

1. Wrote a Diabettech article on the preprint, framed as an update to the April "27,000 times" article.
   The final angle: OpenAI's Greg Brockman said it's "not unreasonable" to feel we're in the AGI era and left
   it to readers to decide; on carb counting the models are no better than a person.
2. Took a hostile peer review (summary and disposition in section 7) and revised the article.
3. Ran new analyses from the public data: underestimation, error as a share of the meal, a per-meal
   chart and a violin chart. These are not in v1 of the preprint.
4. Checked the live Zenodo record. Its metadata has problems (section 5).
5. Built a v2 preprint containing the new analyses and the review fixes.

Nothing has been published or committed yet. Everything below is ready to go but needs doing.

## 2. Package contents

| Path | What it is |
|---|---|
| `deliverables/Street_2026_LLM_Carbohydrate_Reproducibility_Update_preprint_v2.pdf` | v2 preprint, 14 pages, ready for Zenodo |
| `deliverables/Diabettech_AI_carb_counting_September_2026_update.pdf` | The article, 10 pages |
| `deliverables/Zenodo_v2_metadata.md` | Everything to paste into the Zenodo new-version form |
| `repo_additions/v2_analyses.py` | New analysis script; goes at the top level of the 2026-09 repo |
| `repo_additions/output/` | Its outputs: `V2_ANALYSES.md`, `v2_analyses.json`, `v2_fig4_meals.png`, `v2_fig5_violin.png` |
| `build/build_preprint_v2.py` | Rebuilds the v2 PDF (all text and tables inline) |
| `build/build_article.py` | Rebuilds the article PDF (all text inline) |
| `build/figures/` | The five figures both builds use (three are unchanged repo outputs) |
| `context/preprint_v1_as_on_zenodo.pdf` | v1 exactly as on Zenodo (md5 7449cc32474511fa2385ce1a97e08475) |

Rebuild either PDF with `pip install reportlab && python3 build/<script>.py`; output lands in `dist/`
(or `$DIST_DIR`). Fonts: the preprint uses Liberation Serif, the article DejaVu. Both scripts search
the usual font folders and `$FONT_DIR`, and fall back to built-in Times/Helvetica if they can't find them.
On macOS: `brew install --cask font-liberation font-dejavu`, or point `FONT_DIR` at them.

## 3. Tasks, in order

### Task 1. Commit the v2 analysis to the repo (Claude Code can do this)

Repo: https://github.com/tim2000s/llm-food-benchmark-2026-09. It needs the April data from
https://github.com/tim2000s/llm-food-benchmark-academic (the `results/` folder, about 146 MB).

```
git clone https://github.com/tim2000s/llm-food-benchmark-2026-09
git clone --depth 1 https://github.com/tim2000s/llm-food-benchmark-academic
cp <package>/repo_additions/v2_analyses.py llm-food-benchmark-2026-09/
cd llm-food-benchmark-2026-09
pip install numpy scipy matplotlib
APRIL_RESULTS_DIR=../llm-food-benchmark-academic/results python3 v2_analyses.py
diff output/V2_ANALYSES.md <package>/repo_additions/output/V2_ANALYSES.md   # expect no difference
```

Then:
- Add a short "Version 2 analyses" section to README.md saying what `v2_analyses.py` does and how to run it
  (the docstring at the top of the script has the wording).
- Run the tests: `python3 -m unittest discover -s tests -t .` (needs `anthropic` and `openai` installed).
  54 passed in chat. The article and the v2 preprint both say "54 unit tests", so if you add a test,
  update both numbers (article section "A note on who did the work"; preprint section 2.5).
- A regression test for `v2_analyses.py` would be a good addition (for example, that Fable 5.1's
  one-call >10 g-low rate on the strong set is 0.212). If added, update the count as above.
- Commit and push. Suggested message: "Add v2 analyses: underestimation, share-of-reference error, per-photograph and violin figures".

Script notes: it reuses `update_analysis`, `averaging_check` and `averaging_risk` unchanged, and it
monkeypatches `averaging_risk.photo_metrics` to add the extra thresholds. It runs `ar.run` with the full
default `ar.KS`, so its random draws match `averaging_risk.py` exactly. Changing the k list changes the draws.

### Task 2. Decisions for Tim (ask him; don't guess)

1. **Licence.** The v1 and v2 PDFs say CC BY 4.0. The v1 Zenodo record says CC BY-ND 4.0. Recommended: CC BY
   on the record. If Tim wants ND, change the licence line in `build_preprint_v2.py` (the `note` paragraph
   near the top) and rebuild.
2. **Affiliation.** The Zenodo record says "Diabettech Ltd"; the PDF says "Diabettech, United Kingdom".
   Make them match. Is Diabettech a registered company?
3. **Read-through of the v2 PDF.** There was no source file for v1, so v2 was retypeset from v1's text.
   The wording and numbers carry over, but the layout differs from v1. Tim should read it once.

### Task 3. Publish v2 on Zenodo (Tim, or Claude Code via the API with Tim's token and explicit go-ahead)

Use **New version** on record 22879140 so both versions share a concept DOI. Follow
`deliverables/Zenodo_v2_metadata.md`: replace the PDF, paste the new description, set the version to 2.0,
set the licence, fix the related-works link (v1 is missing the "h" in https) and add the two human-study
references.

Via the REST API (https://developers.zenodo.org): `POST /api/deposit/depositions/22879140/actions/newversion`,
then delete the old file from the draft, upload the v2 PDF, `PUT` the metadata, and **publish only after Tim
confirms**. Publishing can't be undone, only superseded by a further version.

v1's description on Zenodo is an early abstract that contradicts the paper: it compares against the first 50
April calls (Sonnet 2.4% to 5.7%, GPT-5.4 4.3% to 10.1%, "higher on all 13"). The paper uses the ten-block
comparison (2.3% and 7.8%). Metadata of v1 can also be edited in place if Tim wants the v1 page corrected.

### Task 4. Point the article at v2

In `build/build_article.py`, the constant `ZEN` and the two places that print "zenodo.org/records/22879140"
(the update banner at the top and the "Preprint:" line at the end) should point at the new record, or
better, the concept DOI, which always resolves to the latest version. Rebuild the article.

### Task 5. Publish the article (Tim)

The article is written for diabettech.com. The PDF is a review copy; the text for the site is in
`build_article.py`. The update banner at the top links back to the April article.

## 4. Numbers to cross-check (all reproduced from the public data in chat)

Five strong-reference photographs (packet label or weighed; mean reference 44.3 g) unless stated.

| Measure | Fable 5.1 | Astra | Sonnet 4.6 default | GPT-5.4 default |
|---|---|---|---|---|
| MAE (g) | 7.0 | 13.2 | 8.8 | 14.7 |
| MAE as share of reference | 17.5% | 35.2% | 20.3% | 38.2% |
| >2 U over at 1:10, 1 call / 20 calls | 0 / 0 | 19.2% / 20.0% | 0 / 0 | 34.7% / 40.0% |
| >10 g low, 1 call / 20 calls | 21.2% / 20.0% | 2.8% / 0.0% | 39.2% / 40.0% | 3.2% / 0.0% |
| Median CV (13 photos) | 6.3% | 5.7% | 5.7% | 10.1% |

- No arm was ever more than 20 g low on the eight non-visual references.
- Churros (80 g, visual estimate): GPT-5.4 default was more than 20 g low in 74.0% of calls and 99.3% of 20-call medians.
- April comparators (ten-block): Sonnet 4.6 2.3%, GPT-5.4 7.8%.
- Human studies: Brazeau et al. 2013 found a mean error of 15.4 g, 20.9% of meals averaging 72.4 g, with 63%
  underestimated (Diabetes Res Clin Pract 99:19-23, PMID 23146371). Rhyner et al. 2016 found a mean absolute
  error of 27.9 g for participants and 12.3 g for GoCARB (J Med Internet Res 18:e101, doi 10.2196/jmir.5567).
- Costs: see Table 8 of v2. The 3- and 5-call columns are per-answer cost × 1,095 × k.

Full detail with intervals: `repo_additions/output/V2_ANALYSES.md`.

## 5. Zenodo v1 record issues found

1. The description is the stale abstract (see Task 3). This is the most important.
2. The licence mismatch (CC BY-ND on the record, CC BY in the PDF).
3. The broken link: `ttps://www.diabettech.com/...`.
4. The affiliation wording.
5. The record is in no Zenodo community.

## 6. Figure numbering

| File | Article | Preprint v2 |
|---|---|---|
| `v2_fig4_meals.png` | Figure 1 | Figure 4 |
| `v2_fig5_violin.png` | Figure 2 | Figure 5 |
| `fig3_risk_by_k.png` | Figure 3 | Figure 2 |
| `fig4_overdose_by_photo.png` | Figure 4 | Figure 3 |
| `fig1_cv_by_arm_blocks.png` | not used | Figure 1 |

v2 keeps v1's section, table and figure numbers, so citations to v1 still work. The new material is section 3.7,
Table 9, Figures 4 and 5, the share-of-reference rows in Table 3, the 3- and 5-call columns in Table 8, and section 7.

## 7. Hostile review: what was done with each point

| # | Point | Status |
|---|---|---|
| 1 | Pseudoreplication: accuracy rests on five meals | Article says "five meals" throughout and gives meal-level ranges. Paper already bootstraps over photographs; v2 Limitations says so explicitly. |
| 2 | Averaging simulated, not live calls across sessions | Caveat added to both. **Open:** a prospective test (fresh 1/3/5/20-call batches on different days) would settle it. |
| 3 | "Gets rid of >5 U errors" overstated | Reworded everywhere to "none remained in the resampled data". |
| 4 | "Overdose" implies a dosing event | Defined as arithmetic on the estimate (v2 §2.3; article). |
| 5 | "Insulin sensitive, like kids" was backwards | Fixed in article: the fewer grams per unit, the more insulin a given error is worth. |
| 6 | Reference uncertainty undefined | Described in v2 §2.3 and Limitations. **Open:** per-photo reference uncertainty (Tim to supply). |
| 7 | Only overestimation analysed | Underestimation added (v2 §3.7, Table 9; article section). |
| 8 | Power calcs over-precise | Now called rough planning estimates. |
| 9 | Tests unnamed | Wilcoxon signed-rank named. |
| 10 | Violin pools dependent observations; % hides grams | Per-meal chart in grams added; violin labelled descriptive. |
| 11 | "These tools" generalisation | Conclusions scoped to "on these photographs". |
| 12 | Core finding is narrower | Both lead with "consistency is not correctness". |
| extra | Retry independence; cost at 3/5 calls; code checks | All added. **Open:** independent audit of the code. |

## 8. Things to keep in mind

- **Disclosure.** Claude Code wrote the benchmark and v1; Claude (chat) did the v2 analyses and revisions.
  Anthropic makes two of the models tested. v2 §2.6 and the acknowledgements say this. Keep it if anything changes.
- **Attribution in the article.** Brockman said "not unreasonable to feel" we're in the AGI era and left it to
  readers. OpenAI made no formal AGI claim, and Anthropic has not called Fable 5.1 AGI (its launch post says "the
  world's most advanced models for coding and knowledge work"). The article is written to that. Don't strengthen it.
- **Human comparison.** It's a rough yardstick: different meals, references and methods. Both documents say so. Keep the caveat.
- **Tim's style for Diabettech.** Short punchy paragraphs, plain British English, direct address, flat opinions,
  hedging tied to specific evidence, no em dashes.
- **v1 results unchanged.** v2 adds material and rewords claims; no v1 number changed. If a rerun of the repo
  scripts disagrees with a v1 number, stop and flag it rather than editing.
