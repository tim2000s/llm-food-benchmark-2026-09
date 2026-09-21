#!/usr/bin/env python3
"""
OpenAI Batch API provider
=========================
Builds one Responses API request per (image, iteration) for an arm, submits a
chunk of them as a batch at the 50% batch discount, and converts the output
into the item dicts that batch_common.build_result_dicts expects.

Orchestration (chunking, resuming, waiting, parallel arms) is in rerun.py.

Changes from the April runner, and why:
- The request comes from the arm. temperature is sent only when the arm sets
  one, because gpt-6-astra does not accept sampling parameters, and
  reasoning.effort is sent only when the arm sets one.
- Reasoning tokens are recorded separately. They are billed as output tokens
  and are the largest uncertainty in the cost of a reasoning model.
- A response that stopped at max_output_tokens (status "incomplete") and a
  refusal content part are both kept distinguishable from a parse failure.
- The batch error file is read as well as the output file. Requests rejected
  at validation appear only there, and the April runner silently lost them.
- A batch that fails on the organisation's enqueued-token limit is reported
  as such, so the driver can resubmit in smaller chunks.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import openai

sys.path.insert(0, str(Path(__file__).resolve().parent))
from batch_common import SYSTEM_PROMPT

PROVIDER = "openai"
ENDPOINT = "/v1/responses"

# OpenAI hard limit is 200 MB per upload. Build to 140 MB worst case.
SAFE_BATCH_MB = 140


def build_request(arm: dict, custom_id: str, image_b64: str) -> dict:
    """Build a single batch line for the Responses API."""
    body = {
        "model": arm["model"],
        "input": [{
            "role": "user",
            "content": [
                {"type": "input_text", "text": SYSTEM_PROMPT},
                {"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_b64}"},
            ],
        }],
        "max_output_tokens": arm["max_tokens"],
        "store": False,
    }
    if arm.get("temperature") is not None:
        body["temperature"] = arm["temperature"]
    if arm.get("effort"):
        body["reasoning"] = {"effort": arm["effort"]}
    return {"custom_id": custom_id, "method": "POST", "url": ENDPOINT, "body": body}


def item_from_line(line: dict) -> dict:
    """Convert one line of a batch output or error file into an item."""
    response = line.get("response") or {}
    body = response.get("body") or {}
    status_code = response.get("status_code")
    item = {
        "custom_id": line.get("custom_id", ""),
        "raw_text": None,
        "usage": None,
        "api_error": None,
        "api_error_class": None,
        "extra": {
            "stop_reason": body.get("status") if isinstance(body, dict) else None,
            "incomplete_reason": ((body.get("incomplete_details") or {}).get("reason")
                                  if isinstance(body, dict) else None),
            "reasoning_tokens": None,
            "returned_model": body.get("model") if isinstance(body, dict) else None,
        },
    }
    if isinstance(body, dict) and isinstance(body.get("usage"), dict):
        usage = body["usage"]
        item["usage"] = {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
        }
        item["extra"]["reasoning_tokens"] = (usage.get("output_tokens_details") or {}).get("reasoning_tokens")

    if line.get("error") or status_code != 200:
        detail = line.get("error") or body
        item["api_error"] = f"HTTP {status_code}: {json.dumps(detail)[:300]}"
        item["api_error_class"] = "api"
        return item

    pieces, refusals = [], []
    for out in body.get("output", []):
        for c in out.get("content") or []:
            if c.get("type") == "output_text":
                pieces.append(c.get("text", ""))
            elif c.get("type") == "refusal":
                refusals.append(c.get("refusal", ""))
    if refusals and not pieces:
        item["api_error"] = f"refusal: {refusals[0][:300]}"
        item["api_error_class"] = "refusal"
        return item
    item["raw_text"] = "".join(pieces)
    return item


def upload_via_curl(jsonl_path: Path, api_key: str) -> str:
    """Upload a JSONL file via curl. The OpenAI SDK has historical broken-pipe
    issues with large multipart uploads, so we shell out for reliability."""
    result = subprocess.run(
        [
            "curl", "-s", "-w", "\nHTTP %{http_code}",
            "https://api.openai.com/v1/files",
            "-H", f"Authorization: Bearer {api_key}",
            "-F", "purpose=batch",
            "-F", f"file=@{jsonl_path}",
        ],
        capture_output=True, text=True, timeout=900,
    )
    out = result.stdout
    if "HTTP 200" not in out:
        raise RuntimeError(f"Upload failed: {out}")
    return json.loads(out.split("\nHTTP")[0])["id"]


class Provider:
    """Submit, poll and fetch OpenAI batches for one arm."""

    name = PROVIDER
    safe_batch_mb = SAFE_BATCH_MB

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = openai.OpenAI(api_key=api_key)

    def submit(self, requests: list[dict], state_dir: Path, label: str) -> dict:
        jsonl_path = state_dir / f"upload_{label}.jsonl"
        with open(jsonl_path, "w") as f:
            for req in requests:
                f.write(json.dumps(req) + "\n")
        try:
            file_id = upload_via_curl(jsonl_path, self.api_key)
        finally:
            jsonl_path.unlink(missing_ok=True)
        batch = self.client.batches.create(
            input_file_id=file_id,
            endpoint=ENDPOINT,
            completion_window="24h",
            metadata={"display_name": f"food-rerun-{label}"},
        )
        return {"batch_id": batch.id, "input_file_id": file_id}

    def poll(self, batch_id: str) -> dict:
        b = self.client.batches.retrieve(batch_id)
        codes = [e.code for e in (b.errors.data if b.errors else [])]
        return {
            "finished": b.status in ("completed", "failed", "expired", "cancelled"),
            "text": f"{b.status} counts={b.request_counts}",
            "token_limit": b.status == "failed" and "token_limit_exceeded" in codes,
            "failed": b.status == "failed",
        }

    def fetch(self, batch_id: str) -> list[dict]:
        b = self.client.batches.retrieve(batch_id)
        lines = []
        for file_id in (b.output_file_id, b.error_file_id):
            if file_id:
                text = self.client.files.content(file_id).text
                lines += [json.loads(l) for l in text.splitlines() if l.strip()]
        return [item_from_line(l) for l in lines]
