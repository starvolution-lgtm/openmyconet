"""Themenraeume Phase 2a: themengebiet, diskussion, beitrag, beitrag_anhang,
themen_teilnahme, uebersetzung + die 6 vorgegebenen Themengebiete

Plan: docs/austausch_phase2_plan.md. Die 6 Startgebiete (Texte von Robby, 25.10.2026)
werden auf Deutsch angelegt; ihre Fassungen in en/nl/fr/es liegen als Handuebersetzung
(anbieter 'manuell') in uebersetzung, gebunden an den SHA-256 des deutschen Originals.
Idempotent: Tabellen nur anlegen, wenn sie fehlen (Adoptionspfad mit create_all), und
die Startgebiete nur einfuegen, wenn noch keine vorgegebenen existieren.

Revision ID: 8be9ab181351
Revises: a0d6f3552d84
Create Date: 2026-10-25 15:54:24.576716

"""
import hashlib
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8be9ab181351'
down_revision = 'a0d6f3552d84'
branch_labels = None
depends_on = None

# (Titel, Beschreibung) je Sprache; 'de' ist das Original.
STARTGEBIETE = [
    {'de': ('Bioelektrische Signale & Elektrophysiologie',
            'Signalformen, zeitliche Muster, Messmethoden, Artefakte, Signalverarbeitung'),
     'en': ('Bioelectric signals & electrophysiology',
            'Signal shapes, temporal patterns, measurement methods, artefacts, signal processing'),
     'nl': ('Bio-elektrische signalen & elektrofysiologie',
            'Signaalvormen, tijdspatronen, meetmethoden, artefacten, signaalverwerking'),
     'fr': ('Signaux bioélectriques & électrophysiologie',
            'Formes de signal, motifs temporels, méthodes de mesure, artefacts, traitement du signal'),
     'es': ('Señales bioeléctricas y electrofisiología',
            'Formas de señal, patrones temporales, métodos de medición, artefactos, procesamiento de señales')},
    {'de': ('Mykologie & Mykorrhiza',
            'Pilzphysiologie, Hyphennetze, Symbiosen, Wachstum und biologische Aktivität'),
     'en': ('Mycology & mycorrhiza',
            'Fungal physiology, hyphal networks, symbioses, growth and biological activity'),
     'nl': ('Mycologie & mycorrhiza',
            'Schimmelfysiologie, hyfennetwerken, symbiosen, groei en biologische activiteit'),
     'fr': ('Mycologie & mycorhize',
            "Physiologie fongique, réseaux d'hyphes, symbioses, croissance et activité biologique"),
     'es': ('Micología y micorrizas',
            'Fisiología fúngica, redes de hifas, simbiosis, crecimiento y actividad biológica')},
    {'de': ('Bodenökologie & Umweltparameter',
            'Bodenchemie, Feuchtigkeit, Temperatur, Nährstoffe und ökologische Zusammenhänge'),
     'en': ('Soil ecology & environmental parameters',
            'Soil chemistry, moisture, temperature, nutrients and ecological relationships'),
     'nl': ('Bodemecologie & omgevingsparameters',
            'Bodemchemie, vochtigheid, temperatuur, voedingsstoffen en ecologische samenhangen'),
     'fr': ('Écologie des sols & paramètres environnementaux',
            'Chimie du sol, humidité, température, nutriments et relations écologiques'),
     'es': ('Ecología del suelo y parámetros ambientales',
            'Química del suelo, humedad, temperatura, nutrientes y relaciones ecológicas')},
    {'de': ('Messtechnik & BioComm',
            'Sensorik, Elektroden, Hardware, Kalibrierung, Messqualität und Feldbetrieb'),
     'en': ('Measurement technology & BioComm',
            'Sensors, electrodes, hardware, calibration, measurement quality and field operation'),
     'nl': ('Meettechniek & BioComm',
            'Sensoren, elektroden, hardware, kalibratie, meetkwaliteit en veldgebruik'),
     'fr': ('Métrologie & BioComm',
            'Capteurs, électrodes, matériel, étalonnage, qualité de mesure et fonctionnement sur le terrain'),
     'es': ('Técnica de medición y BioComm',
            'Sensores, electrodos, hardware, calibración, calidad de medición y funcionamiento en campo')},
    {'de': ('Experimente & wissenschaftliche Validierung',
            'Hypothesen, Versuchsdesign, Kontrollgruppen, Reproduzierbarkeit und biologische Referenzmethoden'),
     'en': ('Experiments & scientific validation',
            'Hypotheses, experimental design, control groups, reproducibility and biological reference methods'),
     'nl': ('Experimenten & wetenschappelijke validatie',
            'Hypothesen, proefopzet, controlegroepen, reproduceerbaarheid en biologische referentiemethoden'),
     'fr': ('Expériences & validation scientifique',
            'Hypothèses, plan expérimental, groupes témoins, reproductibilité et méthodes de référence biologiques'),
     'es': ('Experimentos y validación científica',
            'Hipótesis, diseño experimental, grupos de control, reproducibilidad y métodos biológicos de referencia')},
    {'de': ('Datenanalyse, Modelle & KI',
            'Zeitreihen, Mustererkennung, statistische Auswertung, Simulation und mögliche Closed-Loop-Verfahren'),
     'en': ('Data analysis, models & AI',
            'Time series, pattern recognition, statistical evaluation, simulation and possible closed-loop methods'),
     'nl': ('Data-analyse, modellen & AI',
            'Tijdreeksen, patroonherkenning, statistische analyse, simulatie en mogelijke closed-loop-methoden'),
     'fr': ('Analyse de données, modèles & IA',
            'Séries temporelles, reconnaissance de motifs, évaluation statistique, simulation et procédés possibles en boucle fermée'),
     'es': ('Análisis de datos, modelos e IA',
            'Series temporales, reconocimiento de patrones, evaluación estadística, simulación y posibles procedimientos de lazo cerrado')},
]


def _hash(text):
    # muss omn/themen.py::quelltext_hash entsprechen
    return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()


def _startgebiete_anlegen():
    bind = op.get_bind()
    gebiet = sa.table('themengebiet', sa.column('id', sa.Integer), sa.column('titel', sa.String),
                      sa.column('beschreibung', sa.Text), sa.column('sprache_original', sa.String),
                      sa.column('vorgegeben', sa.Boolean), sa.column('reihenfolge', sa.Integer),
                      sa.column('von_team', sa.Boolean), sa.column('sichtbar', sa.Boolean),
                      sa.column('erstellt_am', sa.DateTime(timezone=True)))
    uebers = sa.table('uebersetzung', sa.column('inhalt_typ', sa.String), sa.column('inhalt_id', sa.Integer),
                      sa.column('feld', sa.String), sa.column('ziel_sprache', sa.String),
                      sa.column('quelltext_hash', sa.String), sa.column('text', sa.Text),
                      sa.column('anbieter', sa.String), sa.column('erstellt_am', sa.DateTime(timezone=True)))
    if bind.execute(sa.select(sa.func.count()).select_from(gebiet).where(gebiet.c.vorgegeben.is_(True))).scalar():
        return
    jetzt = datetime.now(timezone.utc)
    for nr, texte in enumerate(STARTGEBIETE, start=1):
        titel, beschreibung = texte['de']
        gid = bind.execute(gebiet.insert().values(
            titel=titel, beschreibung=beschreibung, sprache_original='de', vorgegeben=True,
            reihenfolge=nr, von_team=True, sichtbar=True, erstellt_am=jetzt,
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


def upgrade():
    vorhanden = set(sa.inspect(op.get_bind()).get_table_names())
    if 'uebersetzung' not in vorhanden:
        op.create_table('uebersetzung',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inhalt_typ', sa.String(length=20), nullable=False),
        sa.Column('inhalt_id', sa.Integer(), nullable=False),
        sa.Column('feld', sa.String(length=20), nullable=False),
        sa.Column('ziel_sprache', sa.String(length=10), nullable=False),
        sa.Column('quelltext_hash', sa.String(length=64), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('anbieter', sa.String(length=20), nullable=False),
        sa.Column('erstellt_am', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('inhalt_typ', 'inhalt_id', 'feld', 'ziel_sprache', 'quelltext_hash', name='uq_uebersetzung_fassung')
        )
        with op.batch_alter_table('uebersetzung', schema=None) as batch_op:
            batch_op.create_index('ix_uebersetzung_inhalt', ['inhalt_typ', 'inhalt_id'], unique=False)

    if 'themen_teilnahme' not in vorhanden:
        op.create_table('themen_teilnahme',
        sa.Column('nutzer_id', sa.Integer(), nullable=False),
        sa.Column('anzeigename', sa.String(length=100), nullable=False),
        sa.Column('regeln_akzeptiert_am', sa.DateTime(timezone=True), nullable=True),
        sa.Column('regeln_fassung', sa.String(length=20), nullable=False),
        sa.Column('beitraege_nach_loeschung', sa.String(length=10), nullable=False),
        sa.Column('original_zuerst', sa.Boolean(), nullable=False),
        sa.Column('zuletzt_gesehen', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['nutzer_id'], ['nutzer.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('nutzer_id')
        )

    if 'themengebiet' not in vorhanden:
        op.create_table('themengebiet',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('titel', sa.String(length=200), nullable=False),
        sa.Column('beschreibung', sa.Text(), nullable=False),
        sa.Column('sprache_original', sa.String(length=10), nullable=False),
        sa.Column('vorgegeben', sa.Boolean(), nullable=False),
        sa.Column('reihenfolge', sa.Integer(), nullable=False),
        sa.Column('von_team', sa.Boolean(), nullable=False),
        sa.Column('erstellt_von', sa.Integer(), nullable=True),
        sa.Column('zusammengefuehrt_in', sa.Integer(), nullable=True),
        sa.Column('sichtbar', sa.Boolean(), nullable=False),
        sa.Column('erstellt_am', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['erstellt_von'], ['nutzer.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['zusammengefuehrt_in'], ['themengebiet.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('themengebiet', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_themengebiet_erstellt_von'), ['erstellt_von'], unique=False)

    if 'diskussion' not in vorhanden:
        op.create_table('diskussion',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('themengebiet_id', sa.Integer(), nullable=False),
        sa.Column('titel', sa.String(length=200), nullable=False),
        sa.Column('beschreibung', sa.Text(), nullable=False),
        sa.Column('sprache_original', sa.String(length=10), nullable=False),
        sa.Column('von_team', sa.Boolean(), nullable=False),
        sa.Column('erstellt_von', sa.Integer(), nullable=True),
        sa.Column('erstellt_am', sa.DateTime(timezone=True), nullable=False),
        sa.Column('letzte_aktivitaet', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sichtbar', sa.Boolean(), nullable=False),
        sa.Column('geschlossen', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['erstellt_von'], ['nutzer.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['themengebiet_id'], ['themengebiet.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('diskussion', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_diskussion_erstellt_von'), ['erstellt_von'], unique=False)
            batch_op.create_index(batch_op.f('ix_diskussion_letzte_aktivitaet'), ['letzte_aktivitaet'], unique=False)
            batch_op.create_index(batch_op.f('ix_diskussion_themengebiet_id'), ['themengebiet_id'], unique=False)

    if 'beitrag' not in vorhanden:
        op.create_table('beitrag',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('diskussion_id', sa.Integer(), nullable=False),
        sa.Column('antwort_auf', sa.Integer(), nullable=True),
        sa.Column('von_team', sa.Boolean(), nullable=False),
        sa.Column('autor_nutzer_id', sa.Integer(), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('art', sa.String(length=20), nullable=True),
        sa.Column('sprache_original', sa.String(length=10), nullable=False),
        sa.Column('erstellt_am', sa.DateTime(timezone=True), nullable=False),
        sa.Column('bearbeitet_am', sa.DateTime(timezone=True), nullable=True),
        sa.Column('entfernt_am', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sichtbar', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['antwort_auf'], ['beitrag.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['autor_nutzer_id'], ['nutzer.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['diskussion_id'], ['diskussion.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('beitrag', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_beitrag_antwort_auf'), ['antwort_auf'], unique=False)
            batch_op.create_index(batch_op.f('ix_beitrag_autor_nutzer_id'), ['autor_nutzer_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_beitrag_diskussion_id'), ['diskussion_id'], unique=False)

    if 'beitrag_anhang' not in vorhanden:
        op.create_table('beitrag_anhang',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('beitrag_id', sa.Integer(), nullable=False),
        sa.Column('dateiname', sa.String(length=255), nullable=False),
        sa.Column('originalname', sa.String(length=255), nullable=False),
        sa.Column('groesse', sa.Integer(), nullable=False),
        sa.Column('hochgeladen_am', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['beitrag_id'], ['beitrag.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('beitrag_anhang', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_beitrag_anhang_beitrag_id'), ['beitrag_id'], unique=False)

    _startgebiete_anlegen()


def downgrade():
    with op.batch_alter_table('beitrag_anhang', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_beitrag_anhang_beitrag_id'))

    op.drop_table('beitrag_anhang')
    with op.batch_alter_table('beitrag', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_beitrag_diskussion_id'))
        batch_op.drop_index(batch_op.f('ix_beitrag_autor_nutzer_id'))
        batch_op.drop_index(batch_op.f('ix_beitrag_antwort_auf'))

    op.drop_table('beitrag')
    with op.batch_alter_table('diskussion', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_diskussion_themengebiet_id'))
        batch_op.drop_index(batch_op.f('ix_diskussion_letzte_aktivitaet'))
        batch_op.drop_index(batch_op.f('ix_diskussion_erstellt_von'))

    op.drop_table('diskussion')
    with op.batch_alter_table('themengebiet', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_themengebiet_erstellt_von'))

    op.drop_table('themengebiet')
    op.drop_table('themen_teilnahme')
    with op.batch_alter_table('uebersetzung', schema=None) as batch_op:
        batch_op.drop_index('ix_uebersetzung_inhalt')

    op.drop_table('uebersetzung')
