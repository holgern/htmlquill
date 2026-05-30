Configuration
=============

HtmlQuill resolves configuration files in this order:

1. ``--config PATH``
2. ``HTMLQUILL_CONFIG``
3. ``$XDG_CONFIG_HOME/htmlquill/config.toml``
4. ``~/.config/htmlquill/config.toml``

Example ``config.toml``
-----------------------

.. code-block:: toml

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

Sections
--------

``defaults``
    Global defaults for all sites. ``browser`` can be ``auto``, ``requests``,
    ``playwright``, or ``chromium``.

``paths``
    Override the default auth file and auth vault file locations.

``challenge``
    ``markers`` is a list of substrings used to detect network-security
    challenge pages (CAPTCHA, block interstitial). When a match is found and
    ``fallback_on_challenge`` is true, HtmlQuill escalates from
    ``requests`` to a browser backend.

``sites``
    Per-site configuration keyed by hostname. Hostname keys must be quoted
    when they contain dots (``[sites."reddit.com"]``). Sites inherit from
    ``defaults`` and override specific keys.

    For Reddit, ``auth = "reddit"`` binds matching Reddit URLs to the
    vault profile created by ``htmlquill auth login reddit``. The
    ``reddit_api`` adapter avoids Reddit's regular HTML pages and uses
    ``oauth.reddit.com``, which is much less likely to return the
    network-security interstitial HTML that normal scraping receives.

Site matching
~~~~~~~~~~~~~

HtmlQuill matches a URL to a site section by the hostname. The site with the
longest matching hostname suffix wins. For example, a URL for
``www.reddit.com`` matches ``sites."reddit.com"``.

Commands
--------

- ``htmlquill config init`` – write a default config file
- ``htmlquill config path`` – print the resolved config path
- ``htmlquill config show URL`` – display effective config for a URL
- ``htmlquill config validate`` – validate config syntax
