# Plan: MkDocs Documentation Site for Read the Docs

## Goal
Create a Material-themed MkDocs documentation site for `llm-pycascade` that builds on Read the Docs (RTD), wired to the existing `.readthedocs.yaml` (which already declares `configuration: mkdocs.yml` but the file does not yet exist). API reference is auto-generated from docstrings via `mkdocstrings`.

## Confirmed Decisions
- **API reference**: auto-generated with `mkdocstrings[python]` (Google-style docstrings already present on all public symbols).
- **Content**: dedicated, structured `docs/` site (README stays as the GitHub landing page).
- **Theme/output**: `mkdocs-material`, HTML only.
- **Config location**: `mkdocs.yml` at repo root (matches existing `.readthedocs.yaml`), Markdown pages under `docs/`.

## Key Context Found in Code
- Public API surface (`src/llm_pycascade/__init__.py`): `run_cascade`, `AppConfig`, `CascadeConfig`, `CascadeEntry`, `DatabaseConfig`, `FailureConfig`, `ProviderConfig`, `ProviderType`, `load_config`, `init_db`, `CascadeError`, `ProviderError`, `ContentBlock`, `Conversation`, `LlmResponse`, `Message`, `MessageRole`, `ToolDefinition`, `__version__`.
- Modules to expose in reference: `cascade`, `config`, `models` (conversation/response/tool), `providers` (base + openai/anthropic/gemini/ollama), `error`, `db`, `persistence`, `secrets`.
- RTD project slug = `llm-pycascade` (from `.github/workflows/rtd-publish.yml`). Site URL: `https://llm-pycascade.readthedocs.io/`. Repo: `https://github.com/paluigi/llm-pycascade`.
- Python build target on RTD: `3.13` (per `.readthedocs.yaml`).
- `config.example.toml` is a complete reference; reuse its content in the configuration page.

## Docstring / API Notes (must follow to avoid broken examples)
- `ContentBlockType` is NOT in `__all__`/`models.__init__`. In the tools guide import it explicitly: `from llm_pycascade.models.response import ContentBlockType`.
- The README quickstart uses a fragile `config.database.path.replace("~", "/home/user")`. In the docs quickstart use robust expansion instead: `from llm_pycascade.config import expand_tilde` (or `os.path.expanduser`).

---

## File Inventory to Create

```
mkdocs.yml                         # root config (Material theme + mkdocstrings)
docs/
├── requirements.txt               # docs build deps
├── index.md                       # landing/overview
├── installation.md                # pip, uv, [keyring] extra, Python >=3.10
├── quickstart.md                  # minimal runnable async example (robust path expansion)
├── configuration.md               # TOML schema: providers, cascades, database, failure_persistence, LLM_PYCASCADE_CONFIG
├── concepts.md                    # cascade, failover, cooldown/backoff table, Retry-After, persistence, attempt log
├── providers.md                   # built-in providers, base_url override, OpenAI-compatible endpoints
├── tools.md                       # tool/function calling guide (correct ContentBlockType import)
├── secrets.md                     # keyring integration vs env vars, resolution order, mask_key
├── error-handling.md             # ProviderError variants + properties, CascadeError, failed-prompt JSON
├── changelog.md                   # v0.1.0 entry; link to GitHub releases
└── reference/
    ├── cascade.md                 # ::: llm_pycascade.cascade
    ├── config.md                  # ::: llm_pycascade.config
    ├── models.md                  # ::: llm_pycascade.models (+ conversation, response, tool)
    ├── providers.md               # ::: llm_pycascade.providers (+ base + each impl)
    ├── error.md                   # ::: llm_pycascade.error
    ├── db.md                      # ::: llm_pycascade.db
    ├── persistence.md             # ::: llm_pycascade.persistence
    └── secrets.md                 # ::: llm_pycascade.secrets
```

## Files to Edit
- `.readthedocs.yaml` — enable the commented-out `python.install` block so RTD installs docs deps **and** the project (so `mkdocstrings`/griffe can introspect it).

---

## mkdocs.yml (skeleton to implement)

```yaml
site_name: llm-pycascade
site_url: https://llm-pycascade.readthedocs.io/
site_description: Resilient cascading LLM inference with failover, circuit breaking, and retry cooldowns.
site_author: Luigi
repo_url: https://github.com/paluigi/llm-pycascade
repo_name: paluigi/llm-pycascade
edit_uri: edit/main/docs/

docs_dir: docs

theme:
  name: material
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.indexes
    - navigation.top
    - content.code.copy
    - content.code.annotate
    - content.tabs.link
    - search.suggest
    - search.highlight
    - toc.follow
  palette:
    - media: "(prefers-color-scheme: light)"
      scheme: default
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
  icon:
    repo: fontawesome/brands/github

nav:
  - Overview: index.md
  - Installation: installation.md
  - Quickstart: quickstart.md
  - Configuration: configuration.md
  - Concepts:
      - How it works: concepts.md
      - Providers: providers.md
      - Tools & function calling: tools.md
      - Secrets & keyring: secrets.md
      - Error handling: error-handling.md
  - API Reference:
      - cascade: reference/cascade.md
      - config: reference/config.md
      - models: reference/models.md
      - providers: reference/providers.md
      - error: reference/error.md
      - db: reference/db.md
      - persistence: reference/persistence.md
      - secrets: reference/secrets.md
  - Changelog: changelog.md

markdown_extensions:
  - admonition
  - attr_list
  - def_list
  - footnotes
  - md_in_html
  - tables
  - toc:
      permalink: true
  - pymdownx.details
  - pymdownx.superfences
  - pymdownx.highlight:
      anchor_linenums: true
      line_spans: __span
      pygments_lang_class: true
  - pymdownx.inlinehilite
  - pymdownx.tabbed:
      alternate_style: true
  - pymdownx.snippets

plugins:
  - search
  - mkdocstrings:
      default_handler: python
      handlers:
        python:
          paths: [src]
          options:
            docstring_style: google
            show_source: true
            show_root_heading: true
            show_root_full_path: false
            show_symbol_type_heading: true
            show_symbol_type_toc: true
            show_signature_annotations: true
            separate_signature: true
            merge_init_into_class: true
            heading_level: 2

extra:
  social:
    - icon: fontawesome/brands/github
      link: https://github.com/paluigi/llm-pycascade
  version:
    provider: mike
```

> Note: `paths: [src]` lets griffe resolve `llm_pycascade` from source without a runtime import. Installing the package on RTD (via `python.install`) is still done as a safety net.

## .readthedocs.yaml change

Replace the commented `python:` block with:

```yaml
python:
  install:
    - requirements: docs/requirements.txt
    - method: pip
      path: .
```

## docs/requirements.txt

```
mkdocs>=1.6
mkdocs-material>=9.5
mkdocstrings[python]>=0.26
```

(`mike` is intentionally NOT required; `version.provider: mike` is a no-op on RTD unless configured — drop the `extra.version` block if you prefer zero-unused config.)

## Reference page content (each `reference/*.md`)
Each file is one or more `mkdocstrings` cross-references, e.g. `reference/models.md`:

```markdown
# Models

::: llm_pycascade.models
::: llm_pycascade.models.conversation
::: llm_pycascade.models.response
::: llm_pycascade.models.tool
```

- `reference/cascade.md` → `::: llm_pycascade.cascade`
- `reference/config.md` → `::: llm_pycascade.config`
- `reference/providers.md` → `::: llm_pycascade.providers` + `::: llm_pycascade.providers.base` + each of openai/anthropic/gemini/ollama
- `reference/error.md` → `::: llm_pycascade.error`
- `reference/db.md` → `::: llm_pycascade.db`
- `reference/persistence.md` → `::: llm_pycascade.persistence`
- `reference/secrets.md` → `::: llm_pycascade.secrets`

## Written-page content guidance
- **index.md**: 2–3 sentence pitch (from README tagline), feature bullets, badges (CI / RTD / PyPI / license), "next steps" links into Quickstart & Configuration.
- **installation.md**: `pip install`, `uv add`, the `[keyring]` extra, Python ≥3.10 requirement.
- **quickstart.md**: copy/adapt README basic example but use robust path expansion; show both a plain prompt and how to read `response.text_only()`.
- **configuration.md**: explain the search order (`LLM_PYCASCADE_CONFIG` → XDG → legacy), embed `config.example.toml` content with per-section explanation.
- **concepts.md**: reuse README architecture ASCII diagram + cooldown/backoff table + Retry-After behavior + persistence behavior + SQLite tables (`attempt_log`, `cooldown`).
- **providers.md**: list built-in providers, default base URLs, `base_url` override for OpenAI-compatible (vLLM/LiteLLM/Together), Ollama needing no key.
- **tools.md**: tool/function-calling guide; correct `ContentBlockType` import; show iterating `response.content`.
- **secrets.md**: `resolve_api_key` resolution order (keyring → env), `set_key`/`get_key`/`has_key`/`delete_key`, `mask_key`, qualified service name `llm-pycascade/<provider>`.
- **error-handling.md**: `ProviderError` variants (http/request/parse/missing_api_key/other), `http_status`/`retry_after_seconds` props, `CascadeError` + failed-prompt path.
- **changelog.md**: initial "v0.1.0 — initial release" entry; link to GitHub Releases.

---

## Validation (run before finishing)
1. Create an isolated env and install docs deps + project:
   `uv pip install -r docs/requirements.txt && uv pip install -e .` (or `pip install -r docs/requirements.txt && pip install -e .`).
2. `mkdocs build --strict` from repo root — must pass with zero warnings (catches broken nav, bad `:::` refs, dead links).
3. `mkdocs serve` — spot-check nav, code highlighting, API reference rendering, dark/light toggle.
4. After push: RTD builds automatically on every push to `main`; confirm the build at the RTD dashboard. (The `rtd-publish.yml` release-trigger is an additional versioned-build trigger.)

## Risks / Gotchas
- If `mkdocs build --strict` fails on `:::` refs, confirm the module path is importable from `src` (griffe `paths: [src]`) — installing the package (`pip install -e .`) resolves this.
- `extra.version.provider: mike` does nothing without `mike` installed; remove it if unused to keep config honest.
- Keep `mkdocs.yml` at repo root (NOT in `docs/`) — `.readthedocs.yaml` already expects it there.

## Out of Scope
- Versioned docs hosting via `mike` (can be added later).
- PDF export.
- i18n / translations.
- Any source-code logic changes (doc-only, except the `.readthedocs.yaml` config edit).
