"""Themenraeume: zwei weitere vorgegebene Gebiete fuer die Oeffnung (Robby 14.11.2026)

"Bodenleben & Bodengesundheit" ist sofort sichtbar (die Fachkontakte koennen den Raum
schon beleben), "Fragen aus der Praxis" bleibt ausgeblendet, bis der Kreis auf alle
registrierten Mitglieder erweitert wird (einblenden in /admin/themen). Muster wie die
6 Startgebiete in 8be9ab181351: Original Deutsch, en/nl/fr/es als Handuebersetzung.
Idempotent: ein Gebiet wird nur angelegt, wenn es noch kein Gebiet mit diesem Titel gibt.

Revision ID: f3b7d91a2c64
Revises: e5a8c3d27f19
Create Date: 2026-11-14 12:00:00.000000

"""
import hashlib
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3b7d91a2c64'
down_revision = 'e5a8c3d27f19'
branch_labels = None
depends_on = None


# (reihenfolge, sichtbar, {sprache: (Titel, Beschreibung)}); 'de' ist das Original.
GEBIETE = [
    (7, True, {
        'de': ('Bodenleben & Bodengesundheit',
               'Bakterien, Pilze und Bodentiere, Humusaufbau, Bodenfruchtbarkeit und Erfahrungen aus Garten, '
               'Landwirtschaft und Forst'),
        'en': ('Soil life & soil health',
               'Bacteria, fungi and soil fauna, humus formation, soil fertility and experience from gardening, '
               'agriculture and forestry'),
        'nl': ('Bodemleven & bodemgezondheid',
               'Bacteriën, schimmels en bodemdieren, humusopbouw, bodemvruchtbaarheid en ervaringen uit tuin, '
               'landbouw en bosbouw'),
        'fr': ('Vie du sol & santé des sols',
               'Bactéries, champignons et faune du sol, formation de l’humus, fertilité des sols et expériences '
               'du jardinage, de l’agriculture et de la sylviculture'),
        'es': ('Vida y salud del suelo',
               'Bacterias, hongos y fauna del suelo, formación de humus, fertilidad del suelo y experiencias de '
               'la jardinería, la agricultura y la silvicultura')}),
    (8, False, {
        'de': ('Fragen aus der Praxis',
               'Fragen rund um Boden, Pilze und Bodenleben – auch ohne Vorwissen. Keine Pilzbestimmung zum '
               'Verzehr und keine persönliche medizinische Beratung.'),
        'en': ('Questions from practice',
               'Questions about soil, fungi and soil life – no prior knowledge needed. No identification of '
               'mushrooms for eating and no personal medical advice.'),
        'nl': ('Vragen uit de praktijk',
               'Vragen over bodem, schimmels en bodemleven – ook zonder voorkennis. Geen determinatie van '
               'paddenstoelen om te eten en geen persoonlijk medisch advies.'),
        'fr': ('Questions de terrain',
               'Questions sur le sol, les champignons et la vie du sol – sans connaissances préalables. Pas '
               'd’identification de champignons destinés à la consommation ni de conseils médicaux personnels.'),
        'es': ('Preguntas desde la práctica',
               'Preguntas sobre el suelo, los hongos y la vida del suelo, sin necesidad de conocimientos previos. '
               'No se identifican setas para consumo ni se ofrece asesoramiento médico personal.')}),
]


def _hash(text):
    # muss omn/themen.py::quelltext_hash entsprechen
    return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()


def _tabellen():
    gebiet = sa.table('themengebiet', sa.column('id', sa.Integer), sa.column('titel', sa.String),
                      sa.column('beschreibung', sa.Text), sa.column('sprache_original', sa.String),
                      sa.column('vorgegeben', sa.Boolean), sa.column('reihenfolge', sa.Integer),
                      sa.column('von_team', sa.Boolean), sa.column('sichtbar', sa.Boolean),
                      sa.column('erstellt_am', sa.DateTime(timezone=True)))
    uebers = sa.table('uebersetzung', sa.column('inhalt_typ', sa.String), sa.column('inhalt_id', sa.Integer),
                      sa.column('feld', sa.String), sa.column('ziel_sprache', sa.String),
                      sa.column('quelltext_hash', sa.String), sa.column('text', sa.Text),
                      sa.column('anbieter', sa.String), sa.column('erstellt_am', sa.DateTime(timezone=True)))
    return gebiet, uebers


def upgrade():
    bind = op.get_bind()
    gebiet, uebers = _tabellen()
    jetzt = datetime.now(timezone.utc)
    for reihenfolge, sichtbar, texte in GEBIETE:
        titel, beschreibung = texte['de']
        if bind.execute(sa.select(sa.func.count()).select_from(gebiet).where(gebiet.c.titel == titel)).scalar():
            continue
        gid = bind.execute(gebiet.insert().values(
            titel=titel, beschreibung=beschreibung, sprache_original='de', vorgegeben=True,
            reihenfolge=reihenfolge, von_team=True, sichtbar=sichtbar, erstellt_am=jetzt,
        ).returning(gebiet.c.id)).scalar()
        zeilen = []
        for lang, (t, b) in texte.items():
            if lang == 'de':
                continue
            zeilen.append(dict(inhalt_typ='themengebiet', inhalt_id=gid, feld='titel', ziel_sprache=lang,
                               quelltext_hash=_hash(titel), text=t, anbieter='manuell', erstellt_am=jetzt))
            zeilen.append(dict(inhalt_typ='themengebiet', inhalt_id=gid, feld='beschreibung', ziel_sprache=lang,
                               quelltext_hash=_hash(beschreibung), text=b, anbieter='manuell', erstellt_am=jetzt))
        bind.execute(uebers.insert(), zeilen)


def downgrade():
    # Nur Gebiete ohne Diskussionen entfernen -- Inhalte von Teilnehmenden bleiben unangetastet.
    bind = op.get_bind()
    gebiet, uebers = _tabellen()
    diskussion = sa.table('diskussion', sa.column('themengebiet_id', sa.Integer))
    for _, _, texte in GEBIETE:
        gid = bind.execute(sa.select(gebiet.c.id).where(gebiet.c.titel == texte['de'][0])).scalar()
        if gid is None or bind.execute(sa.select(sa.func.count()).select_from(diskussion)
                                       .where(diskussion.c.themengebiet_id == gid)).scalar():
            continue
        bind.execute(uebers.delete().where(uebers.c.inhalt_typ == 'themengebiet', uebers.c.inhalt_id == gid))
        bind.execute(gebiet.delete().where(gebiet.c.id == gid))
