import logging
import os
from wit import Wit
from intenthandlers.utils import get_highest_confidence_entity
from intenthandlers.misc import randomize_options, flip_coin, say_quote
from intenthandlers.galastats import count_galateans

logger = logging.getLogger(__name__)

intents = {
    'movie-quote': (say_quote, 'movie quote'),
    'galatean-count': (count_galateans, 'How many Galateans are in Boston?'),
    'randomize': (randomize_options, 'Decide between burgers and tacos'),
    'coin-flip': (flip_coin, 'flip a coin')
}

def merge(wit_session_id, context, response):
    intent = get_highest_confidence_entity(response.get('entities'), 'intent')['value']
    if intent is not None: context['intent'] = intent

    randomize_option = map(lambda x: x.get('value'), response.get('entities').get('randomize_option'))
    if randomize_option is not None:
        context['randomize_option'] = randomize_option

    return context


def say(wit_session_id, context, msg, msg_writer, event):
    msg_writer.send_message(event['channel'], "_{}_".format(msg.get('msg')))
    return context


def error(wit_session_id, context, e):
    # Stub implementation
    raise RuntimeError("Should not have been called. Session: {}. Err   : {}. Context: {}".format(session_id, str(e),
                                                                                                  context))


class GalaWit(object):
    def __init__(self, witlib=Wit):  # Added witlib=Wit to allow test code to send a mock Wit
        wit_token = os.getenv("WIT_ACCESS_TOKEN", "")
        logger.info("wit access token: {}".format(wit_token))

        if wit_token == "":
            logger.error("WIT_ACCESS_TOKEN env var not set.  Will not be able to connect to WIT.ai!")

        # Using dummy implementation of actions since we don't expect to use conversations for now
        # Simple "understanding" interactions with wit.ai shouldn't require these actions to be implemented
        self.actions = {
            'say': say,
            'error': error,
            'merge': merge,
        }
        for intent in intents:
            self.actions[intent] = intents[intent][0]

        self.wit_client = witlib(wit_token, self.actions, logger)

    def interpret(self, msg):
        resp = self.wit_client.message(msg)
        logger.info("resp {}".format(resp))
        return resp

    def evaluate(self, msg, context, wit_session_id, msg_writer, event):
        live_context = context
        while True:
            if live_context == context:
                resp = self.wit_client.converse(wit_session_id, msg, live_context)
            else:
                resp = self.wit_client.converse(wit_session_id, live_context)
            logger.info("resp is {}".format(resp))
            if resp.get('confidence') <= 0:  # .75 in prod
                msg_writer.write_prompt(event['channel'], intents)
                return None
            elif resp.get('type') == 'stop':
                return live_context
            elif resp.get('type') == 'say':
                live_context = self.actions.get('say')(wit_session_id, context, resp, msg_writer, event)
            elif resp.get('type') == 'merge':
                live_context = self.actions.get('merge')(wit_session_id, context, resp)
            else:
                action = resp.get('action')
                if action is None:
                    msg_writer.write_prompt(event['channel'], intents)
                    return None
                logger.info("actions {}".format(self.actions[action]))
                live_context = self.actions[action](msg_writer, event, resp.get('entities'))