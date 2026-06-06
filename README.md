[![PyPI - Version](https://img.shields.io/pypi/v/htmlquill)](https://pypi.org/project/htmlquill/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/htmlquill)
![PyPI - Downloads](https://img.shields.io/pypi/dm/htmlquill)
[![codecov](https://codecov.io/gh/holgern/htmlquill/graph/badge.svg?token=qJDpB7ej1T)](https://codecov.io/gh/holgern/htmlquill)

# HtmlQuill

Convert HTML or a URL to Markdown.

## Installation

```bash
pip install htmlquill
```

Optional Playwright backend:

```bash
pip install "htmlquill[browser]"
playwright install chromium
```

## CLI usage

```bash
# Auto-save using the first Markdown heading
htmlquill convert https://example.com/article

# Manual output path
htmlquill convert https://example.com/article -o article.md

# Preview generated filename without saving
htmlquill convert https://example.com/article --filename-only

# Print Markdown content without saving
htmlquill convert https://example.com/article --stdout

# Save generated filename to a target directory
htmlquill convert https://example.com/article --output-dir notes

# Limit generated filename stem length
htmlquill convert https://example.com/article --filename-max-length 60

# Inspect effective config
htmlquill config show https://example.com

# Initialize config and inspect paths
htmlquill config init
htmlquill config path

# Run diagnostics
htmlquill doctor

# Count generated Markdown structure
htmlquill analyse example.md

# Preview Markdown in the terminal
htmlquill preview example.md
```

`htmlquill SOURCE` is retained as shorthand for `htmlquill convert SOURCE`; it now follows the same auto-save behavior unless `--stdout` is used.

### Command overview

- `htmlquill convert SOURCE [options]`
- `htmlquill config path|show|init|validate`
- `htmlquill auth path|show|init`
- `htmlquill doctor [--url URL] [--fetch] [--json] [--strict]`
- `htmlquill analyse SOURCE` (alias: `htmlquill analyze SOURCE`)
- `htmlquill preview SOURCE`

### Convert options

| Option                    | Description                                                           |
| ------------------------- | --------------------------------------------------------------------- |
| `SOURCE`                  | URL (`https://...`), HTML file path, or `-` for stdin                 |
| `-o`, `--output PATH`     | Manual output file path. Overrides generated filename.                |
| `--stdout`                | Print converted Markdown to stdout and do not save.                   |
| `--filename-only`         | Print resolved output filename and do not save.                       |
| `--filename-max-length N` | Max generated filename stem length, excluding `.md`. Default: `80`.   |
| `--output-dir DIR`        | Directory for generated output files. Default: current directory.     |
| `--force`                 | Overwrite generated output target instead of adding a numeric suffix. |
| `--timeout`               | HTTP timeout override in seconds                                      |
| `--user-agent`            | Custom HTTP User-Agent header                                         |
| `--browser`               | Fetching mode override: `auto`, `requests`, `playwright`, `chromium`  |
| `--config PATH`           | Use this config file                                                  |
| `--no-config`             | Disable config loading                                                |
| `--auth-file PATH`        | Use this auth file                                                    |
| `--no-auth`               | Disable auth loading                                                  |
| `--profile NAME`          | Force a named auth profile                                            |
| `--print-config`          | Deprecated; use `htmlquill config show URL`                           |

### Browser mode details

- **`auto`** (default): tries `requests` first; on HTTP 403 or detected challenge page, falls back to system Chromium, then Playwright.
- **`requests`**: plain HTTP via `requests`.
- **`chromium`**: uses system Chromium via subprocess.
- **`playwright`**: uses Playwright Chromium (optional dependency).

## Configuration files

`htmlquill` resolves config file paths in this order:

1. `--config PATH`
2. `HTMLQUILL_CONFIG`
3. `$XDG_CONFIG_HOME/htmlquill/config.toml`
4. `~/.config/htmlquill/config.toml`

Example `config.toml`:

```toml
version = 1

[defaults]
adapter = "html"
browser = "auto"
timeout = 30.0
fail_on_challenge = true
fallback_on_challenge = true

[paths]
auth_file = "~/.config/htmlquill/auth.json"

[challenge]
markers = [
  "Performing security verification",
  "verifies you are not a bot",
  "You've been blocked by network security",
  "blocked by network security",
  "If you think you've been blocked by mistake, file a ticket",
]

# Browser-backed authentication is opt-in. Add a site rule only when needed:
#
# [sites."example.com"]
# browser = "chromium"
# timeout = 60.0
# auth = "example"
```

Do not force browser mode for sites that return complete article HTML to normal
HTTP clients. For example, Medium articles usually work with the default
`auto` mode; forcing Chromium can be slower and can time out on pages that keep
background connections open.

## Authentication

HtmlQuill supports browser-state auth profiles through `auth.json`.
Use this when a site works in an already-authenticated browser session and you want HtmlQuill to reuse that state.

Auth file resolution order:

1. `--auth-file PATH`
2. `HTMLQUILL_AUTH`
3. `[paths].auth_file` from config
4. `$XDG_CONFIG_HOME/htmlquill/auth.json` or `~/.config/htmlquill/auth.json`

Example `auth.json`:

```json
{
  "version": 1,
  "profiles": {
    "medium": {
      "kind": "browser_state",
      "playwright_storage_state": "~/.config/htmlquill/auth/medium.storage-state.json",
      "chromium_user_data_dir": "~/.config/htmlquill/chromium/medium"
    }
  }
}
```

Security notes:

- Do not commit auth files, storage-state files, or browser profile directories.
- Recommended permissions: `chmod 600 ~/.config/htmlquill/auth.json`.
- Recommended browser profile directory permissions: `chmod 700 ~/.config/htmlquill/chromium/medium`.

## Reddit

HtmlQuill no longer ships a Reddit API/OAuth adapter. Reddit URLs are processed through the normal HTML fetch path, the same as other URLs. If Reddit returns a network-security or login interstitial, use a browser-based fetch profile, retry later, or export/save the page manually. `htmlquill auth login reddit` is intentionally not available.

## Library usage

```python
from htmlquill import html_to_markdown, url_to_markdown

markdown = html_to_markdown("<h1>Hello</h1><p>World</p>")

markdown = url_to_markdown("https://example.com")

# New optional controls (all optional)
markdown = url_to_markdown(
    "https://example.com",
    browser="requests",
    config=True,
    auth=False,
)
```

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
```
