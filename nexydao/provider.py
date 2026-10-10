"""Small Responses API client; fixed endpoint, no tools, no implicit retries."""
import json
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .records import validate


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward the bearer token to any redirect destination.
        return None


def post(payload, key):
    request = Request("https://api.openai.com/v1/responses",
                      data=json.dumps(payload).encode(),
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with build_opener(NoRedirect()).open(request, timeout=90) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("Oversized API response")
            return json.loads(raw)
    except HTTPError as exc:
        # Never print response bodies or headers; these may contain sensitive inputs.
        raise RuntimeError(f"OpenAI HTTP {exc.code}; no automatic retry") from None
    except (URLError, TimeoutError):
        raise RuntimeError("OpenAI transport failure; reservation retained") from None


class OpenAIProvider:
    def __init__(self, config, store, transport=post):
        self.config, self.store, self.transport = config, store, transport

    def decide(self, run, role, instructions, context, schema):
        c = self.config
        if not c.api_key or c.input_rate <= 0 or c.output_rate <= 0:
            raise ValueError("Set local OPENAI_API_KEY and positive model token rates")
        payload = {"model": c.model, "store": False,
                   "instructions": instructions, "input": json.dumps(context, allow_nan=False),
                   "max_output_tokens": c.max_output,
                   "text": {"format": {"type": "json_schema", "name": "decision",
                                        "strict": True, "schema": schema}}}
        # UTF-8 byte count is a conservative token bound for these text-only requests.
        # Extra allowance covers protocol/schema overhead; output includes reasoning tokens.
        input_bound = len(json.dumps(payload).encode()) + 4096
        reserve = (input_bound * c.input_rate + c.max_output * c.output_rate) / Decimal(1_000_000)
        ticket = self.store.reserve(run, role, c.model, reserve, c.budget)
        self.store.event(run, role + ":request", {
            "model": c.model, "input_rate_per_million": str(c.input_rate),
            "output_rate_per_million": str(c.output_rate), "reserved_usd": str(reserve),
            "max_output_tokens": c.max_output, "prompt_version": 1, "schema_version": 1})
        response = self.transport(payload, c.api_key)
        usage = response.get("usage", {})
        inp, out = usage.get("input_tokens"), usage.get("output_tokens")
        if type(inp) is not int or type(out) is not int or min(inp, out) < 0:
            raise ValueError("Missing or invalid API usage; reservation retained")
        cost = (inp * c.input_rate + out * c.output_rate) / Decimal(1_000_000)
        self.store.settle(ticket, cost, usage, response.get("id"))
        if inp > input_bound or out > c.max_output:
            raise ValueError("API usage exceeded reservation bound; stop for operator review")
        if response.get("status") != "completed":
            raise ValueError("Incomplete API response")
        chunks = [part for item in response.get("output", []) if item.get("type") == "message"
                  for part in item.get("content", [])]
        if any(p.get("type") == "refusal" for p in chunks):
            raise ValueError("Model refused deliberation")
        value = json.loads("".join(p["text"] for p in chunks if p.get("type") == "output_text"))
        validate(value, schema)
        return value
