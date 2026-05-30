# htmlquill

Convert HTML or a URL to Markdown.

## Installation

```bash
pip install htmlquill
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

### CLI options

| Option           | Description                                                                      |
| ---------------- | -------------------------------------------------------------------------------- |
| `SOURCE`         | URL (`https://...`), HTML file path, or `-` for stdin                            |
| `-o`, `--output` | Output file path (default: stdout)                                               |
| `--timeout`      | HTTP timeout in seconds (default: 20)                                            |
| `--user-agent`   | Custom HTTP User-Agent header                                                    |
| `--browser`      | Fetching mode: `auto`, `requests`, `playwright`, or `chromium` (default: `auto`) |

### Browser modes

```bash

# Requests-only mode (recommended for Termux / minimal installs)
htmlquill --browser requests https://example.com -o page.md

# Use an installed Chromium executable without Playwright
htmlquill --browser chromium https://example.com -o page.md

# Use Playwright (requires pip install htmlquill[browser])
htmlquill --browser playwright https://example.com -o page.md
```

### Browser mode details

- **`auto`** (default): tries `requests` first; on HTTP 403, falls back to
  system Chromium if available, then Playwright if installed.
- **`requests`**: plain HTTP via the _requests_ library. No browser needed.
  Recommended for Termux and minimal environments.
- **`chromium`**: uses a system-installed Chromium executable via subprocess.
  No Playwright package required. Searches for `chromium`, `chromium-browser`,
  `google-chrome`, or `google-chrome-stable` on `PATH`.
- **`playwright`**: uses headless Chromium via the Playwright Python package.
  Requires `pip install htmlquill[browser] && playwright install chromium`.

Playwright is **optional**. For Termux or minimal installs, use
`--browser requests` or `--browser chromium`.

## Library usage

```python
from htmlquill import html_to_markdown, url_to_markdown

# Convert HTML string
markdown = html_to_markdown("<h1>Hello</h1><p>World</p>")

# Convert with base URL for link resolution
markdown = html_to_markdown(
    '<p><a href="/docs">Docs</a></p>',
    base_url="https://example.com",
)

# Fetch and convert a URL
markdown = url_to_markdown("https://example.com")
```

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
```
