"""Read-only USD simulation attribution and hypothetical portfolio stress.

No probabilities, asset correlations, liquidity model or execution authority.
Inputs come from one reconciled portfolio snapshot, never agent assertions.
"""
from decimal import Decimal, ROUND_UP


SHOCKS = (Decimal('0.10'), Decimal('0.30'), Decimal('0.50'))
PRECISION = Decimal('0.00000001')


def reports(snapshot):
    complete = snapshot['valuation_complete']
    realized = Decimal(snapshot['realized_pnl_usd'])
    fees = Decimal(snapshot['simulation_fees_usd'])
    api = Decimal(snapshot['api_expense_estimate_or_reserved_usd'])
    reserved = Decimal(snapshot['simulation_planning_reserved_usd'])
    held_notional = Decimal(snapshot['simulation_planning_notional_usd'])
    held_fees = Decimal(snapshot['simulation_planning_fee_usd'])
    equity = Decimal(snapshot['net_equity_estimate_usd']) if complete else None
    peak = Decimal(snapshot['peak_observed_net_equity_usd'])
    market = sum((Decimal(p['market_value_usd']) for p in snapshot['positions']), Decimal(0)) if complete else None
    basis = sum((Decimal(p['cost_basis_usd']) for p in snapshot['positions']), Decimal(0))
    unrealized = market-basis if complete else None
    trading = realized+unrealized if complete else None
    net = trading-api if complete else None
    attribution = {
        'status': 'complete' if complete else 'fresh_marks_required',
        'realized_pnl_after_recorded_fees_usd': str(realized),
        'unrealized_pnl_after_recorded_buy_fees_usd': str(unrealized) if complete else None,
        'price_pnl_before_recorded_fees_usd': str(trading+fees) if complete else None,
        'recorded_trading_fees_usd': str(fees),
        'api_expense_estimate_or_reserved_usd': str(api),
        'net_pnl_after_recorded_costs_usd': str(net) if complete else None,
        'equity_change_reconciled': net == equity-Decimal(snapshot['simulated_capital_usd']) if complete else False,
        'unmodelled_costs': ['tax', 'FX', 'unrecorded_fees_and_slippage'],
    }
    scenarios = []
    for shock in SHOCKS:
        loss = ((market+held_notional)*shock+held_fees).quantize(PRECISION, rounding=ROUND_UP) if complete else None
        stressed = equity-loss if complete else None
        drawdown = max(Decimal(0), (peak-stressed)/peak) if complete else None
        scenarios.append({
            'price_decline_fraction': str(shock),
            'loss_usd': str(loss) if complete else None,
            'net_equity_estimate_usd': str(stressed) if complete else None,
            'drawdown_from_observed_peak_fraction': str(drawdown.quantize(PRECISION, rounding=ROUND_UP)) if complete else None,
            'drawdown_limit_reached': drawdown >= Decimal(snapshot['risk_limits']['max_drawdown_fraction']) if complete else None,
        })
    stress = {
        'status': 'hypothetical' if complete else 'fresh_marks_required',
        'basis': 'simultaneous_price_decline_in_holdings_and_fully_deployed_planning_holds',
        'holdings_market_value_usd': str(market) if complete else None,
        'planning_holds_at_risk_usd': str(reserved),
        'deployment_fee_assumption_usd': str(held_fees),
        'scenarios': scenarios,
        'changes_funding_limits': False,
        'execution_authorized': False,
    }
    return attribution, stress
