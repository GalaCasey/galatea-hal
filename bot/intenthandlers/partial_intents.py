import logging

logger = logging.getLogger(__name__)


def partial_randomize(msg_writer, event, wit_resp):
    options = wit_resp.get('entities').get('randomize_options')
    msg_writer.send_message(event['channel'], "_{}_".format(random.choice(options)['value']))