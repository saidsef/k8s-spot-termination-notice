# Kubernetes Spot Instance Notification [![CI](https://github.com/saidsef/k8s-spot-termination-notice/actions/workflows/docker.yml/badge.svg)](#prerequisites) [![Tagging](https://github.com/saidsef/k8s-spot-termination-notice/actions/workflows/tagging.yml/badge.svg)](#prerequisites) [![Release](https://github.com/saidsef/k8s-spot-termination-notice/actions/workflows/release.yml/badge.svg)](#prerequisites) [![Maintainability](https://api.codeclimate.com/v1/badges/6e8a177eb52d300d1111/maintainability)](https://codeclimate.com/github/saidsef/k8s-spot-termination-notice/maintainability) [![Documentation](https://readthedocs.org/projects/k8s-spot-termination-notice/badge/?version=latest)](https://k8s-spot-termination-notice.readthedocs.io/en/latest/)

This service will run as DaemonSet within your K8s cluster running on AWS Spot Instance, it watches the AWS metadata service when running on Spot Instances.

AWS Spot instance receives an interruption notice via the [instance metadata](https://aws.amazon.com/blogs/aws/new-ec2-spot-instance-termination-notices/). The `instance-action` endpoint becomes available when the instance has been marked for interruption and returns the action (`terminate`, `stop`, or `hibernate`) plus the approximate UTC time. The service polls this endpoint via IMDSv2 and notifies Slack when a `terminate` or `stop` action is detected.

Full documentation: [k8s-spot-termination-notice.readthedocs.io](https://k8s-spot-termination-notice.readthedocs.io/).

## Prerequisites

- Kubernetes Cluster (running in AWS)
- Instance metadata PUT response hop limit of 2 or more on each node
- Slack API Token
- Slack Channel

> Add the plain Slack `SLACK_API_TOKEN` and `SLACK_CHANNEL` values, without base64 encoding, in `secret.yml`, under the Secret named `spot-termination-notice`. See [Slack credentials](./docs/deploying.md#slack-credentials).

> A pod outside the host network counts as an extra network hop. With a hop limit of 1, the pod may receive no IMDSv2 token response. See [Change the PUT response hop limit](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-IMDS-existing-instances.html#modify-PUT-response-hop-limit).

## Environmental Variables

- CLUSTER (name shown as the cluster in Slack notifications, defaults to `Default`, and the DaemonSet sets it to the node name)
- SLACK_API_TOKEN
- SLACK_CHANNEL
- NODE_NAME (node to drain, usually set via `spec.nodeName` downward API)
- DRAIN_NODE (`true` to enable node draining on spot termination, default `false`)

See [configuration](./docs/configuration.md) for the Slack app and the values fixed in code.

## Deployment

To deploy this in your cluster, first set the target namespace in Kustomize, then apply:

```shell
cd deployment
kustomize edit set namespace <namespace>
kubectl apply -k .
```

Or from the repository root (modifies `deployment/kustomization.yml` in place):

```shell
(cd deployment && kustomize edit set namespace <namespace>)
kubectl apply -k deployment/
```

If no namespace is set, Kustomize builds namespace-agnostic manifests and `kubectl` applies them to the current context namespace. However, the ClusterRoleBinding subject requires a namespace — always run `kustomize edit set namespace` before applying to ensure the ServiceAccount namespace is injected correctly.

## Documentation

Published at [k8s-spot-termination-notice.readthedocs.io](https://k8s-spot-termination-notice.readthedocs.io/), with the source in [docs/](./docs/README.md).

- [Architecture](./docs/architecture.md) - how a pod detects an interruption and what it does next
- [Configuration](./docs/configuration.md) - the environment variables, the Slack app, and the values fixed in code
- [Deploying on Kubernetes](./docs/deploying.md) - the manifests, the namespace, the Secret, instance metadata and permissions
- [Node draining](./docs/draining.md) - how the pod cordons the node and evicts its pods, and how long that takes
- [Operations](./docs/operations.md) - log lines, health, simulating an interruption, and the common failures
- [CI and releases](./docs/ci.md) - what CI builds and tests, the image tags, and how releases are cut

## Source

Our latest and greatest source can be found on [GitHub](#deployment). Fork us!

## Contributing

We would :heart:  you to contribute by making a [pull request](https://github.com/saidsef/k8s-spot-termination-notice/pulls).

Please read the official [Contribution Guide](./CONTRIBUTING.md) for more information on how you can contribute.

