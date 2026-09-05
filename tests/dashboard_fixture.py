#!/usr/bin/env python3
"""Synthetic, reproducible dashboard preview. Never reads a user's memory stores.

Run: python3 tests/dashboard_fixture.py --out /tmp/cm-preview
The HTML is rendered by the shipped renderer; JSON is illustrative, not live evidence.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/consolidate-memory/scripts"))
import memory_status as ms
import render_html as rh


# Fictional canonical sources: name, home domain, scope, recipients, actual holders.
# The validation below feeds these through the real fleet-layer emitter, with only
# its disk/registry readers replaced. No fixture generation reads a user's stores.
SHARED_FACTS = [
    ("review-conventions", "work", "user-global", [], ["atlas-api", "atlas-web", "team-docs"]),
    ("source-provenance", "work", "user-global", [], ["atlas-api", "atlas-web", "team-docs"]),
    ("evaluation-provenance", "research", "user-global", [], ["eval-lab", "model-notes"]),
    ("shell-portability", "tools", "user-global", [], ["release-tools", "dotfiles"]),
    ("release-checks", "work", "stack-general", ["release-kit"], ["atlas-api", "eval-lab", "release-tools"]),
    ("artifact-provenance", "work", "stack-general", ["release-kit"], ["atlas-api", "eval-lab", "release-tools"]),
    ("benchmark-reproducibility", "work", "stack-general", ["release-kit"], ["eval-lab", "release-tools"]),
    ("contract-versioning", "work", "stack-general", ["api-contract"], ["atlas-api", "atlas-web"]),
]


def sample():
    nodes = []
    for name, domain, groups, facts, baseline, stack, tokens in [
        ("atlas-api", "work", ["release-kit", "api-contract"], 24, 2, 3, 984),
        ("atlas-web", "work", ["api-contract"], 18, 2, 1, 768),
        ("team-docs", "work", [], 12, 2, 0, 510),
        ("eval-lab", "research", ["release-kit"], 20, 1, 3, 812),
        ("model-notes", "research", [], 9, 1, 0, 360),
        ("release-tools", "tools", ["release-kit"], 16, 1, 3, 624),
        ("dotfiles", "tools", [], 8, 1, 0, 312),
    ]:
        nodes.append(dict(node=name, domain=domain, groups=groups, trigger=name == "atlas-api",
                          facts=facts, shared=baseline+stack, universal=baseline, stack=stack,
                          always_loaded_tokens=tokens, mirror_index_tokens=(baseline+stack)*28,
                          recall_tokens=facts*160, sid="sample-"+name))
    edges = [{"a": "atlas-api", "b": "atlas-web", "n": 1},
             {"a": "atlas-api", "b": "eval-lab", "n": 2},
             {"a": "atlas-api", "b": "release-tools", "n": 2},
             {"a": "eval-lab", "b": "release-tools", "n": 3}]
    baseline = [{"name": "review-conventions", "domain": "work", "held": 3},
                {"name": "source-provenance", "domain": "work", "held": 3},
                {"name": "evaluation-provenance", "domain": "research", "held": 2},
                {"name": "shell-portability", "domain": "tools", "held": 2}]
    net = dict(basis="≈ chars/4 (estimate)", basis_scope="fleet", node_def="project stores holding shared facts",
               trigger="atlas-api", nodes=nodes, domains=[{"domain": d} for d in ("work", "research", "tools")],
               stack_edges=edges, universal_facts=baseline,
               # The emitter names only stronger peer intersections, never trigger
               # spokes. These peers hold one more fact than atlas-api has pulled.
               stack_edge_facts=[{"a": "eval-lab", "b": "release-tools",
                                  "names": ["artifact-provenance", "benchmark-reproducibility", "release-checks"]}],
               group_links=[{"group": "release-kit", "home_domain": "work", "members_n": 3, "facts_total": 3,
                             "facts": [{"name": "release-checks", "domain": "work"},
                                       {"name": "artifact-provenance", "domain": "work"},
                                       {"name": "benchmark-reproducibility", "domain": "work"}]},
                            {"group": "api-contract", "home_domain": "work", "members_n": 2, "facts_total": 1,
                             "facts": [{"name": "contract-versioning", "domain": "work"}]}],
               totals=dict(nodes=len(nodes), universal=4, stack=4,
                           **{k: sum(n[k] for n in nodes) for k in ("always_loaded_tokens", "mirror_index_tokens", "recall_tokens")}))
    from fact_schema import stable_fact_id
    holdings = {stable_fact_id(domain, name): dict(fact_id=stable_fact_id(domain, name),
                name=name, domain=domain, scope=scope, holders={'sample-'+h for h in held})
                for name, domain, scope, _, held in SHARED_FACTS}
    import sync_global as sg
    net['fact_holdings'], counts = sg._bounded_fact_holdings(holdings, 'sample-atlas-api')
    net['capture'] = dict(counts, basis='physical shared mirrors plus triggering store',
                          group_scope='trigger', unresolved_identities=0, read_failures=0,
                          read_failure_scope='captured native fact files')
    record = {
        "project": "atlas-api", "session": "example-09",
        "identity": {"domain_id": "work", "enrolled": True, "registry_state": "healthy", "cross_project_allowed": True, "conflicts": 0},
        "scope": {"git_range": "a10cafe..b20cafe", "git_commits": 3, "session_candidates": 2, "memories_reviewed": 24},
        "rigor": {"phase": "final", "applied": "SUBSTANTIAL", "prune_pressure": False},
        "preflight": {"at": "2026-09-05T14:29:00Z", "fails": [], "warns": []},
        "verification": {"confirmed": 5, "corrected": 1, "unverifiable": 1, "method": "subagents"},
        "entries": [
            {"action": "added", "name": "retry-backoff", "tier": "recall", "store": "auto-mem", "scope": "project-local", "reason": "Keep the retry rationale available when changing the queue worker.", "citation": "src/queue.py:42", "files": ["memory/retry-backoff.md"]},
            {"action": "corrected", "name": "test-command", "tier": "always-loaded", "store": "repo", "scope": "project-local", "reason": "The verification command now includes the contract suite.", "citation": "Makefile:18", "files": ["claude_md/CLAUDE.md"]},
            {"action": "skipped", "name": "cache-expiry-claim", "tier": "-", "store": "-", "scope": "project-local", "reason": "No source establishes the claimed expiration window; retain no fact.", "citation": "src/cache.py"}],
        "budget": {"index": {"before_tokens": 1056, "after_tokens": 984, "budget_tokens": 1500, "over": False, "before_lines": 32, "after_lines": 30, "cliff_pct": 16, "fat_hooks": 0},
                   "claude_md": {"before_tokens": 1860, "after_tokens": 1820, "budget_tokens": 4000, "over": False},
                   "global_claude_md": {"present": True, "tokens": 720, "budget_tokens": 4000, "over": False},
                   "claude_md_hierarchy": {"total_files": 2, "worst_path": "src/worker", "worst_path_tokens": 2380},
                   "recall_facts": {"before": 23, "after": 24}},
        "health": {"index_pointers_ok": True, "broken": [], "dangling_links": [], "slug_orphans": [], "schema_drift": {}},
        "audit": {"memory": {"created": 1, "modified": 1, "deleted": 0, "token_delta": 88},
                  "claude_md": {"created": 0, "modified": 1, "deleted": 0, "token_delta": -40},
                  "repo_doc": {"created": 0, "modified": 0, "deleted": 0, "token_delta": 0},
                  "operations": [{"path": "retry-backoff.md", "store": "memory", "op": "created", "token_delta": 160},
                                 {"path": "MEMORY.md", "store": "memory", "op": "modified", "token_delta": -72},
                                 {"path": "CLAUDE.md", "store": "claude_md", "op": "modified", "token_delta": -40}],
                  "conservation": {"possible_loss": False}, "window": "phase 0 → phase 5"},
        "cross_project": {"global_store_facts": 6, "pulled": [{"name": "release-checks", "scope": "stack-general"}], "promoted": [], "refreshed": 0, "held": 0, "gc_removed": 0},
        "usage": {"window": "2026-08-29..2026-09-05", "transcripts": 8, "dream_excluded": 24, "reads": 14, "facts_read": 6, "mentions": 9, "per_fact": [{"name": n, "reads": r} for n, r in [("source-provenance", 3), ("contract-versioning", 3), ("release-checks", 2), ("artifact-provenance", 2), ("queue-boundaries", 2), ("review-conventions", 2)]], "archive_reads": 0, "misses": []},
        "distill": {"sessions": 8, "commands": 96, "n_recurring": 3, "n_chains": 1, "window": "2026-08-06..2026-09-05", "secrets_omitted": 0, "proposed": [], "created": [],
                    "verdict": "nothing: the existing check-release skill already covers the repeated validation chain.",
                    "top": [{"t": "python3 scripts/check_release.py", "n": 12, "d": 5}, {"t": "python3 tests/contracts.py", "n": 8, "d": 4}, {"t": "mypy --config-file mypy.ini", "n": 6, "d": 3}],
                    "top_chains": [{"t": ["python3 tests/contracts.py", "python3 scripts/check_release.py"], "n": 5, "d": 3}], "used": [{"a": "check-release", "n": 4}]},
        "demotion": {"eligible": 0, "verdict": "none: all indexed facts retain a useful recall cue."},
        "workflow_proposals": {"verdict": "nothing: the fleet already has a release check command.", "n_candidates": 1, "n_fleet": 1, "n_blocked": 0,
                               "candidates": [{"candidate": "python3 scripts/check_release.py", "name": "release checks", "form": "command", "disposition": "declined", "reason": "Existing command covers it.", "evidence": {"nodes": ["atlas-api", "release-tools"], "n": 12, "d": 5}, "mechanical": {"distinctive": True, "fleet_recurrence": True, "day_spread": True}}], "decline_anchors": []},
        "dream": {"sleep": "*💤 Following the work back to its sources.*", "beats": ["*The stores and the last checkpoint establish the starting point.*", "*Approved shared facts arrive where they belong.*", "*The session offers candidates, each with a source to check.*", "*One assumption fails verification; it does not become memory.*", "*The proposal makes every change visible before it lands.*", "*The index is measured again, and the record keeps the evidence.*"], "wake": "*☀️ The next session has less to rediscover.*"},
        "network": net, "marker": {"commit": "b20cafe09", "timestamp": "2026-09-05T14:30:00Z"}}
    history = []
    token_history = [620, 740, 910, 1120, 1080, 1200, 1056, 984]
    line_history = [21, 23, 25, 29, 28, 33, 32, 30]
    additions = [
        ("request-tracing", "worker-lifecycle"),
        ("queue-boundaries", "request-validation"),
        ("cache-key-scope", "shutdown-order"),
        ("transaction-boundaries", "error-taxonomy"),
        ("test-isolation", "clock-injection"),
        ("job-idempotency", "queue-observability"),
        ("retry-classification", "worker-cancellation"),
        ("retry-backoff", "release-checks"),
    ]
    for i, tokens in enumerate(token_history):
        c = copy.deepcopy(record)
        c["marker"] = {"commit": "b20cafe%02d" % i, "timestamp": "2026-%sT14:30:00Z" % (["08-15", "08-18", "08-21", "08-24", "08-27", "08-30", "09-02", "09-05"][i])}
        if history:
            c["marker"].update(before_commit=history[-1]["marker"]["commit"],
                               before_timestamp=history[-1]["marker"]["timestamp"])
        c["scope"]["git_range"] = c["marker"].get("before_commit", "a10cafe00") + ".." + c["marker"]["commit"]
        c["session"] = "example-%02d" % i
        c["preflight"]["at"] = c["marker"]["timestamp"]
        before_tokens = token_history[i-1] if i else 540
        c["budget"]["index"].update(before_tokens=before_tokens, after_tokens=tokens,
                                    before_lines=line_history[i-1] if i else 20,
                                    after_lines=line_history[i],
                                    before_bytes=before_tokens*4, after_bytes=tokens*4,
                                    cliff_pct=round(100*max(line_history[i]/200, tokens*4/25600)))
        c["budget"]["recall_facts"] = {"before": 8 + 2*i, "after": 10 + 2*i}
        c["scope"]["memories_reviewed"] = c["budget"]["recall_facts"]["before"]
        claude_tokens = 1820 + (7-i)*40
        c["budget"]["claude_md"].update(before_tokens=claude_tokens+40, after_tokens=claude_tokens)
        c["budget"]["claude_md_hierarchy"].update(
            worst_path_tokens=claude_tokens+560,
            files=[{"path": "CLAUDE.md", "tokens": claude_tokens},
                   {"path": "src/worker/CLAUDE.md", "tokens": 560}])
        local_name, second_name = additions[i]
        added = c["entries"][0]
        added.update(name=local_name, files=["memory/"+local_name+".md"])
        if i < len(token_history)-1:
            added.update(reason="Keep a verified implementation constraint available for later changes.", citation="src/worker.py:42")
            c["cross_project"]["pulled"] = []
        second_entry = copy.deepcopy(added)
        second_entry.update(name=second_name, files=["memory/"+second_name+".md"],
                            reason="Retain the verified companion lesson for this cycle.")
        if i == len(token_history)-1:
            second_entry.update(action="reconciled", scope="stack-general",
                                reason="Absorb the reviewed release-check lesson from the work domain.",
                                citation="shared fact: work/release-checks")
        c["entries"].insert(1, second_entry)
        index_delta = tokens-before_tokens
        c["audit"]["memory"].update(created=2, token_delta=320+index_delta)
        c["audit"]["operations"] = [
            {"path": name+".md", "store": "memory", "op": "created", "token_delta": 160}
            for name in (local_name, second_name)] + [
            {"path": "MEMORY.md", "store": "memory", "op": "modified", "token_delta": index_delta},
            {"path": "CLAUDE.md", "store": "claude_md", "op": "modified", "token_delta": -40}]
        c["usage"]["window"] = c["marker"].get("before_timestamp", "2026-08-12")[:10] + ".." + c["marker"]["timestamp"][:10]
        c["distill"]["window"] = "2026-08-01.." + c["marker"]["timestamp"][:10]
        c["network"]["nodes"][0]["always_loaded_tokens"] = tokens
        c["network"]["nodes"][0]["facts"] = 10 + 2*i
        c["network"]["nodes"][0]["recall_tokens"] = (10 + 2*i)*160
        for key in ("always_loaded_tokens", "mirror_index_tokens", "recall_tokens"):
            c["network"]["totals"][key] = sum(n[key] for n in c["network"]["nodes"])
        history.append(c)
    record = history[-1]
    diffs = {ms.diff_key(record["marker"], record["session"]): {
        "memory/retry-backoff.md": {"op": "created", "lines": [{"t": "+", "s": "Retry delays include jitter to avoid synchronized workers."}], "more": 0},
        "memory/release-checks.md": {"op": "created", "lines": [{"t": "+", "s": "Run the reviewed release checks before publishing the artifact."}], "more": 0},
        "memory/MEMORY.md": {"op": "modified", "lines": [{"t": "-", "s": "Verbose context repeated from individual fact files."}, {"t": "+", "s": "Retry changes: see [[retry-backoff]]."}], "more": 0},
        "claude_md/CLAUDE.md": {"op": "modified", "lines": [{"t": "-", "s": "Run the unit tests."}, {"t": "+", "s": "Run the unit tests and python3 tests/contracts.py."}], "more": 0}}}
    return record, history, diffs


def validate_sample(record, history, diffs):
    """Check fixture accounting and the current engine's actual payload shape."""
    from unittest.mock import patch
    import sync_global as sg

    assert record == history[-1], "Selected record must be the latest history row"
    for i, cycle in enumerate(history):
        assert not ms.validate_cycle_record(cycle), "Fixture violates the cycle contract"
        budget, audit, net = cycle["budget"], cycle["audit"], cycle["network"]
        for store in ("memory", "claude_md", "repo_doc"):
            operations = [op for op in audit["operations"] if op["store"] == store]
            for action in ("created", "modified", "deleted"):
                assert audit[store][action] == sum(op["op"] == action for op in operations)
            assert audit[store]["token_delta"] == sum(op["token_delta"] for op in operations)
        index_op = next(op for op in audit["operations"]
                        if op["store"] == "memory" and op["path"] == "MEMORY.md")
        assert index_op["token_delta"] == budget["index"]["after_tokens"]-budget["index"]["before_tokens"]
        assert budget["claude_md"]["after_tokens"]-budget["claude_md"]["before_tokens"] == audit["claude_md"]["token_delta"]
        assert budget["recall_facts"]["after"]-budget["recall_facts"]["before"] == audit["memory"]["created"]-audit["memory"]["deleted"]
        current = next(n for n in net["nodes"] if n["trigger"])
        assert current["facts"] == budget["recall_facts"]["after"]
        assert current["always_loaded_tokens"] == budget["index"]["after_tokens"]
        for key in ("always_loaded_tokens", "mirror_index_tokens", "recall_tokens"):
            assert net["totals"][key] == sum(n[key] for n in net["nodes"])
        if i:
            previous = history[i-1]["budget"]
            for key in ("index", "claude_md"):
                assert budget[key]["before_tokens"] == previous[key]["after_tokens"]
            assert budget["recall_facts"]["before"] == previous["recall_facts"]["after"]

    net = record["network"]
    stack_by = {n["node"]: {name for name, _, scope, _, held in SHARED_FACTS
                             if scope == "stack-general" and n["node"] in held}
                for n in net["nodes"]}
    edges = lambda rows: sorted((e["a"], e["b"], e["n"]) for e in rows)
    assert edges(net["stack_edges"]) == edges(sg._pairwise_stack_edges(stack_by))
    for node in net["nodes"]:
        assert node["stack"] == len(stack_by[node["node"]])
        assert node["universal"] == sum(scope == "user-global" and node["node"] in held
                                        for _, _, scope, _, held in SHARED_FACTS)
        assert node["shared"] == node["stack"]+node["universal"]
    for scope, key in (("user-global", "universal"), ("stack-general", "stack")):
        assert net["totals"][key] == sum(s == scope and bool(held) for _, _, s, _, held in SHARED_FACTS)
    canonical_rows = [(name, {"domain": domain, "scope": scope,
                             "recipients": json.dumps(recipients)}, "", Path("/synthetic")/(name+".md"))
                      for name, domain, scope, recipients, _ in SHARED_FACTS]
    holder_counts = {(domain, name): len(held) for name, domain, _, _, held in SHARED_FACTS}
    group_rows = {g["group"]: {"home_domain": g["home_domain"]} for g in net["group_links"]}
    with patch.object(sg, "_all_domain_records", return_value=canonical_rows), patch.object(
            sg, "_registry_holder_count", side_effect=lambda _, name, domain: holder_counts[(domain, name)]):
        emitted = sg._fleet_layers(Path("/synthetic"), None, net, stack_by,
                                   set(group_rows), [(g, r["home_domain"]) for g, r in group_rows.items()],
                                   group_rows, fleet_full=True)
    for key in ("domains", "universal_facts", "group_links", "stack_edge_facts"):
        normalize = lambda rows: sorted(json.dumps(row, sort_keys=True) for row in rows)
        assert normalize(net[key]) == normalize(emitted[key]), "Fixture differs from emitter: " + key
    captured = diffs[ms.diff_key(record["marker"], record["session"])]
    assert set(captured) == {op["store"]+"/"+op["path"] for op in record["audit"]["operations"]}
    return True


def write_preview(out):
    out.mkdir(parents=True, exist_ok=True)
    record, history, diffs = sample()
    validate_sample(record, history, diffs)
    html = rh.build_html(record, history, "2026-09-05T14:35:00Z", diffs, record["identity"])
    # Label the artifact itself. The production template never claims data is synthetic.
    html = html.replace('<body>', '<body><div class="sample-notice">Illustrative sample · fictional projects and cycle data · not a live consolidation</div>')
    (out / "index.html").write_text(html, encoding="utf-8")
    (out / "sample.json").write_text(json.dumps({"record": record, "history": history, "diffs": diffs}, indent=2)+"\n", encoding="utf-8")
    return out / "index.html"


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    print(write_preview(p.parse_args().out))
