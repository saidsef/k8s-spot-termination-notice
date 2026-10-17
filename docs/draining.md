# Node draining

Draining is off by default. With `DRAIN_NODE` set to `true`, the pod cordons its node after the
Slack message and evicts the pods on it, so their controllers can recreate them on other nodes
before the instance stops.

## Enabling

Set the value in `deployment/daemonset.yml`:

```yaml
- name: DRAIN_NODE
  value: "true"
```

The drain also needs `NODE_NAME`, which the DaemonSet fills from `spec.nodeName`. Without it, the
pod logs `NODE_NAME not set, skipping drain` and does nothing more.

## Sequence

1. The pod loads the in-cluster configuration from its ServiceAccount.
2. It cordons the node by setting `spec.unschedulable` to `true`.
3. It lists the pods on the node across every namespace.
4. It skips DaemonSet pods and the mirror pods of static pods.
5. It evicts each remaining pod through the
   [Eviction API](https://kubernetes.io/docs/concepts/scheduling-eviction/api-eviction/), with a
   30 second grace period.
6. It retries the evictions that a PodDisruptionBudget blocked, every 5 seconds, until the drain
   deadline.
7. It logs whether the node drained, or lists the pods left on it.

A failure in the first three steps logs `Error draining node:` with the cause and ends the drain.

## Eviction results

| API response | Result |
| --- | --- |
| success | the pod is evicted |
| `404` | the pod no longer exists, and counts as evicted |
| `429` | a PodDisruptionBudget blocks the eviction, and the pod retries it |
| any other error | the pod logs the status and does not retry |

## Timing

AWS sends the notice two minutes before the interruption, and every stage of the response spends
part of that time.

| Stage | Limit |
| --- | --- |
| Detection | up to one poll interval of 5 seconds after AWS publishes the notice |
| Slack message | the identity document read, followed by a Slack request of up to 10 seconds |
| Drain | 90 seconds from the start of the drain |
| Pod shutdown | the 30 second grace period from each eviction |

The pod stops retrying blocked evictions when the next retry would start after the deadline. It
does not wait for evicted pods to terminate. A pod evicted late in the drain may still be inside
its grace period when the instance stops.

## Limits

- DaemonSet pods stay on the node, including the pod of this service.
- Pods without a controller are evicted like any other, and nothing recreates them.
- The service never uncordons a node. If a stopped instance returns under the same Node object,
  `kubectl uncordon` makes it schedulable again.
