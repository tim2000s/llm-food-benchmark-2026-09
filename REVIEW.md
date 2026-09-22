# Independent review of the September food photograph benchmark

## Material to review

- `paper/`: revised manuscript, PDF and Markdown, with figures. Source revision: preprints commit `e9af953`.
- `Test-Images/`: the 13 benchmark photographs.
- `results/`: saved responses and submission state, including failed attempts and retry records.
- `usda_reference.json`: reference values, source descriptions, quality tiers and recorded ranges.
- `output/`: committed analysis outputs. These include earlier analyses retained for transparency.

## Reproduce without API access

Clone both public repositories into sibling directories:

```sh
git clone https://github.com/tim2000s/llm-food-benchmark-2026-09.git
git clone https://github.com/tim2000s/llm-food-benchmark-academic.git
cd llm-food-benchmark-2026-09
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt pytest
export APRIL_RESULTS_DIR="$(cd ../llm-food-benchmark-academic/results && pwd)"
python3 -m pytest -q tests
python3 update_analysis.py
python3 averaging_risk.py
python3 review_analyses.py
git diff --stat -- output
```

These analysis commands read saved data and write outputs. They do not submit requests to model
APIs and require no API keys. Do not run `rerun.py run` for an offline review.
Record both repository commit hashes and package versions with the review. Dependency versions
are lower bounds rather than a locked environment, so rendering or numerical differences should
be investigated rather than assumed to be defects.

## Which outputs support the current paper

`update_analysis.py` computes the base accuracy and reproducibility measures.
`averaging_risk.py` computes the extended averaging simulations and risk figures.
`review_analyses.py` supplies the primary ten-block April baseline, ratio sensitivity,
per-photograph failures, identification comparisons, sample-size approximations and annual costs.
Its `fig1_cv_by_arm_blocks.png` is the manuscript's Figure 1; the earlier figure and
`averaging_check.py` outputs are retained but are not the current primary analysis.

## Requested checks

1. Request construction, prompt identity and provider-specific preprocessing/settings.
2. Retry handling: distinguish completed outcomes from failed API attempts and abandoned duplicates.
3. Parsing and missing-value handling, and the carbohydrate total calculated from portions.
4. Reference provenance, uncertainty and separation of strong from exploratory references.
5. April block selection and aggregation; separate temporal changes from sampling changes.
6. Resampling, handling of parse failures, photograph weighting and uncertainty intervals.
7. Agreement of the manuscript tables and figures with the generated outputs.

The insulin conversions are illustrative arithmetic, not observed clinical outcomes. Successful
responses condition the averaging analysis; rejected responses and retry assumptions need separate
assessment. Zero observed or simulated events do not establish zero population risk.

Please identify the exact reviewed commit, checks performed, discrepancies, and any corrections
needed. Test passage is not an independent audit. Further repeated calls on two days and fuller
reference uncertainty documentation remain proposed work, not completed validation.

## Version 2 handover

Run `python3 v2_analyses.py` after setting `APRIL_RESULTS_DIR` as above. The expected
outputs are `output/V2_ANALYSES.md`, `output/v2_analyses.json` and two v2 figures.
The report and JSON reproduced the handover exactly. The extension temporarily replaces
`averaging_risk.photo_metrics` in its process to add underestimation thresholds; run it
as a separate script as documented. The 54 tests are the existing suite, not an independent
audit of this extension. Supplied v2 draft PDFs and editable build scripts are in `paper/v2/`.
