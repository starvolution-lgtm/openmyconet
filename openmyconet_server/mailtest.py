from dotenv import load_dotenv
import os
load_dotenv()
from flask import Flask
from flask_mail import Mail, Message

app = Flask(__name__)
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

mail = Mail(app)

with app.app_context():
    msg = Message('OpenMycoNet Testmail', recipients=['admin@variabelle.com'])
    msg.body = 'Das ist ein Test.'
    mail.send(msg)
    print('Mail gesendet!')