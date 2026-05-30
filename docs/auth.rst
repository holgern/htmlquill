Authentication
==============

HtmlQuill supports two auth backends:

1. **Encrypted auth vault** (``auth.vault``) for encrypted generic secret storage.
2. **JSON auth file** (``auth.json``) for browser-state profiles.

Encrypted auth vault
--------------------

The encrypted vault stores secrets in ``~/.config/htmlquill/auth.vault`` by default and is encrypted with VaultConfig.

Install support:

.. code-block:: bash

   pip install "htmlquill[secure]"

Useful commands:

.. code-block:: bash

   htmlquill auth vault path
   htmlquill auth vault show

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

Security notes
~~~~~~~~~~~~~~

- Do not commit ``auth.vault``. On POSIX systems the file should be mode
  ``0600``.
- Prefer a password command over a plain environment variable to avoid
  leaving the password in shell history.
- ``auth vault show`` redacts secrets by default.

JSON auth file
--------------

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
       "medium": {
         "kind": "browser_state",
         "playwright_storage_state": "~/.config/htmlquill/auth/medium.storage-state.json",
         "chromium_user_data_dir": "~/.config/htmlquill/chromium/medium"
       }
     }
   }
