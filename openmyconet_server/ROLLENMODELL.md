# Rollenmodell & Forum-Vorbereitung (Phase 2)

## Was jetzt gebaut wurde

- **Magic-Link-Login** (`dashboard.py`): eigene Session (`session['nutzer_logged_in']`/`session['nutzer_id']`), komplett getrennt von `session['admin_*']`.
- **Dashboard-Kernrollen** (Basis-Nutzer / Bewerber / Knotenbetreiber): werden bei jedem Aufruf frisch aus bestehenden Relationen abgeleitet (`nutzer.knoten` vorhanden → Knotenbetreiber, sonst `Bewerbung`-Eintrag vorhanden → Bewerber, sonst Basis-Nutzer). Kein zusätzliches Status-Feld — vermeidet Redundanz und veraltete Zustände.
- **`Nutzer.fachrolle`** (neue Spalte, `models.py`): `'wissenschaftler'` | `'wiss_mitarbeiter'` | `'student'` | `NULL`. Reine Klassifizierung für spätere Forum-Badges, **keine Berechtigungsstufe** — alle drei Werte haben identische Rechte. Admin-pflegbar über `/admin` (Spalte + Filter + Inline-Select), kein Feld im öffentlichen Registrierungsformular (bewusste Entscheidung, siehe Auftrag: Formular soll nicht mehr Felder bekommen).

## Das geplante Forum-Zugriffsmodell (zweistufig, NICHT jetzt gebaut)

Das Forum selbst (Threads, Beiträge, Moderation) ist bewusst nicht Teil dieser Phase. Damit der spätere Bau aber ohne Architektur-Bruch andockt, hier die Anforderung dokumentiert:

1. **Kern-Zugang** — ausschließlich für die wissenschaftliche Rollengruppe. Eine einfache Bedingung auf dem bereits vorhandenen Feld:

    ```python
    def hat_forum_kernzugang(nutzer):
        return nutzer.fachrolle in ('wissenschaftler', 'wiss_mitarbeiter', 'student')
    ```

   Keine neue Tabelle, keine Nachrüstung — genau die "einfache Bedingung auf bestehenden Feldern", die für eine bruchfreie Erweiterung gefordert war.

2. **Granulare Zusatz-Freigabe für Knotenbetreiber** — standardmäßig **kein** Forumszugang, aber der Ersteller eines einzelnen Beitrags/Threads kann gezielt einzelne Knotenbetreiber für genau diesen einen Beitrag freischalten. Das ist **keine** rollenbasierte Zugriffsprüfung auf Forums-Ebene, sondern eine Sichtbarkeits-Entscheidung auf **Objekt-Ebene** (pro Post/Thread). Das bedeutet für den späteren Forum-Bau:

    - Eine `ForumPost`/`ForumThread`-Tabelle braucht ein `ersteller_id` (FK auf `Nutzer`) — der Ersteller entscheidet über Freigaben zu seinem eigenen Beitrag.
    - Eine separate Zuordnungstabelle für die Freigaben selbst, z.B.:

    ```python
    class ForumPostFreigabe(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=False)
        nutzer_id = db.Column(db.Integer, db.ForeignKey('nutzer.id'), nullable=False)
        # optional: erstellt_am, freigegeben_von_id (falls nicht zwingend der Post-Ersteller freigibt)
    ```

    - Zugriffsprüfung für einen konkreten Post wäre dann zweistufig:

    ```python
    def darf_post_sehen(nutzer, post):
        if hat_forum_kernzugang(nutzer):
            return True
        return ForumPostFreigabe.query.filter_by(post_id=post.id, nutzer_id=nutzer.id).first() is not None
    ```

   **Wichtig für den späteren Bau:** Das ist eine Freigabe *pro Post*, nicht *pro Thread* oder *pauschal fürs Forum* — ein Knotenbetreiber, der für Beitrag A freigeschaltet ist, sieht dadurch nicht automatisch Beitrag B. Diese Granularität jetzt schon im Datenmodell-Kommentar festzuhalten war explizit Teil des Auftrags, damit sie beim eigentlichen Forum-Bau nicht verloren geht.

## Warum das jetzt schon so angelegt wird

Die Trennung von "Wer bin ich fachlich" (`fachrolle`, Klassifizierung) und "Was darf ich sehen" (spätere Forum-Zugriffslogik, objektbasiert) ist bewusst so gewählt, dass:

- ein Knotenbetreiber gleichzeitig Wissenschaftler sein kann (häufiger Fall bei Kooperationspartnern), ohne dass sich beide Konzepte gegenseitig überschreiben,
- die künftige Forum-Zugriffsprüfung ohne Schema-Änderung an bestehenden Nutzer-Daten auskommt,
- die granulare Post-Freigabe für Knotenbetreiber später als reine Zusatz-Tabelle ergänzt werden kann, ohne die Kernzugangs-Logik anzufassen.

## Nicht Teil dieser Phase

Kein Forum-Code, keine `ForumPost`/`ForumThread`/`ForumPostFreigabe`-Tabellen, keine Moderationslogik — die obigen Code-Beispiele sind Dokumentation/Vorausschau, keine Implementierung.
