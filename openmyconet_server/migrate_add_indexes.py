"""OBSOLET -- Schema-Migrationen laufen seit 2026-09 ueber Alembic
(`flask db upgrade`, siehe migrations/ und CLAUDE.md).

No-op-Stub, damit aeltere, auf dem Server bereits ausgerollte Deploy-Skript-
Kopien nicht mit "file not found" abbrechen. Kann geloescht werden, sobald
ueberall die neuen Deploy-Skripte laufen.
"""


def main():
    print('migrate_add_indexes.py: obsolet -- Indizes kommen ueber Alembic (flask db upgrade).')


if __name__ == '__main__':
    main()
