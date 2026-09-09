"""Vorprüfung vor dem Postgres-Cutover (Postgres-Block-Plan Schritt 3, Phase 0).

Liest die aktuelle SQLite-DB **read-only** (nur SELECT) und prüft, was Postgres
erzwingt und SQLite bisher ignoriert hat:

  1. VARCHAR(n)-Overflow -- ein Wert länger als die Modell-Länge
  2. news.slug-Duplikate (die PG-Baseline hat UNIQUE(slug))
  3. verwaiste Fremdschlüssel (nutzer_id/knoten_id/... zeigt ins Leere) --
     PG erzwingt die FKs, SQLite tat es mangels PRAGMA foreign_keys=ON nicht
  4. NULL in einer nullable=False-Spalte

Kein Eingriff. Exit 0 = sauber, Exit 1 = Befunde (Details im Bericht).

Aufruf auf dem Server:  cd /home/omn/app && venv/bin/python deploy/pg_precheck.py
"""
import os
import sys

# Das Skript liegt in deploy/ -- ohne das hier kommt deploy/ auf den sys.path
# statt des Repo-Roots und `import omn` schlaegt fehl.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    import sqlalchemy as sa

    from omn import create_app
    from omn.extensions import db

    app = create_app()
    befunde = []

    with app.app_context():
        modell_tabellen = list(db.metadata.sorted_tables)
        ist = sa.MetaData()
        ist.reflect(bind=db.engine)  # das echte Ist-Schema der SQLite-Datei

        with db.engine.connect() as con:
            def anzahl(select_from, *bedingungen):
                stmt = sa.select(sa.func.count()).select_from(select_from)
                for b in bedingungen:
                    stmt = stmt.where(b)
                return con.execute(stmt).scalar() or 0

            for mt in modell_tabellen:
                it = ist.tables.get(mt.name)
                if it is None:
                    print(f'  (Tabelle {mt.name} existiert in SQLite noch nicht -- übersprungen)')
                    continue
                print(f'  {mt.name}: {anzahl(it)} Zeilen geprüft')

                for mc in mt.columns:
                    ic = it.columns.get(mc.name)
                    if ic is None:
                        continue

                    if isinstance(mc.type, sa.String) and mc.type.length:
                        laenge = sa.func.length(sa.cast(ic, sa.Text))
                        zu_lang = anzahl(it, laenge > mc.type.length)
                        if zu_lang:
                            maxlen = con.execute(
                                sa.select(sa.func.max(laenge)).select_from(it)).scalar()
                            befunde.append(
                                f'{mt.name}.{mc.name}: {zu_lang} Wert(e) länger als '
                                f'VARCHAR({mc.type.length}) (max {maxlen})')

                    if not mc.nullable and not mc.primary_key:
                        nullen = anzahl(it, ic.is_(None))
                        if nullen:
                            befunde.append(
                                f'{mt.name}.{mc.name}: {nullen} NULL-Wert(e), Modell sagt NOT NULL')

                for fk in mt.foreign_keys:
                    ziel = ist.tables.get(fk.column.table.name)
                    if ziel is None:
                        continue
                    qc = it.columns[fk.parent.name]
                    zc = ziel.columns[fk.column.name]
                    verwaist = anzahl(
                        it, qc.is_not(None), ~sa.exists(sa.select(1).where(zc == qc)))
                    if verwaist:
                        befunde.append(
                            f'{mt.name}.{fk.parent.name}: {verwaist} Zeile(n) zeigen auf '
                            f'nicht existierende {ziel.name}.{fk.column.name}')

            news = ist.tables.get('news')
            if news is not None:
                dups = con.execute(
                    sa.select(news.c.slug, sa.func.count())
                    .where(news.c.slug.is_not(None))
                    .group_by(news.c.slug)
                    .having(sa.func.count() > 1)
                ).all()
                for slug, n in dups:
                    befunde.append(f'news.slug: {n}x "{slug}" -- PG-Baseline hat UNIQUE(slug)')

    print()
    if befunde:
        print('=== BEFUNDE (vor dem Cutover zu klären) ===')
        for b in befunde:
            print('  -', b)
        sys.exit(1)
    print('=== keine Befunde -- Daten passen ins Postgres-Schema ===')


if __name__ == '__main__':
    main()
