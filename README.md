# htmlquill

Convert HTML or a URL to Markdown.

## Installation

```bash
pip install htmlquill
```

Encrypted auth vault support, used by `htmlquill auth login reddit`, requires the secure extra:

```bash
pip install "htmlquill[secure]"
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
htmlquill auth vault path

# Login to Reddit and store OAuth tokens in the encrypted vault
htmlquill auth login reddit --client-id YOUR_REDDIT_CLIENT_ID

# Inspect redacted vault metadata
htmlquill auth vault show --profile reddit

# Diagnose Reddit API conversion setup
htmlquill doctor --url "https://www.reddit.com/r/SUB/comments/POST_ID/title/" --profile reddit

# Count generated Markdown structure
htmlquill analyse example.md

# Preview Markdown in the terminal
htmlquill preview example.md
```

`htmlquill SOURCE` is retained as shorthand for `htmlquill convert SOURCE`; it now follows the same auto-save behavior unless `--stdout` is used.

### Command overview

- `htmlquill convert SOURCE [options]`
- `htmlquill config path|show|init|validate`
- `htmlquill auth path|show|init|login|logout`
- `htmlquill auth vault path|show`
- `htmlquill doctor [--url URL] [--fetch] [--json] [--strict]`
- `htmlquill analyse SOURCE` (alias: `htmlquill analyze SOURCE`)
- `htmlquill preview SOURCE`

### Convert options

| Option                     | Description                                                                                |
| -------------------------- | ------------------------------------------------------------------------------------------ |
| `SOURCE`                   | URL (`https://...`), HTML file path, or `-` for stdin                                     |
| `-o`, `--output PATH`      | Manual output file path. Overrides generated filename.                                     |
| `--stdout`                 | Print converted Markdown to stdout and do not save.                                        |
| `--filename-only`          | Print resolved output filename and do not save.                                            |
| `--filename-max-length N`  | Max generated filename stem length, excluding `.md`. Default: `80`.                        |
| `--output-dir DIR`         | Directory for generated output files. Default: current directory.                          |
| `--force`                  | Overwrite generated output target instead of adding a numeric suffix.                      |
| `--timeout`                | HTTP timeout override in seconds                                                           |
| `--user-agent`             | Custom HTTP User-Agent header                                                              |
| `--browser`                | Fetching mode override: `auto`, `requests`, `playwright`, `chromium`                       |
| `--config PATH`            | Use this config file                                                                       |
| `--no-config`              | Disable config loading                                                                     |
| `--auth-file PATH`         | Use this auth file                                                                         |
| `--no-auth`                | Disable auth loading                                                                       |
| `--profile NAME`           | Force a named auth profile                                                                 |
| `--print-config`           | Deprecated; use `htmlquill config show URL`                                                |
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
# Set this if you want OAuth token exchange to use the same descriptive UA.
# user_agent = "linux:htmlquill:v0.3.0 (by /u/YOUR_REDDIT_USERNAME)"
fail_on_challenge = true
fallback_on_challenge = true

[paths]
auth_file = "~/.config/htmlquill/auth.json"
auth_vault_file = "~/.config/htmlquill/auth.vault"

[challenge]
markers = [
  "Performing security verification",
  "verifies you are not a bot",
  "You've been blocked by network security",
  "blocked by network security",
  "If you think you've been blocked by mistake, file a ticket",
  "Please try to login with your Reddit account",
]

[sites."medium.com"]
browser = "chromium"
timeout = 60.0
auth = "medium"

[sites."reddit.com"]
adapter = "reddit_api"
auth = "reddit"
timeout = 30.0
user_agent = "linux:htmlquill:v0.3.0 (by /u/YOUR_REDDIT_USERNAME)"
```

For Reddit, `auth = "reddit"` binds matching Reddit URLs to the vault profile created by `htmlquill auth login reddit`. The `reddit_api` adapter avoids Reddit's regular HTML pages and uses `oauth.reddit.com`, which is much less likely to return the network-security interstitial HTML that normal scraping receives.

## Authentication

HtmlQuill supports two auth backends:

1. **Encrypted auth vault** (`auth.vault`) for OAuth tokens. This is the recommended backend for Reddit login.
2. **Legacy JSON auth file** (`auth.json`) for environment-token and browser-state profiles.

### Encrypted auth vault

The encrypted vault is used by `htmlquill auth login reddit`. It stores OAuth tokens in `~/.config/htmlquill/auth.vault` by default and is encrypted with VaultConfig.

Install support:

```bash
pip install "htmlquill[secure]"
```

Useful commands:

```bash
htmlquill auth vault path
htmlquill auth vault show
htmlquill auth vault show --profile reddit
```

Vault path resolution order:

1. `--auth-vault-file PATH`
2. `HTMLQUILL_VAULT_FILE`
3. `[paths].auth_vault_file` from config
4. `$XDG_CONFIG_HOME/htmlquill/auth.vault` or `~/.config/htmlquill/auth.vault`

Vault password resolution order:

1. `HTMLQUILL_VAULT_PASSWORD`
2. `HTMLQUILL_VAULT_PASSWORD_COMMAND`
3. `VAULTCONFIG_PASSWORD`
4. `VAULTCONFIG_PASSWORD_COMMAND`
5. interactive password prompt

For interactive use, let HtmlQuill ask for the vault password. For password-manager integration, prefer a command such as:

```bash
export HTMLQUILL_VAULT_PASSWORD_COMMAND='pass show htmlquill/vault'
```

Do not commit `auth.vault`. On POSIX systems the file should be mode `0600`.

### Legacy auth.json

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
    "reddit": {
      "kind": "bearer_token",
      "token_env": "REDDIT_BEARER_TOKEN"
    },
    "medium": {
      "kind": "browser_state",
      "playwright_storage_state": "~/.config/htmlquill/auth/medium.storage-state.json",
      "chromium_user_data_dir": "~/.config/htmlquill/chromium/medium"
    }
  }
}
```

Use `auth.json` for browser state profiles or manual bearer-token setups. Prefer the encrypted vault for Reddit OAuth login.

- Do not commit auth files, storage-state files, or browser profile dirs.
- Recommended permissions: `chmod 600 ~/.config/htmlquill/auth.json`.

## Reddit login and conversion

Reddit's normal HTML pages may return a network-security block page to non-browser fetchers. For Reddit comments URLs, use HtmlQuill's `reddit_api` adapter with OAuth.

### 1. Install secure auth support

```bash
pip install "htmlquill[secure]"
```

### 2. Configure Reddit defaults

Create or update `~/.config/htmlquill/config.toml`:

```bash
htmlquill config init
```

Set the Reddit site config:

```toml
[paths]
auth_vault_file = "~/.config/htmlquill/auth.vault"

[sites."reddit.com"]
adapter = "reddit_api"
auth = "reddit"
timeout = 30.0
user_agent = "linux:htmlquill:v0.3.0 (by /u/YOUR_REDDIT_USERNAME)"
```

Use your real Reddit username or project contact in the `User-Agent`.

### 3. Create a Reddit app

Create a Reddit app in Reddit's app preferences/developer app page. For HtmlQuill's default local callback, set the redirect URI exactly to:

```text
http://127.0.0.1:8765/callback
```

Copy the client ID. If your Reddit app has a client secret, copy that too. If it is an installed/non-confidential app, it may not have a secret; HtmlQuill allows the secret to be blank.

### 4. Login

```bash
htmlquill auth login reddit --client-id YOUR_REDDIT_CLIENT_ID
```

If your app has a secret:

```bash
htmlquill auth login reddit \
  --client-id YOUR_REDDIT_CLIENT_ID \
  --client-secret YOUR_REDDIT_CLIENT_SECRET
```

You can also use environment variables:

```bash
export REDDIT_CLIENT_ID='...'
export REDDIT_CLIENT_SECRET='...'   # optional
htmlquill auth login reddit
```

The command opens Reddit in your browser, asks you to authorize the app, receives the callback on `127.0.0.1:8765`, then writes an encrypted `reddit` profile to `auth.vault`. HtmlQuill stores OAuth tokens, not your Reddit password.

For headless environments:

```bash
htmlquill auth login reddit \
  --client-id YOUR_REDDIT_CLIENT_ID \
  --print-url \
  --manual-code
```

Open the printed URL manually. After Reddit redirects to the local callback URL, copy the `code=...` query parameter from the browser address bar and paste it into HtmlQuill.

### 5. Verify

```bash
htmlquill auth vault show --profile reddit
htmlquill config show "https://www.reddit.com/r/ObsidianMD/comments/1q2b6fp/title/" --profile reddit
htmlquill doctor --url "https://www.reddit.com/r/ObsidianMD/comments/1q2b6fp/title/" --profile reddit
```

The doctor output should report:

- `reddit:adapter` uses `reddit_api`
- `reddit:token` is available from the encrypted vault
- `reddit:user_agent` is configured

### 6. Convert a Reddit thread

```bash
htmlquill convert \
  "https://www.reddit.com/r/ObsidianMD/comments/1q2b6fp/my_comprehensive_obsidian_setup_web_clipper_bases/" \
  -o reddit-thread.md
```

HtmlQuill will ask for the vault password when it needs to decrypt `auth.vault`.

### Logout or replace credentials

```bash
htmlquill auth logout reddit
htmlquill auth login reddit --force --client-id YOUR_REDDIT_CLIENT_ID
```

`logout` attempts to revoke stored access and refresh tokens, then removes the local `reddit` profile from the vault.

### Reddit troubleshooting

**`secure auth requires VaultConfig`**

Install the secure extra:

```bash
pip install "htmlquill[secure]"
```

**`OAuth authorization timed out`**

The browser did not complete the local callback. Check that the Reddit app redirect URI exactly matches `http://127.0.0.1:8765/callback`, or retry with `--print-url --manual-code`.

**`invalid_grant` or redirect mismatch**

The redirect URI in the Reddit app must exactly match the URI generated by HtmlQuill. If you pass `--redirect-port 9999`, configure Reddit with `http://127.0.0.1:9999/callback`.

**`reddit profile already exists in auth vault`**

Use `--force` to replace it:

```bash
htmlquill auth login reddit --force --client-id YOUR_REDDIT_CLIENT_ID
```

**`Reddit API adapter requires a bearer token`**

Run `htmlquill auth login reddit`, verify the vault with `htmlquill auth vault show --profile reddit`, and make sure `[sites."reddit.com"].auth = "reddit"` is configured.

**`Reddit API adapter requires a descriptive User-Agent`**

Set:

```toml
[sites."reddit.com"]
user_agent = "linux:htmlquill:v0.3.0 (by /u/YOUR_REDDIT_USERNAME)"
```

**Still seeing Reddit network-security HTML**

Run:

```bash
htmlquill config show URL --profile reddit
```

Confirm `adapter` is `reddit_api`. The adapter currently supports Reddit comments URLs only. Other Reddit pages may still use the normal HTML fetch path.

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
