import argparse
import json
from pathlib import Path

from .config import Config
from .ibkr import ProbeError
from .provider import OpenAIProvider
from .records import PROPOSAL, REVIEW
from .store import Store
from .workflow import run_cycle, load_evidence


class DemoProvider:
    """Offline plumbing fixture, never an investment strategy or real AI decision."""
    mode = "demo"
    def decide(self, run, role, instructions, context, schema):
        if schema == PROPOSAL:
            return {"action": "hold", "symbol": "", "allocation_usd": 0,
                    "rationale": "Offline fixture: no verified evidence.", "risks": "Evidence unavailable.",
                    "evidence_ids": [], "invalidation_conditions": "Obtain verified evidence."}
        if schema == REVIEW:
            return {"verdict": "challenge", "rationale": "Offline fixture; verification unavailable.", "evidence_ids": []}
        return {"vote": "revise", "rationale": "Offline fixture; request verified research.", "evidence_ids": []}


def main():
    parser = argparse.ArgumentParser(description="NexyDAO advisory deliberation; execution disabled")
    parser.add_argument("command", choices=["demo", "deliberate", "costs", "broker-check", "market-check"])
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--market-evidence", type=Path)
    args = parser.parse_args()
    store = None
    try:
        config = Config.from_env()
        if (args.evidence or args.market_evidence) and args.command not in {"demo", "deliberate"}:
            raise ValueError("Evidence arguments apply only to deliberation")
        if args.command == "broker-check":
            from .ibkr import BrokerConfig, run_check
            print(json.dumps(run_check(BrokerConfig.from_env()), indent=2))
            return
        if args.command == "market-check":
            from .market import MarketConfig, run_market_check
            print(json.dumps(run_market_check(MarketConfig.from_env()), indent=2))
            return
        evidence = load_evidence(args.evidence)
        if args.market_evidence:
            from .market import MarketConfig, load_market_evidence
            evidence += load_market_evidence(args.market_evidence, MarketConfig.from_env())
        if len(evidence) > 10 or len({item['id'] for item in evidence}) != len(evidence):
            raise ValueError("Combined evidence must have at most ten unique IDs")
        store = Store(config.db)
        if args.command == "costs":
            result = store.costs()
        else:
            provider = DemoProvider() if args.command == "demo" else OpenAIProvider(config, store)
            result = run_cycle(store, provider, evidence)
        print(json.dumps(result, indent=2))
    except ProbeError as exc:
        # All ProbeError messages are fixed local codes, never vendor response text.
        parser.exit(1, f"NexyDAO stopped safely ({exc}). Execution remains disabled.\n")
    except Exception as exc:
        # Print curated error types only, so credentials or vendor response bodies cannot leak.
        parser.exit(1, f"NexyDAO stopped safely ({type(exc).__name__}). Check local configuration, input and audit records.\n")
    finally:
        if store:
            store.close()
