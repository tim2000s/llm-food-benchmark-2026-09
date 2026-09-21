#!/usr/bin/env python3
"""
Run the September 2026 rerun: every test photograph to every arm, N times.

    python3 rerun.py estimate --iterations 50            # no network, no spend
    python3 rerun.py estimate --iterations 50 --count-tokens   # free token count (Claude arms)
    python3 rerun.py run --iterations 50 --yes           # all arms in parallel
    python3 rerun.py status

Each arm runs in its own process, so a slow provider does not hold up the
others. Within an arm, requests are submitted in chunks and each chunk is a
provider batch. Anthropic chunks are submitted together; OpenAI chunks are
submitted one at a time, waiting for each to finish, because the
organisation's enqueued-token limit counts everything in flight and a batch
over that limit fails outright. A batch that fails on that limit is abandoned
and its requests resubmitted in chunks half the size.

Every submitted chunk writes a state file before anything else happens, and a
rerun of the same command skips every (iteration, image) pair already covered
by a live state file. An interrupted run is therefore resumed rather than
paid for twice. Results land in results/<arm>/results_<batch_id>.json in the
April schema, with the arm settings in the file metadata.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arms import ARMS, get_arm
from batch_common import (
    log,
    PROMPT_SHA256,
    SYSTEM_PROMPT,
    discover_images,
    preload_image_data,
    make_id_mapping,
    base_state_metadata,
    write_state_file,
    load_state_file,
    build_result_dicts,
    write_results_file,
)
from food_nutrition_benchmark import DEFAULT_JPEG_QUALITY, MAX_IMAGE_DIM

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
POLL_SEC = 60
TOKEN_LIMIT_BACKOFF_SEC = 300
API_KEY_ENV = {"claude": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}

# Tokens per request used by the estimate, as (low, high). Measured for the
# April models (april_token_usage.py: input median, output mean and p90).
# For the two new models these are assumptions, stated with their basis, and
# the output figure is the dominant uncertainty because reasoning is billed as
# output. The first chunk of a real run replaces them with measurements.
TOKEN_ASSUMPTIONS = {
    "sonnet-4-6-default": {
        "in": (3380, 3380), "out": (1499, 2390),
        "basis": "April measured: output mean and p90 at temperature 0.01",
    },
    "gpt-5-4-default": {
        "in": (4532, 4591), "out": (819, 1279),
        "basis": "April measured: output mean and p90 at temperature 0.01",
    },
    "fable-5-1": {
        "in": (3400, 4900), "out": (1500, 4800),
        "basis": ("assumed: prompt text 1.0-1.35x Sonnet 4.6 for the newer tokenizer, "
                  "image 1,600-2,460 tokens; output is the April Sonnet answer length "
                  "at the same tokenizer ratio plus 0-3,000 thinking tokens at low effort"),
    },
    "gpt-6-astra": {
        "in": (4500, 5500), "out": (1000, 4000),
        "basis": ("assumed: input as GPT-5.4 to 20% above for an unknown tokenizer; "
                  "output is the April GPT-5.4 answer plus 200-3,000 reasoning tokens at low effort"),
    },
}


def _provider_module(provider: str):
    if provider == "claude":
        import anthropic_batch_runner as mod
    elif provider == "openai":
        import openai_batch_runner as mod
    else:
        raise ValueError(provider)
    return mod


def arm_dir(arm_name: str) -> Path:
    return RESULTS_DIR / arm_name


def state_dir(arm_name: str) -> Path:
    return arm_dir(arm_name) / "state"


def all_pairs(iterations: int, images: list[Path]) -> list[tuple[int, str]]:
    return [(it, img.name) for it in range(1, iterations + 1) for img in images]


def live_states(arm_name: str) -> list[tuple[Path, dict]]:
    out = []
    for sf in sorted(state_dir(arm_name).glob("chunk_*.json")):
        meta = load_state_file(sf)
        if meta.get("status") != "abandoned":
            out.append((sf, meta))
    return out


def covered_pairs(arm_name: str) -> set[tuple[int, str]]:
    return {(e["iteration"], e["image_file"])
            for _, meta in live_states(arm_name) for e in meta["id_map"].values()}


def chunk_size(mod, arm: dict, image_data: dict[str, str], cap: int) -> int:
    """Largest chunk that fits the provider's payload limit, capped at `cap`."""
    worst = max(len(json.dumps(mod.build_request(arm, "idx0", b64))) + 1
                for b64 in image_data.values())
    return max(1, min(cap, int(mod.SAFE_BATCH_MB * 1024 * 1024 / worst)))


def submit_chunk(provider, mod, arm: dict, images: list[Path], image_data: dict[str, str],
                 pairs: list[tuple[int, str]]) -> tuple[Path, dict]:
    records, id_map = make_id_mapping(pairs)
    requests = [mod.build_request(arm, r["custom_id"], image_data[r["image_file"]]) for r in records]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    label = f"{arm['name']}_{stamp}"
    sdir = state_dir(arm["name"])
    sdir.mkdir(parents=True, exist_ok=True)
    ids = provider.submit(requests, sdir, label)
    meta = base_state_metadata(arm["model"], arm["provider"], images, pairs, id_map,
                               sub_index=0, n_subbatches=0, jpeg_quality=DEFAULT_JPEG_QUALITY)
    meta.update(ids)
    meta.update({"arm": arm, "status": "submitted", "label": label})
    sf = write_state_file(sdir, f"chunk_{stamp}.json", meta)
    log.info(f"[{arm['name']}] submitted {len(pairs)} requests as {ids['batch_id']}")
    return sf, meta


def download(provider, arm: dict, sf: Path, meta: dict) -> None:
    items = provider.fetch(meta["batch_id"])
    for it in items:
        returned = (it.get("extra") or {}).get("returned_model")
        if returned and not returned.startswith(arm["model"]):
            log.warning(f"[{arm['name']}] {it['custom_id']}: requested {arm['model']}, returned {returned}")
    results = build_result_dicts(items, arm["model"], arm["provider"], meta["id_map"])
    out = arm_dir(arm["name"]) / f"results_{meta['batch_id']}.json"
    write_results_file(out, arm["model"], arm["provider"], {
        "run_id": meta["label"],
        "iterations": "batch",
        "display": arm["model"],
        "images": meta["images"],
        "image_max_dim": meta["max_image_dim"],
        "jpeg_quality": meta["jpeg_quality"],
        "prompt_sha256": meta["prompt_sha256"],
        "batch_provider_id": meta["batch_id"],
        "arm": arm,
    }, results)
    meta["status"] = "downloaded"
    write_state_file(sf.parent, sf.name, meta)
    n_ok = sum(r["success"] for r in results)
    log.info(f"[{arm['name']}] {meta['batch_id']}: {n_ok}/{len(results)} parsed -> {out.name}")
    if len(results) != len(meta["id_map"]):
        log.warning(f"[{arm['name']}] {meta['batch_id']}: {len(results)} results for "
                    f"{len(meta['id_map'])} requests")


def wait_and_download(provider, arm: dict, sf: Path, meta: dict) -> str:
    """Block until the batch finishes, then download it. Returns an outcome:
    'downloaded', 'token_limit' (state abandoned) or 'failed'."""
    last = None
    while True:
        try:
            p = provider.poll(meta["batch_id"])
        except Exception as e:
            log.warning(f"[{arm['name']}] poll failed, retrying: {e}")
            time.sleep(POLL_SEC)
            continue
        if p["text"] != last:
            log.info(f"[{arm['name']}] {meta['batch_id']}: {p['text']}")
            last = p["text"]
        if p["finished"]:
            break
        time.sleep(POLL_SEC)
    if p["token_limit"]:
        meta["status"] = "abandoned"
        write_state_file(sf.parent, sf.name, meta)
        return "token_limit"
    if p["failed"]:
        meta["status"] = "failed"
        write_state_file(sf.parent, sf.name, meta)
        return "failed"
    download(provider, arm, sf, meta)
    return "downloaded"


def run_arm(arm_name: str, iterations: int, max_per_chunk: int) -> None:
    arm = get_arm(arm_name)
    mod = _provider_module(arm["provider"])
    key = os.environ.get(API_KEY_ENV[arm["provider"]])
    if not key:
        sys.exit(f"{API_KEY_ENV[arm['provider']]} not set")
    provider = mod.Provider(key)
    images = discover_images()
    image_data = preload_image_data(images, arm["provider"], DEFAULT_JPEG_QUALITY)
    size = chunk_size(mod, arm, image_data, max_per_chunk)
    sequential = arm["provider"] == "openai"
    wanted = all_pairs(iterations, images)
    # A bookkeeping fault that stopped pairs being recognised as covered would
    # otherwise resubmit, and bill, the same requests without end.
    submit_budget = 2 * len(wanted)

    while True:
        done = covered_pairs(arm_name)
        remaining = [p for p in wanted if p not in done]
        if not remaining:
            break
        chunk = remaining[:size]
        submit_budget -= len(chunk)
        if submit_budget < 0:
            sys.exit(f"[{arm_name}] submitted twice the requested number of requests; "
                     f"stopping. Inspect {state_dir(arm_name)}")
        sf, meta = submit_chunk(provider, mod, arm, images, image_data, chunk)
        if sequential:
            outcome = wait_and_download(provider, arm, sf, meta)
            if outcome == "token_limit":
                size = max(1, size // 2)
                log.warning(f"[{arm_name}] enqueued-token limit; chunk size now {size}, "
                            f"waiting {TOKEN_LIMIT_BACKOFF_SEC}s")
                time.sleep(TOKEN_LIMIT_BACKOFF_SEC)
            elif outcome == "failed":
                sys.exit(f"[{arm_name}] batch {meta['batch_id']} failed; stopping this arm")

    for sf, meta in live_states(arm_name):
        if meta["status"] == "submitted":
            wait_and_download(provider, arm, sf, meta)
    log.info(f"[{arm_name}] complete")


def estimate(arm_names: list[str], iterations: int, max_per_chunk: int, count_tokens: bool) -> None:
    images = discover_images()
    n = iterations * len(images)
    print(f"{len(images)} images x {iterations} iterations = {n} requests per arm\n")
    total_lo = total_hi = total_ceiling = 0.0
    rows = []
    for name in arm_names:
        arm = get_arm(name)
        mod = _provider_module(arm["provider"])
        image_data = preload_image_data(images, arm["provider"], DEFAULT_JPEG_QUALITY)
        # Build every request once, so a malformed arm fails here rather than at the provider.
        for b64 in image_data.values():
            json.dumps(mod.build_request(arm, "idx0", b64))
        size = chunk_size(mod, arm, image_data, max_per_chunk)
        a = dict(TOKEN_ASSUMPTIONS[name])
        if count_tokens and arm["provider"] == "claude":
            a["in"] = _count_claude_input(arm, image_data)
            a["basis"] += "; input counted with count_tokens"
        lo = n * (a["in"][0] * arm["price_in"] + a["out"][0] * arm["price_out"]) / 1e6
        hi = n * (a["in"][1] * arm["price_in"] + a["out"][1] * arm["price_out"]) / 1e6
        ceiling = n * (a["in"][1] * arm["price_in"] + arm["max_tokens"] * arm["price_out"]) / 1e6
        total_lo, total_hi, total_ceiling = total_lo + lo, total_hi + hi, total_ceiling + ceiling
        rows.append((name, arm, a, lo, hi, ceiling, size))

    print(f"{'arm':<20} {'model':<18} {'in tok':>11} {'out tok':>11} {'$ est':>13} {'$ ceiling':>10}  chunk")
    for name, arm, a, lo, hi, ceiling, size in rows:
        print(f"{name:<20} {arm['model']:<18} {a['in'][0]:>5}-{a['in'][1]:<5} "
              f"{a['out'][0]:>5}-{a['out'][1]:<5} {lo:>6.0f}-{hi:<6.0f} {ceiling:>10.0f}  {size}")
    print(f"{'total':<20} {'':<18} {'':>11} {'':>11} {total_lo:>6.0f}-{total_hi:<6.0f} {total_ceiling:>10.0f}")
    print("\nBatch-tier prices; the ceiling assumes every request uses its full max_tokens.")
    for name, _, a, *_ in rows:
        print(f"  {name}: {a['basis']}")


def _count_claude_input(arm: dict, image_data: dict[str, str]) -> tuple[int, int]:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    counts = []
    for b64 in image_data.values():
        params = _provider_module("claude").build_request(arm, "idx0", b64)["params"]
        counts.append(client.messages.count_tokens(
            model=params["model"], messages=params["messages"]).input_tokens)
    return min(counts), max(counts)


def status(arm_names: list[str]) -> None:
    for name in arm_names:
        states = sorted(state_dir(name).glob("chunk_*.json"))
        by = {}
        for sf in states:
            s = load_state_file(sf).get("status")
            by[s] = by.get(s, 0) + 1
        n_res = len(list(arm_dir(name).glob("results_*.json")))
        print(f"{name:<20} chunks {by or '{}'}  results files {n_res}")


def run_parallel(arm_names: list[str], iterations: int, max_per_chunk: int) -> None:
    procs = []
    for name in arm_names:
        arm_dir(name).mkdir(parents=True, exist_ok=True)
        logf = open(arm_dir(name) / "run.log", "a")
        cmd = [sys.executable, str(Path(__file__).resolve()), "_arm", name,
               "--iterations", str(iterations), "--max-per-chunk", str(max_per_chunk)]
        procs.append((name, subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)))
        log.info(f"started {name} (pid {procs[-1][1].pid}), log results/{name}/run.log")
    failed = []
    for name, p in procs:
        if p.wait() != 0:
            failed.append(name)
    status(arm_names)
    if failed:
        sys.exit(f"arms that exited with an error: {failed}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["estimate", "run", "status", "_arm"])
    ap.add_argument("arm", nargs="?", help="internal: the arm for _arm")
    ap.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS))
    ap.add_argument("--iterations", "-n", type=int, default=50)
    ap.add_argument("--max-per-chunk", type=int, default=1000)
    ap.add_argument("--count-tokens", action="store_true",
                    help="count Claude input tokens with the free count_tokens endpoint")
    ap.add_argument("--yes", action="store_true", help="required for run: confirms the spend")
    args = ap.parse_args()

    if args.action == "estimate":
        estimate(args.arms, args.iterations, args.max_per_chunk, args.count_tokens)
    elif args.action == "status":
        status(args.arms)
    elif args.action == "run":
        if not args.yes:
            sys.exit("run spends money; check `estimate` first and pass --yes")
        missing = sorted({API_KEY_ENV[get_arm(a)["provider"]] for a in args.arms}
                         - {k for k in API_KEY_ENV.values() if os.environ.get(k)})
        if missing:
            sys.exit(f"not set: {missing}")
        run_parallel(args.arms, args.iterations, args.max_per_chunk)
    elif args.action == "_arm":
        run_arm(args.arm, args.iterations, args.max_per_chunk)


if __name__ == "__main__":
    main()
