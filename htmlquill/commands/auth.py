"""Auth command group."""

from __future__ import annotations

import json
import os
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import click
import typer

from htmlquill.auth import (
    load_auth,
    redacted_auth_dict,
    resolve_auth,
    resolve_auth_path,
)
from htmlquill.config import (
    HtmlQuillConfig,
    load_config,
)
from htmlquill.fetch import FetchError
from htmlquill.reddit_oauth import (
    build_authorize_url,
    exchange_code_for_tokens,
    revoke_token,
)
from htmlquill.vault import (
    AuthVault,
    get_vault_password,
    load_auth_vault,
    redacted_profile_dict,
    redacted_vault_dict,
    resolve_auth_vault_path,
    save_auth_vault,
)

app = typer.Typer(help="Inspect and manage htmlquill auth profiles.")
vault_app = typer.Typer(help="Manage the encrypted auth vault.")
app.add_typer(vault_app, name="vault")

_AUTH_TEMPLATE = (
    "{\n"
    '  "version": 1,\n'
    '  "profiles": {\n'
    '    "reddit": {\n'
    '      "kind": "bearer_token",\n'
    '      "token_env": "REDDIT_BEARER_TOKEN"\n'
    "    },\n"
    '    "medium": {\n'
    '      "kind": "browser_state",\n'
    '      "playwright_storage_state": "~/.config/htmlquill/auth/'
    'medium.storage-state.json",\n'
    '      "chromium_user_data_dir": "~/.config/htmlquill/chromium/medium"\n'
    "    }\n"
    "  }\n"
    "}\n"
)


def _resolved_auth_path(
    *,
    auth_file: str | None,
    config: str | None,
) -> Path:
    cfg = load_config(Path(config).expanduser() if config else None)
    config_dir = cfg.source_path.parent if cfg.source_path is not None else None
    return resolve_auth_path(
        explicit_auth_path=auth_file,
        config_auth_path=cfg.auth_file,
        config_dir=config_dir,
    )


def _resolved_auth_vault_path(
    *,
    auth_vault_file: str | None,
    config: str | None,
) -> Path:
    cfg = load_config(Path(config).expanduser() if config else None)
    config_dir = cfg.source_path.parent if cfg.source_path is not None else None
    return resolve_auth_vault_path(
        explicit_vault_path=auth_vault_file,
        config_vault_path=cfg.auth_vault_file,
        config_dir=config_dir,
    )


def _load_config_or_default(config: str | None) -> HtmlQuillConfig:
    return load_config(Path(config).expanduser() if config else None)


@app.command("path")
def auth_path(
    auth_file: str | None = typer.Option(None, "--auth-file"),
    config: str | None = typer.Option(None, "--config"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Print the resolved auth file path."""

    path = _resolved_auth_path(auth_file=auth_file, config=config)
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "auth_path": str(path),
                    "exists": path.exists(),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        typer.echo(path)


@app.command("show")
def auth_show(
    profile: str | None = typer.Option(None, "--profile"),
    auth_file: str | None = typer.Option(None, "--auth-file"),
    config: str | None = typer.Option(None, "--config"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show redacted auth profile metadata."""

    path = _resolved_auth_path(auth_file=auth_file, config=config)
    if not path.exists():
        raise click.ClickException(f"auth file not found: {path}")

    store = load_auth(path, strict_permissions=False)

    if profile:
        resolved = resolve_auth(store, profile_name=profile)
        payload: dict[str, object] = {
            "auth_path": str(path),
            "profile": profile,
            "data": redacted_auth_dict(resolved),
        }
    else:
        profiles: dict[str, object] = {}
        for profile_name in sorted(store.profiles):
            profiles[profile_name] = redacted_auth_dict(
                resolve_auth(store, profile_name=profile_name)
            )
        payload = {
            "auth_path": str(path),
            "profiles": profiles,
        }

    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@app.command("init")
def auth_init(
    auth_file: str | None = typer.Option(None, "--auth-file"),
    config: str | None = typer.Option(None, "--config"),
    force: bool = typer.Option(False, "--force"),
    print_only: bool = typer.Option(False, "--print"),
) -> None:
    """Initialize an auth.json skeleton."""

    path = _resolved_auth_path(auth_file=auth_file, config=config)
    if print_only:
        typer.echo(_AUTH_TEMPLATE, nl=False)
        return

    if path.exists() and not force:
        raise click.ClickException(
            f"auth file already exists: {path} (use --force to overwrite)"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_AUTH_TEMPLATE, encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)
    typer.echo(f"wrote auth template to {path}")


# --- Vault subcommands ---


@vault_app.command("path")
def vault_path(
    auth_vault_file: str | None = typer.Option(None, "--auth-vault-file"),
    config: str | None = typer.Option(None, "--config"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Print the resolved auth vault file path."""
    path = _resolved_auth_vault_path(auth_vault_file=auth_vault_file, config=config)
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "auth_vault_path": str(path),
                    "exists": path.exists(),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        typer.echo(path)


@vault_app.command("show")
def vault_show(
    profile: str | None = typer.Option(None, "--profile"),
    auth_vault_file: str | None = typer.Option(None, "--auth-vault-file"),
    config: str | None = typer.Option(None, "--config"),
    redacted: bool = typer.Option(True, "--redacted/--no-redacted"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show auth vault contents (redacted by default)."""
    path = _resolved_auth_vault_path(auth_vault_file=auth_vault_file, config=config)
    if not path.exists():
        raise click.ClickException(f"auth vault not found: {path}")

    vault = load_auth_vault(path, prompt=True)

    if profile:
        if profile not in vault.profiles:
            raise click.ClickException(f"profile {profile!r} not found in auth vault")
        if redacted:
            payload: dict[str, object] = {
                "auth_vault_path": str(path),
                "profile": redacted_profile_dict(vault.profiles[profile]),
            }
        else:
            p = vault.profiles[profile]
            payload = {
                "auth_vault_path": str(path),
                "profile": {"name": p.name, "kind": p.kind, **p.data},
            }
    else:
        if redacted:
            payload = redacted_vault_dict(vault)
        else:
            payload = {
                "version": vault.version,
                "source_path": str(vault.source_path),
                "profiles": {
                    name: {"name": p.name, "kind": p.kind, **p.data}
                    for name, p in vault.profiles.items()
                },
            }

    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


# --- OAuth login/logout ---


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth callback code and state."""

    captured_code: str | None = None
    captured_state: str | None = None
    captured_error: str | None = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "error" in params:
            _OAuthCallbackHandler.captured_error = params.get("error", ["unknown"])[0]
            self._respond(400, "Authorization denied.")
            return

        code_list = params.get("code", [])
        state_list = params.get("state", [])

        if not code_list:
            _OAuthCallbackHandler.captured_error = "No authorization code received."
            self._respond(400, "Missing authorization code.")
            return

        _OAuthCallbackHandler.captured_code = code_list[0]
        _OAuthCallbackHandler.captured_state = state_list[0] if state_list else None
        self._respond(200, "Authorization successful. You may close this window.")

    def _respond(self, status: int, message: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        pass  # suppress HTTP server logs


def _run_local_callback_server(
    port: int, timeout: float = 120
) -> tuple[str | None, str | None]:
    """Run a local HTTP server to capture OAuth callback.

    Returns (code, state) or raises on error.
    """
    _OAuthCallbackHandler.captured_code = None
    _OAuthCallbackHandler.captured_state = None
    _OAuthCallbackHandler.captured_error = None

    server = HTTPServer(("127.0.0.1", port), _OAuthCallbackHandler)
    server.timeout = 1.0  # check every second

    elapsed = 0.0
    while elapsed < timeout:
        server.handle_request()
        if _OAuthCallbackHandler.captured_code:
            server.server_close()  # type: ignore[unreachable]
            return (
                _OAuthCallbackHandler.captured_code,
                _OAuthCallbackHandler.captured_state,
            )
        elif _OAuthCallbackHandler.captured_error:
            server.server_close()  # type: ignore[unreachable]
            raise click.ClickException(
                f"OAuth authorization error: {_OAuthCallbackHandler.captured_error}"
            )
        elapsed += 1.0

    server.server_close()
    raise click.ClickException("OAuth authorization timed out.")


@app.command("login")
def auth_login(
    provider: str = typer.Argument(..., help="Provider name (only 'reddit' supported)"),
    client_id: str | None = typer.Option(None, "--client-id"),
    client_secret: str | None = typer.Option(None, "--client-secret"),
    scope: str = typer.Option("read", "--scope"),
    redirect_port: int = typer.Option(8765, "--redirect-port"),
    config: str | None = typer.Option(None, "--config"),
    auth_vault_file: str | None = typer.Option(None, "--auth-vault-file"),
    force: bool = typer.Option(False, "--force"),
    print_url: bool = typer.Option(False, "--print-url"),
    manual_code: bool = typer.Option(False, "--manual-code"),
) -> None:
    """Login to a provider and store credentials securely in the auth vault."""
    if provider != "reddit":
        raise click.ClickException("only 'reddit' provider is supported for now")

    cfg = _load_config_or_default(config)
    user_agent = cfg.defaults.user_agent or "linux:htmlquill:v0.3.0"

    vault_path = _resolved_auth_vault_path(
        auth_vault_file=auth_vault_file, config=config
    )

    # Load existing vault if any.
    existing_vault: AuthVault | None = None
    if vault_path.exists():
        existing_vault = load_auth_vault(vault_path, prompt=True)
        if "reddit" in existing_vault.profiles and not force:
            raise click.ClickException(
                "reddit profile already exists in auth vault. Use --force to replace."
            )

    # Resolve client_id
    if not client_id:
        client_id = os.environ.get("REDDIT_CLIENT_ID", "")
    if not client_id:
        client_id = typer.prompt("Reddit app client ID")

    # Resolve client_secret (optional for installed apps)
    if client_secret is None and not os.environ.get("REDDIT_CLIENT_SECRET"):
        client_secret = typer.prompt(
            "Reddit app client secret (press Enter to skip)",
            default="",
            show_default=False,
        )
        if not client_secret:
            client_secret = None

    redirect_uri = f"http://127.0.0.1:{redirect_port}/callback"
    state = secrets.token_urlsafe(32)

    authorize_url = build_authorize_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=state,
        scope=scope,
        duration="permanent",
    )

    if print_url:
        typer.echo(f"Open this URL in your browser:\n{authorize_url}")
    else:
        typer.echo("Opening browser for Reddit authorization...")
        webbrowser.open(authorize_url)

    if manual_code:
        code = typer.prompt("Paste the authorization code from the browser")
        returned_state = None
    else:
        typer.echo(f"Waiting for authorization callback on {redirect_uri} ...")
        code, returned_state = _run_local_callback_server(redirect_port)
        if returned_state is not None and returned_state != state:
            raise click.ClickException(
                "OAuth state mismatch: possible CSRF attack. Aborting."
            )

    typer.echo("Exchanging authorization code for tokens...")
    try:
        tokens = exchange_code_for_tokens(
            client_id=client_id,
            client_secret=client_secret,
            code=code,
            redirect_uri=redirect_uri,
            user_agent=user_agent,
            timeout=30.0,
        )
    except FetchError as exc:
        raise click.ClickException(str(exc)) from exc

    now = int(__import__("time").time())

    # Build or update vault payload.
    vault_payload: dict[str, Any]
    if existing_vault is not None:
        vault_payload = {
            "version": existing_vault.version,
            "profiles": {},
        }
        for name, profile in existing_vault.profiles.items():
            vault_payload["profiles"][name] = {
                "kind": profile.kind,
                **profile.data,
            }
    else:
        vault_payload = {"version": 1, "profiles": {}}

    vault_payload["profiles"]["reddit"] = {
        "kind": "reddit_oauth",
        "client_id": client_id,
        "client_secret": client_secret,
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_at": int(now + (tokens.expires_in or 3600)),
        "scope": tokens.scope,
        "token_type": tokens.token_type,
        "created_at": now,
        "updated_at": now,
    }

    # Prompt for vault password.
    password = get_vault_password("HtmlQuill vault password: ")
    confirm = get_vault_password("Confirm HtmlQuill vault password: ")
    if password != confirm:
        raise click.ClickException("Vault passwords do not match.")

    save_auth_vault(vault_path, vault_payload, password=password)
    typer.echo(f"Saved encrypted Reddit profile 'reddit' to {vault_path}")


@app.command("logout")
def auth_logout(
    provider: str = typer.Argument(..., help="Provider name (only 'reddit' supported)"),
    config: str | None = typer.Option(None, "--config"),
    auth_vault_file: str | None = typer.Option(None, "--auth-vault-file"),
    force: bool = typer.Option(
        False,
        "--force",
        help="Remove profile even if revocation fails.",
    ),
) -> None:
    """Logout from a provider and remove credentials from the auth vault."""
    if provider != "reddit":
        raise click.ClickException("only 'reddit' provider is supported for now")

    vault_path = _resolved_auth_vault_path(
        auth_vault_file=auth_vault_file, config=config
    )

    if not vault_path.exists():
        raise click.ClickException(f"auth vault not found: {vault_path}")

    vault = load_auth_vault(vault_path, prompt=True)

    if "reddit" not in vault.profiles:
        raise click.ClickException("reddit profile not found in auth vault")

    profile = vault.profiles["reddit"]
    client_id = profile.data.get("client_id", "")
    client_secret = profile.data.get("client_secret")
    access_token = profile.data.get("access_token", "")
    refresh_token = profile.data.get("refresh_token", "")

    cfg = _load_config_or_default(config)
    user_agent = cfg.defaults.user_agent or "linux:htmlquill:v0.3.0"

    # Try to revoke tokens.
    revocation_ok = True
    for token, hint in [
        (access_token, "access_token"),
        (refresh_token, "refresh_token"),
    ]:
        if not token or not isinstance(token, str) or not token.strip():
            continue
        try:
            revoke_token(
                client_id=str(client_id),
                client_secret=client_secret if isinstance(client_secret, str) else None,
                token=str(token),
                token_type_hint=hint,
                user_agent=user_agent,
                timeout=30.0,
            )
        except FetchError:
            revocation_ok = False
            typer.echo(
                f"Warning: failed to revoke {hint}. Network may be unavailable.",
                err=True,
            )

    if not revocation_ok and not force:
        raise click.ClickException(
            "Token revocation failed. Use --force to remove the local profile anyway."
        )

    # Remove profile from vault.
    vault_payload: dict[str, Any] = {
        "version": vault.version,
        "profiles": {},
    }
    for name, p in vault.profiles.items():
        if name == "reddit":
            continue
        vault_payload["profiles"][name] = {"kind": p.kind, **p.data}

    password = get_vault_password("HtmlQuill vault password: ")
    save_auth_vault(vault_path, vault_payload, password=password)
    typer.echo(f"Removed Reddit profile 'reddit' from {vault_path}")
