import httplib2
import datetime
import requests
import os
import logging
import json
import base64
import re

from cryptography.fernet import Fernet
from utils import get_highest_confidence_entity
from fuzzywuzzy import process
from apiclient import discovery, errors
from oauth2client.service_account import ServiceAccountCredentials


logger = logging.getLogger(__name__)


def get_credentials():
    credfile = open('credfile', 'rb').read()
    # The following two lines are used to typecast the string env variable to a base64 accepted by Fernet
    b_key = base64.urlsafe_b64decode(os.getenv('FERNET_KEY', ""))
    key = base64.urlsafe_b64encode(b_key)
    try:
        crypt = Fernet(key)
    except ValueError:
        return None

    try:
        raw_string = crypt.decrypt(credfile)
    except:
        return None

    cred_json = json.loads(raw_string)
    credentials = ServiceAccountCredentials.from_json(cred_json)
    return credentials


# Note: All drive interaction functions interact with the service account drive at this time
def get_google_drive_list(msg_writer, event, wit_entities, user_name, channel_name):
    credentials = get_credentials()
    if credentials is None:
        msg_writer.send_message(event['channel'], "Invalid decryption key")
        return
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)

    files = service.files().list().execute()['files']
    if not files:
        msg_writer.send_message(event['channel'], "No files in this drive")
    else:
        file_names = [x['name'] for x in files]

        message_string = "```"

        for file_name in file_names:
            message_string = message_string + file_name + "\n"

        message_string += "```"

        msg_writer.send_message(event['channel'], message_string)


def get_id_from_name(files, file_name):
    for f in files:
        if f['name'] == file_name:
            return f['id']


def view_drive_file(msg_writer, event, wit_entities, user_name, channel_name):
    credentials = get_credentials()
    if credentials is None:
        msg_writer.send_message(event['channel'], "Invalid decryption key")
        return
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)

    files = service.files().list().execute()['files']

    file_names = [x['name'] for x in files]

    desired_file_name = get_highest_confidence_entity(wit_entities, 'randomize_option')['value']

    likely_file = process.extractOne(desired_file_name, file_names)

    if likely_file and likely_file[1] >= 75:  # Arbitrary probability cutoff
        likely_file_id = get_id_from_name(files, likely_file[0])
        msg_writer.send_message(event['channel'], "```File ID: {}```".format(likely_file_id))

    else:
        msg_writer.send_message(event['channel'], "No file found with that name, sorry")


def create_drive_file(msg_writer, event, wit_entities, user_name, channel_name):
    credentials = get_credentials()
    if credentials is None:
        msg_writer.send_message(event['channel'], "Invalid decryption key")
        return
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)

    desired_file_name = get_highest_confidence_entity(wit_entities, 'randomize_option')['value']

    blank_id = service.files().create(body={"name": desired_file_name}).execute()

    if blank_id:
        msg_writer.send_message(event['channel'], "Created file '{}'".format(desired_file_name))
    else:
        msg_writer.write_error(event['channel'], "Failure in file creation")


def delete_drive_file(msg_writer, event, wit_entities, user_name, channel_name):
    credentials = get_credentials()
    if credentials is None:
        msg_writer.send_message(event['channel'], "Invalid decryption key")
        return
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)

    desired_file_name = get_highest_confidence_entity(wit_entities, 'randomize_option')['value']
    files = service.files().list().execute()['files']
    file_names = [x['name'] for x in files]
    likely_file = process.extractOne(desired_file_name, file_names)

    if likely_file and likely_file[1] >= 75:  # Arbitrary probability cutoff
        file_id = get_id_from_name(files, likely_file[0])

        try:
            service.files().delete(fileId=file_id).execute()
            msg_writer.send_message(event['channel'], "{} deleted".format(likely_file[0]))
        except errors.HttpError:
            msg_writer.send_message(event['channel'], "I can't delete that file")

    else:
        msg_writer.send_message(event['channel'], "No file found with that name, sorry")


def send_email(msg_writer, event, wit_entities, user_name, channel_name):
    msg_text = event['text']
    email_string = "<mailto:.*@.*\..*\|.*@.*\..*>"  # matches <mailto:example@sample.com|example@sample.com>
    string_cleaner = re.compile(email_string)
    cleaned_msg_text = string_cleaner.sub("", msg_text)
    msg_to = get_highest_confidence_entity(wit_entities, 'email')['value']
    if not msg_to:
        msg_writer.send_message(event['channel'], "I can't understand where you want me to send the message, sorry")
        return

    data = {
        'function': 'send_mail_from_hal',
        'to_field': msg_to, 'subject': "Message from Hal",
        "text_field": cleaned_msg_text, 'token': os.getenv("GOOGLE_SLACK_TOKEN", "")
    }
    target_url = os.getenv("SCRIPTS_URL", "")

    try:
        resp = requests.get(target_url, data)
        if resp.status_code == 200:
            msg_writer.send_message(event['channel'], "Message Sent")
            logger.info("message sent")
            logger.info("resp {}".format(resp.text))
        else:
            logger.info("resp {}".format(resp.text))
            msg_writer.send_message(event['channel'], "Message failed to send")

    except Exception as e:
        msg_writer.write_error(event['channel'], e)
        logger.info("contents {}".format(e.content))


# Valid, but examines the calendar of the service account
def view_calendar(msg_writer, event, wit_entities, user_name, channel_name):
    credentials = get_credentials()
    if credentials is None:
        msg_writer.send_message(event['channel'], "Invalid decryption key")
        return
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)
    now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    logger.info('Getting the upcoming 10 events')
    eventsResult = service.events().list(
        calendarId='primary', timeMin=now, maxResults=10, singleEvents=True,
        orderBy='startTime').execute()
    events = eventsResult.get('items', [])

    if not events:
        msg_writer.send_message(event['channel'], 'No upcoming events found.')
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        msg_writer.send_message("".format(start, event['summary']))

""" # Used with old scripts
def count_galateans(msg_writer, event, wit_entities, user_name, channel_name):
    data = {
        "token": "dummy",
        "user_name": user_name,
        "user_id": event['user'],
        "channel_name": channel_name,
        "channel_id": event['channel'],
        "text": "count of Galateans",
        "action": "hal"
    }
    target_url = "dummy"

    resp = requests.get(target_url, data)
    if resp.status_code == 200:
        resp_json = json.loads(resp.text)
        msg_writer.send_message_with_attachments(event['channel'], resp_json['text'], resp_json['attachments'])
    else:
        logger.info("response failed {}".format(resp.text))
"""