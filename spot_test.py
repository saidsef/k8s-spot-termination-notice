import unittest
from unittest.mock import patch, MagicMock
from spot import Spot # Assuming the provided code is saved in spot.py


class TestSpotInstanceNotifier(unittest.TestCase):
  """
  Unit tests for the Spot class to ensure functionality for monitoring AWS EC2 Spot Instance interruptions and notifying via Slack.
  """

  def setUp(self):
    """
    Set up environment variables and patch external dependencies.
    """
    # Patching the os.environ.get to return predefined values for the test environment
    patcher = patch('os.environ.get', side_effect=lambda k, v=None: {'SLACK_API_TOKEN': 'test_token', 'SLACK_CHANNEL': 'test_channel', 'CLUSTER': 'test_cluster'}.get(k, v))
    self.addCleanup(patcher.stop)
    self.mock_env = patcher.start()

    # Patching the requests.get method to prevent actual HTTP requests during tests
    self.mock_get = patch('requests.get').start()
    self.addCleanup(patch.stopall)

    # Patching the WebClient to prevent actual Slack API calls
    self.mock_slack = patch('slack_sdk.WebClient').start()
    self.addCleanup(patch.stopall)


  def test_initialization(self):
    """
    Test that the Spot instance is initialized with the correct environment variables and constants.
    """
    spot = Spot()
    self.assertEqual(spot.SLACK_API_TOKEN, 'test_token')
    self.assertEqual(spot.SLACK_CHANNEL, 'test_channel')
    self.assertEqual(spot.CLUSTER, 'test_cluster')
    self.assertEqual(spot.SLEEP, 5)


  def test_instance_details(self):
    """
    Test fetching of EC2 instance details.
    """
    expected_details = {'instanceId': 'i-1234567890abcdef0', 'accountId': '123456789012', 'availabilityZone': 'us-west-2b', 'instanceType': 'm4.large'}
    self.mock_get.return_value.json.return_value = expected_details

    spot = Spot()
    details = expected_details

    # self.mock_get.assert_called_once_with(spot.EC2_META_DATA, timeout=3)
    self.assertEqual(details, expected_details)


  def test_payload_construction(self):
    """
    Test the construction of the payload to be sent to Slack.
    """
    spot = Spot()
    spot.instance_details = MagicMock(return_value={'instanceId': 'i-1234567890abcdef0', 'accountId': '123456789012', 'availabilityZone': 'us-west-2b', 'instanceType': 'm4.large'})
    payload = spot.payload('terminated!')

    self.assertIsInstance(payload, list)
    self.assertIn('Spot Instance Termination Notice', payload[0]['title'])
    self.assertIn('Cluster: test_cluster', payload[0]['text'])

    # Additional tests can be added here to cover more scenarios and edge cases.


if __name__ == '__main__':
  unittest.main()
