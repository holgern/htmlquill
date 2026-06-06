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

Sections
--------

``defaults``
    Global defaults for all sites. ``browser`` can be ``auto``, ``requests``,
    ``playwright``, or ``chromium``.

``paths``
    Override the default auth file location.

``challenge``
    ``markers`` is a list of substrings used to detect network-security
    challenge pages (CAPTCHA, block interstitial). When a match is found and
    ``fallback_on_challenge`` is true, HtmlQuill escalates from
    ``requests`` to a browser backend.

``sites``
    Per-site configuration keyed by hostname. Hostname keys must be quoted
    when they contain dots (``[sites."medium.com"]``). Sites inherit from
    ``defaults`` and override specific keys. Prefer the default ``auto`` mode
    when normal HTTP fetching returns complete content. Forced browser mode can
    time out on pages that keep background connections open.

Site matching
~~~~~~~~~~~~~

HtmlQuill matches a URL to a site section by the hostname. The site with the
longest matching hostname suffix wins.

Commands
--------

- ``htmlquill config init`` – write a default config file
- ``htmlquill config path`` – print the resolved config path
- ``htmlquill config show URL`` – display effective config for a URL
- ``htmlquill config validate`` – validate config syntax
