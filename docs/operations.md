# Operations

The service writes its logs to standard output. It serves no HTTP endpoint and exports no metrics.

## Logs

```shell
kubectl logs -n <namespace> -l app.kubernetes.io/name=spot-termination-notice --prefix
```

The log level is fixed at `INFO`. The line for each poll and the IMDSv1 fallback both log at
`DEBUG`, so neither appears.

| Level | Message | Meaning |
| --- | --- | --- |
| `INFO` | `Spot termination watcher started (node=..., cluster=..., drain=...)` | the pod started, with its settings |
| `WARNING` | `Spot metadata request failed: ...` | the metadata service did not answer a poll |
| `WARNING` | `Spot interruption detected: action=...` | AWS marked the instance for interruption |
| `INFO` | `Slack notification sent` | Slack accepted the message |
| `ERROR` | `Failed to send Slack notification: ...` | Slack refused the message or was unreachable, followed by a traceback |
| `WARNING` | `NODE_NAME not set, skipping drain` | draining is on but the node name is missing |
| `INFO` | `Disruption budgets block N eviction(s), retrying in 5s` | PodDisruptionBudgets blocked some evictions |
| `INFO` | `Node ... drained successfully` | every pod was evicted |
| `WARNING` | `Node ... drained with N pod(s) left: ...` | the drain ended with pods still on the node |
| `ERROR` | `Error draining node: ...` | the in-cluster configuration, the cordon or the pod list failed |
| `INFO` | `Interruption handled, waiting for the node to shut down` | the pod is idle |

The `Spot interruption detected` line suits a log-based alert that does not depend on Slack.

## Health

The liveness probe runs `pgrep python` in the container. It checks that the process exists, and it
does not check that the process can reach the metadata service or Slack. The DaemonSet defines no
readiness probe.

## Simulating an interruption

AWS Fault Injection Service sends a real interruption notice to chosen Spot Instances with the
`aws:ec2:send-spot-instance-interruptions` action, and the EC2 console offers the same through
**Initiate interruption** on a Spot request. AWS interrupts the instance afterwards, so the test
costs the node. AWS documents both in
[test Spot Instance interruptions using AWS FIS](https://docs.aws.amazon.com/fis/latest/userguide/fis-tutorial-spot-interruptions.html)
and [initiate a Spot Instance interruption](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/initiate-a-spot-instance-interruption.html).

## Common failures

| Symptom | Cause |
| --- | --- |
| no `Spot interruption detected` line during an interruption | the node has a hop limit of 1 and requires IMDSv2, see [instance metadata](deploying.md#instance-metadata) |
| `Spot metadata request failed` on every poll | the pod cannot reach `169.254.169.254`, for example because a NetworkPolicy blocks it |
| `Failed to send Slack notification` with `not_in_channel` | the bot is not a member of the channel |
| `Failed to send Slack notification` with `invalid_auth` or `not_authed` | the token is wrong or empty, or the Secret holds a base64-encoded token |
| `Failed to send Slack notification` with `channel_not_found` | `SLACK_CHANNEL` names no channel the bot can see, or holds a base64-encoded value |
| `Failed to send Slack notification` with `missing_scope` | the Slack app lacks the `chat:write` scope |
| `Error draining node:` with `403` | the ClusterRoleBinding does not name the ServiceAccount in the namespace the pod runs in |
| `Node ... drained with N pod(s) left` | a PodDisruptionBudget still blocked an eviction at the deadline, or an eviction failed with the error logged before it |
| the `Cluster` part of each message shows `cluster-name-goes-here` | `deployment/daemonset.yml` still holds the placeholder for `CLUSTER`, see [configuration](configuration.md#environment-variables) |
| no pod on some nodes | the node has a taint the DaemonSet does not tolerate, or an architecture other than `amd64` and `arm64` |
