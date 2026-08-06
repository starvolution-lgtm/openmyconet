"""
Taeglicher Mail-Monitoring-Test (Dead-Man's-Switch ueber healthchecks.io).

Versucht eine echte Test-Mail ueber denselben SMTP-Weg zu senden, den auch
Registrierungs-/Bestaetigungsmails nutzen. Bei Erfolg meldet sich das Skript
bei healthchecks.io ("Ping") -- bleibt dieser Ping aus (weil die Mail fehlschlaegt
oder der Cronjob selbst nicht laeuft), schlaegt healthchecks.io nach Ablauf der
Grace-Time ueber einen von openmyconet.de unabhaengigen Kanal Alarm. Das loest
das Henne-Ei-Problem einer E-Mail-Warnung bei kaputtem Mailversand.

Aufruf: python monitoring_test_mail.py (per Cronjob, siehe Deployment-Notiz)
"""

import os
import smtplib
import urllib.request
from datetime import datetime
from email.mime.text import MIMEText

from dotenv import load_dotenv

BASIS_VERZEICHNIS = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASIS_VERZEICHNIS, '.env'))

HC_PING_URL = 'https://hc-ping.com/bb3f5443-f9be-48c3-bdf8-4da65fb74b95'


def test_mail_senden():
    nachricht = MIMEText(
        f"Automatischer taeglicher Mail-Monitoring-Test.\n\nZeitpunkt: {datetime.now().isoformat()}\n\n"
        "Diese Mail bestaetigt, dass der SMTP-Versand von openmyconet.de funktioniert."
    )
    nachricht['Subject'] = 'OpenMycoNet Mail-Monitoring-Test'
    nachricht['From'] = os.getenv('MAIL_DEFAULT_SENDER')
    nachricht['To'] = 'kontakt@openmyconet.de'

    with smtplib.SMTP(os.getenv('MAIL_SERVER'), int(os.getenv('MAIL_PORT', 587)), timeout=15) as server:
        server.starttls()
        server.login(os.getenv('MAIL_USERNAME'), os.getenv('MAIL_PASSWORD'))
        server.send_message(nachricht)


if __name__ == '__main__':
    try:
        test_mail_senden()
        urllib.request.urlopen(HC_PING_URL, timeout=10)
        print('Test-Mail erfolgreich gesendet, healthchecks.io benachrichtigt.')
    except Exception as fehler:
        # Bewusst sofort den /fail-Endpunkt anstoßen statt nur zu schweigen --
        # healthchecks.io alarmiert dann ohne auf die Grace-Time warten zu muessen.
        try:
            urllib.request.urlopen(HC_PING_URL + '/fail', timeout=10)
        except Exception:
            pass
        print(f'Fehler beim Mail-Test: {fehler}')
        raise
