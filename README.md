# Kubernetes Spot Instance Notification [![CI](https://github.com/saidsef/k8s-spot-termination-notice/actions/workflows/docker.yml/badge.svg)](#prerequisites) [![Tagging](https://github.com/saidsef/k8s-spot-termination-notice/actions/workflows/tagging.yml/badge.svg)](#prerequisites) [![Release](https://github.com/saidsef/k8s-spot-termination-notice/actions/workflows/release.yml/badge.svg)](#prerequisites) [![Maintainability](https://api.codeclimate.com/v1/badges/6e8a177eb52d300d1111/maintainability)](https://codeclimate.com/github/saidsef/k8s-spot-termination-notice/maintainability)

This service will run as DaemonSet within your K8s cluster running on AWS Spot Instance, it watches the AWS metadata service when running on Spot Instances.

AWS Spot instance receives an interruption notice via the [instance metadata](https://aws.amazon.com/blogs/aws/new-ec2-spot-instance-termination-notices/). The `instance-action` endpoint becomes available when the instance has been marked for interruption and returns the action (`terminate`, `stop`, or `hibernate`) plus the approximate UTC time. The service polls this endpoint via IMDSv2 and notifies Slack when a `terminate` or `stop` action is detected.

## Prerequisites

- Kubernetes Cluster (running in AWS)
- Slack API Token
- Slack Channel

> Add Slack `SLACK_API_TOKEN` and `SLACK_CHANNEL` in `secret.yml`, under the Secret named `spot-termination-notice`

## Environmental Variables

- CHANNEL (otherwise it will be to `default`)
- SLACK_API_TOKEN
- SLACK_CHANNEL
- NODE_NAME (node to drain, usually set via `spec.nodeName` downward API)
- DRAIN_NODE (`true` to enable node draining on spot termination, default `false`)

## Deployment

To deploy this in your cluster:

> Update `kustomization.yml` namespace field to deploy in a different `namespace`

> The default namespace is `default`

```shell
kubectl apply -k deployment/
```

## Source

Our latest and greatest source of Jenkins can be found on [GitHub](#deployment). Fork us!

## Contributing

We would :heart:  you to contribute by making a [pull request](https://github.com/saidsef/k8s-spot-termination-notice/pulls).

Please read the official [Contribution Guide](./CONTRIBUTING.md) for more information on how you can contribute.

## TODO

> Drain Node feature is now available behind the `DRAIN_NODE` environment variable.
