"""The four arms of the September 2026 rerun.

An arm is a model plus the request settings it is run under. The April run
(Diabetologia dataset) sent temperature 0.01 to every model. Neither
claude-fable-5-1 nor gpt-6-astra accepts a sampling parameter, so both new
models run at the provider default, and the two April models are rerun here
without the temperature setting so that all four arms are sampled the same way.

Reasoning is set to the lowest level each new model allows ("low"). This is a
modelling choice: it is the setting closest to deterministic that remains, and
it is matched across the two new models. The April models are left at their
April reasoning settings (Sonnet 4.6 without thinking, GPT-5.4 at its default),
so that the only change for them is sampling.

Image sizes are the April per-provider maxima (1568 px for Claude, 2048 px for
OpenAI) so each provider sees the same pixels it saw in April.

Prices are batch-tier US dollars per million tokens, checked on 21 September
2026 against the Claude API skill's model table and
https://developers.openai.com/api/docs/pricing.
"""

ARMS = {
    "fable-5-1": {
        "provider": "claude",
        "model": "claude-fable-5-1",
        "max_tokens": 16000,
        "temperature": None,
        "effort": "low",
        "price_in": 5.00,
        "price_out": 25.00,
    },
    "sonnet-4-6-default": {
        "provider": "claude",
        "model": "claude-sonnet-4-6",
        "max_tokens": 8000,
        "temperature": None,
        "effort": None,
        "price_in": 1.50,
        "price_out": 7.50,
    },
    "gpt-6-astra": {
        "provider": "openai",
        "model": "gpt-6-astra",
        "max_tokens": 16000,
        "temperature": None,
        "effort": "low",
        "price_in": 5.00,
        "price_out": 25.00,
    },
    "gpt-5-4-default": {
        "provider": "openai",
        "model": "gpt-5.4",
        "max_tokens": 6000,
        "temperature": None,
        "effort": None,
        "price_in": 1.25,
        "price_out": 7.50,
    },
}


def get_arm(name: str) -> dict:
    if name not in ARMS:
        raise KeyError(f"unknown arm {name!r}; choose from {sorted(ARMS)}")
    return {"name": name, **ARMS[name]}
