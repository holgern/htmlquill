Authentication
==============

HtmlQuill supports browser-state auth profiles through ``auth.json``.

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

Security notes
--------------

- Do not commit ``auth.json``, storage-state files, or browser profile
  directories.
- Recommended permissions: ``chmod 600 ~/.config/htmlquill/auth.json``.
- Recommended browser profile directory permissions: ``chmod 700 ~/.config/htmlquill/chromium/medium``.
