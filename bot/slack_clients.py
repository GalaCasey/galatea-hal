import requests
import logging
import re
import time
import json

from intenthandlers.utils import memoized
from slacker import Slacker
from slackclient import SlackClient

logger = logging.getLogger(__name__)


def is_direct_message(channel_id):
    return re.search('^D', channel_id)


class SlackClients(object):
    def __init__(self, token):
        self.token = token

        data = {"token": self.token}
        target_url = "https://slack.com/api/users.list"
        resp = requests.get(target_url, data)
        if resp.status_code == 200:
            resp_json = json.loads(resp.text)
            self.users = resp_json['members']
        else:
            self.users = []
            logger.error("Failed to get user list")

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

    @memoized
    def get_user_name_from_id(self, user_id):
        for user in self.users:
            if user['id'] == user_id:
                return user

        # Called when user is not found in self.users
        data = {"token": self.token, "user": user_id}
        target_url = "https://slack.com/api/users.info"
        resp = requests.get(target_url, data)
        if resp.status_code == 200:
            resp_json = json.loads(resp.text)
            user = resp_json['user']
            self.users.append(user)
            return user
        else:
            logger.error("username request failed")
            return "username request failed"

    @memoized
    def get_channel_name_from_id(self, channel_id):
        data = {"token": self.token, "channel": channel_id}
        target_url = "https://slack.com/api/channels.info"
        resp = requests.get(target_url, data)
        if resp.status_code == 200:
            resp_json = json.loads(resp.text)
            channel = resp_json['channel']
            return channel
        else:
            logger.info("channel name request failed")
            return "channel name request failed"
