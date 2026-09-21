# Food photograph benchmark, September 2026 rerun

The April 2026 batch benchmark (Diabetologia submission, public companion repository
`tim2000s/llm-food-benchmark-academic`) sent 13 food photographs 500 times each to each model at
temperature 0.01 and measured the spread and accuracy of the carbohydrate estimates. This
repository reruns it against two newer models, Claude Fable 5.1 and GPT-6 Astra.

Neither new model accepts a sampling parameter, and neither lets reasoning be switched off, so the
near-deterministic condition of the April run can no longer be reproduced on current models. The
rerun therefore samples every arm at the provider default, including fresh runs of the two April
models, so that the four arms are measured under the same conditions and the April figures serve
as a best case that is no longer available.

## Arms

| arm | model | sampling | reasoning | max output tokens |
|---|---|---|---|---|
| `fable-5-1` | `claude-fable-5-1` | default | effort low | 16,000 |
| `gpt-6-astra` | `gpt-6-astra` | default | effort low | 16,000 |
| `sonnet-4-6-default` | `claude-sonnet-4-6` | default | none, as April | 8,000 |
| `gpt-5-4-default` | `gpt-5.4` | default | default, as April | 6,000 |

Low effort is a modelling choice: it is the setting closest to deterministic that each new model
still allows, and it is matched between them. The April models change only in sampling. Prompt,
image preprocessing (1,568 px for Claude, 2,048 px for OpenAI, JPEG quality 85) and the response
parser are the April ones, and `prompt_sha256` in every results file checks the first of these.
The settings are in `arms.py`.

## Running it

    python3 rerun.py estimate --iterations 50                  # builds every request, no network
    python3 rerun.py estimate --iterations 50 --count-tokens   # Claude input tokens, free endpoint
    ANTHROPIC_API_KEY=... OPENAI_API_KEY=... python3 rerun.py run --iterations 50 --yes
    python3 rerun.py status
    python3 averaging_check.py --april

`run` starts one process per arm, so the four run in parallel, and each logs to
`results/<arm>/run.log`. It is safe to repeat: pairs already submitted are skipped, so an
interrupted run resumes instead of paying twice. OpenAI chunks go one at a time, because the
organisation's enqueued-token limit fails a batch outright, and a chunk that hits it is resubmitted
at half the size. Batches are billed at half the standard rate by both providers.

## The averaging check

`averaging_check.py` asks how much an app gains by sending a photograph k times and using the
median answer. It makes no new calls. For each photograph it draws 2,000 random subsets of k calls
from the calls already made (seed 20260921) and applies the same subsets to every arm, so
differences between arms come from the models and not from which calls each happened to draw.
Every arm is truncated to the first n successful calls, where n is the smallest count any arm has
for that photograph. Output is `output/AVERAGING_CHECK.md` and `output/averaging_check.json`.

## Changes from the April code

The runners in this repository were seeded verbatim from the academic repository at `e100d50`
(first commit here), so `git diff` against that commit shows every change. The ones that affect
results:

- The Anthropic reader took `content[0]` as the answer. On a model that always thinks, that is
  the thinking block, so every Fable 5.1 answer would have been lost. It now joins the text blocks.
- Refusals from either provider are recorded as failures with `error_class` `refusal` and not
  parsed. No server-side fallback to another model is requested.
- The stop reason is kept on every row, and OpenAI reasoning tokens separately, so a truncated
  answer is distinguishable from a malformed one and reasoning cost can be measured.
- The OpenAI batch error file is now read. Requests rejected at validation appear only there.

The April-only decoders for legacy request IDs, and the separate sequential submitter, were
removed; the driver's chunking replaces the latter.

## Cost

`rerun.py estimate` prints the estimate and its basis. For the two April models the tokens per
request are the April measurements (`april_token_usage.py`). For the two new models they are
assumptions, and output tokens, which include reasoning, are the dominant uncertainty; the first
completed chunk of each arm replaces them with measurements.
