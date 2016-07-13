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
from intenthandlers.drive import view_drive_file
from intenthandlers.drive import create_drive_file
from intenthandlers.drive import delete_drive_file
# from intenthandlers.google_actions import send_email
from intenthandlers.drive import get_google_drive_list
from slack_clients import is_direct_message


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
    def __init__(self, slack_clients, msg_writer):
        self.clients = slack_clients
        self.msg_writer = msg_writer
        self.wit_client = GalaWit()
        self.conversations = []
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
            'nag-response': (self.clients.nag_response, "I did the task")
            # 'send-email': (send_email, "hello person@galatea-associates.com"),
        }

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

        # Add username and channel name to the event object
        user_name = self.clients.get_user_name_from_id(event['user'])
        if is_direct_message(channel_id):
            channel_name = "Direct Message"
        else:
            channel_name = self.clients.get_channel_name_from_id(channel_id)
        event.update({"user_name": user_name, "channel_name": channel_name})

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
            self._conversations_update(self.intents[intent_value][0](self.msg_writer, event, wit_resp['entities']))
        else:
            raise ReferenceError("No function found to handle intent {}".format(intent_value))

    def _proof_message(self, event):
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
        possible_matches = []
        for conversation in self.conversations:
            if intent in conversation['waiting_for']:
                possible_matches.append(conversation)
        if not possible_matches:
            return
        elif len(possible_matches) == 1:
            return possible_matches[0]
        else:
            return conversation_intent_types[intent](possible_matches, wit_resp, event)

    def _conversations_update(self, conversation):
        if conversation:
            found = False
            for old_conv in self.conversations:
                if old_conv['id'] == conversation['id']:
                    found = True
                    self.conversations.remove(old_conv)
                    if not conversation['done']:
                        self.conversations.append(conversation)
            if not found:
                self.conversations.append(conversation)