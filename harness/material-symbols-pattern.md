# Material Symbols Subset — Maintenance Pattern

**Source:** BL-025-F009 (sweep done 2026-05-02 → 2026-05-03 after
the prod 字符方框 incident traced to hotfix `bb637a1`).

**Lives at:**
- `scripts/regenerate-material-symbols-subset.sh` — the generator.
- `scripts/material-symbols-icons-manifest.txt` — the explicit
  list for icons the script's grep can't see.
- `src/app/fonts/material-symbols-outlined.woff2` — the shipped
  glyph subset, served by `next/font/local`.
- `tests/integration/material-symbols-coverage.test.ts` — the CI
  guard that catches a regression silently.
- `.github/pull_request_template.md` — the PR-time checklist.

## The 5 categories of "icon name in code" the script must handle

The original BIx-F005-B subset script only matched two literal
forms; the prod hotfix sweep turned up five more dynamic forms
that grep heuristics either miss or flag with too many false
positives:

| # | Shape | Caught by |
|---|---|---|
| 1 | `<span class="material-symbols-outlined">name</span>` (single line) | Pattern 1 |
| 2 | `<span class="material-symbols-outlined">…\n  name\n  …</span>` (multi line) | Pattern 2 |
| 3 | `icon: "name"` constant (audit log meta, sidebar nav, etc.) | Pattern 3 |
| 4 | JSX prop `<MyButton icon="name">` | Pattern 4 |
| 5a | JSX ternary in expression position: `{cond ? "name_a" : "name_b"}` | **manifest** (Pattern 5) |
| 5b | Object value with key ≠ `icon`: `{ up: "trending_up", down: "trending_down" }` | **manifest** |
| 5c | Multi-line array element: `["icon_a", "icon_b", "icon_c"]` (one per line) | **manifest** |
| 5d | Function `return "name";` | **manifest** |
| 5e | `?? "fallback"` in nullish-coalesce | **manifest** |

We trialled grep patterns 6 (array element) + 7 (return statement)
during F009.2 and bailed: the recall lift went from ~88 → ~219
discovered icons, the vast majority of which were not Material
Symbols — non-icon string constants, audit-log action verbs, etc.
The font fetch isn't picky about extras (Google Fonts ignores
unknown names) but the noise made the discovered list misleading
and made the surrounding exclusion regex unmaintainable. **The
manifest is the right home for the dynamic-form cases**: one line
per icon, with a comment pointing at the call site, so a future
sweep can reproduce the audit trail.

## When you add a new icon

1. **If it lands in form 1-4:** the next CI run regenerates the
   woff2 and ships the glyph automatically. Nothing to do.
2. **If it lands in form 5a-5e (or any unfamiliar dynamic shape):**
   - Append a line to `scripts/material-symbols-icons-manifest.txt`:
     ```
     icon_name        # path/to/file.tsx:LINE | <pattern reason>
     ```
   - Run `./scripts/regenerate-material-symbols-subset.sh` locally.
   - Commit the manifest change + the regenerated
     `src/app/fonts/material-symbols-outlined.woff2` together.
3. Reviewer L1 runs the F009.3 guard test
   (`material-symbols-coverage.test.ts`) which fails if:
   - A manifest entry is malformed.
   - The script's pattern pipeline shrinks below ~50 unique icons
     (signal that someone broke the patterns).
   - The shipped woff2 is empty / missing.

## How the prod incident landed

Hotfix `bb637a1` (2026-05-02) — users reported character squares
in `/dashboard` + `/knowledge-base` for ~19 icons:
`trending_flat`, `bookmark_added`, `auto_fix_high`, etc. Root
cause was a mix of forms 5a (JSX ternary) + 5b (object value) +
5c (array element) — the original 4-pattern grep silently missed
all of them, the woff2 shipped without those glyphs, and the
browser fell back to displaying raw Unicode private-use code
points (the boxes).

The sweep added Pattern 4 (JSX prop) inline + the manifest as the
catch-all, regenerated the woff2 to ~9.2KB / 80 icons. F009.1
extended the manifest with the 10 BL-025 icons (`folder_open`,
`auto_awesome`, `restart_alt`, `file_copy`, `archive`,
`unarchive`, `more_vert`, `compare_arrows`, `restore`, `movie`)
ahead of F004 landing so the woff2 was warm by the time those
spans appeared in the codebase. F009.3 codifies the guard test.
F009.4 surfaces the maintenance contract at PR-review time.
