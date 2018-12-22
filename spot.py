#!/bin/env python3

import os
import logging
from time import time, sleep
from requests import get, post
from slackclient import SlackClient

logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR)

class Spot(object):
    def __init__(self):
        self.SLACK_API_TOKEN = os.environ.get('SLACK_API_TOKEN', None)
        self.SLACK_CHANNEL   = os.environ.get('SLACK_CHANNEL', None)
        self.EC2_META_DATA   = 'http://169.254.169.254/latest/dynamic/instance-identity/document/'
        self.SPOT_META_URL   = 'http://169.254.169.254/latest/meta-data/spot/termination-time'
        self.SLEEP           = 5
        self.CLUSTER         = os.environ.get('CLUSTER'. 'Default')

    def instance_details(self):
        return get(self.EC2_META_DATA, timeout=3).json()

    def payload(self, m):
        details = self.instance_details()
        return [{
            "fallback": m,
            "color": "#a30b24",
            "pretext": "",
            "author_name": "Mr Bot",
            "author_icon": "http://ohai.mr-bot.co/assets/mrbot-500-5a2319d6ea6fa0362f73f3334805e012.png",
            "title": "Spot Instance Termination Notice",
            "title_link": "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-interruptions.html",
            "text": "Cluster: {}, instanceId: {}, accountId: {}, AZ: {}, instanceType: {}".format(self.CLUSTER, details['instanceId'], details['accountId'], details['availabilityZone'], details['instanceType']),
            "fields": [{
                "title": "Priority",
                "value": "High",
                "short": "false"
            }],
            "footer": "SpotInstaceWatcher",
            "ts": time()
        }]

    def slackit(self):
        slack = SlackClient(self.SLACK_API_TOKEN)
        slack.api_call(
            "chat.postMessage",
            channel=self.SLACK_CHANNEL,
            attachments = self.payload('terminated!')
        )

    def watcher(self):
        while get(self.SPOT_META_URL).status_code != 200:
            logging.info('still alive, looping ...')
            sllep(self.SLEEP)

        self.slackit()

if __name__ == '__main__':
    spot = Spot()
    spot.watcher()
