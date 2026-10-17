# Configuration

The service reads its configuration from environment variables when it starts.

## Environment variables

| Variable | Default | Value in the DaemonSet | Effect |
| --- | --- | --- | --- |
| `SLACK_API_TOKEN` | none | the `SLACK_API_TOKEN` key of the `spot-termination-notice` Secret | the bot token for `chat.postMessage` |
| `SLACK_CHANNEL` | none | the `SLACK_CHANNEL` key of the same Secret | the channel that receives the message |
| `CLUSTER` | `Default` | the node name, from `spec.nodeName` | the name in the `Cluster` part of the message and in the start-up log line |
| `NODE_NAME` | none | the node name, from `spec.nodeName` | the node to cordon and drain |
| `DRAIN_NODE` | `false` | `false` | `true`, in any letter case, enables [node draining](draining.md) |

The DaemonSet fills `CLUSTER` from the node name, so each message names the node in its `Cluster`
part. To show a cluster name, replace the `valueFrom` of `CLUSTER` in `deployment/daemonset.yml`
with a literal value:

```yaml
- name: CLUSTER
  value: "production-eu-west-1"
```

## Slack

The service posts with the Slack Web API method
[`chat.postMessage`](https://docs.slack.dev/reference/methods/chat.postMessage).

| Requirement | Detail |
| --- | --- |
| Token | a bot token, starting `xoxb-`, from a Slack app with the `chat:write` scope |
| Channel | a channel ID such as `C0123456789`, or a channel name |
| Membership | the bot must be a member of the channel |

The message is a single attachment titled `Spot Instance Terminate Notice` or
`Spot Instance Stop Notice`. Its text names the cluster, and the instance ID, account ID,
Availability Zone and instance type from the instance identity document. A detail the document
lacks shows as `unknown`.

## Fixed values

`spot.py` sets these values, and no environment variable changes them.

| Value | Setting |
| --- | --- |
| Poll interval | 5 seconds |
| Instance metadata request timeout | 3 seconds |
| Slack request timeout | 10 seconds |
| Kubernetes API request timeout | 10 seconds |
| Drain deadline | 90 seconds, see [timing](draining.md#timing) |
| Eviction grace period | 30 seconds |
| Log level | `INFO` |
