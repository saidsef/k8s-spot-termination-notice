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
    self.assertIn('instance-action', spot.spot_meta_url)
    self.assertIn('instance-identity', spot.ec2_meta_data)

  def test_meta_get_uses_imdsv2_token(self):
    spot = Spot()
    token_resp = MagicMock()
    token_resp.status_code = 200
    token_resp.text = 'imds-token'

    data_resp = MagicMock()
    data_resp.status_code = 200
    data_resp.json.return_value = {'action': 'terminate'}

    self.mock_get.side_effect = [token_resp, data_resp]

    result = spot._meta_get(spot.spot_meta_url)

    self.assertEqual(self.mock_get.call_count, 2)
    self.assertEqual(result.status_code, 200)

  def test_meta_get_falls_back_to_imdsv1(self):
    spot = Spot()
    token_resp = MagicMock()
    token_resp.status_code = 403

    data_resp = MagicMock()
    data_resp.status_code = 200
    data_resp.json.return_value = {'action': 'terminate'}

    self.mock_get.side_effect = [token_resp, data_resp]

    result = spot._meta_get(spot.spot_meta_url)

    self.assertEqual(self.mock_get.call_count, 2)
    self.assertEqual(result.status_code, 200)

  def test_instance_details_success(self):
    expected = {
      'instanceId': 'i-1234567890abcdef0',
      'accountId': '123456789012',
      'availabilityZone': 'us-west-2b',
      'instanceType': 'm4.large'
    }
    token_resp = MagicMock()
    token_resp.status_code = 200
    token_resp.text = 'token'
    data_resp = MagicMock()
    data_resp.json.return_value = expected
    self.mock_get.side_effect = [token_resp, data_resp]

    spot = Spot()
    result = spot.instance_details()

    self.assertEqual(result, expected)

  def test_instance_details_request_error(self):
    self.mock_get.side_effect = requests.exceptions.ConnectionError("connection refused")

    spot = Spot()
    result = spot.instance_details()

    self.assertEqual(result["status"], "error")
    self.assertIn("connection refused", result["message"])

  def test_instance_action_returns_data(self):
    token_resp = MagicMock()
    token_resp.status_code = 200
    token_resp.text = 'token'
    action_resp = MagicMock()
    action_resp.status_code = 200
    action_resp.json.return_value = {'action': 'terminate', 'time': '2025-09-18T08:22:00Z'}
    self.mock_get.side_effect = [token_resp, action_resp]

    spot = Spot()
    result = spot.instance_action()

    self.assertEqual(result['action'], 'terminate')

  def test_instance_action_returns_empty_on_404(self):
    token_resp = MagicMock()
    token_resp.status_code = 200
    token_resp.text = 'token'
    action_resp = MagicMock()
    action_resp.status_code = 404
    self.mock_get.side_effect = [token_resp, action_resp]

    spot = Spot()
    result = spot.instance_action()

    self.assertEqual(result, {})

  def test_instance_action_returns_empty_on_exception(self):
    self.mock_get.side_effect = requests.exceptions.ConnectionError("refused")

    spot = Spot()
    result = spot.instance_action()

    self.assertEqual(result, {})

  def test_payload_construction(self):
    spot = Spot()
    spot.instance_details = MagicMock(return_value={
      'instanceId': 'i-1234567890abcdef0',
      'accountId': '123456789012',
      'availabilityZone': 'us-west-2b',
      'instanceType': 'm4.large'
    })
    payload = spot.payload('terminated!', 'terminate')

    self.assertIsInstance(payload, list)
    self.assertIn('Spot Instance Terminate Notice', payload[0]['title'])
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
    payload = spot.payload('terminated!', 'stop')

    self.assertIn('Cluster: Default', payload[0]['text'])
    self.assertIn('Spot Instance Stop Notice', payload[0]['title'])

  def test_payload_safe_on_error_details(self):
    spot = Spot()
    spot.instance_details = MagicMock(return_value={
      "status": "error",
      "message": "Request error"
    })
    payload = spot.payload('terminated!', 'terminate')

    self.assertIn('instanceId: unknown', payload[0]['text'])

  def test_watcher_sends_slack_on_termination(self):
    spot = Spot()
    spot.slackit = MagicMock()
    spot.instance_action = MagicMock(return_value={'action': 'terminate'})
    spot.instance_details = MagicMock(return_value={'instanceId': 'i-123'})

    spot.watcher()

    spot.slackit.assert_called_once_with('terminate')

  def test_watcher_sends_slack_on_stop(self):
    spot = Spot()
    spot.slackit = MagicMock()
    spot.instance_action = MagicMock(return_value={'action': 'stop'})
    spot.instance_details = MagicMock(return_value={'instanceId': 'i-123'})

    spot.watcher()

    spot.slackit.assert_called_once_with('stop')

  def test_watcher_ignores_no_action(self):
    spot = Spot()
    spot.slackit = MagicMock()
    spot.drain = MagicMock()
    spot.sleep = 0.01
    spot.instance_details = MagicMock(return_value={'instanceId': 'i-123'})

    responses = [{}, {}, {'action': 'terminate'}]
    spot.instance_action = MagicMock(side_effect=responses)

    spot.watcher()

    self.assertEqual(spot.instance_action.call_count, 3)
    spot.drain.assert_called_once()
    spot.slackit.assert_called_once()

  def test_watcher_ignores_hibernate(self):
    spot = Spot()
    spot.slackit = MagicMock()
    spot.drain = MagicMock()
    spot.sleep = 0.01
    spot.instance_details = MagicMock(return_value={'instanceId': 'i-123'})

    responses = [{'action': 'hibernate'}, {'action': 'hibernate'}, {'action': 'terminate'}]
    spot.instance_action = MagicMock(side_effect=responses)

    spot.watcher()

    self.assertEqual(spot.instance_action.call_count, 3)
    spot.drain.assert_called_once()
    spot.slackit.assert_called_once()

  def test_watcher_loops_until_termination(self):
    spot = Spot()
    spot.slackit = MagicMock()
    spot.drain = MagicMock()
    spot.sleep = 0.01
    spot.instance_details = MagicMock(return_value={'instanceId': 'i-123'})

    responses = [{}, {}, {'action': 'terminate'}]
    spot.instance_action = MagicMock(side_effect=responses)

    spot.watcher()

    self.assertEqual(spot.instance_action.call_count, 3)
    spot.drain.assert_called_once()
    spot.slackit.assert_called_once()

  def test_watcher_survives_meta_get_exception(self):
    spot = Spot()
    spot.slackit = MagicMock()
    spot.drain = MagicMock()
    spot.sleep = 0.01
    spot.instance_details = MagicMock(return_value={'instanceId': 'i-123'})

    action_resp = MagicMock()
    action_resp.status_code = 200
    action_resp.json.return_value = {'action': 'terminate'}

    with patch.object(spot, '_meta_get', side_effect=[
      requests.exceptions.ConnectionError("timeout"),
      requests.exceptions.ConnectionError("timeout"),
      action_resp
    ]):
      spot.watcher()

    spot.drain.assert_called_once()
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
    spot.instance_action = MagicMock(return_value={'action': 'terminate'})
    spot.instance_details = MagicMock(return_value={'instanceId': 'i-123'})

    spot.watcher()

    spot.drain.assert_called_once()
    spot.slackit.assert_called_once()


if __name__ == '__main__':
  unittest.main()
