import unittest
import requests
from unittest.mock import patch, MagicMock
from spot import Spot


class TestSpotInstanceNotifier(unittest.TestCase):
  def setUp(self):
    patcher = patch('os.environ.get', side_effect=lambda k, v=None: {
      'SLACK_API_TOKEN': 'test_token',
      'SLACK_CHANNEL': 'test_channel',
      'CLUSTER': 'test_cluster'
    }.get(k, v))
    self.addCleanup(patcher.stop)
    self.mock_env = patcher.start()

    self.mock_get = patch('spot.get').start()
    self.addCleanup(patch.stopall)

    self.mock_slack = patch('slack_sdk.WebClient').start()
    self.addCleanup(patch.stopall)

  def test_initialization(self):
    spot = Spot()
    self.assertEqual(spot.slack_api_token, 'test_token')
    self.assertEqual(spot.slack_channel, 'test_channel')
    self.assertEqual(spot.cluster, 'test_cluster')
    self.assertEqual(spot.sleep, 5)

  def test_instance_details_success(self):
    expected = {
      'instanceId': 'i-1234567890abcdef0',
      'accountId': '123456789012',
      'availabilityZone': 'us-west-2b',
      'instanceType': 'm4.large'
    }
    self.mock_get.return_value.json.return_value = expected

    spot = Spot()
    result = spot.instance_details()

    self.mock_get.assert_called_once_with(spot.ec2_meta_data, timeout=3)
    self.assertEqual(result, expected)

  def test_instance_details_request_error(self):
    self.mock_get.side_effect = requests.exceptions.ConnectionError("connection refused")

    spot = Spot()
    result = spot.instance_details()

    self.assertEqual(result["status"], "error")
    self.assertIn("connection refused", result["message"])

  def test_payload_construction(self):
    spot = Spot()
    spot.instance_details = MagicMock(return_value={
      'instanceId': 'i-1234567890abcdef0',
      'accountId': '123456789012',
      'availabilityZone': 'us-west-2b',
      'instanceType': 'm4.large'
    })
    payload = spot.payload('terminated!')

    self.assertIsInstance(payload, list)
    self.assertIn('Spot Instance Termination Notice', payload[0]['title'])
    self.assertIn('Cluster: test_cluster', payload[0]['text'])

  def test_payload_default_cluster(self):
    patcher = patch('os.environ.get', side_effect=lambda k, v=None: {
      'SLACK_API_TOKEN': 'test_token',
      'SLACK_CHANNEL': 'test_channel'
    }.get(k, v))
    patcher.start()
    self.addCleanup(patcher.stop)

    spot = Spot()
    spot.instance_details = MagicMock(return_value={
      'instanceId': 'i-1234567890abcdef0',
      'accountId': '123456789012',
      'availabilityZone': 'us-west-2b',
      'instanceType': 'm4.large'
    })
    payload = spot.payload('terminated!')

    self.assertIn('Cluster: Default', payload[0]['text'])

  def test_watcher_sends_slack_on_termination(self):
    spot = Spot()
    spot.slackit = MagicMock()
    spot.instance_details = MagicMock(return_value={'instanceId': 'i-123'})

    responses = [MagicMock(status_code=404), MagicMock(status_code=200)]
    self.mock_get.side_effect = responses

    spot.watcher()

    self.assertEqual(self.mock_get.call_count, 2)
    spot.slackit.assert_called_once()

  def test_watcher_ignores_non_200_statuses(self):
    spot = Spot()
    spot.slackit = MagicMock()
    spot.sleep = 0.01
    spot.instance_details = MagicMock(return_value={'instanceId': 'i-123'})

    responses = [MagicMock(status_code=404), MagicMock(status_code=500), MagicMock(status_code=200)]
    self.mock_get.side_effect = responses

    spot.watcher()

    self.assertEqual(self.mock_get.call_count, 3)
    spot.slackit.assert_called_once()


if __name__ == '__main__':
  unittest.main()
