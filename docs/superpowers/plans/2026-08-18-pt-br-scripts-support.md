# BetterGI Scripts PT-BR Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make priority BetterGI scripts work with Brazilian Portuguese game text without breaking existing Chinese/English users.

**Architecture:** Consume the new semantic script API from BetterGI core (`genshin.gameCulture`, `getText`, `getTexts`, `findTextKey`, `findTextKeyAndClick`) instead of embedding localized UI strings directly in JS. Migrate high-value scripts first, then add a scanner to identify remaining language-dependent OCR literals.

**Tech Stack:** BetterGI JavaScript scripting runtime, OCR recognition APIs, manifest metadata.

**Spec:** `/mnt/data/bettergi-ptbr-design.md` (source design approved in ChatGPT session; this repository plan is the executable version)

## Global Constraints

- Do not hand-edit generated `repo.json` for ordinary script changes.
- Keep scripts in their existing category directories.
- Any new script API usage must be represented in `bettergi.d.ts` and guarded by an appropriate minimum `bgi_version` where required.
- Do not replace Chinese strings with Portuguese strings; replace functional language-specific literals with semantic keys.
- Keep non-functional logs/descriptions localized separately from automation matching logic.
- Prefer the BetterGI core semantic API; do not duplicate an independent translation catalog in every script.

---

### Task 1: Update script type declarations for semantic localization API

**Files:**
- Modify: `bettergi.d.ts` (exact path to be confirmed in repository)

**Interfaces:**
- Consumes core API from BetterGI
- Produces type declarations for:
  - `genshin.gameCulture: string`
  - `genshin.getText(key: string): string`
  - `genshin.getTexts(key: string): string[]`
  - semantic OCR helpers when exposed by core

- [ ] Locate the canonical `bettergi.d.ts`.
- [ ] Add declarations matching exact runtime names/signatures.
- [ ] Document semantic keys at a high level without duplicating translations.
- [ ] Validate declaration syntax.
- [ ] Commit as `feat(types): declare localized game text APIs`.

### Task 2: Migrate AutoPlan common OCR helper usage

**Files:**
- Modify: `repo/js/AutoPlan/utils/tool.js`
- Modify manifest/version metadata only if required

**Interfaces:**
- Consumes: `genshin.findTextKey`, `genshin.findTextKeyAndClick`
- Produces: AutoPlan flows independent of hardcoded strings for critical prompts

- [ ] Replace functional searches for `退出秘境`, `退出挑战`, `地脉异常`, `确认`, and `物品过期` with semantic keys.
- [ ] Preserve coordinate regions, retry timing, cancellation, and click behavior.
- [ ] Keep user-facing log text unchanged unless needed for clarity.
- [ ] Ensure the script minimum BetterGI version covers the new API.
- [ ] Validate JS syntax/manifest.
- [ ] Commit as `refactor(autoplan): use semantic OCR text keys`.

### Task 3: Migrate priority daily/commission scripts

**Files:**
- Modify only scripts found by scan that use OCR text for daily commissions/rewards/teleport confirmation

**Interfaces:**
- Consumes semantic text API
- Produces PT-BR-compatible critical daily flows

- [ ] Search for `findText`, `findTextAndClick`, OCR `.text` comparisons, `.includes(...)`, and `OcrMatch` with CJK literals.
- [ ] Group matches by semantic meaning rather than translating ad hoc.
- [ ] Use existing keys where possible; request/add a core key only when no suitable semantic key exists.
- [ ] Validate each changed script manifest and syntax.
- [ ] Commit in small functional groups.

### Task 4: Migrate priority fishing/artifact scripts

**Files:**
- Candidate families from repository scan: AutoFishing variants, OCRArtifacts, inventory/material OCR utilities

**Interfaces:**
- Consumes semantic text API for UI prompts; raw OCR remains valid for dynamic item/number text

- [ ] Distinguish static UI labels from dynamic OCR content.
- [ ] Replace only static functional labels with semantic keys.
- [ ] Do not force semantic keys onto arbitrary item names/counts that must remain OCR data.
- [ ] Validate syntax/manifest after each group.
- [ ] Commit per script family.

### Task 5: Add repository scanner for language-dependent OCR literals

**Files:**
- Create: `tools/i18n/scan-ocr-literals.*` or repository-consistent tooling path
- Optionally update CI/build tooling after local behavior is stable

**Interfaces:**
- Produces report containing file, line, literal, and matching context

- [ ] Detect CJK literals passed to `findText`, `findTextAndClick`, OCR matchers, `.includes`, and equality comparisons against OCR results.
- [ ] Ignore README/log/comment-only strings where they cannot influence automation.
- [ ] Support an allowlist for intentional localized data.
- [ ] Run scanner across `repo/js` and record remaining hotspots.
- [ ] Commit as `chore(i18n): scan functional OCR literals`.

### Task 6: Entity-name decoupling inventory

**Files:**
- Create: `docs/i18n/entity-name-dependencies.md`

**Interfaces:**
- Produces categorized list of scripts depending on localized character/item/domain/NPC/region names

- [ ] Scan arrays/maps/comparisons of localized entity names.
- [ ] Separate user-facing display names from functional selectors.
- [ ] Classify each dependency as `stable-id candidate`, `OCR dynamic`, or `translation-only`.
- [ ] Do not mass-rewrite entities until the core stable-ID strategy exists.
- [ ] Commit as `docs(i18n): inventory localized entity dependencies`.

### Task 7: Verification

- [ ] Validate all modified JSON manifests parse successfully.
- [ ] Validate all modified JavaScript files parse successfully with available tooling.
- [ ] Confirm no generated `repo.json` was hand-edited.
- [ ] Confirm all new runtime API references are covered by `bettergi.d.ts` and minimum `bgi_version` where needed.
- [ ] Review diff for unrelated build/generated files.
- [ ] Document runtime tests that still require the BetterGI desktop client/game environment.
