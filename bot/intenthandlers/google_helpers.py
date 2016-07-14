import requests
import os
import logging
import json
import httplib2
import base64
# import re
import copy

from cryptography.fernet import Fernet, InvalidToken
# from oauth2client.service_account import ServiceAccountCredentials
from oauth2client import client
from slack_clients import is_direct_message

logger = logging.getLogger(__name__)

SCOPES = 'https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/calendar https://mail.google.com/' \
         ' https://www.googleapis.com/auth/gmail.compose https://www.googleapis.com/auth/spreadsheets'

class GoogleCredentials(object):
    def __init__(self, msg_writer):
        self.msg_writer = msg_writer
        b_key = base64.urlsafe_b64decode(os.getenv('FERNET_KEY', ""))
        key = base64.urlsafe_b64encode(b_key)
        logger.info("Fernet Key {}".format(key))
        try:
            self.crypt = Fernet(key)
        except ValueError:
            logger.error("Null decryption key given")
        hal_credentials = self._get_hal_credentials()
        self._credentials_dict = {'hal': hal_credentials}

        # The following two lines are used to typecast the string env variable to a base64 accepted by Fernet


    def _get_hal_credentials(self):
        credfile = open('credfile', 'rb').read()

        try:
            raw_string = self.crypt.decrypt(credfile)
        except InvalidToken:
            logger.error("Invalid decryption key given")
            return None

        cred_json = json.loads(raw_string.decode('ascii'))
        credentials = client.OAuth2Credentials.from_json(cred_json)

        return credentials

    def get_credential(self, event, state_id, user='hal'):
        try:
            return self._credentials_dict[user]  # how do we want to handle expiry?
        except KeyError:
            flow = client.flow_from_clientsecrets('client_secrets.json',
                                                  scope=SCOPES,
                                                  redirect_uri="https://beepboophq.com/proxy/dummy_id")
            # where dummy id contains user id,
            auth_uri = flow.step1_get_authorize_url('state')
            if not is_direct_message(event['channel']):
                self.msg_writer.send_message(event['channel'], "I'll send you the authorization link in a direct message")
            channel = event['user_dm']
            self.msg_writer.send_message(channel, "Click here to authorize {}".format(auth_uri))
            return None

    # This function feels really janky
    def add_credential_return_state_id(self, credentials, state):
        try:
            raw_string = self.crypt.decrypt(state)
        except InvalidToken:
            logger.error("Invalid decryption key given")
            return

        state_json = json.loads(raw_string)
        user_id = state_json.get('user_id')
        self._credentials_dict.update({user_id: credentials})

        return state_json


def get_credentials(msg_writer, event):
    """
    Generates credentials used to access google services via oauth
    :return: oauth2client credentials object, unless environment decryption key
    was invalid, then None
    """
    if 'google_credentials' in event and not event['google_credentials'].access_token_expired:
        return event['google_credentials'].authorize(httplib2.Http())
    else:
        flow = client.flow_from_clientsecrets('client_secrets.json',
                                              scope=SCOPES,
                                              redirect_uri="https://beepboophq.com/proxy/dummy_id")
        #where dummy id contains user id,
        auth_uri = flow.step1_get_authorize_url('state')
        if not is_direct_message(event['channel']):
            msg_writer.send_message(event['channel'], "I'll send you the authorization link in a direct message")
        channel = event['user_dm']
        msg_writer.send_message(channel, "Click here to authorize {}".format(auth_uri))
        return {'authorization': 'state'}

# not working when pointed to old scripts
# uncomment and update when implemented in scripts
"""
def send_email(msg_writer, event, wit_entities):
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
        "text_field": cleaned_msg_text,
        'token': os.getenv("GOOGLE_SLACK_TOKEN", "")
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
"""


def google_query(function, parameters, event):
    """
    :param function: Name of the function to be called in google scripts
    :param parameters: parameters of the function
    :param event: Event object containing information about the slack event
    :return: The text of the response provided by google, in json format
    """

    target_url = os.getenv("SCRIPTS_URL", "")
    token = os.getenv("GOOGLE_SLACK_TOKEN", "")
    data = copy.deepcopy(parameters)
    try:
        channel_name = event['channel_name']['name']
    except TypeError:
        channel_name = event['channel_name']

    data.update({
        'function': function,
        'token': token,
        'user_name': event['user_name']['profile']['real_name'],
        'user_id': event['user'],
        'channel_name': channel_name,
        'channel_id': event['channel'],
        'action': 'hal'
    })
    logger.info("data is {}".format(data))
    resp = requests.get(target_url, data)

    if resp.status_code == 200:
        resp_json = json.loads(resp.text)
        logger.info("resp text {}, json {}".format(resp.text, resp_json))
        return resp_json
    else:
        raise GoogleAccessError(resp.status_code)


class GoogleAccessError(Exception):
    def __init__(self, *error_args):
        Exception.__init__(self, "Bad response status {}".format(error_args))
