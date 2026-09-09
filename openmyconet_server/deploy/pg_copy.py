"""SQLite -> PostgreSQL kopieren (Postgres-Block-Plan Schritt 3, Phase 2/3).

Voraussetzung: `DATABASE_URL` in der .env zeigt auf das ZIEL-Postgres und dort
ist das Schema schon per `flask db upgrade` angelegt (leere Tabellen).

  cd /home/omn/app          # bzw. app-staging
  venv/bin/python deploy/pg_copy.py

Ablauf: alle Tabellen in FK-Reihenfolge (`metadata.sorted_tables`), typisiert
gelesen (Boolean -> bool, DateTime -> datetime ueber die Modell-Spalten),
in EINER Transaktion nach PG. Danach die Sequenzen auf max(id)+1. Zum Schluss
Zeilenzahl-Abgleich pro Tabelle.

Bricht ab, wenn eine Zieltabelle nicht leer ist (Schutz vor Doppel-Lauf) --
`--force` ueberschreibt diese Pruefung nicht, sondern ist bewusst nicht da:
dann vorher `dropdb`/`createdb` + `flask db upgrade`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    import sqlalchemy as sa

    from omn import create_app
    from omn.extensions import db

    app = create_app()
    with app.app_context():
        ziel = db.engine
        if ziel.dialect.name != 'postgresql':
            sys.exit(f'FEHLER: DATABASE_URL zeigt auf {ziel.dialect.name}, nicht postgresql. '
                     f'.env pruefen.')

        # Quelle: die SQLite-Datei im selben instance/-Verzeichnis.
        sqlite_pfad = os.path.join(app.instance_path, 'openmyconet.db')
        if not os.path.isfile(sqlite_pfad):
            sqlite_pfad = os.path.join(os.path.dirname(__file__), '..', 'instance', 'openmyconet.db')
        if not os.path.isfile(sqlite_pfad):
            sys.exit(f'FEHLER: SQLite-Quelle nicht gefunden ({sqlite_pfad})')
        quelle = sa.create_engine(f'sqlite:///{os.path.abspath(sqlite_pfad)}')
        quelle_md = sa.MetaData()
        quelle_md.reflect(bind=quelle)

        tabellen = list(db.metadata.sorted_tables)

        # Schutz: Zieltabellen muessen leer sein
        with ziel.connect() as z:
            nicht_leer = [
                t.name for t in tabellen
                if z.execute(sa.select(sa.func.count()).select_from(t)).scalar()
            ]
        if nicht_leer:
            sys.exit(f'FEHLER: Zieltabellen nicht leer: {nicht_leer}. '
                     f'Erst dropdb/createdb + flask db upgrade.')

        print('== Kopieren (eine Transaktion)')
        kopiert = {}
        with quelle.connect() as q, ziel.begin() as z:
            for t in tabellen:
                src = quelle_md.tables.get(t.name)
                if src is None:
                    print(f'   {t.name}: Quelle fehlt -- uebersprungen')
                    continue
                cols = [t.c[c.name] for c in t.columns if c.name in src.c]
                rows = [dict(r) for r in q.execute(sa.select(*cols)).mappings()]
                if rows:
                    z.execute(sa.insert(t), rows)
                kopiert[t.name] = len(rows)
                print(f'   {t.name}: {len(rows)}')

            print('== Sequenzen setzen')
            for t in tabellen:
                pks = list(t.primary_key.columns)
                if len(pks) != 1 or not isinstance(pks[0].type, sa.Integer):
                    continue
                col = pks[0]
                seq = z.execute(sa.select(sa.func.pg_get_serial_sequence(t.name, col.name))).scalar()
                if not seq:
                    continue
                maxval = z.execute(sa.select(sa.func.coalesce(sa.func.max(col), 0))).scalar()
                z.execute(sa.select(sa.func.setval(seq, maxval + 1, False)))
                print(f'   {t.name}.{col.name} -> {maxval + 1}')

        print('== Abgleich')
        fehler = []
        with quelle.connect() as q, ziel.connect() as z:
            for name, n_quelle in kopiert.items():
                t = db.metadata.tables[name]
                n_ziel = z.execute(sa.select(sa.func.count()).select_from(t)).scalar()
                marker = 'ok' if n_ziel == n_quelle else 'ABWEICHUNG'
                if n_ziel != n_quelle:
                    fehler.append(f'{name}: Quelle {n_quelle}, Ziel {n_ziel}')
                print(f'   {name}: {n_ziel} ({marker})')

        if fehler:
            print('\n=== ABGLEICH FEHLGESCHLAGEN ===')
            for f in fehler:
                print('  -', f)
            sys.exit(1)
        print('\n=== Kopie vollstaendig ===')


if __name__ == '__main__':
    main()
