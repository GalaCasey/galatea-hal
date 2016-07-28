import json
import logging

from gala_wit import GalaWit
from intenthandlers.utils import get_highest_confidence_entity
from intenthandlers.misc import say_quote
from intenthandlers.misc import randomize_options
from intenthandlers.misc import flip_coin
from intenthandlers.conversation_matching import onboarding_conversation_match
from intenthandlers.conversation_matching import nag_conversation_match
from intenthandlers.galastats import count_galateans
from intenthandlers.google_helpers import GoogleCredentials
from intenthandlers.drive import view_drive_file
from intenthandlers.drive import create_drive_file
from intenthandlers.drive import delete_drive_file
from intenthandlers.google_helpers import send_email
from intenthandlers.drive import get_google_drive_list
from state import WaitState
from state import ConversationState
from slack_clients import is_direct_message
from oauth2client import client
import os
from intenthandlers.google_helpers import SCOPES


logger = logging.getLogger(__name__)

# List of users for the bot to ignore
user_ignore_list = ['USLACKBOT']

# A list of intents which are part of conversations. Could be merged into intents as a separate entry in the tuple
conversation_intent_types = {
    'accounts-setup': onboarding_conversation_match,
    'desk-setup': onboarding_conversation_match,
    'phones-setup': onboarding_conversation_match,
    'email-setup': onboarding_conversation_match,
    'slack-setup': onboarding_conversation_match,
    'onboarding-start': None,
    'nag-users': None,
    'nag-response': nag_conversation_match
}


class RtmEventHandler(object):
    def __init__(self, slack_clients, msg_writer, event_processing_q, state_updating_q):
        self.state_updating_q = state_updating_q  # this q holds objects which update some internal state
        self.event_processing_q = event_processing_q  # this q holds objects representing events to act upon
        self.clients = slack_clients
        self.msg_writer = msg_writer
        self.wit_client = GalaWit()
        self.conversations = {}
        self.wait_states = {}
        self.credentials = GoogleCredentials(msg_writer, slack_clients)
        # this is a mapping of wit.ai intents to code that will handle those intents
        self.intents = {
            'movie-quote': (say_quote, 'movie quote'),
            'galatean-count': (count_galateans, 'How many Galateans are in Boston?'),
            'randomize': (randomize_options, 'Decide between burgers and tacos'),
            'coin-flip': (flip_coin, 'flip a coin'),
            'get-google-drive': (get_google_drive_list, "What is in your google drive?"),
            'view-drive-file': (view_drive_file, "show getting started"),
            'create-drive-file': (create_drive_file, "create filename"),
            'delete-drive-file': (delete_drive_file, "delete filename"),
            'nag-users': (self.clients.nag_users, "Nag John Casey about hal"),
            'nag-response': (self.clients.nag_response, "I did the task"),
            'send-email': (send_email, "hello person@galatea-associates.com"),
        }

    def state_check(self):
        """
        Called regularly by the slack bot. Used to ensure that state is maintained.
        """
        if not self.state_updating_q.empty():
            self._process_q()

    def handle(self, event):
        if 'type' in event:
            self._handle_by_type(event['type'], event)

    def _handle_by_type(self, event_type, event):
        # See https://api.slack.com/rtm for a full list of events
        # logger.info("event type is {}".format(event_type))
        if event_type == 'error':
            # error
            self.msg_writer.write_error(event['channel'], json.dumps(event))
        elif event_type == 'message':
            # message was sent to channel
            self._handle_message(event)
        elif event_type == 'channel_joined':
            # you joined a channel
            self.msg_writer.say_hi(event['channel'], event.get('user', ""))
        elif event_type == 'group_joined':
            # you joined a private group
            self.msg_writer.say_hi(event['channel'], event.get('user', ""))
        else:
            pass

    def _handle_message(self, event):

        if not self._proof_message(event):
            return

        msg_txt = event['text']
        channel_id = event['channel']

        # Remove mention of the bot so that the rest of the code doesn't need to
        msg_txt = self.clients.remove_mention(msg_txt).strip()

        # Ask wit to interpret the text and send back a list of entities
        logger.info("Asking wit to interpret| {}".format(msg_txt))
        wit_resp = self.wit_client.interpret(msg_txt)

        # Add username and channel name, user dm, and cleaned text to the event object
        user_name = self.clients.get_user_name_from_id(event['user'])
        if is_direct_message(channel_id):
            channel_name = "Direct Message"
        else:
            channel_name = self.clients.get_channel_name_from_id(channel_id)
        event.update({
            "user_name": user_name,
            "channel_name": channel_name,
            "user_dm": self.clients.get_dm_id_from_user_id(event['user']),
            "cleaned_text": msg_txt
        })

        # Find the intent with the highest confidence that met our default threshold
        intent_entity = get_highest_confidence_entity(wit_resp['entities'], 'intent')

        # If we couldn't find an intent entity, let the user know
        if intent_entity is None:
            self.msg_writer.write_prompt(channel_id, self.intents)
            return

        intent_value = intent_entity['value']
        if intent_value in conversation_intent_types:
            match = self._conversation_match(intent_value, wit_resp, event)
            if match:
                event.update({"conversation": match})

        if intent_value in self.intents:
            t = {
                'intent': self.intents[intent_value][0],
                'msg_writer': self.msg_writer,
                'event': event,
                'wit_entities': wit_resp['entities'],
                'credentials': self.credentials,
                'state_q': self.state_updating_q
            }
            self.event_processing_q.put(t)

        else:
            raise ReferenceError("No function found to handle intent {}".format(intent_value))

    def _process_q(self):
        state = self.state_updating_q.get()
        if state['type'] == 'flask_response':
            self._check_flask(state)
        elif state['type'] == 'state_update':
            self._handle_state_change(state)

    def _check_flask(self, auth_json):
        """
        _check_flask checks to see if there are any messages from the flask thread. If there are, it processes them
        by finishing the authentication flow, and then resuming the interrupted user command.
        :return: None
        """
        auth_code = auth_json.get('auth_code')
        encrypted_state = auth_json.get('encrypted_state')
        if auth_code is not None:

            flow = client.OAuth2WebServerFlow(client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
                                              client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
                                              scope=SCOPES,
                                              redirect_uri=os.getenv("CALLBACK_URI", ""))
            credentials = flow.step2_exchange(auth_code)
            state_id = self.credentials.add_credential_return_state_id(credentials, encrypted_state)
            logger.info('state id {}'.format(state_id))
            logger.info('waitstates {}'.format(self.wait_states))
            state = self.wait_states.get(state_id)
            logger.info('state {}'.format(state))

            if state is None:
                raise KeyError

            t = {
                'intent': self.intents[state.get_intent_value()][0],
                'msg_writer': self.msg_writer,
                'event': state.get_event(),
                'wit_entities': state.get_wit_entities(),
                'credentials': state.get_credentials(),
                'state_q': self.state_updating_q
            }
            self.event_processing_q.put(t)
            self.wait_states.pop(state_id)
        else:
            state_id = self.credentials.return_state_id(encrypted_state)
            self.wait_states.pop(state_id)

    def _handle_state_change(self, state_json):
        """
        :param state_json: The state returned by the intent handling function
        Updates the state dicts based on they type of the state returned.
        :return: None
        """
        state = state_json['state']
        if isinstance(state, ConversationState):
            self._conversations_update(state)
        elif isinstance(state, WaitState):
            self.wait_states.update({state.get_id(): state})

    def _proof_message(self, event):
        """
        :param event: The triggering message event
        Checks the event to see if this is a message that should be processed
        :return: Bool indicating whether or not the Rtm should continue processing the message
        """
        # Event won't have a user if slackbot is unfurling messages for you
        if 'user' not in event:
            return False

        # Filter out messages from the bot itself
        if self.clients.is_message_from_me(event['user']):
            return False

        msg_txt = event['text']
        channel_id = event['channel']

        # Filter out message unless this bot is mentioned or it is a direct message
        if not (is_direct_message(channel_id) or self.clients.is_bot_mention(msg_txt)):
            return False

        # Ensure that we don't go to wit with messages posted by an ignored user
        if event['user'] in user_ignore_list:
            return False

        return True

    def _conversation_match(self, intent, wit_resp, event):
        """
        :param intent: The most likely intended intent returned by wit
        :param wit_resp: The total response from wit
        :param event: The triggering event
        _conversation_match attempts to return the conversation connected to the event based on event information and
        the wit response
        :return: A Conversation State from self.conversations
        """
        possible_matches = []
        for conversation in self.conversations:
            if intent in self.conversations[conversation].get_waiting_for():
                possible_matches.append(self.conversations[conversation])
        if not possible_matches:
            return
        elif len(possible_matches) == 1:
            return possible_matches[0]
        else:
            # Not fully implemented, will certainly break if called
            return conversation_intent_types[intent](possible_matches, wit_resp, event)

    def _conversations_update(self, conversation):
        """
        :param conversation: A Conversation that needs to be updated, added to, or removed from self.conversations
        _conversations_update adds to, updates, or removes from self.conversations based on the id and the state of the
        passed conversation
        :return: None
        """
        conv_id = conversation.get_id()
        if conv_id in self.conversations:
            if conversation.complete():
                self.conversations.pop(conv_id)
            else:
                self.conversations[conv_id] = conversation
        else:
            self.conversations[conv_id] = conversation
