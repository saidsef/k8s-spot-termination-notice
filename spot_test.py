import unittest
import requests
from unittest.mock import patch, MagicMock
from kubernetes import client
from spot import Spot


class TestSpotInstanceNotifier(unittest.TestCase):
  def setUp(self):
    patcher = patch('os.environ.get', side_effect=lambda k, v=None: {
      'SLACK_API_TOKEN': 'test_token',
      'SLACK_CHANNEL': 'test_channel',
      'CLUSTER': 'test_cluster',
      'NODE_NAME': 'test-node',
      'DRAIN_NODE': 'false'
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
    self.assertEqual(spot.node_name, 'test-node')
    self.assertFalse(spot.drain_node)
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

  def test_initialization_drain_node_default(self):
    patcher = patch('os.environ.get', side_effect=lambda k, v=None: {
      'SLACK_API_TOKEN': 'test_token',
      'SLACK_CHANNEL': 'test_channel',
      'CLUSTER': 'test_cluster',
      'NODE_NAME': 'test-node'
    }.get(k, v))
    patcher.start()
    self.addCleanup(patcher.stop)

    spot = Spot()
    self.assertFalse(spot.drain_node)

  def test_initialization_drain_node_true(self):
    patcher = patch('os.environ.get', side_effect=lambda k, v=None: {
      'SLACK_API_TOKEN': 'test_token',
      'SLACK_CHANNEL': 'test_channel',
      'CLUSTER': 'test_cluster',
      'NODE_NAME': 'test-node',
      'DRAIN_NODE': 'true'
    }.get(k, v))
    patcher.start()
    self.addCleanup(patcher.stop)

    spot = Spot()
    self.assertTrue(spot.drain_node)

  def test_drain_skipped_when_disabled(self):
    spot = Spot()
    spot.drain_node = False
    spot.node_name = 'test-node'

    with patch('spot.config.load_incluster_config') as mock_config, \
         patch('spot.client.CoreV1Api') as mock_api:
      spot.drain()
      mock_config.assert_not_called()
      mock_api.assert_not_called()

  def test_drain_skipped_when_node_name_missing(self):
    spot = Spot()
    spot.drain_node = True
    spot.node_name = None

    with patch('spot.config.load_incluster_config') as mock_config, \
         patch('spot.client.CoreV1Api') as mock_api:
      spot.drain()
      mock_config.assert_not_called()
      mock_api.assert_not_called()

  def test_drain_cordons_and_evicts_pods(self):
    spot = Spot()
    spot.drain_node = True
    spot.node_name = 'test-node'

    mock_v1 = MagicMock()
    mock_pod = MagicMock()
    mock_pod.metadata.name = 'test-pod'
    mock_pod.metadata.namespace = 'default'
    mock_pod.metadata.owner_references = None
    mock_pod.metadata.annotations = None
    mock_v1.list_pod_for_all_namespaces.return_value.items = [mock_pod]

    with patch('spot.config.load_incluster_config') as mock_config, \
         patch('spot.client.CoreV1Api', return_value=mock_v1):
      spot.drain()
      mock_config.assert_called_once()
      mock_v1.patch_node.assert_called_once_with('test-node', {'spec': {'unschedulable': True}})
      mock_v1.create_namespaced_pod_eviction.assert_called_once()

  def test_drain_skips_daemonset_pods(self):
    spot = Spot()
    spot.drain_node = True
    spot.node_name = 'test-node'

    mock_v1 = MagicMock()
    mock_pod = MagicMock()
    mock_pod.metadata.name = 'ds-pod'
    mock_pod.metadata.namespace = 'default'
    owner_ref = MagicMock()
    owner_ref.kind = 'DaemonSet'
    mock_pod.metadata.owner_references = [owner_ref]
    mock_pod.metadata.annotations = None
    mock_v1.list_pod_for_all_namespaces.return_value.items = [mock_pod]

    with patch('spot.config.load_incluster_config'), \
         patch('spot.client.CoreV1Api', return_value=mock_v1), \
         patch('spot.client.V1Eviction') as mock_eviction:
      spot.drain()
      mock_eviction.assert_not_called()

  def test_drain_skips_mirror_pods(self):
    spot = Spot()
    spot.drain_node = True
    spot.node_name = 'test-node'

    mock_v1 = MagicMock()
    mock_pod = MagicMock()
    mock_pod.metadata.name = 'mirror-pod'
    mock_pod.metadata.namespace = 'kube-system'
    mock_pod.metadata.owner_references = None
    mock_pod.metadata.annotations = {'kubernetes.io/config.mirror': 'pod-config'}
    mock_v1.list_pod_for_all_namespaces.return_value.items = [mock_pod]

    with patch('spot.config.load_incluster_config'), \
         patch('spot.client.CoreV1Api', return_value=mock_v1), \
         patch('spot.client.V1Eviction') as mock_eviction:
      spot.drain()
      mock_eviction.assert_not_called()

  def test_drain_handles_api_exception(self):
    spot = Spot()
    spot.drain_node = True
    spot.node_name = 'test-node'

    mock_v1 = MagicMock()
    mock_pod = MagicMock()
    mock_pod.metadata.name = 'test-pod'
    mock_pod.metadata.namespace = 'default'
    mock_pod.metadata.owner_references = None
    mock_pod.metadata.annotations = None
    mock_v1.list_pod_for_all_namespaces.return_value.items = [mock_pod]
    mock_v1.create_namespaced_pod_eviction.side_effect = client.exceptions.ApiException(status=429, reason="Too Many Requests")

    with patch('spot.config.load_incluster_config'), \
         patch('spot.client.CoreV1Api', return_value=mock_v1):
      spot.drain()
      mock_v1.create_namespaced_pod_eviction.assert_called_once()

  def test_drain_handles_general_exception(self):
    spot = Spot()
    spot.drain_node = True
    spot.node_name = 'test-node'

    with patch('spot.config.load_incluster_config', side_effect=Exception("config error")), \
         patch('spot.client.CoreV1Api'):
      spot.drain()

  def test_watcher_calls_drain_when_termination_detected(self):
    spot = Spot()
    spot.slackit = MagicMock()
    spot.drain = MagicMock()
    spot.instance_details = MagicMock(return_value={'instanceId': 'i-123'})

    responses = [MagicMock(status_code=404), MagicMock(status_code=200)]
    self.mock_get.side_effect = responses

    spot.watcher()

    self.assertEqual(self.mock_get.call_count, 2)
    spot.drain.assert_called_once()
    spot.slackit.assert_called_once()


if __name__ == '__main__':
  unittest.main()
