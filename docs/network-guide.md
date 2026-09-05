# A memory network you can reason about

This walkthrough uses fictional sibling repositories under `$HOME/src/`. It describes
local projects sharing one plugin control plane. It does not connect computers over
the internet. Use `/cm-doctor` or `./cm doctor <project-path>` to resolve actual stores;
never construct native memory paths by hand.

![Three trust domains, two recipient groups, and a local-only project](assets/network-topology.svg)

## The example

| Domain | Projects | Role |
| --- | --- | --- |
| `work` | `atlas-api`, `atlas-web`, `team-docs` | Product backend, frontend, documentation |
| `research` | `eval-lab`, `model-notes` | Experiments and their supporting notes |
| `tools` | `release-tools`, `dotfiles` | Release automation and developer configuration |
| Unenrolled | `scratch` | Isolated experiments; local consolidation only |

Two groups are created in the `work` home domain:

- `api-contract`: `atlas-api` and `atlas-web`. A same-domain recipient restriction.
- `release-kit`: `atlas-api`, `eval-lab`, and `release-tools`. A specific cross-domain grant.

An ordinary `user-global` fact in `work` is **domain-global**, not installation-global.
A `stack-general` fact also requires a matching detected stack. If a fact declares
`recipients: [release-kit]`, only members of that group can receive it, still subject
to relevance, sensitivity, identity, and budget checks. This excludes other `work`
projects as well. Multiple recipients name a union of groups, not an intersection.

## Marketplace workflow

Use `/cm-domain` in each repo, specifying its intended domain. Use `/cm-group` to
create the two groups and add the projects listed above. The commands present plans
and request the grants they need. `/cm-connect` is the simpler two-repo wizard: it
uses `personal` for unenrolled projects, never automatically moves a project already
enrolled elsewhere, and pulls in both projects at the end.

In `atlas-api`, `/cm-share "<one claim>"` verifies and drafts a fact. The command
classifies scope from the claim's content, checks another applicable project, and
asks whether to address a group or the whole domain. The confirmation includes the
narrowed audience. A project-local fact belongs in local memory instead.

The following is an **illustrative frontmatter fragment**, not a complete fact to
paste into the writer. A shared Python release-check lesson might include:

```yaml
scope: stack-general
stacks: [python]
domain: work
recipients: [release-kit]
```

`atlas-api`, `eval-lab`, and `release-tools` must actually use detectable Python
for this example to reach all three. Group membership alone does not satisfy the
stack check. The command drafts the remaining required metadata and verified body.

## Exact maintainer CLI walkthrough

Run these commands from the **consolidate-memory checkout**. `./cm` is not a
marketplace slash command. Paths below assume the seven example repos already exist;
substitute your own. No part of this documentation creates grants on your machine.

### 1. Survey and plan

```bash
./cm doctor "$HOME/src/atlas-api"
./cm project enroll "$HOME/src/atlas-api" --domain work
./cm project enroll "$HOME/src/atlas-web" --domain work
./cm project enroll "$HOME/src/team-docs" --domain work
./cm project enroll "$HOME/src/eval-lab" --domain research
./cm project enroll "$HOME/src/model-notes" --domain research
./cm project enroll "$HOME/src/release-tools" --domain tools
./cm project enroll "$HOME/src/dotfiles" --domain tools
```

These enrollment invocations show plans. Read any mirror revocation/quarantine
forecast before applying. A repo already in a different domain needs `move-domain`,
not another `enroll`.

### 2. Apply the reviewed enrollment plans

```bash
./cm project enroll "$HOME/src/atlas-api" --domain work --apply --confirm enroll-work
./cm project enroll "$HOME/src/atlas-web" --domain work --apply --confirm enroll-work
./cm project enroll "$HOME/src/team-docs" --domain work --apply --confirm enroll-work
./cm project enroll "$HOME/src/eval-lab" --domain research --apply --confirm enroll-research
./cm project enroll "$HOME/src/model-notes" --domain research --apply --confirm enroll-research
./cm project enroll "$HOME/src/release-tools" --domain tools --apply --confirm enroll-tools
./cm project enroll "$HOME/src/dotfiles" --domain tools --apply --confirm enroll-tools
```

The path is positional and **comes before flags**. Leave `scratch` unenrolled.
Enrollment grants access; it does not guarantee that any fact has been pulled.

### 3. Create the home-domain groups

```bash
./cm group create release-kit --domain work
./cm group create api-contract --domain work
# After reviewing those plans:
./cm group create release-kit --domain work --apply --confirm create-group-release-kit
./cm group create api-contract --domain work --apply --confirm create-group-api-contract
```

Only a fact from `work` can target these `work`-home groups. A grant does not give
`eval-lab` permission to author `research` facts into a `work` group; create a
research-home group for that direction if needed.

### 4. Grant each recipient

```bash
./cm group add release-kit "$HOME/src/atlas-api"
./cm group add release-kit "$HOME/src/eval-lab"
./cm group add release-kit "$HOME/src/release-tools"
./cm group add api-contract "$HOME/src/atlas-api"
./cm group add api-contract "$HOME/src/atlas-web"
# After reviewing the membership plans:
./cm group add release-kit "$HOME/src/atlas-api" --apply --confirm add-group-release-kit
./cm group add release-kit "$HOME/src/eval-lab" --apply --confirm add-group-release-kit
./cm group add release-kit "$HOME/src/release-tools" --apply --confirm add-group-release-kit
./cm group add api-contract "$HOME/src/atlas-api" --apply --confirm add-group-api-contract
./cm group add api-contract "$HOME/src/atlas-web" --apply --confirm add-group-api-contract
./cm group show release-kit
./cm group show api-contract
```

### 5. Author, absorb, and inspect

Author the lesson through `/cm-share` in `atlas-api`. For a maintainer with an
already verified, reviewed draft, the equivalent authoring entry point is:

```bash
./cm canonical upsert release-checks --file /tmp/release-checks.md --origin --project "$HOME/src/atlas-api"
```

The draft supplies `domain`, `scope`, `stacks` when appropriate, and `recipients`.
The writer checks the metadata and publishes the origin mirror and recall pointer.
Do not invent a draft just to make this command succeed.

Recipients absorb on their own next dream or `/cm-sync`. The maintainer pull and
inspection equivalents are:

```bash
./cm pull "$HOME/src/eval-lab"
./cm pull "$HOME/src/release-tools"
./cm tokens "$HOME/src/atlas-api" --fleet=full --json
./cm tokens "$HOME/src/atlas-api"
```

`--fleet=full` captures all domains/groups available to the fleet view; it is a
read-only observability mode, not a sharing grant. `/cm-network` includes costs and
utility in its normal workflow. To verify membership independently of whether any
facts have arrived, use `group show` and `project show`.

## Read the graph without overclaiming

| Surface | Evidence it supplies |
| --- | --- |
| Domain lanes | The captured projects' trust domains |
| Solid connections | Pairwise intersections of held `stack-general` facts |
| Selected group / dashed routes | Operator-granted membership; not proof of delivery |
| Baseline chips | `user-global` facts and the number of projects recorded as holding each |
| Costs | Approximate token costs for indexes, mirrored recall cues, and fact bodies |
| Full inventory | Every embedded node and edge, including those beyond the 16-node diagram |

The snapshot can omit unenrolled repos, projects with no shared holdings, and
registry-only nodes that have no local store to scan. It is not a complete inventory
of directories on disk. The emitter also caps baseline/group/name detail; “all
captured” means the saved payload, not uncapped live state.

A `work` baseline held by **3 of 7** fleet projects is expected in this example. It
is not automatically a four-project backlog. The other domains are separate.
Similarly, zero recorded organic reads means **no evidence of use**, not proof that
a memory is useless.

## If a fact does not arrive

1. Check the recipient's resolved domain and registry health with `doctor`.
2. Inspect `group show` if the fact has `recipients:`. The group must exist in the
   fact's home domain and include the recipient.
3. Check the fact's scope and the recipient's detectable stack. Groups do not bypass relevance.
4. Run `/cm-sync` there and read its pulled/refreshed/held counts. Budget holds require
   reducing the index; enrollment does not override them.
5. Inspect `./cm conflicts <project-path>` for edited mirrors and stale group identities.

## Migration and revocation

**Legacy store:** migration requires an **enrolled maintenance project** as its
caller. Populate the destination domains before enrolling the remaining recipients:
first enrollment revokes managed mirrors that the destination does not admit.
For an initial migration, use a separate maintenance repo with no managed mirrors,
or review the revocation forecast carefully for an existing caller. The example
below assumes that maintenance repo already exists.

```bash
CM_MIGRATION_PROJECT="$HOME/src/memory-admin"
./cm doctor "$CM_MIGRATION_PROJECT"
./cm project enroll "$CM_MIGRATION_PROJECT" --domain work
# If not already enrolled, apply the reviewed maintenance-project grant:
./cm project enroll "$CM_MIGRATION_PROJECT" --domain work --apply --confirm enroll-work
./cm migrate "$CM_MIGRATION_PROJECT" --plan
```

Inventory does not assign facts automatically. Review **every** row, resolve any
duplicate-source collision, then assign it to a domain or explicitly exclude it.
The stems below are examples; replace them with stems from your inventory.
Planning, assignments, exclusions, and collision decisions save a migration plan;
they do not yet copy canonical facts.

```bash
./cm migrate "$CM_MIGRATION_PROJECT" --assign review-conventions --domain work
./cm migrate "$CM_MIGRATION_PROJECT" --assign evaluation-provenance --domain research
./cm migrate "$CM_MIGRATION_PROJECT" --exclude retired-lesson
# Only when an inventory row reports a collision; choose the reviewed source:
# ./cm migrate "$CM_MIGRATION_PROJECT" --resolve-collision review-conventions --keep legacy
./cm migrate "$CM_MIGRATION_PROJECT" --validate
./cm migrate "$CM_MIGRATION_PROJECT" --plan
# After reviewing the complete, resolved assignment plan:
./cm migrate "$CM_MIGRATION_PROJECT" --apply --confirm migrate-apply
./cm migrate "$CM_MIGRATION_PROJECT" --status
```

An existing destination requires an explicit `--on-existing` decision
(`keep-existing`, `replace-with-migrated`, or `exclude`); inspect the destination
before choosing. Check the migrated facts and their destinations before closing
dual-read mode. **Rollback is available only before finalization.** Choose the
appropriate branch:

```bash
# If verification fails, roll back the applied migration:
# ./cm migrate "$CM_MIGRATION_PROJECT" --rollback --confirm migrate-rollback
# If verification succeeds, finalize; this removes the rollback state:
./cm migrate "$CM_MIGRATION_PROJECT" --finalize
```

Then enroll and sync the intended recipients using the earlier steps. Each receives
only facts admitted by its domain, group membership, and relevance checks.

Use `/cm-data` for scoped cleanup. Native memory includes data this plugin does not
own; deleting the entire directory is not an uninstall procedure.

**Removing a group member** withdraws its managed group mirrors: clean mirrors are
deleted, edited ones quarantined. Plan first:

```bash
./cm group remove release-kit "$HOME/src/eval-lab"
# After reviewing the withdrawal:
./cm group remove release-kit "$HOME/src/eval-lab" --apply --confirm remove-group-release-kit
```

A populated group cannot be deleted; remove its named members first. A recreated
group name gets a fresh identity, so older fact recipients are withheld until
explicitly reconfirmed with `--repoint`. Group targeting is not silently retargeted.
`forget` acknowledgments are lazy: offline projects retain their copy until they pull
or run GC.

Implementation references: [command workflows](../plugins/consolidate-memory/commands),
[delivery policy](../plugins/consolidate-memory/scripts/domain_policy.py),
[stack relevance and topology](../plugins/consolidate-memory/scripts/sync_global.py),
[group lifecycle](../plugins/consolidate-memory/scripts/cm_ops.py), and
[security model](../SECURITY.md).
