"""
backup_alarm.py -- schickt eine Alarm-Mail, wenn das Storage-Box-Backup
fehlschlaegt (aufgerufen von deploy/borg_common.sh::alarm).

    venv/bin/python3 deploy/backup_alarm.py "<Betreff>" "<Text>"

Nutzt denselben SMTP-Weg wie monitoring_test_mail.py (Zugangsdaten aus
/home/omn/app/.env), bewusst OHNE App/MailQueue: der Alarm darf nicht von der
Datenbank abhaengen. Empfaenger: ALARM_EMPFAENGER (borg.env, als
Umgebungsvariable durchgereicht) -> ADMIN_NOTIFY_EMAIL -> MAIL_USERNAME.
Fehler beim Versand werden nur ausgegeben (Exit 0), damit der Aufrufer
weiterlaeuft; den Ausfall der Mail selbst faengt healthchecks.io ab.
"""
import os
import smtplib
import socket
import sys
from email.mime.text import MIMEText

from dotenv import load_dotenv


def main():
    load_dotenv('/home/omn/app/.env')
    betreff = sys.argv[1] if len(sys.argv) > 1 else 'Backup-Alarm'
    text = sys.argv[2] if len(sys.argv) > 2 else ''
    empfaenger = (os.getenv('ALARM_EMPFAENGER') or os.getenv('ADMIN_NOTIFY_EMAIL')
                  or os.getenv('MAIL_USERNAME'))
    if not empfaenger or not os.getenv('MAIL_SERVER'):
        print('Alarm-Mail nicht moeglich: MAIL_SERVER/Empfaenger fehlt')
        return
    msg = MIMEText(f'{text}\n\nServer: {socket.gethostname()}\n'
                   'Details: journalctl --user -u omn-backup-storagebox -n 100\n')
    msg['Subject'] = f'[OpenMycoNet Backup] {betreff}'
    msg['From'] = os.getenv('MAIL_DEFAULT_SENDER') or os.getenv('MAIL_USERNAME')
    msg['To'] = empfaenger
    try:
        with smtplib.SMTP(os.getenv('MAIL_SERVER'), int(os.getenv('MAIL_PORT', 587)), timeout=20) as s:
            s.starttls()
            s.login(os.getenv('MAIL_USERNAME'), os.getenv('MAIL_PASSWORD'))
            s.send_message(msg)
        print(f'Alarm-Mail an {empfaenger} gesendet')
    except Exception as e:  # Alarm darf nie selbst crashen
        print(f'Alarm-Mail fehlgeschlagen: {e}')


if __name__ == '__main__':
    main()
