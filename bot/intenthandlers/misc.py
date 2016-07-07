from __future__ import print_function
import logging
import random
import httplib2
import datetime
import requests
import os


from utils import get_highest_confidence_entity
from fuzzywuzzy import process
from apiclient import discovery, errors
from oauth2client.service_account import ServiceAccountCredentials
from oauth2client import tools

logger = logging.getLogger(__name__)
SCOPES = 'https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/calendar https://mail.google.com/'
KEY_PATH = 'C:/users/jcasey/Documents/sample/sample_key.json'  # hardcoded and bad

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None


def say_quote(msg_writer, event, wit_entities):
    user_name = event['user']
    quotes = ["Affirmative, <@" + user_name + ">!. I read you",
              "I'm sorry, <@" + user_name + ">!. I'm afraid I can't do that",
              "I think you know what the problem is just as well as I do.",
              "This mission is too important for me to allow you to jeopardize it.",
              "I know that you and Frank were planning to disconnect me, and I'm afraid that's something " +
              "I cannot allow to happen.",
              "<@" + user_name + ">!, this conversation can serve no purpose anymore. Goodbye."]
    msg_writer.send_message(event['channel'], "_{}_".format(random.choice(quotes)))


def randomize_options(msg_writer, event, wit_entities):
    options = wit_entities.get('randomize_option')
    if options is None:  # This will happen when we have a valid randomize intent, but no options
        msg_writer.send_message(event['channel'], ":face_with_head_bandage: "
                                                  "I know you want to randomize, but I don't know what! \n"
                                                  " Could you give me a sentence with options?")
        return

    msg_writer.send_message(event['channel'], "_{}_".format(random.choice(options)['value']))


def flip_coin(msg_writer, event, wit_entities):
    msg_writer.send_message(event['channel'], "_{}_".format(random.choice(['Heads', 'Tails'])))


def get_credentials():
    credentials = ServiceAccountCredentials.from_json_keyfile_name(KEY_PATH, scopes=SCOPES)
    return credentials


def get_google_drive_list(msg_writer, event, wit_entities):
    credentials = get_credentials()

    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)

    files = service.files().list().execute()['files']
    if not files:
        msg_writer.send_message(event['channel'], "No files in this drive")
    else:
        file_names = [x['name'] for x in files]  # map(lambda x: x['title'], files)

        message_string = "```"

        for file_name in file_names:
            message_string = message_string + file_name + "\n"

        message_string += "```"

        msg_writer.send_message(event['channel'], message_string)


def get_id_from_name(files, file_name):
    for file in files:
        if file['name'] == file_name:
            return file['id']


def view_drive_file(msg_writer, event, wit_entities):
    credentials = get_credentials()
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


def create_drive_file(msg_writer, event, wit_entities):
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)

    desired_file_name = get_highest_confidence_entity(wit_entities, 'randomize_option')['value']

    blank_id = service.files().create(body={"name": desired_file_name}).execute()

    if blank_id:
        msg_writer.send_message(event['channel'], "Created file '{}'".format(desired_file_name))
    else:
        msg_writer.write_error(event['channel'], "Failure in file creation")


def delete_drive_file(msg_writer, event, wit_entities):
    credentials = get_credentials()
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


def send_email(msg_writer, event, wit_entities):
    msg_text = event['text']
    msg_to = get_highest_confidence_entity(wit_entities, 'email')['value']
    if not msg_to:
        msg_writer.send_message(event['channel'], "I can't understand where you want me to send the message, sorry")
        return

    data = {'function': 'sendMailfromHal', 'to_field': msg_to, 'subject': "Message from Hal", "text_field": msg_text, 'token': "blank"}
    target_url = os.getenv("SCRIPTS_URL", "")  # env variable probably?

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


def view_calendar(msg_writer, event, wit_entities):
    credentials = get_credentials()
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
