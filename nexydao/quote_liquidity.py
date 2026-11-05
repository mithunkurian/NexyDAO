"""Quote-backed spread screen, not verified depth, capacity or execution liquidity.

Evidence trust is assigned only by application receipt loaders. This freezes and
revalidates their sanitized quote observations across advisory calls; it does not
authenticate arbitrary caller-supplied evidence or attest size-unit settings.
"""
from decimal import Decimal,localcontext,ROUND_UP
from dataclasses import dataclass
from datetime import datetime,timezone
import json
import re
import time

from .ibkr import ProbeError
from .market import canonical,validate_quote_observation

MAX_SPREAD=Decimal('0.01')


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ProbeError('duplicate_quote_summary_field')
        result[key]=value
    return result


@dataclass(frozen=True,init=False)
class QuoteLiquidity:
    payload:bytes

    def __init__(self,evidence,now=None):
        now=time.time() if now is None else now
        entries=[];identifiers=set()
        for item in evidence:
            if item.get('verification')!='verified_quote':continue
            identifier=item.get('id')
            if (not isinstance(identifier,str) or not re.fullmatch('quote-[0-9a-f]{64}',identifier)
                    or identifier in identifiers or not isinstance(item.get('summary'),str) or len(item['summary'])>4000):
                raise ProbeError('invalid_liquidity_quote_identity')
            identifiers.add(identifier)
            try:view=json.loads(item['summary'],object_pairs_hook=_unique)
            except (ValueError,TypeError,RecursionError):raise ProbeError('invalid_liquidity_quote_summary') from None
            if not isinstance(view,dict) or set(view)!={'contract','quote','received_at','expires_at','scope'}:
                raise ProbeError('liquidity_quote_observation_required')
            validate_quote_observation(view['contract'],view['quote'],view['received_at'],view['expires_at'],now)
            if (type(item.get('expires_at')) is not int or item['expires_at']!=view['expires_at']
                    or item.get('source_url')!='ibkr://contract/'+str(view['contract']['con_id'])
                    or item.get('observed_at')!=datetime.fromtimestamp(view['quote']['event_time'],timezone.utc).isoformat()):
                raise ProbeError('liquidity_quote_binding_mismatch')
            entries.append({'id':identifier,**view})
        if len(entries)>10:raise ProbeError('liquidity_quote_count_limit')
        object.__setattr__(self,'payload',canonical(entries))

    def _entries(self,now=None):
        entries=json.loads(self.payload)
        for view in entries:
            validate_quote_observation(view['contract'],view['quote'],view['received_at'],view['expires_at'],now)
        return entries

    def assert_current(self,evidence):
        if QuoteLiquidity(evidence).payload!=self.payload:raise ProbeError('quote_changed_during_deliberation')
        self._entries()

    def reasons(self,allocations,snapshot=None):
        entries=self._entries();reasons=[]
        for allocation in allocations:
            symbol=allocation['symbol'];cited=set(allocation.get('evidence_ids',[]))
            matching=[view for view in entries if view['contract']['symbol']==symbol]
            if not any(view['id'] in cited for view in matching):
                reasons.append('fresh_quote_liquidity_evidence_required');continue
            contracts={view['contract']['con_id'] for view in matching}
            if len(contracts)!=1:reasons.append('liquidity_quote_contract_ambiguous')
            if snapshot is not None:
                for position in snapshot['positions']:
                    if position['symbol']==symbol and position['contract_id'] not in contracts:
                        reasons.append('liquidity_position_contract_mismatch')
            with localcontext() as context:
                context.prec=50
                if any(Decimal(view['quote']['ask'])-Decimal(view['quote']['bid'])>
                       Decimal(view['quote']['bid'])*MAX_SPREAD for view in matching):
                    reasons.append('quote_spread_limit_exceeded')
        return sorted(set(reasons))

    def report(self):
        rows=[]
        for view in self._entries():
            with localcontext() as context:
                context.prec=50
                bid=Decimal(view['quote']['bid']);ask=Decimal(view['quote']['ask'])
                rows.append({'quote_id':view['id'],'symbol':view['contract']['symbol'],'contract_id':view['contract']['con_id'],
                    'spread_fraction':str(((ask-bid)/bid).quantize(Decimal('0.00000001'),rounding=ROUND_UP)),
                    'spread_within_limit':ask-bid<=bid*MAX_SPREAD,'expires_at':view['expires_at']})
        return {'status':'quote_spread_screen_only','model_version':1,'max_spread_fraction':str(MAX_SPREAD),
                'quotes':rows,'size_units_verified':False,'executable_depth_verified':False,
                'portfolio_exit_capacity_verified':False,'market_liquidity_verified':False,'execution_authorized':False}
