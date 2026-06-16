export const meta = {
  name: 'devsecops-preflight',
  description: 'Deep multi-agent white-hat DevSecOps security review + gate for the consolidate-memory plugin. Recon → parallel pentesters per attack surface (loop-until-dry) → 3-vote adversarial verification → severity-ranked gate. Returns PASS only when no confirmed High/Critical remains.',
  phases: [
    { title: 'Recon', detail: 'orient on the attack surface' },
    { title: 'Pentest', detail: 'parallel white-hat agents per surface; loop until no new findings' },
    { title: 'Verify', detail: '3 independent adversarial verifiers per finding' },
    { title: 'Synthesize', detail: 'dedup, severity-rank, compute the go/no-go gate' },
  ],
}

// ── scope ───────────────────────────────────────────────────────────────────
// Standalone + reusable: defaults target this repo's plugin; override via args.
const PLUGIN = (args && args.plugin) || 'plugins/consolidate-memory'
const MAX_ROUNDS = (args && args.maxRounds) || 3   // loop-until-dry ceiling (deep)
const DRY_STREAK = 2                                // consecutive empty rounds → stop
// Optional surface filter (args.only = ['secrets','fs',…]) — e.g. to re-gate just the
// surfaces touched by a remediation. Unset ⇒ all surfaces (full deep gate). Accept args
// as an object OR a JSON string (the runtime may deliver either).
let _args = args
if (typeof _args === 'string') { try { _args = JSON.parse(_args) } catch { _args = {} } }
const ONLY = (_args && _args.only) || null

// The attack surfaces. One white-hat agent owns each, every round.
const SURFACES = [
  { key: 'injection', title: 'Command/script injection & subprocess safety',
    files: [`${PLUGIN}/scripts/memory_status.py`],
    focus: 'subprocess/git argv construction, any shell=True/os.system/eval/exec, argument injection (e.g. a tampered .consolidation-state.json commit reaching git as an option), unsanitized values flowing into a process call' },
  { key: 'fs', title: 'Filesystem safety & destructive ops',
    files: [`${PLUGIN}/scripts/sync_global.py`, `${PLUGIN}/scripts/render_dashboard.py`],
    focus: 'the --gc deletion path (could it delete a project-authored / non-global_ref file, or outside the store?), path traversal via fact names, writes outside the intended store, unlink(missing_ok) misuse, symlink/cache-copy abuse' },
  { key: 'secrets', title: 'Secrets / PII leakage',
    files: [`${PLUGIN}/scripts/extract_signals.py`],
    focus: 'can a credential evade the _SECRET firewall and land in a persisted memory file? what exactly is stored vs dropped? token/base64/PEM/JWT shapes the regex misses, partial-scrub leaks, secrets in error tool-results or git data' },
  { key: 'supplychain', title: 'Supply-chain & plugin manifest',
    files: [`${PLUGIN}/.claude-plugin/plugin.json`, '.claude-plugin/marketplace.json', 'install.sh', '.gitignore'],
    focus: 'manifest correctness, source pinning, ${CLAUDE_PLUGIN_ROOT} misuse, what files get bundled into the published plugin (does any personal data / memory / secret ship?), install.sh safety (rm/symlink/backups), malicious-marketplace threat model' },
  { key: 'dos', title: 'Input robustness / denial-of-service',
    files: [`${PLUGIN}/scripts/extract_signals.py`, `${PLUGIN}/scripts/memory_status.py`],
    focus: 'ReDoS in any regex (nested/overlapping quantifiers), unbounded reads of huge/malformed JSONL, a single enormous line, infinite loops, memory/CPU exhaustion, crash on malformed frontmatter' },
  { key: 'logic', title: 'Cross-project replication & provenance abuse',
    files: [`${PLUGIN}/scripts/sync_global.py`],
    focus: 'can a crafted global fact poison many projects? mirror/global_ref spoofing, provenance (projects:) tampering, stack-keyword over-match causing unwanted spread, index-pointer injection, budget/ceiling bypass' },
  { key: 'trust', title: 'Trust boundary / prompt-injection via memory',
    files: [`${PLUGIN}/skills/consolidate-memory/SKILL.md`, `${PLUGIN}/skills/consolidate-memory/references/harness-map.md`],
    focus: 'a recalled memory / global fact arrives in a future session inside a system-reminder — can malicious fact content hijack the consolidation (instruct deletion, exfiltration, writing secrets)? does SKILL.md treat memory content as data or as instructions? over-broad write scope' },
]

// ── schemas (validated at the tool boundary; agents must conform) ─────────────
const SEVERITIES = ['Critical', 'High', 'Medium', 'Low', 'Info']
const FINDINGS_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          title: { type: 'string' },
          severity: { type: 'string', enum: SEVERITIES },
          file: { type: 'string' },
          line: { type: 'string', description: 'line number or range, or "" if not line-specific' },
          rationale: { type: 'string', description: 'why this is a real security issue' },
          exploit: { type: 'string', description: 'concrete attacker steps / preconditions; "" if theoretical' },
          recommendation: { type: 'string' },
        },
        required: ['title', 'severity', 'file', 'line', 'rationale', 'exploit', 'recommendation'],
      },
    },
  },
  required: ['findings'],
}
const VERDICT_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    real: { type: 'boolean', description: 'true only if a genuinely exploitable/relevant security issue under this lens' },
    severity: { type: 'string', enum: SEVERITIES },
    reason: { type: 'string' },
  },
  required: ['real', 'severity', 'reason'],
}

// ── helpers ──────────────────────────────────────────────────────────────────
const keyOf = (f) => `${(f.file || '').trim()}::${(f.title || '').trim().toLowerCase()}`
const sevRank = (s) => Math.max(0, SEVERITIES.indexOf(s))  // Info=4..Critical=0 → invert below
const rank = (s) => SEVERITIES.length - 1 - sevRank(s)     // Critical=4 … Info=0

const pentestPrompt = (s, recon, known, round) => `
You are a senior WHITE-HAT penetration tester on an authorized pre-release security
review of a Claude Code plugin (consolidate-memory). This is a defensive audit of our
OWN code before publishing it. Your surface: **${s.title}**.

Read these files in full and trace the data flow:
${s.files.map((f) => `  - ${f}`).join('\n')}
Read other files in ${PLUGIN}/ if needed to follow a flow.

Focus specifically on: ${s.focus}

Recon orientation:
${recon}

Already-reported findings (do NOT repeat these; hunt for NEW, distinct issues):
${known}

Round ${round}. Report ONLY real, defensible security findings — issues an attacker or
a malicious input could actually leverage, or that violate a stated security property
(stdlib-only, no exec, secrets firewall, local-only, no data exfiltration, GC never
touches project-authored facts). For each: cite file + line, give a concrete exploit
or precondition, assign a severity, and a fix. Be precise; do NOT pad with style nits
or speculative "could theoretically" issues — those waste the verification budget.
If you find nothing new on this surface, return an empty findings array.`

const verifyPrompt = (f, lens) => `
You are an independent adversarial verifier on a white-hat security review. A peer
reported this finding about the consolidate-memory plugin. Your job is to try to
REFUTE it through the lens of **${lens}**.

Finding: "${f.title}" [claimed ${f.severity}]
File: ${f.file}:${f.line || '?'}
Rationale: ${f.rationale}
Exploit/precondition: ${f.exploit || '(none given)'}
Recommended fix: ${f.recommendation}

Read the cited file(s) yourself and judge under the ${lens} lens:
- exploitability: is there a realistic path to trigger it, given the actual threat
  model (attacker needs local FS write? a malicious marketplace? a crafted transcript?)
- impact: if triggered, what is the real harm? does it breach a stated property?
- false-positive: does the code already mitigate it, or is the claim mistaken?

Default to real=false if the issue is not genuinely exploitable or is already
mitigated. Set real=true ONLY if it survives scrutiny under your lens. Give the
severity you'd assign and a one-line reason.`

// ── Phase: Recon ─────────────────────────────────────────────────────────────
phase('Recon')
const recon = await agent(
  `You are the security lead orienting a pre-release audit of the Claude Code plugin at
   ${PLUGIN} (plus repo-root .claude-plugin/marketplace.json and install.sh). Read the
   manifests and skim each script. In 8-12 lines, summarize: entry points, what runs
   external processes, what reads/writes the filesystem, what crosses a trust boundary
   (transcripts, recalled memory, cross-project replication), and what ships in the
   published plugin. This orients the per-surface pentesters; be concrete (file names).`,
  { label: 'recon', phase: 'Recon' },
)

// ── Phase: Pentest (parallel per surface, loop-until-dry) ─────────────────────
phase('Pentest')
const ACTIVE = ONLY ? SURFACES.filter((s) => ONLY.includes(s.key)) : SURFACES
log(`Pentesting ${ACTIVE.length}/${SURFACES.length} surface(s): ${ACTIVE.map((s) => s.key).join(', ')}`)
const seen = new Set()
const fresh = []
let dry = 0, round = 0
while (dry < DRY_STREAK && round < MAX_ROUNDS) {
  round++
  const known = [...seen].join('\n') || '(none yet)'
  const batches = await parallel(
    ACTIVE.map((s) => () =>
      agent(pentestPrompt(s, recon, known, round),
        { label: `pentest:${s.key}:r${round}`, phase: 'Pentest', schema: FINDINGS_SCHEMA })
        .then((r) => (r && r.findings ? r.findings.map((f) => ({ ...f, surface: s.key })) : [])),
    ),
  )
  const found = batches.filter(Boolean).flat()
  const newOnes = found.filter((f) => {
    const k = keyOf(f)
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })
  if (newOnes.length === 0) { dry++ } else { dry = 0; fresh.push(...newOnes) }
  log(`Pentest round ${round}: ${found.length} reported, ${newOnes.length} new (total ${fresh.length}); dry streak ${dry}/${DRY_STREAK}`)
}
log(`Pentest done after ${round} round(s): ${fresh.length} distinct candidate findings`)

// ── Phase: Verify (3 independent adversarial votes per finding) ───────────────
// HARDENED against transient API errors that silently dropped votes in an earlier run:
// (1) each vote RETRIES (up to 3 attempts) on a null/throttled result — this recovers
// individual failed votes (it does not reduce the initial concurrent burst); (2) the
// verdict FAILS CLOSED — a finding we can't get ≥2 successful votes on is escalated as
// 'unverified', never silently dropped (a security gate must not clear what it couldn't
// check). A clean PASS therefore also requires zero unverified High/Critical.
phase('Verify')
const LENSES = ['exploitability', 'impact', 'false-positive']
const VOTE_ATTEMPTS = 3

const voteWithRetry = async (f, lens) => {
  for (let attempt = 1; attempt <= VOTE_ATTEMPTS; attempt++) {
    const v = await agent(verifyPrompt(f, lens),
      { label: `verify:${f.surface}:${lens}${attempt > 1 ? `:retry${attempt}` : ''}`,
        phase: 'Verify', schema: VERDICT_SCHEMA })
    if (v) return v   // got a vote
  }
  return null         // exhausted retries → missing vote (handled fail-closed below)
}

const verified = await parallel(
  fresh.map((f) => () =>
    parallel(LENSES.map((lens) => () => voteWithRetry(f, lens)))
      .then((votes) => {
        const v = votes.filter(Boolean)
        const yes = v.filter((x) => x.real)
        let state, sev
        if (v.length < 2) {
          state = 'unverified'                                   // fail closed: escalate
          sev = f.severity                                       // trust finder severity
        } else if (yes.length >= 2) {
          state = 'confirmed'
          sev = yes.map((x) => x.severity).sort((a, b) => rank(b) - rank(a))[0]
        } else {
          state = 'rejected'
          sev = f.severity
        }
        return { ...f, state, confirmedSeverity: sev, voteCount: v.length, votes: v }
      }),
  ),
)

// ── Phase: Synthesize + gate ─────────────────────────────────────────────────
phase('Synthesize')
const byState = (s) => verified.filter(Boolean).filter((x) => x.state === s)
  .sort((a, b) => rank(b.confirmedSeverity) - rank(a.confirmedSeverity))
const confirmed = byState('confirmed')
const unverified = byState('unverified')   // votes errored out — escalated, not dropped
const rejected = byState('rejected')
const bySeverity = SEVERITIES.reduce((acc, s) => {
  acc[s] = confirmed.filter((f) => f.confirmedSeverity === s).length
  return acc
}, {})
// Fail-closed gate: block on confirmed High/Critical OR any High/Critical we couldn't verify.
const blocking = [...confirmed, ...unverified].filter((f) => rank(f.confirmedSeverity) >= rank('High'))
const gate = blocking.length === 0 ? 'PASS' : 'BLOCK'
log(`GATE: ${gate} — ${blocking.length} blocking, ${confirmed.length} confirmed, ${unverified.length} unverified(escalated), ${rejected.length} rejected`)

return {
  gate,
  blocking_count: blocking.length,
  rounds: round,
  counts: { candidates: fresh.length, confirmed: confirmed.length, unverified: unverified.length, rejected: rejected.length },
  bySeverity,
  confirmed,
  unverified: unverified.map((u) => ({ title: u.title, surface: u.surface, file: u.file, severity: u.confirmedSeverity, voteCount: u.voteCount })),
  rejected: rejected.map((r) => ({ title: r.title, surface: r.surface, file: r.file, reason: (r.votes[0] || {}).reason || '' })),
}
