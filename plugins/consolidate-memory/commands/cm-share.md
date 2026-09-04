---
name: cm-share
description: Author ONE shared cross-project fact from a single claim sentence — verified against the live repo(s), shown to the user, written only on their confirmation.
---

A single fact into the shared layer, with the dream's own verification discipline
(see `docs/cm-commands-onboarding.spec.md` §2.2). This is AUTHORING — the claim
must survive verification before it may exist. NO VERIFY, NO WRITE.

1. **Read the single sources first (never paraphrase them):**
   `${CLAUDE_PLUGIN_ROOT}/skills/consolidate-memory/references/harness-map.md` §
   "verification recipes", and the Phase-2 scope cascade in
   `${CLAUDE_PLUGIN_ROOT}/skills/consolidate-memory/SKILL.md`.

2. **Verify.** Check the claim against THIS repo's live files/git with the
   recipes; for a `user-global`/`stack-general` scope, name at least one other
   existing project where it holds (G2.3). A claim that fails verification is
   reported and dropped, never written.

3. **Scope by content** (the cascade, never vibes). A `project-local` claim does
   not belong here — point at `cm local upsert` instead.

4. **Dedup.** Grep the domain canonicals for the same content; a duplicate
   reconciles onto the existing fact, never a second copy.

5. **Draft + show.** Draft the fact (frontmatter + body) and SHOW it — including
   the before/after diff when the stem already exists (a replace freezes other
   projects' mirrors at their next pull). The user's confirmation is the gate.

6. **Write** through the sole canonical writer — one journaled transact
   (canonical + catalog + registry + this project's mirror + pointer):

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py canonical upsert <stem> --file <draft-file> --origin --project .
   ```

Enrolled projects only (the writer refuses otherwise). A secret-shaped draft is
refused by the firewall — rephrase, never weaken it. A `stack-general` fact's
`stacks:` must be detectable; the writer's own error names the undetectable set.
