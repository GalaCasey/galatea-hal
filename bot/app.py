#!/usr/bin/env python

import logging
import os
from threads import FlaskThread, WorkerPoolThread
from queue import Queue

from beepboop import resourcer
from beepboop import bot_manager

from slack_bot import SlackBot
from slack_bot import spawn_bot

logger = logging.getLogger(__name__)


def main():
    log_level = os.getenv("LOG_LEVEL", "INFO")
    logging.basicConfig(format='%(asctime)s - %(levelname)s: %(message)s', level=log_level)
    # Log this at error level even though it's not an error, because we want to be sure the message is seen
    logging.error("logging level: {}".format(log_level))

    slack_token = os.getenv("SLACK_TOKEN", "")
    logging.info("slack token: {}".format(slack_token))

    if slack_token == "":
        logging.info("SLACK_TOKEN env var not set, expecting token to be provided by Resourcer events")
        slack_token = None
        botManager = bot_manager.BotManager(spawn_bot)
        res = resourcer.Resourcer(botManager)
        res.start()
    else:
        state_updating_q = Queue()
        flask_thread = FlaskThread(state_updating_q)
        flask_thread.start()
        event_processing_q = Queue()
        intent_runner_pool = WorkerPoolThread(event_processing_q, state_updating_q)
        intent_runner_pool.start()
        # only want to run a single instance of the bot in dev mode
        bot = SlackBot(state_updating_q, event_processing_q, slack_token)
        bot.start({})


if __name__ == "__main__":
    main()
