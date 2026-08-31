"""
build_rag_index.py -- Baut die Wissensbasis des RAG-Chatbots neu auf.

Hintergrund: Die Chunk-Liste in rag_chatbot.py war urspruenglich ein
handkuratierter Schnappschuss aus translations.js. Sie wurde von nichts
automatisch aktualisiert und ist mit dem Ausbau der Website (BioComm-Seiten,
Methodik, Mykorrhiza-Wissensseiten, Quellennachweise, Leihgeraet, Medien ...)
immer weiter veraltet.

Dieses Skript erzeugt `rag_chunks.json` aus den echten Textquellen:
  * app/static/translations.json  -- thematisch zu Chunks gebuendelt
  * News-Tabelle (falls DB erreichbar)  -- je Meldung ein eigener Chunk

rag_chatbot.py laedt `rag_chunks.json` beim Import; fehlt die Datei, faellt
es auf die eingebaute _FALLBACK_CHUNKS-Liste zurueck.

Aufruf:  venv/Scripts/python.exe build_rag_index.py
Sicher mehrfach ausfuehrbar -- schreibt die Datei jedes Mal komplett neu.
Nach Textaenderungen an translations.json bzw. neuen News erneut ausfuehren
(lokal generieren + per scp hochladen, oder direkt auf dem Server laufen
lassen, damit die News mitgezogen werden).
"""
import os
import re
import html
import json

BASE = os.path.dirname(__file__)
TRANSLATIONS_PATH = os.path.join(BASE, "app", "static", "translations.json")
OUT_PATH = os.path.join(BASE, "rag_chunks.json")

LANGS = ["de", "en", "nl", "fr", "es"]
MAX_CHARS = 4000  # pro Chunk -- haelt den zusammengesetzten Kontext handhabbar

# ---------------------------------------------------------------------------
# Thematische Gruppen: (slug, titel, [key-praefixe/exakte keys])
#
# titel ist entweder ein translations-key (wird pro Sprache aufgeloest, mit
# Fallback auf DE) oder ein {lang: text}-dict fuer Gruppen ohne passenden key.
# Ein key gehoert zur Gruppe, wenn er == praefix ist oder mit ihm beginnt.
# Mehrfachzuordnung ist erlaubt (z.B. "facts" in Vision und in Fakten).
# UI-Chrome (nav_*, btn_*, *_lbl_*, *_error, meta_*, *_page_title ...) wird
# bewusst nicht aufgenommen.
# ---------------------------------------------------------------------------

GROUPS = [
    ("vision", "label_vision", [
        "hero_sub", "vision_p1", "vision_p2", "vision_p3", "vision_p4",
        "vision_quote", "vision_closing", "h2_vision", "meta_desc_index",
        "vision_biocomm_intro",
    ]),
    ("ueber-das-projekt", "label_ueber", [
        "about_", "h2_ueber", "footer_copy", "footer_impressum",
        "q_footer_right",
    ]),
    ("mykorrhiza-grundlagen", "myk_h1", [
        "desc_warum", "myk_s1_", "myk_s2_", "myk_s4_",
        "q_s1_", "q_ref1_", "q_ref2_", "q_ref14_", "q_ref16_",
    ]),
    ("kritische-einordnung", "myk_s3_h2", [
        "myk_s3_", "q_sk_", "q_ref11_", "q_ref12_",
    ]),
    ("elektrische-aktivitaet", "myk2_h1", [
        "myk2_s1_", "myk2_s2_",
        "q_s2_", "q_s3_", "q_ref3_", "q_ref4_", "q_ref5_", "q_ref6_",
        "q_ref7_", "q_ref08_", "q_ref15_",
    ]),
    ("biocomm-plattform", "biocomm_teaser_h2", [
        "biocomm_teaser_", "bc_s1_", "bc_s2_", "bc_s3_", "bc_s4_", "bc_quote",
        "bc_intro", "bc_h1", "vision_biocomm_",
    ]),
    ("biocomm-hardware", "bch_h1", [
        "bch_", "bc_hw_", "bc_status_2", "bc_status_3", "bc_status_4",
        "myk2_s3_", "a_node_info_hw", "a_node_info_geo",
    ]),
    ("biocomm-software", "bcs_h1", [
        "bcs_", "bc_sw_", "bc_status_1",
    ]),
    ("entwicklungsstand", {
        "de": "Entwicklungsstand von Hardware & Software",
        "en": "Development status of hardware & software",
        "nl": "Ontwikkelingsstatus van hardware & software",
        "fr": "Etat de developpement du materiel et du logiciel",
        "es": "Estado de desarrollo de hardware y software",
    }, [
        "biocomm_teaser_p2", "biocomm_teaser_p3",
        "bc_s4_", "bc_status_1_", "bc_status_2_", "bc_status_3_",
        "bc_status_4_", "bc_status_5_", "bc_status_6_",
        "bch_status_h", "bch_status_p", "bch_s6_h2", "bch_step_",
        "bch_table_1_", "bch_table_2_", "bch_table_3_", "bch_table_4_",
        "bch_table_5_", "bch_table_6_",
        "bcs_status_h2", "bcs_table_1_", "bcs_table_2_", "bcs_table_3_",
        "bcs_table_4_", "bcs_table_5_", "bcs_loop_badge", "bcs_sim_badge",
        "a_node_info_hw",
    ]),
    ("mitmachen-knoten", "label_mitmachen", [
        "desc_mitmachen", "steps", "myk3_s1_",
        "a_node_question", "a_node_info_", "a_node_req_", "a_node_lbl_loan",
        "a_node_geocode_hint",
    ]),
    ("rollen-methodik", "wwa_h1", [
        "wwa_", "a_role_intro", "a_node_question",
        "koop_wege_text",
    ]),
    ("citizen-science", "myk3_h1", [
        "myk3_s2_", "myk3_s3_",
        "q_s5_", "q_ref9_", "q_ref10_", "q_ref17_", "q_ref18_",
        "cards",
    ]),
    ("datenschutz", "label_daten", [
        "desc_daten", "desc_daten_note", "a_privacy_notice", "a_privacy_label",
        "flow_nodes", "link_daten_biocomm",
    ]),
    ("spenden", "label_spenden", [
        "donate_p", "donate_note", "donate_claim", "h2_spenden",
        "donate_fee_label",
    ]),
    ("foerderer-kooperation", "f_section_label", [
        "f_intro_", "f_h2_", "f_vorteile", "f_beitrag_note", "f_steps",
        "f_premium_note", "f_form_note", "f_v0_", "f_v1_", "f_v2_", "f_v3_",
        "f_next_", "f_cta_", "f_opts",
        "home_koop_teaser", "koop_wege_text", "desc_kooperationen",
        "a_foerderer_hint", "a_foerderer_note",
        "wwa_role_hyphist_", "wwa_role_sporist_", "wwa_role_mycelist_",
    ]),
    ("registrierung", "a_h2", [
        "a_intro", "a_role_intro", "desc_anmelden", "form_options",
        "a_opt_", "a_newsletter_label", "a_lbl_role",
    ]),
    ("anwendungen", "vision_apps_h", [
        "vision_apps", "vision_apps_intro", "myk_s5_",
    ]),
    ("fakten-zahlen", {
        "de": "Fakten & Zahlen", "en": "Facts & Numbers",
        "nl": "Feiten & Cijfers", "fr": "Faits & Chiffres",
        "es": "Hechos & Cifras",
    }, [
        "facts", "q_ref16_",
    ]),
    ("medien-musik-buch", "h1_medien", [
        "desc_medien", "musik_p1", "musik_p2", "musik_p3", "musik_ki_hinweis",
        "buch_desc", "buch_note", "buch_teaser_text",
        "br_tagline", "br_note", "br_caption_1", "br_caption_2", "br_caption_3",
    ]),
    ("quellen-erkenntnispfad", {
        "de": "Quellennachweise & Erkenntnispfad",
        "en": "References & path of knowledge",
        "nl": "Bronnen & kennispad",
        "fr": "Sources & parcours de connaissance",
        "es": "Fuentes & recorrido del conocimiento",
    }, [
        "q_subtitle", "q_intro", "q_intro_strong", "q_path_",
        "q_s1_title", "q_s2_title", "q_s3_title", "q_s4_title", "q_s5_title",
        "q_footer_left", "q_footer_right",
    ]),
]

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def clean(value):
    """Beliebigen translations-Wert (str / list / dict) zu Klartext machen."""
    parts = []

    def walk(v):
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            for item in v:
                walk(item)
        elif isinstance(v, dict):
            for item in v.values():
                walk(item)

    walk(value)
    text = " ".join(parts)
    text = html.unescape(TAG_RE.sub(" ", text))
    return WS_RE.sub(" ", text).strip()


def resolve_title(spec, lang, block, de_block):
    if isinstance(spec, dict):
        return spec.get(lang) or spec["de"]
    raw = block.get(spec) or de_block.get(spec) or spec
    return clean(raw)


# Keys, die nie in den Index dürfen — auch wenn eine Gruppe sie versehentlich
# matcht. `leih_*`: die Leihgeräte-Seite wurde am 24.08.2026 zugunsten von
# /biocomm/hardware eingestellt (301-Redirect), ihre Texte in translations.json
# sind toter, teils veralteter Stand (u.a. `leih_status`).
EXCLUDE_PREFIXES = ("leih_", "nav_leihgeraete")


def match(key, prefixes):
    if any(key.startswith(p) for p in EXCLUDE_PREFIXES):
        return False
    return any(key == p or key.startswith(p) for p in prefixes)


def build_from_translations():
    with open(TRANSLATIONS_PATH, encoding="utf-8") as f:
        tr = json.load(f)
    de_block = tr["de"]

    chunks = []
    cid = 0
    for lang in LANGS:
        block = tr.get(lang) or {}
        for slug, title_spec, prefixes in GROUPS:
            seen = set()
            texts = []
            for key, value in block.items():
                if key in seen or not match(key, prefixes):
                    continue
                seen.add(key)
                piece = clean(value)
                if piece:
                    texts.append(piece)
            if not texts:
                continue
            body = " ".join(texts)
            if len(body) > MAX_CHARS:
                body = body[:MAX_CHARS].rsplit(" ", 1)[0] + " …"
            cid += 1
            chunks.append({
                "id": cid,
                "lang": lang,
                "slug": slug,
                "title": resolve_title(title_spec, lang, block, de_block),
                "text": body,
            })
    return chunks


def build_from_news(start_id):
    """News-Meldungen als eigene Chunks -- nur wenn die DB erreichbar ist."""
    try:
        from app import app
        from models import News
    except Exception as e:  # pragma: no cover - nur ausserhalb App-Umgebung
        print(f"  News uebersprungen (Import fehlgeschlagen: {e})")
        return []

    chunks = []
    cid = start_id
    try:
        with app.app_context():
            rows = News.query.order_by(News.veroeffentlicht.desc()).all()
            for n in rows:
                lang = (n.sprache or "de").lower()
                if lang not in LANGS:
                    lang = "de"
                body = clean(" ".join(filter(None, [n.untertitel, n.inhalt])))
                if not body:
                    continue
                if len(body) > MAX_CHARS:
                    body = body[:MAX_CHARS].rsplit(" ", 1)[0] + " …"
                datum = n.veroeffentlicht.strftime("%Y-%m-%d") if n.veroeffentlicht else ""
                cid += 1
                chunks.append({
                    "id": cid,
                    "lang": lang,
                    "slug": "news",
                    "title": f"News ({datum}): {n.titel}".strip(),
                    "text": body,
                })
    except Exception as e:  # pragma: no cover
        print(f"  News uebersprungen (DB-Fehler: {e})")
        return []
    return chunks


def main():
    print("Baue RAG-Wissensbasis ...")
    chunks = build_from_translations()
    print(f"  {len(chunks)} Chunks aus translations.json "
          f"({len(GROUPS)} Themen x {len(LANGS)} Sprachen, leere weggelassen)")

    news_chunks = build_from_news(chunks[-1]["id"] if chunks else 0)
    if news_chunks:
        print(f"  {len(news_chunks)} News-Chunks")
    chunks.extend(news_chunks)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=1)
    print(f"{len(chunks)} Chunks -> {os.path.relpath(OUT_PATH, BASE)}")


if __name__ == "__main__":
    main()
