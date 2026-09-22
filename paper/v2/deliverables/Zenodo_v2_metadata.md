# Zenodo: new version (v2) of record 22879140

Use "New version" on the existing record so the two versions share a concept DOI.

## Files
- Remove: Street_2026_LLM_Carbohydrate_Reproducibility_Update_preprint.pdf
- Add: Street_2026_LLM_Carbohydrate_Reproducibility_Update_preprint_v2.pdf

## Version
2.0

## Publication date
2026-09-22

## Description (paste in full; replaces the out-of-date v1 description)

In April 2026 a benchmark sent 13 food photographs about 500 times each to four vision-capable large language models (LLMs) at temperature 0.01 and reported median within-photograph coefficients of variation (CV) of 2.4% to 11.0%. Two newer models, Claude Fable 5.1 and GPT-6 Astra, accept no sampling parameter and cannot run without reasoning, so that condition can no longer be reproduced. This update sent the same photographs and prompt 50 times each to the two new models and to Claude Sonnet 4.6 and GPT-5.4 at provider-default sampling. An application can respond to the lost control by sending a photograph several times and taking the median answer. Simulated from the calls already made, the median of 20 calls cut the share of estimates more than 1 U (10 g) from the model's own typical answer from between 3.4% and 17.5% to 1.5% or less. On the five photographs with packet-label or weighed references, no estimate implying an insulin overdose above 5 U remained in the resampled 20-call medians, but the share implying an overdose above 2 U did not fall: 19.2% with one call and 20.0% with 20 for Astra, and 34.7% and 40.0% for GPT-5.4. Each photograph's rate moved towards 0% if the model's typical answer was within 20 g of the reference and towards 100% if it was not, so averaging removed outlying estimates and left systematic error in place. Underestimation followed the same pattern: no model was more than 20 g below any of the eight non-visual references, but Fable 5.1 and Sonnet 4.6 were more than 10 g low in 21.2% and 39.2% of single estimates and 20.0% and 40.0% of 20-call medians. Mean absolute error as a share of the reference was 17.5% for Fable 5.1, 20.3% for Sonnet 4.6, 35.2% for Astra and 38.2% for GPT-5.4, against about 21% reported for adults with type 1 diabetes estimating their own, larger meals in a separate study. Compared across all ten 50-call blocks of the April runs, default sampling raised the median CV of Sonnet 4.6 from 2.3% (95% CI 1.8 to 3.2) to 5.7% (4.2 to 7.1) and of GPT-5.4 from 7.8% (4.8 to 10.6) to 10.1% (7.8 to 17.4); Fable 5.1 and Astra had 6.3% (5.4 to 8.9) and 5.7% (3.3 to 9.8). Astra returned unparseable output in 40 of 50 calls on one photograph and in 1% elsewhere. Five strong-reference photographs did not resolve differences in accuracy between models; as a rough planning estimate, detecting a 5 g difference would need between 13 and 57 photographs depending on the pair. Overdose rates depend on the insulin-to-carbohydrate ratio assumed, and at 1 U per 5 g every model exceeded 2 U in at least 15% of estimates.

Version 2 adds underestimation, error as a share of the reference, a per-photograph chart and the distribution of individual answers, a comparison with published human carbohydrate-counting error, and clarifications following a second critical review. No result reported in version 1 has changed. Section 7 of the PDF lists the changes.

## Licence
CC BY 4.0 (`cc-by-4.0`), confirmed by Tim on 22 September 2026.

## Related works (keep the existing entries, fix one, add three)
- Continues: 10.2139/ssrn.6577780 (DOI), Preprint
- Is derived from: https://www.diabettech.com/i-asked-ai-to-count-my-carbs-27000-times-it-couldnt-give-me-the-same-answer-twice/ (URL)  <- fix: v1 is missing the "h" in https
- Is supplemented by: https://github.com/tim2000s/llm-food-benchmark-2026-09 (URL)
- Is supplemented by: https://github.com/tim2000s/llm-food-benchmark-academic (URL)  <- v1 lists this as "Other"
- References: 10.2196/jmir.5567 (DOI), Journal article  <- Rhyner et al. 2016
- References: https://pubmed.ncbi.nlm.nih.gov/23146371/ (URL), Journal article  <- Brazeau et al. 2013

## Affiliation
Diabettech Ltd, confirmed by Tim on 22 September 2026.

## Keywords
Unchanged. Optionally capitalise "Automated Insulin Delivery" to match the others.

## Before publishing
Commit repo_additions/ to github.com/tim2000s/llm-food-benchmark-2026-09 (v2_analyses.py at the top level, the four files in output/),
because section 6 of the PDF names v2_analyses.py.
