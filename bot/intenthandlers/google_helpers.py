import os
import logging
import json
import httplib2
import base64
import re
import uuid
import copy
import requests
from uuid import uuid4
from email.mime.text import MIMEText
from state import WaitState
from intenthandlers.utils import get_highest_confidence_entity
from cryptography.fernet import Fernet, InvalidToken
from oauth2client import client
from slack_clients import is_direct_message
from apiclient import discovery

logger = logging.getLogger(__name__)

SCOPES = 'https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/calendar https://mail.google.com/' \
         ' https://www.googleapis.com/auth/gmail.compose https://www.googleapis.com/auth/spreadsheets'


class GoogleCredentials(object):
    """
    GoogleCredentials creates and holds credential objects used with Google OAuth. In addition, it handles encrypting
    and decrypting state uuids as they are passed through the Google environment
    """
    def __init__(self, msg_writer):
        self.msg_writer = msg_writer
        # The following two lines are used to typecast the string env variable to a base64 accepted by Fernet
        b_key = base64.urlsafe_b64decode(os.getenv('FERNET_KEY', ""))
        key = base64.urlsafe_b64encode(b_key)
        logger.info("Fernet Key {}".format(key))
        try:
            self.crypt = Fernet(key)
        except ValueError:
            logger.error("Null decryption key given")
        hal_credentials = self._get_hal_credentials()
        self._credentials_dict = {'hal': hal_credentials}

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
            return self._credentials_dict[user]
        except KeyError:
            # create and encrypt state
            state = {'state_id': str(state_id.hex), 'user_id': user}
            encrypted_state = self.crypt.encrypt(json.dumps(state).encode('utf-8'))

            # generate flow, and begin auth
            flow = client.OAuth2WebServerFlow(client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
                                              client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
                                              scope=SCOPES,
                                              redirect_uri=os.getenv("CALLBACK_URI", ""))
            flow.params['access_type'] = 'offline'
            auth_uri = flow.step1_get_authorize_url(state=encrypted_state)
            if not is_direct_message(event['channel']):
                self.msg_writer.send_message(event['channel'],
                                             "I'll send you the authorization link in a direct message")
            channel = event['user_dm']
            self.msg_writer.send_message(channel, "Click here to authorize {}".format(auth_uri))
            return None

    # This function feels really janky
    def add_credential_return_state_id(self, credentials, state):

        try:
            raw_string = self.crypt.decrypt(state.encode('utf-8'))
        except InvalidToken:
            logger.error("Invalid decryption key given")
            return

        state_json = json.loads(raw_string.decode('ascii'))
        user_id = state_json.get('user_id')
        self._credentials_dict.update({user_id: credentials})

        return uuid.UUID(state_json.get('state_id'))


def send_email(msg_writer, event, wit_entities, credentials):
    """
    :param msg_writer: A message writer used to write output to slack
    :param event: The triggering event
    :param wit_entities: The entities of the wit response
    :param credentials: A Google Credentials object used to validate with google Oauth
    send_email generates an email from the message text and sends it to the indicated email address
    :return: A WaitState if the user is not authenticated, nothing if they are
    """
    state_id = uuid4()
    current_creds = credentials.get_credential(event, state_id, user=event['user'])
    if current_creds is None:
        state = WaitState(build_uuid=state_id, intent_value='send-email', event=event,
                          wit_entities=wit_entities, credentials=credentials)
        return state
    http = current_creds.authorize(httplib2.Http())
    service = discovery.build('gmail', 'v1', http=http)

    msg_text = event['cleaned_text']
    email_string = "<mailto:.*@.*\..*\|.*@.*\..*>"  # matches <mailto:example@sample.com|example@sample.com>
    string_cleaner = re.compile(email_string)
    cleaned_msg_text = string_cleaner.sub("", msg_text)
    msg_to = get_highest_confidence_entity(wit_entities, 'email')['value']
    if not msg_to:
        msg_writer.send_message(event['channel'], "I can't understand where you want me to send the message, sorry")
        return

    message = MIMEText(cleaned_msg_text)
    message['to'] = msg_to
    message['from'] = "{}@galatea-associates.com".format(event['user_name']['profile']['last_name'])
    message['subject'] = "Message via Hal from {}".format(event['user_name']['profile']['real_name'])

    message_encoded = {'raw': base64.urlsafe_b64encode(message.as_string().encode('utf-8')).decode('utf-8')}

    service.users().messages().send(userId="me", body=message_encoded).execute()


def google_query(function, parameters, event):
    """
    :param function: Name of the function to be called in google scripts
    :param parameters: parameters of the function
    :param event: Event object containing information about the slack event
    This function should not be used. Currently used by galastats.py, but that should be upgraded, and this function
    deleted
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
    """
    error used in google_query. Should be deleted along with google_query
    """
    def __init__(self, *error_args):
        Exception.__init__(self, "Bad response status {}".format(error_args))
