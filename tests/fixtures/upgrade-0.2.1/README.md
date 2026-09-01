# Vendored 0.2.1 upgrade fixture (synthetic)

Synthetic, not copied from anyone's personal memory. Used by `tests/smoke.py`
to pin 0.3.0 migrate against a v0.2.1-shaped layout:

- `legacy/` — untagged facts as they sat in `~/.claude/memory`
- `unknown-pool/` — the 0.2.1 unenrolled sharing pool (`domains/unknown/facts`)
- `personal/` — a dest domain that already has a canonical (`already.md`)

`dup.md` exists in both legacy and unknown-pool (same stem, different bodies)
so `--keep legacy` must clear collisions. `plain.md` is legacy-only.
`already.md` is dest-exists. Tests copy these into a hermetic HOME; they never
touch a live fleet.
