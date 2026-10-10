"""Shared strict schemas and local validation; model output is always untrusted."""
import math


def schema(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


TEXT = {"type": "string", "minLength": 1, "maxLength": 3000}
REFERENCES = {"type": "array", "items": {"type": "string"}, "maxItems": 20}
PROPOSAL = schema({
    "action": {"type": "string", "enum": ["hold", "investigate", "propose_investment"]},
    "symbol": {"type": "string", "maxLength": 32},
    "allocation_usd": {"type": "number", "minimum": 0},
    "rationale": TEXT, "risks": TEXT, "evidence_ids": REFERENCES,
    "invalidation_conditions": TEXT,
})
REVIEW = schema({"verdict": {"type": "string", "enum": ["pass", "challenge", "veto"]},
                 "rationale": TEXT, "evidence_ids": REFERENCES})
VOTE = schema({"vote": {"type": "string", "enum": ["approve", "revise", "reject"]},
               "rationale": TEXT, "evidence_ids": REFERENCES})


def validate(value, spec):
    kind = spec["type"]
    valid = {"object": lambda: isinstance(value, dict),
             "array": lambda: isinstance(value, list),
             "string": lambda: isinstance(value, str),
             "number": lambda: type(value) in (int, float) and math.isfinite(value)}
    if not valid[kind]():
        raise ValueError(f"Invalid {kind} in decision record")
    if "enum" in spec and value not in spec["enum"]:
        raise ValueError("Invalid decision enum")
    if kind == "object":
        if set(value) != set(spec["required"]):
            raise ValueError("Missing or unexpected decision fields")
        for key, child in spec["properties"].items():
            validate(value[key], child)
    if kind in ("string", "array"):
        lower = spec.get("minLength", 0)
        upper = spec.get("maxLength", spec.get("maxItems", 3000))
        if not lower <= len(value) <= upper:
            raise ValueError("Decision field exceeds length bounds")
    if kind == "array":
        for item in value:
            validate(item, spec["items"])
    if kind == "number" and value < spec.get("minimum", 0):
        raise ValueError("Negative allocation")


def validate_references(record, evidence):
    if not set(record["evidence_ids"]).issubset({e["id"] for e in evidence}):
        raise ValueError("Agent cited unknown evidence")
