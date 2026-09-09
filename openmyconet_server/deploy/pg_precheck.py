"""Vorprüfung vor dem Postgres-Cutover (Postgres-Block-Plan Schritt 3, Phase 0).

Liest die aktuelle SQLite-DB **read-only** und prüft, was Postgres erzwingt und
SQLite bisher ignoriert hat:

  1. VARCHAR(n)-Overflow -- ein Wert länger als die Modell-Länge
  2. news.slug-Duplikate (die PG-Baseline hat UNIQUE(slug))
  3. verwaiste Fremdschlüssel (nutzer_id/knoten_id/... zeigt ins Leere) --
     PG erzwingt die FKs, SQLite tat es mangels PRAGMA foreign_keys=ON nicht
  4. NULL in einer nullable=False-Spalte

Kein Eingriff. Exit 0 = sauber, Exit 1 = Befunde (Details im Bericht).

Aufruf auf dem Server:  cd /home/omn/app && venv/bin/python deploy/pg_precheck.py
"""
import sqlite3
import sys


def main():
    import sqlalchemy as sa

    from omn import create_app
    from omn.extensions import db

    app = create_app()
    with app.app_context():
        db_pfad = db.engine.url.database
        tabellen = list(db.metadata.sorted_tables)

    con = sqlite3.connect(f'file:{db_pfad}?mode=ro', uri=True)
    vorhandene = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}

    befunde = []

    def q1(sql, *p):
        return con.execute(sql, p).fetchone()[0]

    for tab in tabellen:
        if tab.name not in vorhandene:
            print(f'  (Tabelle {tab.name} existiert in SQLite noch nicht -- übersprungen)')
            continue
        zeilen = q1(f'SELECT count(*) FROM "{tab.name}"')

        for col in tab.columns:
            # 1. String-Länge
            if isinstance(col.type, sa.String) and col.type.length:
                zu_lang = q1(
                    f'SELECT count(*) FROM "{tab.name}" '
                    f'WHERE length(CAST("{col.name}" AS TEXT)) > ?', col.type.length)
                if zu_lang:
                    maxlen = q1(f'SELECT max(length(CAST("{col.name}" AS TEXT))) FROM "{tab.name}"')
                    befunde.append(
                        f'{tab.name}.{col.name}: {zu_lang} Wert(e) länger als '
                        f'VARCHAR({col.type.length}) (max {maxlen})')

            # 4. NULL in NOT-NULL-Spalte
            if not col.nullable and not col.primary_key:
                nullen = q1(f'SELECT count(*) FROM "{tab.name}" WHERE "{col.name}" IS NULL')
                if nullen:
                    befunde.append(
                        f'{tab.name}.{col.name}: {nullen} NULL-Wert(e), Modell sagt NOT NULL')

        # 3. verwaiste FKs
        for fk in tab.foreign_keys:
            ziel_tab = fk.column.table.name
            ziel_col = fk.column.name
            quell_col = fk.parent.name
            if ziel_tab not in vorhandene:
                continue
            verwaist = q1(
                f'SELECT count(*) FROM "{tab.name}" q '
                f'WHERE q."{quell_col}" IS NOT NULL '
                f'AND NOT EXISTS (SELECT 1 FROM "{ziel_tab}" z '
                f'                WHERE z."{ziel_col}" = q."{quell_col}")')
            if verwaist:
                befunde.append(
                    f'{tab.name}.{quell_col}: {verwaist} Zeile(n) zeigen auf '
                    f'nicht existierende {ziel_tab}.{ziel_col}')

        print(f'  {tab.name}: {zeilen} Zeilen geprüft')

    # 2. slug-Duplikate
    if 'news' in vorhandene:
        dups = con.execute(
            "SELECT slug, count(*) FROM news WHERE slug IS NOT NULL "
            "GROUP BY slug HAVING count(*) > 1").fetchall()
        for slug, n in dups:
            befunde.append(f'news.slug: {n}x "{slug}" -- PG-Baseline hat UNIQUE(slug)')

    con.close()

    print()
    if befunde:
        print('=== BEFUNDE (vor dem Cutover zu klären) ===')
        for b in befunde:
            print('  -', b)
        sys.exit(1)
    print('=== keine Befunde -- Daten passen ins Postgres-Schema ===')


if __name__ == '__main__':
    main()
