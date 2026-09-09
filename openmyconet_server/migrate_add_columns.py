"""OBSOLET -- Schema-Migrationen laufen seit 2026-09 ueber Alembic
(`flask db upgrade`, siehe migrations/ und CLAUDE.md).

Diese Datei ist nur noch ein No-op-Stub, damit aeltere, auf dem Server bereits
ausgerollte Deploy-Skript-Kopien (release.sh / deploy_staging.sh vor der
Umstellung) nicht mit "file not found" abbrechen. Kann geloescht werden, sobald
ueberall die neuen Deploy-Skripte laufen.

WICHTIG: hier NICHTS mehr tun -- die frueheren Zeilen legten u. a.
`nutzer.rolle` + `ix_nutzer_login_token` an, die Alembic gerade entfernt hat.
"""


def main():
    print('migrate_add_columns.py: obsolet -- Migrationen laufen ueber Alembic (flask db upgrade).')


if __name__ == '__main__':
    main()
