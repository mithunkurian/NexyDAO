"""Non-agent policy. No execution library or network capability exists here."""
from decimal import Decimal

INITIAL_CAPITAL = Decimal("5000")
ANNUAL_NET_TARGET = Decimal("0.15")
MAX_POSITION = Decimal("500")
MIN_CASH_RESERVE = Decimal("4000")


def evaluate(proposal, reviews, votes, owner_policy=None):
    from .owner_policy import from_env, proposal_reasons
    owner_policy = owner_policy or from_env()
    owner_policy.assert_current()
    reasons = ["execution_disabled_milestone_1"]
    reasons.extend(proposal_reasons(proposal, owner_policy))
    if proposal["action"] == "propose_investment":
        reasons.append("verified_market_evidence_pipeline_not_implemented")
        if not proposal["symbol"] or not proposal["evidence_ids"] or proposal["allocation_usd"] <= 0:
            reasons.append("incomplete_investment_proposal")
    elif proposal["allocation_usd"] != 0:
        reasons.append("non_investment_must_have_zero_allocation")
    if Decimal(str(proposal["allocation_usd"])) > MAX_POSITION:
        reasons.append("position_limit_exceeded")
    if INITIAL_CAPITAL - Decimal(str(proposal["allocation_usd"])) < MIN_CASH_RESERVE:
        reasons.append("cash_reserve_breached")
    if len(reviews) != 2 or any(r["verdict"] != "pass" for r in reviews):
        reasons.append("risk_clearance_missing")
    if len(votes) != 3 or sum(v["vote"] == "approve" for v in votes) < 2:
        reasons.append("committee_approval_missing")
    return {"execution_authorized": False, "reasons": reasons}


class PaperBroker:
    mode = "paper"

    def execute(self, *args, **kwargs):
        raise PermissionError("Broker execution is disabled; authorization system is incomplete")
