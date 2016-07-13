import httplib2
import logging
from intenthandlers.utils import get_highest_confidence_entity
from intenthandlers.google_helpers import get_credentials
from fuzzywuzzy import process
from apiclient import discovery, errors

logger = logging.getLogger(__name__)
"""
Note: All drive interaction functions interact with the service account drive at this time
Eventually, all of these functions should use google_query in google helpers
"""


def get_google_drive_list(msg_writer, event, wit_entities):
    """
    :param msg_writer: writer used to write to the slack channel
    :param event: slack event object
    :param wit_entities: entity object returned by wit API call
    :return: None, list of drive files is written to slack channel
    """
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

"""
def get_google_drive_list(msg_writer, event, wit entities):
    drive_list = google_query("get_drive_list", {"text": "get drive list"}, event)
    msg_writer.send_message_with_attachments(event['channel'], drive_list.get('text'), drive_list.get('attachments'))
"""


def view_drive_file(msg_writer, event, wit_entities):
    """
    :param msg_writer: writer used to write to the slack channel
    :param event: slack event object
    :param wit_entities: entity object returned by wit API call
    :return: None, list of drive files with the name specified by wit_entities is written to slack channel
    """
    credentials = get_credentials()
    if credentials is None:
        msg_writer.send_message(event['channel'], "Invalid decryption key")
        return
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)

    files = service.files().list().execute()['files']

    file_names = [x['name'] for x in files]

    try:
        desired_file_name = get_highest_confidence_entity(wit_entities, 'randomize_option')['value']
    except TypeError:
        msg_writer.send_message(event['channel'], "I don't know what file you're talking about")
        return

    likely_file = process.extractOne(desired_file_name, file_names)

    if likely_file and likely_file[1] >= 75:  # Arbitrary probability cutoff
        likely_file_id = get_id_from_name(files, likely_file[0])
        msg_writer.send_message(event['channel'], "```File ID: {}```".format(likely_file_id))

    else:
        msg_writer.send_message(event['channel'], "No file found with that name, sorry")

"""
def get_drive_file(msg_writer, event, wit entities):
    file_name = get_highest_confidence_entity(wit_entities, 'randomize_option')['value']
    file_list = google_query("get_drive_file", {"text": "get drive file", "file_name": file_name}, event)
    msg_writer.send_message_with_attachments(event['channel'], file_list.get('text'), file_list.get('attachments'))
"""


def create_drive_file(msg_writer, event, wit_entities):
    """
    :param msg_writer: writer used to write to the slack channel
    :param event: slack event object
    :param wit_entities: entity object returned by wit API call
    :return: None, affirmitive message indicating creation of file with name specified by wit_entities is sent
    to slack channel
    """
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

"""
def create_drive_file(msg_writer, event, wit entities):
    file_name = get_highest_confidence_entity(wit_entities, 'randomize_option')['value']
    google_query("create_drive_file", {"text": "create drive file", "file_name": file_name}, event)
    msg_writer.send_message(event['channel'], "{} created".format(file_mame))
"""


def delete_drive_file(msg_writer, event, wit_entities):
    """
    :param msg_writer: writer used to write to the slack channel
    :param event: slack event object
    :param wit_entities: entity object returned by wit API call
    :return: None, affirmitive message indicating deletion of file with name specified by wit_entities is sent
    to slack channel
    """
    credentials = get_credentials()
    if credentials is None:
        msg_writer.send_message(event['channel'], "Invalid decryption key")
        return
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)

    try:
        desired_file_name = get_highest_confidence_entity(wit_entities, 'randomize_option')['value']
    except TypeError:
        msg_writer.send_message(event['channel'], "I don't know what file you're talking about")
        return

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

"""
def delete_drive_file(msg_writer, event, wit entities):
    file_name = get_highest_confidence_entity(wit_entities, 'randomize_option')['value']
    google_query("delete_drive_file", {"text": "delete drive file", "file_name": file_name}, event)
    msg_writer.send_message(event['channel'], "{} deleted".format(file_mame))
"""


def get_id_from_name(files, file_name):
    for f in files:
        if f['name'] == file_name:
            return f['id']