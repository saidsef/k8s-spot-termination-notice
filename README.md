# Kubernetes Spot Instance Notification

This service will run as DaemonSet within your K8s cluster running on AWS Spot Instance, it watches the AWS metadata service when running on Spot Instances.

AWS Spot instance receives termination notice via the [instance meta data](https://aws.amazon.com/blogs/aws/new-ec2-spot-instance-termination-notices/), that field will become available when the instance has been marked for termination, and will contain the time when a shutdown signal will be sent to the instance’s operating system.

This service will notify you via Slack that an Spot instance will be taken out of service.

## Prerequisites

- Kubernetes Cluster (running in AWS)
- Slack API Token
- Slack Channel

## Environmental Variables

- CHANNEL (otherwise it will be to `default`)
- SLACK_API_TOKEN
- SLACK_CHANNEL

## Deployment

To deoloy this in your cluster:

> Update `kustomization.yml` to deploy in a different `namespace`

> otherwise this will be deployed to `default` namespace

```shell
kubectl apply -k deployment/
```

## Source

Our latest and greatest source of Jenkins can be found on [GitHub](#deployment). Fork us!

## Contributing

We would :heart:  you to contribute by making a [pull request](https://github.com/saidsef/k8s-spot-termination-notice/pulls).

Please read the official [Contribution Guide](./CONTRIBUTING.md) for more information on how you can contribute.

## TODO

- [] Drain Node
