# htmlquill

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
# Convert a URL
htmlquill https://example.com -o example.md

# Convert a local HTML file
htmlquill page.html -o page.md

# Read from stdin
cat page.html | htmlquill - > page.md

# Write to stdout (default when -o is omitted)
htmlquill page.html
```

### Config and auth examples

```bash
# Inspect effective config for a URL (with redacted auth details)
htmlquill --print-config https://example.com

# Use an explicit config file
htmlquill --config ./htmlquill.toml https://example.com -o page.md

# Use a browser profile for a protected site
htmlquill --browser chromium --profile medium https://medium.com/... -o article.md
```

### CLI options

| Option             | Description                                                          |
| ------------------ | -------------------------------------------------------------------- |
| `SOURCE`           | URL (`https://...`), HTML file path, or `-` for stdin                |
| `-o`, `--output`   | Output file path (default: stdout)                                   |
| `--timeout`        | HTTP timeout override in seconds                                     |
| `--user-agent`     | Custom HTTP User-Agent header                                        |
| `--browser`        | Fetching mode override: `auto`, `requests`, `playwright`, `chromium` |
| `--config PATH`    | Use this config file                                                 |
| `--no-config`      | Disable config loading                                               |
| `--auth-file PATH` | Use this auth file                                                   |
| `--no-auth`        | Disable auth loading                                                 |
| `--profile NAME`   | Force a named auth profile                                           |
| `--print-config`   | Print resolved effective URL config and exit                         |

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
browser = "auto"
timeout = 30.0
user_agent = "Mozilla/5.0 htmlquill/0.1"
fail_on_challenge = true
fallback_on_challenge = true

[paths]
auth_file = "~/.config/htmlquill/auth.json"

[challenge]
markers = [
  "Performing security verification",
  "verifies you are not a bot",
]

[sites."medium.com"]
browser = "chromium"
timeout = 60.0
auth = "medium"
```

## Auth file

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

### Security notes

- `auth.json` contains sensitive session material.
- Recommended permissions: `chmod 600 ~/.config/htmlquill/auth.json`.
- Do not commit auth files, storage-state files, or browser profile dirs.
- Prefer environment variables for tokens.

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
