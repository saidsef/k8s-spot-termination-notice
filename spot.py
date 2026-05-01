#!/usr/bin/env python3

import os
import logging
from time import time, sleep
from requests import get, exceptions
from slack_sdk import WebClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Spot(object):
  def __init__(self):
    self.slack_api_token = os.environ.get('SLACK_API_TOKEN')
    self.slack_channel = os.environ.get('SLACK_CHANNEL')
    self.cluster = os.environ.get('CLUSTER')
    self.ec2_meta_data = 'http://169.254.169.254/latest/dynamic/instance-identity/document/'
    self.spot_meta_url = 'http://169.254.169.254/latest/meta-data/spot/termination-time'
    self.sleep = 5

  def instance_details(self):
    try:
      return get(self.ec2_meta_data, timeout=3).json()
    except exceptions.RequestException as e:
      logger.error(f"Request error: {e}")
      return {"status": "error", "message": f"Request error: {e}"}
    except Exception as e:
      logger.error(f"Error fetching instance details: {e}")
      return {"status": "error", "message": f"Could not fetch instance details: {e}"}

  def payload(self, m):
    details = self.instance_details()
    cluster_name = self.cluster or 'Default'
    return [{
      "fallback": m,
      "color": "#a30b24",
      "pretext": "",
      "author_name": "Mr Bot",
      "author_icon": "http://ohai.mr-bot.co/assets/mrbot-500-5a2319d6ea6fa0362f73f3334805e012.png",
      "title": "Spot Instance Termination Notice",
      "title_link": "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-interruptions.html",
      "text": "Cluster: {}, instanceId: {}, accountId: {}, AZ: {}, instanceType: {}".format(cluster_name, details['instanceId'], details['accountId'], details['availabilityZone'], details['instanceType']),
      "fields": [{
        "title": "Priority",
        "value": "High",
        "short": "false"
      }],
      "footer": "SpotInstaceWatcher",
      "ts": time()
    }]

  def slackit(self):
    slack = WebClient(token=self.slack_api_token)
    slack.api_call(
      "chat.postMessage",
      channel=self.slack_channel,
      attachments=self.payload('terminated!')
    )

  def watcher(self):
    while get(self.spot_meta_url, timeout=3).status_code != 200:
      logger.info(f"Instance {self.instance_details().get('instanceId')} still alive, looping ...")
      sleep(self.sleep)

    self.slackit()


if __name__ == '__main__':
  spot = Spot()
  spot.watcher()
