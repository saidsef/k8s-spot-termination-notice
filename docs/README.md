# k8s-spot-termination-notice

k8s-spot-termination-notice warns a Slack channel when AWS marks a Spot Instance in a Kubernetes
cluster for interruption. It runs as a DaemonSet, so each node has one pod, and that pod polls the
instance metadata service of its own node for an interruption notice. When the notice arrives, the
pod posts the instance details to Slack. With draining enabled, the pod goes on to cordon the node
and evict its pods before the instance stops.

## Components

| Component | Detail |
| --- | --- |
| Service | `spot.py`, a single Python process that polls the instance metadata service |
| Image | `docker.io/saidsef/k8s-spot-termination-notice`, built by CI for `linux/amd64` and `linux/arm64` |
| Manifests | Kustomize under `deployment/`: a DaemonSet, its RBAC, and a Secret for the Slack credentials |

## Requirements

| Requirement | Value |
| --- | --- |
| Kubernetes | a cluster on EC2 nodes, with `kubectl` and `kustomize` |
| Instance metadata | enabled on each node, with a PUT response hop limit of 2 or more |
| Slack | a bot token with the `chat:write` scope, and a channel the bot belongs to |
| Python | 3.13 or later, with [uv](https://docs.astral.sh/uv/), to run the tests from a source checkout |

[Deploying on Kubernetes](deploying.md#instance-metadata) explains the hop limit.

## Quick start

Replace the two placeholders in `deployment/secret.yml` with the plain bot token and channel. The
commands below set a namespace and apply the manifests:

```shell
kubectl create namespace spot-termination-notice
cd deployment
kustomize edit set namespace spot-termination-notice
kubectl apply -k .
kubectl logs -n spot-termination-notice -l app.kubernetes.io/name=spot-termination-notice --prefix
```

Each pod logs `Spot termination watcher started` once it runs. Draining stays off until
`DRAIN_NODE` is `true`, see [node draining](draining.md).

## Documentation

| Page | Contents |
| --- | --- |
| [Architecture](architecture.md) | How a pod detects an interruption and what it does next, with a diagram |
| [Configuration](configuration.md) | The environment variables, the Slack app, and the values fixed in code |
| [Deploying on Kubernetes](deploying.md) | The manifests, the namespace, the Secret, instance metadata and permissions |
| [Node draining](draining.md) | How the pod cordons the node and evicts its pods, and how long that takes |
| [Operations](operations.md) | Log lines, health, simulating an interruption, and the common failures |
| [CI and releases](ci.md) | What CI builds and tests, the image tags, and how releases are cut |

## Repository

Source code and releases: [github.com/saidsef/k8s-spot-termination-notice](https://github.com/saidsef/k8s-spot-termination-notice)
