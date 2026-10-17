import signal
import unittest
import requests
from unittest.mock import patch, MagicMock
from kubernetes import client
from spot import Spot, main, exit_on_sigterm


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
    self.mock_put = patch('spot.put').start()
    self.mock_put.return_value.status_code = 200
    self.mock_put.return_value.text = 'imds-token'
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
    data_resp = MagicMock()
    data_resp.status_code = 200
    data_resp.json.return_value = {'action': 'terminate'}
    self.mock_get.return_value = data_resp

    result = spot._meta_get(spot.spot_meta_url)

    self.mock_put.assert_called_once()
    self.assertEqual(self.mock_put.call_args.args, (f'{spot.meta_base}/api/token',))
    self.assertEqual(self.mock_put.call_args.kwargs['headers'], {'X-aws-ec2-metadata-token-ttl-seconds': '21600'})
    self.mock_get.assert_called_once()
    self.assertEqual(self.mock_get.call_args.kwargs['headers'], {'X-aws-ec2-metadata-token': 'imds-token'})
    self.assertEqual(result.status_code, 200)

  def test_meta_get_falls_back_to_imdsv1(self):
    spot = Spot()
    self.mock_put.return_value.status_code = 403

    data_resp = MagicMock()
    data_resp.status_code = 200
    data_resp.json.return_value = {'action': 'terminate'}
    self.mock_get.return_value = data_resp

    result = spot._meta_get(spot.spot_meta_url)

    self.mock_get.assert_called_once()
    self.assertNotIn('headers', self.mock_get.call_args.kwargs)
    self.assertEqual(result.status_code, 200)

  def test_meta_get_falls_back_when_token_request_fails(self):
    spot = Spot()
    self.mock_put.side_effect = requests.exceptions.ConnectTimeout("hop limit")

    data_resp = MagicMock()
    data_resp.status_code = 200
    self.mock_get.return_value = data_resp

    result = spot._meta_get(spot.spot_meta_url)

    self.mock_get.assert_called_once()
    self.assertNotIn('headers', self.mock_get.call_args.kwargs)
    self.assertEqual(result.status_code, 200)

  def test_instance_action_with_imdsv2_required(self):
    action_resp = MagicMock()
    action_resp.status_code = 200
    action_resp.json.return_value = {'action': 'terminate', 'time': '2026-10-17T15:53:08Z'}
    unauthorised_resp = MagicMock()
    unauthorised_resp.status_code = 401

    def imds(url, headers=None, timeout=None):
      if headers and headers.get('X-aws-ec2-metadata-token') == 'imds-token':
        return action_resp
      return unauthorised_resp
    self.mock_get.side_effect = imds

    spot = Spot()
    result = spot.instance_action()

    self.assertEqual(result['action'], 'terminate')

  def test_instance_details_success(self):
    expected = {
      'instanceId': 'i-1234567890abcdef0',
      'accountId': '123456789012',
      'availabilityZone': 'us-west-2b',
      'instanceType': 'm4.large'
    }
    data_resp = MagicMock()
    data_resp.json.return_value = expected
    self.mock_get.return_value = data_resp

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
    action_resp = MagicMock()
    action_resp.status_code = 200
    action_resp.json.return_value = {'action': 'terminate', 'time': '2025-09-18T08:22:00Z'}
    self.mock_get.return_value = action_resp

    spot = Spot()
    result = spot.instance_action()

    self.assertEqual(result['action'], 'terminate')

  def test_instance_action_returns_empty_on_404(self):
    action_resp = MagicMock()
    action_resp.status_code = 404
    self.mock_get.return_value = action_resp

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

  def test_slackit_posts_message(self):
    spot = Spot()
    spot.instance_details = MagicMock(return_value={'instanceId': 'i-1234567890abcdef0'})

    with patch('spot.WebClient', autospec=True) as mock_client:
      with self.assertLogs('spot', level='INFO') as logs:
        spot.slackit('terminate')

    self.assertIn('Slack notification sent', '\n'.join(logs.output))
    mock_client.assert_called_once()
    self.assertEqual(mock_client.call_args.kwargs['token'], 'test_token')
    self.assertEqual(mock_client.call_args.kwargs['timeout'], 10)

    api_call = mock_client.return_value.api_call
    api_call.assert_called_once()
    args, kwargs = api_call.call_args
    self.assertEqual(args, ('chat.postMessage',))
    self.assertEqual(kwargs['json']['channel'], 'test_channel')
    self.assertIn('Spot Instance Terminate Notice', kwargs['json']['attachments'][0]['title'])

  def test_slackit_logs_failure_without_raising(self):
    spot = Spot()
    spot.instance_details = MagicMock(return_value={'instanceId': 'i-1234567890abcdef0'})

    with patch('spot.WebClient', autospec=True) as mock_client:
      mock_client.return_value.api_call.side_effect = RuntimeError("slack is down")
      with self.assertLogs('spot', level='ERROR') as logs:
        spot.slackit('stop')

    output = '\n'.join(logs.output)
    self.assertIn('RuntimeError', output)
    self.assertIn('slack is down', output)

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
      mock_v1.patch_node.assert_called_once_with('test-node', {'spec': {'unschedulable': True}}, _request_timeout=10)
      mock_v1.create_namespaced_pod_eviction.assert_called_once()
      name, namespace, eviction = mock_v1.create_namespaced_pod_eviction.call_args.args
      self.assertEqual((name, namespace), ('test-pod', 'default'))
      self.assertIsInstance(eviction, client.V1Eviction)
      self.assertEqual(eviction.metadata.name, 'test-pod')
      self.assertEqual(eviction.metadata.namespace, 'default')
      self.assertEqual(eviction.delete_options.grace_period_seconds, 30)

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

  def _drain_one_pod(self, eviction_side_effect):
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
    mock_v1.create_namespaced_pod_eviction.side_effect = eviction_side_effect

    clock = [1000.0]

    def advance(seconds):
      clock[0] += seconds

    with patch('spot.config.load_incluster_config'), \
         patch('spot.client.CoreV1Api', return_value=mock_v1), \
         patch('spot.time', side_effect=lambda: clock[0]), \
         patch('spot.sleep', side_effect=advance) as mock_sleep, \
         self.assertLogs('spot', level='INFO') as logs:
      spot.drain()
    return mock_v1, mock_sleep, '\n'.join(logs.output)

  def test_drain_retries_blocked_eviction_until_it_succeeds(self):
    blocked = client.exceptions.ApiException(status=429, reason="Too Many Requests")
    mock_v1, mock_sleep, output = self._drain_one_pod([blocked, blocked, None])

    self.assertEqual(mock_v1.create_namespaced_pod_eviction.call_count, 3)
    self.assertEqual(mock_sleep.call_count, 2)
    self.assertIn('Node test-node drained successfully', output)

  def test_drain_stops_retrying_at_the_deadline(self):
    blocked = client.exceptions.ApiException(status=429, reason="Too Many Requests")
    mock_v1, mock_sleep, output = self._drain_one_pod(blocked)

    self.assertEqual(mock_v1.create_namespaced_pod_eviction.call_count, 19)
    self.assertEqual(mock_sleep.call_count, 18)
    self.assertIn('drained with 1 pod(s) left: default/test-pod', output)

  def test_drain_treats_missing_pod_as_evicted(self):
    gone = client.exceptions.ApiException(status=404, reason="Not Found")
    mock_v1, mock_sleep, output = self._drain_one_pod(gone)

    mock_v1.create_namespaced_pod_eviction.assert_called_once()
    mock_sleep.assert_not_called()
    self.assertIn('Node test-node drained successfully', output)

  def test_drain_does_not_retry_other_errors(self):
    error = client.exceptions.ApiException(status=500, reason="Internal Server Error")
    mock_v1, mock_sleep, output = self._drain_one_pod(error)

    mock_v1.create_namespaced_pod_eviction.assert_called_once()
    mock_sleep.assert_not_called()
    self.assertIn('drained with 1 pod(s) left: default/test-pod', output)

  def test_drain_sets_request_timeouts(self):
    mock_v1, _, _ = self._drain_one_pod(None)

    self.assertEqual(mock_v1.patch_node.call_args.kwargs['_request_timeout'], 10)
    self.assertEqual(mock_v1.list_pod_for_all_namespaces.call_args.kwargs['_request_timeout'], 10)
    self.assertEqual(mock_v1.create_namespaced_pod_eviction.call_args.kwargs['_request_timeout'], 10)

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

  def test_watcher_notifies_before_draining(self):
    spot = Spot()
    calls = MagicMock()
    spot.slackit = calls.slackit
    spot.drain = calls.drain
    spot.instance_action = MagicMock(return_value={'action': 'terminate'})

    spot.watcher()

    self.assertEqual([c[0] for c in calls.mock_calls], ['slackit', 'drain'])

  def test_watcher_logs_quiet_polls_at_debug(self):
    spot = Spot()
    spot.slackit = MagicMock()
    spot.drain = MagicMock()
    spot.sleep = 0.01
    spot.instance_action = MagicMock(side_effect=[{}, {'action': 'terminate'}])

    with self.assertLogs('spot', level='DEBUG') as logs:
      spot.watcher()

    self.assertIn('DEBUG:spot:No interruption detected, next check in 0.01s', logs.output)

  def test_idle_keeps_the_process_running(self):
    spot = Spot()
    with patch('spot.sleep', side_effect=[None, None, RuntimeError('stop')]) as mock_sleep:
      with self.assertRaises(RuntimeError):
        spot.idle()
    self.assertEqual(mock_sleep.call_count, 3)

  def test_main_handles_one_interruption_then_idles(self):
    with patch('spot.signal.signal') as mock_signal, \
         patch('spot.Spot') as mock_spot:
      main()

    mock_signal.assert_called_once_with(signal.SIGTERM, exit_on_sigterm)
    mock_spot.return_value.watcher.assert_called_once()
    mock_spot.return_value.idle.assert_called_once()

  def test_sigterm_exits_cleanly(self):
    with self.assertRaises(SystemExit) as raised:
      exit_on_sigterm(signal.SIGTERM, None)
    self.assertEqual(raised.exception.code, 0)


if __name__ == '__main__':
  unittest.main()
