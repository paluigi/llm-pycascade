# Installation

`llm-pycascade` requires **Python 3.10+**.

## pip

```bash
pip install llm-pycascade
```

## uv

```bash
uv add llm-pycascade
```

## With optional keyring support

Install the `[keyring]` extra to enable secure, OS-backed API key storage
(macOS Keychain, Windows Credential Manager, Freedesktop Secret Service):

```bash
pip install llm-pycascade[keyring]
```

```bash
uv add 'llm-pycascade[keyring]'
```

See [Secrets & keyring](secrets.md) for how the resolution order works.

## Development install

For contributing or building the docs locally:

```bash
git clone https://github.com/paluigi/llm-pycascade.git
cd llm-pycascade
uv sync --all-extras --dev
```

The documentation site can be built with:

```bash
pip install -r docs/requirements.txt
mkdocs serve
```
