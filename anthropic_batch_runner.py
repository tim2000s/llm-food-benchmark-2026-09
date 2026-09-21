#!/usr/bin/env python3
"""
Anthropic Message Batches API provider
======================================
Builds one Messages API request per (image, iteration) for an arm, submits a
chunk of them as a Message Batch at the 50% batch discount, and converts the
results into the item dicts that batch_common.build_result_dicts expects.

Orchestration (chunking, resuming, waiting, parallel arms) is in rerun.py.

Changes from the April runner, and why:
- The request comes from the arm rather than a model string, because the
  sampling and reasoning settings now differ between arms. temperature is
  sent only when the arm sets one: claude-fable-5-1 rejects it with a 400.
- The response text is the concatenation of the text blocks. The April code
  read content[0], which on a model that always thinks is the thinking block,
  so every answer would have been parsed as empty.
- stop_reason is kept on every row. A refusal is recorded as a failure with
  error_class "refusal" rather than parsed, and a max_tokens stop is kept so
  that a truncated answer is distinguishable from a malformed one.
- No server-side refusal fallback is requested, since a fallback would answer
  some requests with a different model inside a per-model measurement.
"""
from __future__ import annotations

import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent))
from batch_common import SYSTEM_PROMPT

PROVIDER = "claude"

# Anthropic batch limit is 256 MB. Build to 150 MB to leave headroom for
# HTTP/JSON overhead and the per-request envelope.
SAFE_BATCH_MB = 150


def build_request(arm: dict, custom_id: str, image_b64: str) -> dict:
    """Build a single batch request for the Messages API.

    custom_id must match ^[a-zA-Z0-9_-]{1,64}$; we use idx<N> form.
    """
    params = {
        "model": arm["model"],
        "max_tokens": arm["max_tokens"],
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": SYSTEM_PROMPT},
                {"type": "image", "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": image_b64,
                }},
            ],
        }],
    }
    if arm.get("temperature") is not None:
        params["temperature"] = arm["temperature"]
    if arm.get("effort"):
        params["output_config"] = {"effort": arm["effort"]}
    return {"custom_id": custom_id, "params": params}


def item_from_result(result) -> dict:
    """Convert one batch result (SDK object) into a build_result_dicts item."""
    item = {
        "custom_id": result.custom_id,
        "raw_text": None,
        "usage": None,
        "api_error": None,
        "api_error_class": None,
        "extra": {"stop_reason": None, "returned_model": None},
    }
    if result.result.type != "succeeded":
        err_obj = getattr(result.result, "error", None)
        item["api_error"] = f"{result.result.type}: {err_obj if err_obj else ''}"[:500]
        item["api_error_class"] = "api"
        return item

    msg = result.result.message
    if getattr(msg, "usage", None) is not None:
        item["usage"] = {
            "input_tokens": getattr(msg.usage, "input_tokens", None),
            "output_tokens": getattr(msg.usage, "output_tokens", None),
        }
    item["extra"]["stop_reason"] = getattr(msg, "stop_reason", None)
    item["extra"]["returned_model"] = getattr(msg, "model", None)

    if msg.stop_reason == "refusal":
        details = getattr(msg, "stop_details", None)
        category = getattr(details, "category", None) if details else None
        item["api_error"] = f"refusal: category={category}"
        item["api_error_class"] = "refusal"
        return item

    item["raw_text"] = "".join(
        getattr(block, "text", "") for block in (msg.content or [])
        if getattr(block, "type", None) == "text"
    )
    return item


class Provider:
    """Submit, poll and fetch Message Batches for one arm."""

    name = PROVIDER
    safe_batch_mb = SAFE_BATCH_MB

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def submit(self, requests: list[dict], state_dir: Path, label: str) -> dict:
        batch = self.client.messages.batches.create(requests=requests)
        return {"batch_id": batch.id}

    def poll(self, batch_id: str) -> dict:
        batch = self.client.messages.batches.retrieve(batch_id)
        rc = batch.request_counts
        text = (f"{batch.processing_status} succeeded={rc.succeeded} errored={rc.errored} "
                f"processing={rc.processing} expired={rc.expired} canceled={rc.canceled}")
        return {"finished": batch.processing_status == "ended", "text": text,
                "token_limit": False, "failed": False}

    def fetch(self, batch_id: str) -> list[dict]:
        return [item_from_result(r) for r in self.client.messages.batches.results(batch_id)]
