#!/bin/env python3

import os
import logging
from time import time, sleep
from requests import get, exceptions
from slack_sdk import WebClient

# Configure logging
logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Spot(object):
  """
  A class to monitor AWS EC2 Spot Instance interruptions and notify via Slack.

  Attributes:
  SLACK_API_TOKEN (str): Slack API token for authentication.
  SLACK_CHANNEL (str): Slack channel ID where notifications will be sent.
  EC2_META_DATA (str): URL to fetch EC2 instance metadata.
  SPOT_META_URL (str): URL to check for EC2 Spot Instance termination notices.
  SLEEP (int): Time in seconds to wait between checks for termination notices.
  CLUSTER (str): Name of the cluster the instance belongs to.
  """

  def __init__(self):
    """
    Initializes the Spot instance with environment variables and constants.
    """
    self.SLACK_API_TOKEN = os.environ.get('SLACK_API_TOKEN', None)
    self.SLACK_CHANNEL = os.environ.get('SLACK_CHANNEL', None)
    self.EC2_META_DATA = 'http://169.254.169.254/latest/dynamic/instance-identity/document/'
    self.SPOT_META_URL = 'http://169.254.169.254/latest/meta-data/spot/termination-time'
    self.SLEEP = 5
    self.CLUSTER = os.environ.get('CLUSTER', None)

  def instance_details(self):
    """
    Fetches and returns the EC2 instance details.

    Returns:
    dict: A dictionary containing the EC2 instance details.
    """
    try:
      return get(self.EC2_META_DATA, timeout=3).json()
    except exceptions.RequestException as e:
      logging.error(f"Request error: {e}")
      return {"status": "error", "message": f"Request error: {e}"}
    except exceptions.ConnectionError as e:
      logging.error(f"Connection error: {e}")
      return {"status": "error", "message": f"Connection error: {e}"}
    except Exception as e:
      logging.error(f"Error fetching instance details: {e}")
      return {"status": "error", "message": f"Could not fetch instance details: {e}"}

  def payload(self, m):
    """
    Constructs the payload to be sent to Slack.

    Args:
    m (str): The message to be included in the payload.

    Returns:
    list: A list containing the payload dictionary.
    """
    details = self.instance_details()
    CLUSTER = 'Default' if self.CLUSTER is None else self.CLUSTER
    return [{
      "fallback": m,
      "color": "#a30b24",
      "pretext": "",
      "author_name": "Mr Bot",
      "author_icon": "http://ohai.mr-bot.co/assets/mrbot-500-5a2319d6ea6fa0362f73f3334805e012.png",
      "title": "Spot Instance Termination Notice",
      "title_link": "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-interruptions.html",
      "text": "Cluster: {}, instanceId: {}, accountId: {}, AZ: {}, instanceType: {}".format(CLUSTER, details['instanceId'], details['accountId'], details['availabilityZone'], details['instanceType']),
      "fields": [{
        "title": "Priority",
        "value": "High",
        "short": "false"
      }],
      "footer": "SpotInstaceWatcher",
      "ts": time()
    }]

  def slackit(self):
    """
    Sends a notification to Slack using the constructed payload.
    """
    slack = WebClient(token=self.SLACK_API_TOKEN)
    slack.api_call(
      "chat.postMessage",
      channel=self.SLACK_CHANNEL,
      attachments=self.payload('terminated!')
    )

  def watcher(self):
    """
    Monitors for EC2 Spot Instance termination notices and sends notifications.
    """
    while get(self.SPOT_META_URL).status_code != 200:
      logging.info(f"Instance {self.instance_details().get('instanceId')} still alive, looping ...")
      sleep(self.SLEEP)

    self.slackit()


if __name__ == '__main__':
  spot = Spot()
  spot.watcher()
