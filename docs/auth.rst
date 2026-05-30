Authentication
==============

HtmlQuill supports two auth backends:

1. **Encrypted auth vault** (``auth.vault``) for OAuth tokens. This is the
   recommended backend for Reddit login.
2. **Legacy JSON auth file** (``auth.json``) for environment-token and
   browser-state profiles.

Encrypted auth vault
--------------------

The encrypted vault is used by ``htmlquill auth login reddit``. It stores
OAuth tokens in ``~/.config/htmlquill/auth.vault`` by default and is encrypted
with VaultConfig.

Install support:

.. code-block:: bash

   pip install "htmlquill[secure]"

Useful commands:

.. code-block:: bash

   htmlquill auth vault path
   htmlquill auth vault show
   htmlquill auth vault show --profile reddit

Vault path resolution order
~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. ``--auth-vault-file PATH``
2. ``HTMLQUILL_VAULT_FILE``
3. ``[paths].auth_vault_file`` from config
4. ``$XDG_CONFIG_HOME/htmlquill/auth.vault`` or
   ``~/.config/htmlquill/auth.vault``

Vault password resolution order
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. ``HTMLQUILL_VAULT_PASSWORD``
2. ``HTMLQUILL_VAULT_PASSWORD_COMMAND``
3. ``VAULTCONFIG_PASSWORD``
4. ``VAULTCONFIG_PASSWORD_COMMAND``
5. interactive password prompt

For interactive use, let HtmlQuill ask for the vault password. For
password-manager integration, prefer a command such as:

.. code-block:: bash

   export HTMLQUILL_VAULT_PASSWORD_COMMAND='pass show htmlquill/vault'

Security notes
~~~~~~~~~~~~~~

- Do not commit ``auth.vault``. On POSIX systems the file should be mode
  ``0600``.
- Prefer a password command over a plain environment variable to avoid
  leaving the password in shell history.
- ``auth vault show`` redacts secrets by default.

Reddit login and logout
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   htmlquill auth login reddit --client-id YOUR_REDDIT_CLIENT_ID

See :doc:`reddit` for the complete Reddit login quickstart.

.. code-block:: bash

   htmlquill auth logout reddit

``logout`` attempts to revoke stored access and refresh tokens, then removes
the local ``reddit`` profile from the vault.

Legacy auth.json
----------------

Auth file resolution order:

1. ``--auth-file PATH``
2. ``HTMLQUILL_AUTH``
3. ``[paths].auth_file`` from config
4. ``$XDG_CONFIG_HOME/htmlquill/auth.json`` or
   ``~/.config/htmlquill/auth.json``

Example ``auth.json``:

.. code-block:: json

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

Use ``auth.json`` for browser state profiles or manual bearer-token setups.
Prefer the encrypted vault for Reddit OAuth login.
