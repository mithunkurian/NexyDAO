import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path


def positive(name: str, default: str, allow_zero: bool = False) -> Decimal:
    value = Decimal(os.environ.get(name, default))
    if not value.is_finite() or value < 0 or (not allow_zero and value == 0):
        raise ValueError(f"{name} must be finite and positive")
    return value


@dataclass(frozen=True)
class Config:
    db: Path
    model: str
    api_key: str = field(repr=False)
    budget: Decimal = Decimal("1")
    input_rate: Decimal = Decimal("0")
    output_rate: Decimal = Decimal("0")
    max_output: int = 1200

    @classmethod
    def from_env(cls):
        if os.environ.get("NEXYDAO_BROKER_MODE", "paper") != "paper":
            raise ValueError("Only paper mode is permitted")
        if os.environ.get("NEXYDAO_EXECUTION_ENABLED", "false").lower() != "false":
            raise ValueError("Execution cannot be enabled in milestone 1")
        cap = int(os.environ.get("NEXYDAO_MAX_OUTPUT_TOKENS", "1200"))
        if not 128 <= cap <= 4096:
            raise ValueError("Output token cap must be between 128 and 4096")
        model = os.environ.get("NEXYDAO_MODEL", "gpt-4o-mini").strip()
        if not model:
            raise ValueError("Model must not be empty")
        return cls(Path(os.environ.get("NEXYDAO_DB", "data/nexydao.sqlite3")),
                   model, os.environ.get("OPENAI_API_KEY", ""),
                   positive("NEXYDAO_API_BUDGET_USD", "1"),
                   positive("NEXYDAO_INPUT_USD_PER_MILLION", "0", True),
                   positive("NEXYDAO_OUTPUT_USD_PER_MILLION", "0", True), cap)
