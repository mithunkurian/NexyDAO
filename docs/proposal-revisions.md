# Linked advisory proposal revisions

`--revise-run RUN_UUID` starts one new AI advisory cycle linked to a completed AI
run in the same persistent database. It does not resume a failed/running run, reuse
approvals, authorize execution or create an automatic retry/schedule. The operator
chooses when to start a bounded development trial; investment reasoning remains
with the CEO and reviewers. Autonomous revision orchestration remains future work.

## Review and evidence scope

The new cycle receives a compact historical proposal, risk reviews and committee
votes, labelled unverified. It loads current owner policy, portfolio state, costs
and explicitly supplied evidence. Old receipts are not refreshed or imported and
historical citations are not accepted as current references. Each researcher,
manager and reviewer repeats the applicable current checks. Research/Portfolio
Manager stages cannot be dropped when revising a parent that used them; six, seven,
eight or nine new calls run according to the selected workflow.

Current risk officers receive the same current proposal, without each other's
new review. Committee calls remain separate. Researchers share the same current
facts and historical feedback, without the other's new report. Past feedback can
influence reasoning; this is logical role separation, not statistical independence.
Prompt version 10 distinguishes revision history from evidence/permission. A valid
outcome may still be abstention or investigation; no forced change creates a buy.

## Audit and bounds

Each result records its parent UUID, SHA-256 of the canonical parent result, root
UUID and revision depth. A separate `run_revisions` table records the link alongside
creation of the new run. Chains allow at most three revisions after the root;
ancestors must be completed AI records with matching links/hashes. Parent result
loading is bounded to 256 KiB per record. Parent changes detected during review
fail the child. Results do not recursively embed earlier results, so context does
not grow by copying entire chains. The existing three-result AI memory still applies.

These checks detect inconsistent local records; an administrator able to rewrite
all hashes/links and SQLite state is outside this integrity boundary. Existing
databases add the link table without relabelling old runs or resetting capital/costs.
Failed revisions remain failed, cannot become parents, and retain incurred or
uncertain API costs under the same lifetime budget. No failed cycle auto-retries.

## Commands

Use the existing protected credentials, owner policy, persistent `NEXYDAO_DB` and
fresh evidence. Take the parent UUID from a completed result in that database:

```bash
python3 -m nexydao deliberate --revise-run PARENT_UUID --research-evidence /private/sec-research.json
python3 -m nexydao research --revise-run PARENT_UUID --research-evidence /private/sec-research.json
python3 -m nexydao portfolio --with-research --revise-run PARENT_UUID --research-evidence /private/sec-research.json
```

Choose the command that repeats the parent's stages. Research still runs before
short-lived quote collection; `research` and `portfolio --with-research` retain
their existing quote-input restrictions. A quote-free Portfolio Manager must
abstain. Demo/accounting/collector commands reject `--revise-run` before opening
the database. Execution stays disabled even after unanimous fresh approval.

All 234 offline tests and the isolated demo passed locally. Coverage includes fresh
six/nine-stage review, stage preservation, current policy/costs, invalid parents,
lineage depth, parent changes, stale citations, retained failed-call costs and
legacy schema migration. Ubuntu and live paid revision acceptance remain pending.
A schema/prompt change alone does not establish paid API
acceptance, verified thesis prose, full P3 completion or autonomous operation.
