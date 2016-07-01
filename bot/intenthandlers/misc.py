from __future__ import print_function
import logging
import random
import httplib2

from utils import get_highest_confidence_entity
from fuzzywuzzy import fuzz, process
from apiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials
from oauth2client import tools

logger = logging.getLogger(__name__)
SCOPES = 'https://www.googleapis.com/auth/drive.metadata.readonly'
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
    service = discovery.build('drive', 'v2', http=http)

    files = service.files().list().execute()['items']

    file_names = [x['title'] for x in files]  # map(lambda x: x['title'], files)

    message_string = "```"

    for file_name in file_names:
        message_string = message_string + file_name + "\n"

    message_string += "```"

    msg_writer.send_message(event['channel'], message_string)


def get_id_from_name(files, file_name):
    for file in files:
        if file['title'] == file_name:
            return file['id']


def view_drive_file(msg_writer, event, wit_entities):
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v2', http=http)

    files = service.files().list().execute()['items']

    file_names = [x['title'] for x in files]

    desired_file_name = get_highest_confidence_entity(wit_entities, 'randomize_option')['value']

    likely_file = process.extractOne(desired_file_name, file_names)

    if likely_file[1] >= 80:  # Arbitrary probability cutoff
        likely_file_id = get_id_from_name(files, likely_file[0])
        logger.info("file name {}, file id {}".format(likely_file, likely_file_id))
        msg_writer.send_message(event['channel'], "```File ID: {}```".format(likely_file_id))
    else:
        msg_writer.send_message(event['channel'], "No file found with that name, sorry")