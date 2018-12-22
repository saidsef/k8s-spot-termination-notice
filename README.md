# Kubernetes (K8S) Spot Instance Notification

This service will run as DaemonSet within your K8S cluster running on AWS Spot Instance.

AWS Spot instance receives termination notice via the [instance meta data](https://aws.amazon.com/blogs/aws/new-ec2-spot-instance-termination-notices/), that field will become available when the instance has been marked for termination, and will contain the time when a shutdown signal will be sent to the instance’s operating system.

This service will notify you via Slack that an Spot instance will be taken out of service/terminated.

## Prerequisites
 - Kubernetes Cluster (running in AWS)
 - Slack API Token
 - Slack Channel

## Environmental Variables
 - CHANNEL (otherwise it will be to `Default`)
 - SLACK_API_TOKEN
 - SLACK_CHANNEL

## TODO
 [ ] Drain Node
