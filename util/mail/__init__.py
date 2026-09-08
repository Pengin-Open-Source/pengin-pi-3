import os
import boto3
from dotenv import load_dotenv
from util.mail.config import Message as Mail

load_dotenv()


def send_mail(RECIPIENT, TOKEN=None, TYPE=None, **kwargs):
  mailer = Mail(RECIPIENT=RECIPIENT, TOKEN=TOKEN, TYPE=TYPE, **kwargs)
  try:
    client = boto3.client(
        'ses',
        region_name=os.getenv('AWS_REGION', 'us-west-2'),
        aws_access_key_id=mailer.USERNAME_SMTP,
        aws_secret_access_key=mailer.PASSWORD_SMTP,
    )

    response = client.send_raw_email(
        Source=mailer.msg['From'],
        Destinations=[RECIPIENT],
        RawMessage={'Data': mailer.msg.as_bytes()},
    )
    print('Email sent via boto3! MessageId:', response.get('MessageId'))
    return response
  except Exception as e:
    print('Error sending email via Boto3: ', e)
