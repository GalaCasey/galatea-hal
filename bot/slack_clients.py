import requests
import logging
import re
import time
import json

from slacker import Slacker
from slackclient import SlackClient

logger = logging.getLogger(__name__)


def is_direct_message(channel_id):
    return re.search('^D', channel_id)


class SlackClients(object):
    def __init__(self, token):
        self.token = token

        # Slacker is a Slack Web API Client
        self.web = Slacker(token)

        # SlackClient is a Slack Websocket RTM API Client
        self.rtm = SlackClient(token)

    def bot_user_id(self):
        return self.rtm.server.login_data['self']['id']

    def is_message_from_me(self, user):
        return user == self.rtm.server.login_data['self']['id']

    def is_bot_mention(self, message):
        bot_user_name = self.rtm.server.login_data['self']['id']
        if re.search("@{}".format(bot_user_name), message):
            return True
        else:
            return False

    def remove_mention(self, message):
        bot_user_name = self.rtm.server.login_data['self']['id']
        tmp = re.sub("<@{}>:".format(bot_user_name), "", message)
        tmp = re.sub("<@{}>".format(bot_user_name), "", tmp)
        return tmp

    def send_user_typing_pause(self, channel_id, sleep_time=3.0):
        user_typing_json = {"type": "typing", "channel": channel_id}
        self.rtm.server.send_to_websocket(user_typing_json)
        time.sleep(sleep_time)

    def get_user_name_from_id(self, user_id):
        data = {"token": self.token, "user": user_id}
        target_url = "https://slack.com/api/users.info"
        resp = requests.get(target_url, data)
        if resp.status_code == 200:
            resp_json = json.loads(resp.text)
            user_name = resp_json['user']['real_name']
            return user_name
        else:
            logger.info("username request failed")
            return "username request failed"

    def get_channel_name_from_id(self, channel_id):
        data = {"token": self.token, "channel": channel_id}
        target_url = "https://slack.com/api/channels.info"
        resp = requests.get(target_url, data)
        if resp.status_code == 200:
            resp_json = json.loads(resp.text)
            channel_name = resp_json['channel']['name']
            return channel_name
        else:
            logger.info("channel name request failed")
            return "channel name request failed"
