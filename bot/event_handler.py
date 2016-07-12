import json
import logging


from gala_wit import GalaWit
from intenthandlers.utils import get_highest_confidence_entity
from intenthandlers.misc import say_quote
from intenthandlers.misc import randomize_options
from intenthandlers.misc import flip_coin
from intenthandlers.galastats import GalateanStore
from intenthandlers.drive import view_drive_file
from intenthandlers.drive import create_drive_file
from intenthandlers.drive import delete_drive_file
# from intenthandlers.google_actions import send_email
from intenthandlers.drive import get_google_drive_list
from slack_clients import is_direct_message


logger = logging.getLogger(__name__)

# this is a mapping of wit.ai intents to code that will handle those intents
"""
intents = {
    'movie-quote': (say_quote, 'movie quote'),
    'galatean-count': (self.gala_store.count_galateans, 'How many Galateans are in Boston?'),
    'randomize': (randomize_options, 'Decide between burgers and tacos'),
    'coin-flip': (flip_coin, 'flip a coin'),
    'get-google-drive': (get_google_drive_list, "What is in your google drive?"),
    'view-drive-file': (view_drive_file, "show getting started"),
    'create-drive-file': (create_drive_file, "create filename"),
    'delete-drive-file': (delete_drive_file, "delete filename"),
    'send-email': (send_email, "hello person@galatea-associates.com"),
    # ' view-calendar': (view_calendar, "calendar") Not currently very functional
}"""

# List of users for the bot to ignore
user_ignore_list = ['USLACKBOT']

conversation_intent_types = []

class RtmEventHandler(object):
    def __init__(self, slack_clients, msg_writer):
        self.clients = slack_clients
        self.msg_writer = msg_writer
        self.wit_client = GalaWit()
        self.gala_store = None
        self.intents = {
            'movie-quote': (say_quote, 'movie quote'),
            'galatean-count': (self._count_galateans, 'How many Galateans are in Boston?'),
            'randomize': (randomize_options, 'Decide between burgers and tacos'),
            'coin-flip': (flip_coin, 'flip a coin'),
            'get-google-drive': (get_google_drive_list, "What is in your google drive?"),
            'view-drive-file': (view_drive_file, "show getting started"),
            'create-drive-file': (create_drive_file, "create filename"),
            'delete-drive-file': (delete_drive_file, "delete filename"),
            # 'send-email': (send_email, "hello person@galatea-associates.com"),
        }
        self.conversations = set()

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

        # Initialize self.gala_store if this is the first message
        self._initialize_galastats(event)

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
                event.add({"conversation": match})

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
            if conversation['waiting_for'] == intent:
                possible_matches.append(conversation)
        if not possible_matches:
            return
        elif len(possible_matches) == 1:
            return possible_matches[0]
        else:
            # do something to account for multiple matches
            return possible_matches[0]

    def _conversations_update(self, conversation):
        if conversation:
            found = False
            for old_conv in self.conversations:
                if old_conv['id'] == conversation['id']:
                    self.conversations.remove(old_conv)
                    self.conversations.add(conversation)
            if not found:
                self.conversations.add(conversation)

    # Initializes galastats upon the first user message event
    def _initialize_galastats(self, event):
        if self.gala_store is not None:
            pass
        else:
            self.gala_store = GalateanStore(event)

    # Wrapper function to handle the fact that gala_store can't be initialized until the first
    # user message event.
    def _count_galateans(self, msg_writer, event, wit_resp):
        return self.gala_store.count_galateans(msg_writer, event, wit_resp)
