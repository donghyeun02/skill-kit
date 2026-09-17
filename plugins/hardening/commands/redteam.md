---
description: Red team / blue team audit — evidence-gated security, performance & quality detection, verified before report, then approval-gated fixes.
argument-hint: '[path | . | blank=uncommitted]  [--security] [--perf] [--quality] [--fix] [--paranoid]'
---

# Red Team / Blue Team Audit

**Input**: $ARGUMENTS

A two-phase audit of your code:

- 🔴 **Red Team** — independent reviewers hunt for security, performance, and quality problems _in parallel_, then every CRITICAL/HIGH is **verified against real evidence** before it reaches you.
- 🔵 **Blue Team** — after you approve, fixes are applied with minimal diffs and then verified.

This command is **self-contained**: it uses the built-in `general-purpose` agent with the
rubrics embedded below, so it works in any Claude Code install (no plugins required).

> ⚖️ **Prime directive — no false alarms.** A finding you cannot back with concrete
> evidence (a line of code, a grep hit, a tracked file) is downgraded or dropped. Crying
> CRITICAL on a theoretical issue is itself a defect. Severity is _earned with proof_.

## Arguments

Parse `$ARGUMENTS`:

- **Scope** (first non-flag token):
  - a path → audit that file or directory
  - `.` → audit the whole project
  - _blank_ → audit uncommitted changes (`git diff --name-only HEAD`); if not a git repo, fall back to `.`
- **Area flags** (any combination; none given → run all three):
  - `--security` · `--perf` · `--quality`
- **`--fix`** → skip the approval gate and auto-fix CONFIRMED CRITICAL + HIGH findings (default: gate ON).
- **`--paranoid`** → also report THEORETICAL / latent findings (off by default; otherwise they are noted briefly, not promoted).

---

## Finding schema (every reviewer uses this)

```json
{
  "severity": "CRITICAL | HIGH | MEDIUM | LOW",
  "confidence": "CONFIRMED | LIKELY | THEORETICAL",
  "area": "Security | Perf | Quality",
  "location": "path:line",
  "issue": "one line, specific",
  "evidence": "what in the code proves this (quote/symbol/why it triggers)",
  "exploit_or_impact": "concrete consequence — for security, how it is actually reached",
  "fix": "smallest concrete change that resolves it"
}
```

### Severity is evidence-gated (read carefully)

- **CRITICAL** — _confirmed, reachable_ exploit / data loss / **live** secret leak. Must be
  CONFIRMED. A risk that requires code that does not yet exist ("if someone later references
  this…") is **not** CRITICAL — it is a latent misconfiguration, cap at MEDIUM.
- **HIGH** — confirmed real bug or significant degradation on a real path.
- **MEDIUM** — maintainability/correctness smell, or a latent/THEORETICAL security issue
  (footgun that is not currently reachable).
- **LOW** — style / minor.

Distinguish **active vulnerability** (reachable now) from **latent misconfiguration**
(dangerous shape, not currently exploitable). Never report the latter as the former.

---

## Step 1 — Scope & Stack Detection

1. Resolve the target file set from the scope rule above.
2. Detect language/framework from manifests: `package.json` (note Next.js / Vite / CRA),
   `requirements.txt`/`pyproject.toml`, `go.mod`, `pom.xml`/`build.gradle`, `Cargo.toml`,
   `composer.json`, etc.
3. If the target set is empty (e.g. no uncommitted changes), tell the user and stop.

Print a one-line scope summary: `scope: <N files> · stack: <lang/framework>`.

---

## Step 1.5 — Reachability triage (run before the reviewers)

Findings in unreachable code waste reviewer effort and inflate the report (a real lesson:
a "critical" can hang off a file that nothing imports). Before launching reviewers, do a quick
reachability sweep over the scope:

- For each non-entrypoint source file, check whether it is actually imported anywhere
  (`grep -rn "from '.*<basename>'" src/` — match real import statements, not bare substrings).
- Mark files with **no live importer** as DEAD.

Pass this DEAD list to the reviewers. Any issue located in a DEAD file is capped at **LOW** with
fix = "delete the dead file" — do not let security/perf findings in unreachable code be promoted.
Entrypoints (routes, `page`/`layout`, `main`, exported library surface) are always reachable.

---

## Step 2 — 🔴 Red Team (parallel detection)

Launch the selected reviewers **in a single message** (concurrent `Agent` calls,
`subagent_type: general-purpose`). Run only the areas selected by the flags (all three if none given).

Give **every** reviewer this shared instruction block plus its area-specific rubric:

> You are an independent red-team reviewer. You have NOT seen any other review. Your job is to
> FIND problems, not to approve — but you are judged on PRECISION, not volume. Read the listed
> files. Report only issues you can point to at a specific `file:line` AND back with `evidence`.
> Mark `confidence`: CONFIRMED (you traced it and it is reachable), LIKELY (strong signal,
> not fully traced), THEORETICAL (dangerous shape, not currently reachable). Do NOT inflate
> severity: a THEORETICAL security issue is MEDIUM, not CRITICAL. Do not edit any files.
> Return a JSON array using the Finding schema (empty array if none).

### Reviewer 1 — Security (`--security`)

Hunt for (OWASP Top 10): hardcoded secrets/tokens/keys; **client-bundle secret exposure**
(framework env-var prefixes — see the Secret-Exposure sub-protocol below); injection
(SQL/NoSQL/command/path/template); broken access control / IDOR; XSS via
`dangerouslySetInnerHTML` / unsanitized HTML or runtime-evaluated remote content; SSRF in
fetch of user-controlled URLs; path traversal in file-reading routes; unsafe deserialization;
weak/hand-rolled crypto; missing input validation at boundaries; sensitive data in logs/errors;
missing security headers (CSP etc.); vulnerable/outdated dependencies.
**For every secret/exposure finding, follow the Secret-Exposure sub-protocol and report the
verified status (tracked? referenced in client code? present in build output?) — do not assume.**

### Reviewer 2 — Performance (`--perf`)

Hunt for: N+1 / unbatched I/O; missing pagination / unbounded queries; missing indexes implied
by query shape; O(n²)+ hot paths; redundant work in loops; memory leaks / unbounded growth;
blocking calls on hot/async paths; missing caching of expensive repeat work; heavy libs imported
eagerly instead of code-split (`next/dynamic`); runtime work that belongs at build time;
oversized payloads; request waterfalls; unoptimized images; re-render churn (missing memoization,
inline object/array props).

### Reviewer 3 — Quality (`--quality`)

Hunt for: silently swallowed errors (empty catch / log-and-continue with bad state); missing
error handling on fetch/await/I/O (e.g. no `response.ok` check); functions > 50 lines; files

> 800 lines; nesting > 4 deep; `any` defeating the type system; mutation where immutability is
> expected; magic numbers/strings; dead / duplicated code (DRY); leaky abstractions; missing tests
> for new logic; leftover `console.log`/debug in production paths.

---

## Step 2.5 — 🔎 Verification Pass (the part that prevents false alarms)

**Before anything reaches the report**, the orchestrator independently verifies every
CRITICAL and HIGH finding (and any CONFIRMED-security finding at any severity). Do not trust a
reviewer's severity on faith — prove it or downgrade it.

For each such finding, run concrete read-only checks and record the result:

- **Reachability** — is the vulnerable code actually called on a real path? (grep for the
  symbol/route; confirm it is wired up, not dead code).
- **Secret exposure** → run the **Secret-Exposure sub-protocol** below in full.
- **Injection / traversal** — confirm the tainted input truly flows unsanitized to the sink
  (read the function end to end; check for an upstream guard the reviewer missed).
- **Dead code** — confirm the file/function is imported nowhere. Match **real import
  statements**, not bare substrings: `grep` for `integrity` will falsely hit a prop named
  `integrityStatus`. Grep `from '...<name>'` / `import ... <name>`, and confirm the symbol is
  actually used, before calling something dead or live.
- **Exploit chains** — check whether findings compound. A "latent" secret in `.env` plus a
  path-traversal file-read is a _live_ chain (the traversal reads the secret). Link chained
  findings in the report and rate the chain by its realized impact, not the weakest link.

Then adjust: **CONFIRMED** stays; **LIKELY** stays but is labeled; **THEORETICAL** is capped at
MEDIUM (or held back unless `--paranoid`). If a claimed CRITICAL fails verification, **say so
explicitly in the report** with the evidence that downgraded it — transparency over face-saving.

### Secret-Exposure sub-protocol (framework-aware)

Client-bundled secrets depend on the framework's public-env prefix:

| Framework | Public (ships to browser) prefix | Server-only (safe)            |
| --------- | -------------------------------- | ----------------------------- |
| Next.js   | `NEXT_PUBLIC_`                   | no prefix                     |
| Vite      | `VITE_`                          | no prefix / loaded via server |
| CRA       | `REACT_APP_`                     | no prefix                     |

A public-prefixed var is **only actually leaked when client code references it** (the bundler
inlines the literal at that reference). So verify, in order:

```bash
# 1. Is the env file even committed? (gitignored + untracked = no repo leak)
grep -nE '\.env' .gitignore;  git ls-files --error-unmatch .env 2>/dev/null
# 2. Is the public-prefixed secret referenced in source at all?
grep -rn 'NEXT_PUBLIC_<NAME>' src/        # adjust prefix per framework
# 3. Did it actually get inlined into the shipped bundle?
grep -rl 'NEXT_PUBLIC_<NAME>' .next/static 2>/dev/null   # build output
# 4. Rotation needed? Only if it was ever referenced in client code historically:
git log -p -S 'NEXT_PUBLIC_<NAME>' -- src/ | head
```

Classify the result honestly:

- Referenced in client code **and/or** present in build output → **CONFIRMED CRITICAL, live leak**, rotate now.
- Public prefix but **no reference anywhere and not in build** → **MEDIUM latent misconfiguration**
  (footgun naming); fix = rename to server-only var; rotate **only** if git history shows past client use.
- `.env` tracked in git → separate **HIGH** (repo leak) regardless of prefix.

Never report "secret exposed" as CRITICAL without completing checks 1–3.

---

## Step 3 — Consolidated Report (the gate)

Merge findings. Deduplicate across reviewers (keep highest _verified_ severity). Sort by
severity (CRITICAL → LOW). When several findings share one root cause, **group them** and name
the single fix that resolves the set (e.g. "compile MDX at build time" resolving a perf + a
security item at once).

```
🔴 RED TEAM FINDINGS   scope: <files> · stack: <lang>

| #  | Severity | Conf.     | Area     | Location          | Issue                          |
|----|----------|-----------|----------|-------------------|--------------------------------|
| 1  | CRITICAL | CONFIRMED | Security | api/route.ts:17   | Path traversal → arbitrary read |
| 2  | MEDIUM   | THEORET.  | Security | .env              | Public-prefixed key, unreferenced (latent) |
| 3  | HIGH     | CONFIRMED | Perf     | mdx-components:4  | Eager heavy import in every page |
...

Summary: <c> CRITICAL · <h> HIGH · <m> MEDIUM · <l> LOW
Root-cause groups: [#3,#6,#13] → one fix: compile MDX at build time
Exploit chains:    [#1 latent secret] + [#2 path traversal] → live: traversal reads the .env secret
Downgraded on verification: [#2 was reported CRITICAL → MEDIUM: not referenced in src, absent from .next/static]
Dead-code findings: [#14] capped at LOW → fix = delete unreachable file
```

If there are **zero** verified findings, say so plainly and stop — do not invent issues.

---

## Step 4 — Approval Gate

**Unless `--fix` was passed**, STOP here and ask:

> 무엇을 수정할까요? `all` / `critical+high` / 번호 지정(예: `1,2,5`) / `none`

Wait for the user's choice. Do not edit anything before they answer.

With `--fix`: skip the prompt, select all CONFIRMED CRITICAL + HIGH findings, and continue.

---

## Step 5 — 🔵 Blue Team (fix)

For each approved finding, in severity order:

1. Apply the **smallest correct fix** for that specific issue. No drive-by refactors,
   no reformatting untouched code, no scope creep.
2. Prefer the reviewer's recommended fix; deviate only if it is wrong or unsafe, and say why.
3. For secrets: rename to server-only vars, move usage to server code, and flag the value for
   **rotation only if** the verification step showed real/historical client exposure (removing
   it from source does not un-leak an already-shipped value).
4. Prefer fixing a whole root-cause group with its single shared fix over patching each symptom.

Keep a running list of what changed per finding.

---

## Step 6 — Verification

**Preflight first.** Confirm the toolchain can actually run (correct Node/runtime version,
deps installed, build command exists). If the environment itself blocks verification (e.g. the
build fails on a Node-version mismatch unrelated to your change), report **"could not verify —
<reason>"**, not PASS. A green checkmark you did not actually earn is a false alarm in the other
direction. Distinguish "my fix broke the build" from "the build was already un-runnable here."

Then run whatever the project provides, scoped to what exists:

- Build / compile (e.g. `tsc --noEmit`, `next build`, `go build ./...`, `mvn -q compile`)
- Tests (`npm test`, `pytest -q`, `go test ./...`, etc.)
- Lint / type check / format check

If a build or test breaks **because of a fix**, repair it before reporting success. If a finding
cannot be safely auto-fixed, leave it and mark it for manual review — do not fake a fix. Where
practical, re-verify the original evidence is gone (e.g. re-grep the build output for a secret,
re-request the traversal path and confirm it is now rejected).

---

## Step 7 — Final Report

```
🔵 BLUE TEAM RESULT

Fixed:     #1, #3          (CRITICAL: 1 · HIGH: 1)
Verified:  build PASS · tests PASS · lint PASS · evidence re-checked
Deferred:  #5 (manual review — risky to auto-change)
Skipped:   #4 (not approved)

⚠️ Action required (human): rotate <X> only if git history confirmed past client exposure.
```

Then stop. Do **not** commit or push unless the user explicitly asks.

---

## Notes

- **Precision over volume.** The verification pass (Step 2.5) exists because parallel reviewers
  over-claim; the orchestrator's job is to be the skeptic that demands evidence before alarming
  the user. A downgraded finding is a success, not a miss.
- Red-team reviewers run read-only — only the Blue Team phase (Step 5) edits files.
- Reviewers are deliberately independent (separate agents, no shared context) so blind spots
  differ and more real issues surface.
- This is a heavyweight, on-demand audit — run it before a PR or when a feature is done, not on
  every save. For fast per-commit checks (secret scanning, lint) use a `pre-commit` git hook; it
  complements this command rather than replacing it.
- To share: `/plugin marketplace add donghyeun02/claude-kit` then `/plugin install hardening@claude-kit`
  (ships `/redteam` and `/harden` together — `/harden` depends on `/redteam`). Or commit this file to a
  project's `.claude/commands/redteam.md` so everyone on the repo gets `/redteam` automatically.
