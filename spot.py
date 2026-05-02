#!/usr/bin/env python3

import os
import logging
import json
from time import time, sleep
from requests import get, exceptions
from slack_sdk import WebClient
from kubernetes import client, config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Spot(object):
  def __init__(self):
    self.slack_api_token = os.environ.get('SLACK_API_TOKEN')
    self.slack_channel = os.environ.get('SLACK_CHANNEL')
    self.cluster = os.environ.get('CLUSTER')
    self.node_name = os.environ.get('NODE_NAME')
    self.drain_node = str(os.environ.get('DRAIN_NODE', 'false')).lower() == 'true'
    self.meta_base = 'http://169.254.169.254/latest'
    self.ec2_meta_data = f'{self.meta_base}/dynamic/instance-identity/document/'
    self.spot_meta_url = f'{self.meta_base}/meta-data/spot/instance-action'
    self.sleep = 5

  def _meta_get(self, url, timeout=3):
    try:
      token_resp = get(
        f'{self.meta_base}/api/token',
        headers={'X-aws-ec2-metadata-token-ttl-seconds': '21600'},
        timeout=timeout
      )
      if token_resp.status_code == 200:
        headers = {'X-aws-ec2-metadata-token': token_resp.text}
        return get(url, headers=headers, timeout=timeout)
    except exceptions.RequestException:
      pass
    return get(url, timeout=timeout)

  def instance_details(self):
    try:
      return self._meta_get(self.ec2_meta_data, timeout=3).json()
    except exceptions.RequestException as e:
      logger.error(f"Request error: {e}")
      return {"status": "error", "message": f"Request error: {e}"}
    except Exception as e:
      logger.error(f"Error fetching instance details: {e}")
      return {"status": "error", "message": f"Could not fetch instance details: {e}"}

  def instance_action(self):
    try:
      resp = self._meta_get(self.spot_meta_url, timeout=3)
      if resp.status_code == 200:
        return resp.json()
      return {}
    except exceptions.RequestException as e:
      logger.warning(f"Spot metadata request failed: {e}")
      return {}
    except Exception as e:
      logger.warning(f"Unexpected error reading spot metadata: {e}")
      return {}

  def payload(self, m, action='terminate'):
    details = self.instance_details()
    cluster_name = self.cluster or 'Default'
    return [{
      "fallback": m,
      "color": "#a30b24",
      "pretext": "",
      "author_name": "Mr Bot",
      "author_icon": "http://ohai.mr-bot.co/assets/mrbot-500-5a2319d6ea6fa0362f73f3334805e012.png",
      "title": "Spot Instance {} Notice".format(action.capitalize()),
      "title_link": "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-interruptions.html",
      "text": "Cluster: {}, instanceId: {}, accountId: {}, AZ: {}, instanceType: {}".format(
        cluster_name, details.get('instanceId', 'unknown'), details.get('accountId', 'unknown'),
        details.get('availabilityZone', 'unknown'), details.get('instanceType', 'unknown')
      ),
      "fields": [{
        "title": "Priority",
        "value": "High",
        "short": "false"
      }],
      "footer": "SpotInstaceWatcher",
      "ts": time()
    }]

  def slackit(self, action='terminate'):
    slack = WebClient(token=self.slack_api_token)
    slack.api_call(
      "chat.postMessage",
      channel=self.slack_channel,
      attachments=self.payload('terminated!', action)
    )

  def _is_daemonset_pod(self, pod):
    for ref in (pod.metadata.owner_references or []):
      if ref.kind == "DaemonSet":
        return True
    return False

  def _is_mirror_pod(self, pod):
    if pod.metadata.annotations and "kubernetes.io/config.mirror" in pod.metadata.annotations:
      return True
    return False

  def drain(self):
    if not self.drain_node:
      return
    if not self.node_name:
      logger.warning("NODE_NAME not set, skipping drain")
      return
    try:
      config.load_incluster_config()
      v1 = client.CoreV1Api()

      logger.info(f"Cordoning node {self.node_name} ...")
      body = {"spec": {"unschedulable": True}}
      v1.patch_node(self.node_name, body)

      logger.info(f"Evicting pods from node {self.node_name} ...")
      field_selector = f"spec.nodeName={self.node_name}"
      pods = v1.list_pod_for_all_namespaces(field_selector=field_selector)

      for pod in pods.items:
        if self._is_daemonset_pod(pod) or self._is_mirror_pod(pod):
          logger.info(f"Skipping pod {pod.metadata.namespace}/{pod.metadata.name}")
          continue
        try:
          eviction = client.V1Eviction(
            metadata=client.V1ObjectMeta(name=pod.metadata.name, namespace=pod.metadata.namespace),
            delete_options=client.V1DeleteOptions(grace_period_seconds=30)
          )
          v1.create_namespaced_pod_eviction(pod.metadata.name, pod.metadata.namespace, eviction)
          logger.info(f"Evicted pod {pod.metadata.namespace}/{pod.metadata.name}")
        except client.exceptions.ApiException as e:
          logger.error(f"Failed to evict pod {pod.metadata.namespace}/{pod.metadata.name}: {e.status} {e.reason}")

      logger.info(f"Node {self.node_name} drained successfully")
    except Exception as e:
      logger.error(f"Error draining node: {e}")

  def watcher(self):
    while True:
      action_data = self.instance_action()
      action = action_data.get('action', '')
      if action in ('terminate', 'stop'):
        break

      logger.info(f"Instance {self.instance_details().get('instanceId')} still alive, looping ...")
      sleep(self.sleep)

    self.drain()
    self.slackit(action)


if __name__ == '__main__':
  spot = Spot()
  spot.watcher()
