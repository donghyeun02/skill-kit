---
description: Continuous adversarial hardening — red team attacks, blue team fixes on a branch, scored each cycle so you can watch the service get stronger over time.
argument-hint: "[path | . | blank=whole repo]  [--dimension security|perf|a11y]  [--target 90]  [--branch <name>]"
---

# Hardening Arena

**Input**: $ARGUMENTS

A scored, adversarial improvement loop. Each **cycle**: 🔴 the red team attacks one quality
dimension with extreme scenarios, 🔵 the blue team writes a proposal and applies fixes **on a
dedicated branch**, then the dimension is **re-scored** so the improvement is measurable. Run it
repeatedly and the scoreboard shows the service getting harder over time.

`/redteam` is the per-cycle detection+fix engine; `/harden` wraps it with scoring, a written
proposal, a scoreboard, and branch safety.

> Current build: **one dimension per run, one cycle per invocation (manual), auto-fix on a
> dedicated branch + written proposal, no push/PR.** Automation (`/loop`, `/schedule`) and extra
> dimensions can be layered on later without changing this core.

---

## Arguments

- **Scope** (first non-flag token): a path, `.`, or blank = whole repo.
- **`--dimension`** — `security` (default) · `perf` · `a11y`. One per run.
- **`--target`** — target score 0–100 (default `90`; for `a11y`, AA conformance = the required
  target, AAA = stretch). Used only to report distance-to-goal; a manual run is always one cycle.
- **`--branch`** — work branch (default `hardening/<dimension>`).

---

## Step 0 — Branch safety (do this first, always)

1. Confirm a git repo. If not, stop and tell the user (offer `git init`).
2. **Never work on `main`/`master`.** Checkout (create if missing) the work branch
   `hardening/<dimension>`. If the working tree has unrelated uncommitted changes, stop and ask
   — do not mix them into a hardening cycle.
3. This command **never pushes and never opens a PR.** All output stays on the local branch for
   the user to review.

---

## Step 1 — Baseline score (S₀)

Run the dimension's **scorer** (see Scoring rubrics) against the current code on the branch.
Record `S₀` and the open-finding breakdown `{critical, high, medium, low}`.

If a prior scoreboard exists (`docs/hardening/scoreboard.json`), read the last cycle's
`scoreAfter` for this dimension and use it as a sanity check — S₀ should match unless the code
changed since.

---

## Step 2 — 🔴 Red Team (extreme-scenario attack)

Invoke the detection engine for this dimension. Reuse the `/redteam` workflow
(parallel reviewers → **Step 2.5 verification pass** → evidence-gated findings), but with an
**adversarial, extreme-scenario framing** appropriate to the dimension:

- **security** — actively try to break it: crafted traversal/injection payloads, auth-bypass
  paths, secret-exfil chains, SSRF, abuse of unauthenticated endpoints. Think like an attacker
  with the source in hand.
- **perf** — extreme load, huge inputs/payloads, slow-network and cold-cache scenarios, N+1
  blowups, worst-case algorithmic paths.
- **a11y** — keyboard-only navigation, screen-reader traversal, reduced-motion, contrast at
  worst color pairs, focus traps, missing labels/roles.

Carry over every guardrail already in `/redteam`: reachability triage first (dead code → LOW),
precise-import verification, exploit-chain linking, no false alarms, confidence labels.

---

## Step 3 — 🔵 Blue Team proposal (제안서)

Before touching code, write a proposal to
`docs/hardening/proposals/<YYYY-MM-DD-HHMM>-<dimension>.md`:

```markdown
# Hardening Proposal — <dimension> — <date>

Baseline score: S₀ = <n>/100   (open: C<c> H<h> M<m> L<l>)
Target: <target>   ( a11y only: AA required / AAA stretch )

## Red team found
- [SEVERITY] <issue> @ file:line — <evidence> — <exploit/impact, chains noted>

## Blue team proposes
- Fix <#>: <smallest change> — expected score gain ≈ +<n> — risk: <low/med> — <why>
- Tradeoffs accepted (e.g. a11y AAA→AA where design constrains): <note>

## Out of scope this cycle
- <deferred items + why>
```

The proposal is the artifact the user reviews even if they never read the diff.

---

## Step 4 — Apply fixes on the branch

Apply the proposed fixes — smallest correct change per finding, no drive-by refactors, dead-code
findings resolved by deletion. Follow `/redteam` Blue Team rules (secrets → rename + rotation
flag only if real exposure; prefer one shared fix for a root-cause group).

---

## Step 5 — Re-score (S₁) & verify

1. **Preflight** the toolchain (runtime version, deps, build availability). If the environment
   blocks measurement (e.g. build can't run), record the score as **"unverified — <reason>"** and
   say so — never report a gain you could not measure.
2. Run build/tests/lint scoped to what exists; repair anything your fix broke.
3. Re-run the dimension scorer → `S₁`. Compute `Δ = S₁ − S₀`.
4. Where practical, re-confirm the original evidence is gone (e.g. the traversal payload is now
   rejected).

---

## Step 6 — Scoreboard (measure the curve)

Append one row to **`docs/hardening/scoreboard.md`** and one record to
**`docs/hardening/scoreboard.json`**.

**Fixed items must be self-describing.** A finding `#id` is meaningful only inside one run's
report — in the scoreboard it tells the reader nothing ("what was #1?"). Record each fix as a
short **stable label + severity + location**, and keep the per-finding `#id` detail in the
cycle's proposal, not here.

`scoreboard.json` record:
```json
{
  "cycle": 3,
  "date": "2026-06-04T14:00:00Z",
  "dimension": "security",
  "scoreBefore": 61,
  "scoreAfter": 86,
  "delta": 25,
  "fixed": [
    { "label": "path-traversal", "severity": "CRITICAL", "location": "api/local-mdx/route.ts" },
    { "label": "missing-security-headers", "severity": "MEDIUM", "location": "next.config.ts" }
  ],
  "open": { "critical": 0, "high": 2, "medium": 4, "low": 3 },
  "branch": "hardening/security",
  "commit": "<sha>"
}
```

`scoreboard.md` table (short labels + severity, never bare `#id`s; link the proposal for detail):
```
| Cycle | Date       | Dim      | Score   | Δ   | Fixed (severity) |
|-------|------------|----------|---------|-----|------------------|
| 3     | 2026-06-04 | security | 61 → 86 | +25 | path-traversal (C) · security-headers (M) |
```

---

## Step 7 — Commit & report (one cycle, then stop)

1. Commit the proposal + fixes + scoreboard to the branch in one commit:
   ```
   harden(<dimension>): cycle <n> — score <S₀>→<S₁> (+Δ)
   ```
   (No push, no PR.)
2. Report:

```
🏟️  HARDENING CYCLE <n> — <dimension>

Score:    <S₀> → <S₁>   (Δ +<n>)        target <target> — <reached / N to go>
Fixed:    #1 CRITICAL traversal · #2 secret prefix
Open:     C0 · H2 · M4 · L3
Branch:   hardening/security  (commit <sha>, not pushed)
Proposal: docs/hardening/proposals/<file>.md

Next cycle would target: <highest-value open finding>. Run /harden again to continue.
```

---

## Scoring rubrics (repeatable, derived from verified findings)

**Score = clamp(100 − Σ severity weights, 0, 100)**, computed from the *verified* open findings:

| Severity | Weight |
|----------|--------|
| CRITICAL | 25 |
| HIGH     | 10 |
| MEDIUM   | 4 |
| LOW      | 1 |

- **security** — weights as above over verified security findings; baseline-hygiene gaps
  (no CSP/security headers, secrets with public prefix, `.env` tracked, unvalidated route input)
  each count as at least one finding so they pull the score down until fixed.
- **perf** — prefer a measured score (Lighthouse Performance / Core Web Vitals) when the app
  runs; otherwise fall back to the weighted-findings formula and label it "static estimate."
- **a11y** — prefer axe/Lighthouse a11y score and WCAG conformance %. **AA = required target**
  (treat AA failures as HIGH); AAA failures count as LOW (stretch). Note design-driven AA
  compromises explicitly in the proposal.

The number is meaningful *because it is reproducible*: same code + same verified findings → same
score. A rising curve across cycles = real, attributable hardening.

---

## Adding a dimension later

A dimension is just `{ attack rubric, fix policy, scorer }`. To add one (e.g. `seo`,
`bundle-size`): give the red team an extreme-scenario rubric, give the blue team a fix policy,
and define a scorer that returns 0–100 (measured tool score preferred, weighted-findings
fallback). Everything else — branch, proposal, scoreboard, report — is reused unchanged.

## Notes & safety

- One dimension, one cycle, per manual run — predictable and reviewable. To run unattended later:
  `/loop` (session open) or `/schedule` (remote cron). Keep the same branch-only, no-push rails.
- The scoreboard is the point: don't skip Step 6. Without the recorded Δ there is no proof the
  service got stronger.
- Honesty over optics: an unverified score, a downgraded finding, or "no findings this cycle"
  are all valid outcomes. Never inflate Δ to look productive.
- Everything stays on `hardening/<dimension>`. The user decides if/when it reaches `main`.
