# 007 — Review

Spec: [spec.md](spec.md) · Plan: [plan.md](plan.md) · Reviewed: 2026-11-20

Branch `work/007-v1-docs-cleanup`, 11 commits over `main` (spec/plan + tasks 1–10).
All 10 plan tasks are `done`.

## Automated checks
- `make lint typecheck` (from `Chatbot/`): **pass** — ruff format/check, eslint, pyright
  0 errors, `tsc -b` clean.
- `make unit`: **pass** — backend 158 passed; frontend 13 files, 67 tests passed.
- `make -C shared drift APP=Chatbot` (from `Apps/`): **pass** — all 10 canonical copies `ok current`.
- `make integration`: **pass** — 29 passed (testcontainers).
- `make e2e`: **pass** — 17 passed; stack torn down with `down -v`. Run by the reviewer
  because `CLAUDE.md` says `E2E self-contained: yes`.
- `cd backend && uv sync --locked`: **pass** (110 packages resolved, lock consistent).
- Mermaid parse with `npx @mermaid-js/mermaid-cli@11`: **not run by the reviewer**: the
  sandbox refused the `npx` download. The task 10 commit says both blocks rendered with
  mermaid-cli 11.16. I read both blocks by hand and found no syntax problem. The
  GitHub-preview fallback is under *Against the spec*.

## Against the spec
- [x] **Spec grep finds nothing** — **met.** `grep -rniE 'mkdocs|kroki|make docs|api-reference|plantuml|8004|8005' --exclude-dir={node_modules,.venv,.git,work} --exclude='*_PLAN.md' .`
  has three hits, all inside `sha256` hashes in `backend/uv.lock`
  (lines 1082, 1830, 2276: lxml, respx, watchfiles wheels). The plan expected this; it
  is not leftover tooling. The `uv.lock` diff only removes packages (the mkdocs
  family, `markdown`, `pathspec`, `platformdirs`, `watchdog`, …). It adds or bumps
  nothing.
- [x] **`ls docs/`** — **met.** It lists `adr/`, `architecture.md`, `work/` and the
  four `*_PLAN.md` files. `docs/adr/README.md` lists 001–007 as a table, and
  `docs/adr/index.md` is gone (renamed with no content change).
- [ ] **Two Mermaid `flowchart` blocks that parse** — **user to verify.**
  `grep -c '```mermaid' docs/architecture.md` = 2; they are `flowchart LR` (line 13)
  and `flowchart TB` (line 74), and there is no PlantUML. The parse could not be run
  here (see above). Open `docs/architecture.md` in GitHub's preview after the push, or
  run `cd Chatbot && awk '/^```mermaid/{n++;f=1;next} /^```/{f=0} f{print > ("/tmp/b" n ".mmd")}' docs/architecture.md && for b in /tmp/b1 /tmp/b2; do npx -y @mermaid-js/mermaid-cli@11 -i $b.mmd -o $b.svg; done`.
  Both must render.
- [x] **Relative links resolve** — **met.** The plan's link-check loop over
  `README.md`, `CLAUDE.md`, `docs/architecture.md`, `docs/adr/*.md` prints nothing.
- [x] **Every name in architecture.md exists** — **met.** I extracted all 351
  backticked items and grepped them in `backend/`, `frontend/`, `deployment/`, compose
  files, `Makefile` and `.github/`. The only misses were file paths, prose and event
  literals, so I checked those separately. Every named file exists (hooks, `src/test/`,
  `src/i18n/`, `utils/{clipboard,prefs,uuid}.ts`, `adapters/web/mock.py`,
  `routers/limiter.py`, `services/conversation/language.py`, `frontend/nginx.conf`).
  Env vars map to `Settings` fields (`llm_api_key`, `attachment_max_extracted_chars`,
  `chatbot_cli_user`, `chatbot_language`). `aclosing` is in
  `send_message.py`/`edit_message.py`. `llama.service`, `chatbot-stack.service` and
  `docker-autoupdate.timer` (`OnUnitActiveSec=5min`) are in `Infrastructure/`.
  Spot-checked facts that hold: title `[:60]`, `retry: 1` / `retry: false`,
  `creatingRef`, `MOBILE_BREAKPOINT = 640`, `/health` `include_in_schema=False`,
  `http_<status>` codes, `chatbot_token` / `chatbot_lang`, `ondelete="CASCADE"` chain,
  port 120, the canonical-copies list (matches the `canonical:` headers).
- [x] **CLAUDE.md shape** — **met.** *Documentation* points to `architecture.md`,
  `adr/`, `work/`. *Architecture* is three sentences, a link and *Gotchas while
  coding*, with no per-file layer list and no entity fields. `grep -niE '\bpi\b|mkdocs|make docs' CLAUDE.md`
  is empty. (The spec's `pi\b` also matches `api`; the plan's `\bpi\b` is the right
  form.) The diff touches only *Documentation*, the `make docs` line, *Architecture*
  and the removed *Deployment*. *Commands*, *E2E*, *Test strategy*, *CI/CD* and
  *Conventions to keep* are unchanged.
- [x] **`make docs` / compose** — **met in substance.** `make docs` prints
  `make: Nothing to be done for 'docs'.`, not "No rule to make target", because
  `docs/` is a directory and make treats it as an up-to-date file. No rule exists:
  `make -pq | grep '^docs:'` is empty and the `.PHONY` entry is gone. `kroki` is
  absent from `docker compose config --services`, `--profile docs` and
  `--profile '*'`. See note N1.
- [x] **`cd backend && uv sync --locked`** — **met** (above).
- [x] **`make test` passes** — **met.** lint, typecheck, unit, integration and e2e all
  pass when run separately (above).
- [ ] **Jacopo agrees each fact is stated in one place** — **user to verify.** Read
  `CLAUDE.md` and `docs/architecture.md` side by side. The only overlap is deliberate:
  a few *Gotchas* restate rules that architecture.md describes, phrased as do/don't.
  Also confirm the container diagram matches the mini-PC (plan task 10 asked for this
  too).

## Blueprint
- §10 (docs are plain Markdown; ADR list in `adr/README.md`): holds.
- §11 (CLAUDE.md holds app-specific facts; architecture lives in docs): holds.
- Hard rules: no code, test, migration, config or canonical file is changed, and no
  `noqa` / `ignore` / skip was added. The only non-docs changes are the tooling removals
  the spec asks for (`Makefile`, `docker-compose.yml`, `pyproject.toml`, `uv.lock`) and
  `.gitignore` (N2).
- Secrets/config: nothing committed; no new environment variables. `KROKI_HOST_PORT`
  is no longer used. Nothing to change on the mini-PC.
- Migrations: none.

## Findings
- **note N1** — `Makefile` (no line: the target is gone): the spec's literal check
  ("No rule to make target") cannot pass while a `docs/` directory exists; make says
  "Nothing to be done". The intent (no `docs` target) is met. Famiglia 003 behaved the
  same. Future specs should test with `make -n docs` / `make -pq | grep '^docs:'`.
- **note N2** — `.gitignore:18` (removed `# MkDocs` / `site/`): not in the plan's file
  list, but it is a docs-tooling leftover that the spec's intent covers. Task 10's
  commit says why. In scope.
- **note N3** — `CLAUDE.md` (removed *Deployment*): a few facts were dropped instead
  of moved. The dev Garage host port 3907 and that e2e `!reset`s it (both still in
  `docker-compose.yml` / `docker-compose.e2e.yml`); "re-run `garage_init` once" after
  adding the bucket (architecture.md:48 says only that the bucket must be in
  `GARAGE_BUCKETS`); "listing and reading work with the LLM off". None is a coding-time
  trap, so this is acceptable. The LLM-off claim was left out on purpose (plan
  *Approach*).
- **note N4** — `deployment/docker-compose.yml:18`, `deployment/README.md:12`,
  `deployment/.env.example:26` still say sending a message "errors cleanly" when llama
  is down. The spec leaves this to the backlog item *A stopped LLM cuts the stream off
  with no `error` event*, but that item names only CLAUDE.md, where the claim is now
  gone. I added a backlog line so these three comments get fixed with that item.
- **note N5** — `docs/architecture.md:192`: "There is no CORS: the browser reaches the
  API same-origin." This was not checked against every dev path. The Vite dev server
  proxies `/api`, so it holds for `make frontend` too.

No must-fix or should-fix findings.

## Verdict
**ready to ship once confirmed**

Left for the user to confirm:
1. Both Mermaid diagrams in `docs/architecture.md` render (GitHub preview after push,
   or the mermaid-cli command above).
2. You have read `CLAUDE.md` and `docs/architecture.md`: each fact is stated in one
   place, and the container diagram matches the mini-PC.

Both items confirmed by user, 2026-11-20.

---
Shipped: merge of work/007-v1-docs-cleanup · Date: 2026-11-20
