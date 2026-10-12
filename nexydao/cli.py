import argparse
import json
from pathlib import Path

from .config import Config
from .ibkr import ProbeError
from .sec import SourceError
from .owner_policy import OwnerPolicyError, from_env as owner_policy_from_env
from .portfolio import PortfolioError
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
    parser.add_argument("command", choices=["demo", "deliberate", "costs", "broker-check", "market-check", "source-check", "research", "owner-policy", "portfolio", "portfolio-report", "sim-fill", "sim-settle", "portfolio-mark"])
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--market-evidence", type=Path)
    parser.add_argument("--research-evidence", type=Path)
    parser.add_argument('--fill',type=Path)
    parser.add_argument('--settlement-id')
    parser.add_argument('--with-research',action='store_true')
    args = parser.parse_args()
    store = None
    try:
        config = Config.from_env()
        owner_policy = owner_policy_from_env()
        if args.fill and args.command!='sim-fill' or args.settlement_id and args.command!='sim-settle':
            raise ValueError('Simulation arguments apply only to their accounting commands')
        if args.with_research and args.command!='portfolio': raise ValueError('Research modifier requires portfolio command')
        if (args.evidence or args.market_evidence or args.research_evidence) and args.command not in {"demo", "deliberate", "research", "portfolio", "portfolio-mark"}:
            raise ValueError("Evidence arguments apply only to deliberation")
        if args.command=='portfolio-mark' and (not args.market_evidence or args.evidence or args.research_evidence):
            raise ValueError('Portfolio marking requires one signed market receipt')
        if args.command=='sim-fill' and not args.fill or args.command=='sim-settle' and not args.settlement_id:
            raise ValueError('Explicit simulated fill/settlement input required')
        if args.command == 'owner-policy':
            print(json.dumps({'policy': owner_policy.document(), 'sha256': owner_policy.digest,
                              'execution_authorized': False}, indent=2))
            return
        if args.command == 'source-check':
            from .sec import ResearchConfig, run_source_check
            print(json.dumps(run_source_check(ResearchConfig.from_env()), indent=2))
            return
        if (args.command == 'research' or args.with_research) and (not args.research_evidence or args.market_evidence):
            raise ValueError('Research requires a signed filing receipt; run it before collecting short-lived quotes')
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
        if args.research_evidence:
            from .sec import ResearchConfig, load_research_evidence
            evidence += load_research_evidence(args.research_evidence, ResearchConfig.from_env())
        if len(evidence) > 10 or len({item['id'] for item in evidence}) != len(evidence):
            raise ValueError("Combined evidence must have at most ten unique IDs")
        store = Store(config.db)
        if args.command in {'portfolio-report','sim-fill','sim-settle','portfolio-mark'}:
            from .portfolio import Portfolio
            ledger=Portfolio(store)
            if args.command=='portfolio-report': result=ledger.snapshot()
            elif args.command=='sim-fill':
                if args.fill.stat().st_size>4000: raise ValueError('Simulation fill size limit')
                result=ledger.fill(json.loads(args.fill.read_text(encoding='utf-8')),owner_policy)
            elif args.command=='sim-settle': result=ledger.settle(args.settlement_id)
            else:
                from .market import MarketConfig
                result=ledger.mark(args.market_evidence,MarketConfig.from_env())
            print(json.dumps(result,indent=2))
            return
        if args.command == "costs":
            result = store.costs()
        else:
            provider = DemoProvider() if args.command == "demo" else OpenAIProvider(config, store)
            result = run_cycle(store, provider, evidence, research=args.command == 'research' or args.with_research,
                               owner_policy=owner_policy,portfolio=args.command=='portfolio')
        print(json.dumps(result, indent=2))
    except (ProbeError, SourceError, OwnerPolicyError, PortfolioError) as exc:
        # All ProbeError messages are fixed local codes, never vendor response text.
        parser.exit(1, f"NexyDAO stopped safely ({exc}). Execution remains disabled.\n")
    except Exception as exc:
        # Print curated error types only, so credentials or vendor response bodies cannot leak.
        parser.exit(1, f"NexyDAO stopped safely ({type(exc).__name__}). Check local configuration, input and audit records.\n")
    finally:
        if store:
            store.close()
