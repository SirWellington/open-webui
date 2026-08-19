# Wellington — custom OpenWebUI fork

A fork of [open-webui/open-webui](https://github.com/open-webui/open-webui) that adds
search, web-fetch, and document tooling. It is built to stay easy to sync with upstream
while keeping all customizations.

Every customization lives in exactly one of two places:

1. **This folder (`wellington/`)** — self-contained configs, assets, and tooling.
   Moving it never touches the upstream tree.
2. **A small, fixed set of core-file edits** — the only files modified inside the
   upstream source tree (kept minimal so rebase conflicts stay small and predictable).

---

## Layout

```
wellington/
├── functions/            # OpenWebUI Function(s) — import via Admin → Functions
│   └── better_qwen3_8.py
├── skills/               # OpenWebUI Skill(s) — import via Admin → Skills
│   └── search_the_web.md
├── tools/                # OpenWebUI Tool specs + helpers
│   ├── web_search.spec.json
│   ├── crawl4ai.spec.json
│   ├── make_inline_specs.py
│   └── c4ai-llm-patch/   # optional Crawl4AI thinking/LLM patch
├── searxng-config/
│   └── settings.yml      # SearXNG engine config (secrets via !process "env:…")
├── docker-compose.custom.yaml   # full stack (owui + docling + crawl4ai + searxng + mcpo)
├── mcpo.json             # MCP→OpenAPI bridge config (Holds the Crawl4AI Bearer token) [gitignored]
├── mcpo.json.example     # committed template for mcpo.json
├── .env.example          # template for the REPO-ROOT .env (all custom vars + placeholders)
├── memory.md             # local agent notes [gitignored]
├── sync.ps1              # Windows: status / rebase onto upstream/main
├── sync.sh               # Linux/macOS: status / rebase onto upstream/main
└── README.md
```

The live secrets live in the **repo-root `.env`** (one directory up), which is gitignored.

---

## Core edits (the only upstream files modified)

These are the *only* files outside `wellington/` that differ from upstream. They are the
entire sync-conflict surface. Preserve them on every rebase.

| File | Change |
| --- | --- |
| `Dockerfile` | `NODE_OPTIONS=--max-old-space-size=8192` (SvelteKit build heap bump) |
| `backend/open_webui/utils/middleware.py` | Crawl4AI markdown-surfacing fix |
| `backend/open_webui/models/automations.py` | persistent-chat automation |
| `backend/open_webui/utils/automations.py` | persistent-chat automation logic |
| `backend/open_webui/routers/tasks.py` | automation / title-generation task wiring |
| `src/lib/apis/automations/index.ts` | automations API client |
| `src/lib/components/AutomationModal.svelte` | automations UI |
| `src/lib/components/automations/AutomationEditor.svelte` | automation editor UI |
| `src/lib/components/automations/ChatTargetDropdown.svelte` | chat-target picker (new file) |
| `src/lib/components/common/Select.svelte` | select component tweak |
| `src/lib/components/layout/Sidebar/ChatItem.svelte` | generated-title display |
| `src/lib/i18n/locales/en-US/translation.json` | i18n strings |

> Note: `requirements.txt`, `backend/open_webui/retrieval/web/utils.py`,
> `backend/open_webui/tools/builtin.py`, `backend/open_webui/config.py`, and
> `src/lib/components/admin/Settings/WebSearch.svelte` were **reverted to pristine
> upstream** (the earlier Scrapling web-fetcher was removed). They no longer count
> against the conflict surface.

---

## Setup

### 1. Environment secrets — repo-root `.env`

Create `<repo>/.env` from the template (do **not** commit it):

```bash
cp wellington/.env.example .env
# then edit .env and fill in real values
```

Required variables (and who consumes them):

| Variable | Used by |
| --- | --- |
| `WEBUI_SECRET_KEY` | OpenWebUI (JWT signing) |
| `MCPO_API_KEY` | mcpo REST bridge auth |
| `CRAWL4AI_API_KEY` | Crawl4AI MCP server **and** the Bearer token in `wellington/mcpo.json` |
| `DOCLING_API_KEY` | docling-server |
| `SEARXNG_SECRET` | SearXNG `server.secret_key` |
| `SEARXNG_BRAVE_API_KEY` | SearXNG `braveapi` engine key |

### 2. `wellington/mcpo.json` (Crawl4AI token)

mcpo does **not** support env-var substitution in its JSON config, so the real
`CRAWL4AI_API_KEY` must be pasted in here:

```bash
cp wellington/mcpo.json.example wellington/mcpo.json
# replace CHANGE-ME-CRAWL4AI_API_KEY with the SAME value as CRAWL4AI_API_KEY in .env
```

`wellington/mcpo.json` is gitignored; `wellington/mcpo.json.example` is the committed template.

### 3. SearXNG config

`wellington/searxng-config/settings.yml` references the two SearXNG secrets via
SearXNG's env indirection, so no secrets are stored in it:

```yaml
server:
  secret_key: !process "env:SEARXNG_SECRET"
engines:
  - name: braveapi
    api_key: !process "env:SEARXNG_BRAVE_API_KEY"
```

The compose file injects `SEARXNG_SECRET` / `SEARXNG_BRAVE_API_KEY` into the `searxng`
service from the repo-root `.env`.

### 4. Crawl4AI LLM patch (optional)

`wellington/tools/c4ai-llm-patch/` contains an optional thinking/LLM patch for Crawl4AI.
Apply it to the Crawl4AI container only if you need that behavior.

---

## Run

Run from the **repo root** so Docker Compose reads the repo-root `.env`:

```bash
docker compose -f wellington/docker-compose.custom.yaml up -d
```

Services started:

| Service | Purpose |
| --- | --- |
| `open-webui` | the app (built from the repo-root `Dockerfile`; `build.context: ..`) |
| `docling-server` | document conversion (PDF/DOCX → markdown) |
| `crawl4ai` | web → markdown crawler (exposed as the `md`/`crawl` tools via mcpo) |
| `searxng` | metasearch engine (JSON API) |
| `searxng-mcp` | SearXNG MCP server |
| `mcpo` | MCP → OpenAPI/REST bridge that exposes the above as OpenWebUI tools |

The in-app **web-fetch engine is `safe_web`** (set in the compose `environment`).
The earlier Scrapling stealth fetcher was removed; Crawl4AI is the heavy web-fetch
tool, reachable through mcpo as the `md` / `crawl` tools.

---

## Re-importing functions / skills / tools

OpenWebUI loads Functions, Skills, and Tools **from its database, not from these files**.
The files in `wellington/functions|skills|tools` are the source of truth. After a fresh
install or a rebase, re-import them through the UI:

- **Functions** → Admin → Functions → import `wellington/functions/*.py`
- **Skills** → Admin → Skills → import `wellington/skills/*.md`
- **Tools** → Admin → Tools → import `wellington/tools/*.spec.json`
  (regenerate with `python wellington/tools/make_inline_specs.py` if you change them —
  run it from the `wellington/` directory)

---

## Syncing with upstream

The branch tracks `upstream/open-webui` (`origin` is your fork). Use the helper:

```bash
# Windows (PowerShell)
.\wellington\sync.ps1                 # status + fetch only
.\wellington\sync.ps1 -Rebase         # rebase onto upstream/main

# Linux / macOS
bash wellington/sync.sh               # status + fetch only
bash wellington/sync.sh --rebase      # rebase onto upstream/main
```

Or manually:

```bash
git fetch upstream
git rebase upstream/main
# resolve conflicts in the 12 core files listed above, then:
git rebase --continue
```

**Why this stays easy:**
- All custom assets are in `wellington/` (untracked-by-upstream), so upstream never
  conflicts with them.
- Only the 12 core files above can conflict, and each change is small and localized.
- The helper refuses a dirty tree unless you explicitly `--force`/`-Force`
  (it then stashes and restores your uncommitted work).

**After a rebase, always:**
1. Rebuild the image (`docker compose -f wellington/docker-compose.custom.yaml build`).
2. Re-import any Functions/Skills/Tools if you changed them.
3. `git grep -in "scrapling\|patchright\|browserforge\|curl-cffi" backend src Dockerfile`
   should return nothing (Scrapling must stay removed).

---

## Secrets checklist

- Repo-root `.env` — **gitignored** (all six custom secrets).
- `wellington/mcpo.json` — **gitignored** (Crawl4AI Bearer token).
- `wellington/memory.md` — **gitignored** (local notes).
- `wellington/searxng-config/settings.yml` — contains **no** raw secrets (uses `!process "env:…"`).
- Committed templates (safe to share): `wellington/.env.example`, `wellington/mcpo.json.example`.

If you ever `git diff` a tracked file and see a real key, treat it as an incident:
rotate the key, move it to `.env`, and keep only the placeholder in the committed file.
