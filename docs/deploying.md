# Deploying on Kubernetes

The manifests under `deployment/` are plain Kustomize, with a single entry point.

## Layout

```text
deployment/
├── kustomization.yml   # common labels and the three resource files
├── rbac.yml            # ServiceAccount, ClusterRole and ClusterRoleBinding
├── daemonset.yml       # the DaemonSet
└── secret.yml          # the Slack token and channel
```

## Namespace

The manifests set no namespace. The ClusterRoleBinding names the ServiceAccount as its subject,
and a ServiceAccount subject needs a namespace. Kustomize writes the namespace into that subject
only when the kustomization sets one, so set it before applying:

```shell
kubectl create namespace spot-termination-notice
cd deployment
kustomize edit set namespace spot-termination-notice
kubectl apply -k .
kubectl rollout status ds/spot-termination-notice -n spot-termination-notice
```

`kustomize edit` writes the namespace into `deployment/kustomization.yml`.

## Slack credentials

`secret.yml` holds the bot token and the channel under `stringData`, which takes plain text.
Replace both placeholders with the plain values, without base64 encoding. Kubernetes encodes them
when it stores the Secret.

To keep the token out of the repository, remove `secret.yml` from `resources` in
`kustomization.yml` and create the Secret directly:

```shell
kubectl create secret generic spot-termination-notice -n spot-termination-notice \
  --from-literal=SLACK_API_TOKEN='<bot-token>' \
  --from-literal=SLACK_CHANNEL='<channel-id>'
```

[Configuration](configuration.md#slack) lists what the token and the channel need.

## Instance metadata

The pod reaches the instance metadata service through the node, and a pod outside the host network
counts as an extra network hop. With a PUT response hop limit of 1, the IMDSv2 token response
never reaches the pod. The pod waits out the request timeout and falls back to IMDSv1. On an
instance that requires IMDSv2, that read fails as well, so the pod never sees a notice, and it logs
nothing about the failure at the `INFO` level.

Each node needs a hop limit of 2 or more. For a running instance:

```shell
aws ec2 modify-instance-metadata-options --instance-id <instance-id> \
  --http-put-response-hop-limit 2 --http-endpoint enabled
```

For new nodes, set `HttpPutResponseHopLimit` in the `MetadataOptions` of the launch template.
Karpenter applies a hop limit of 1 with IMDSv2 required unless the EC2NodeClass sets
`spec.metadataOptions.httpPutResponseHopLimit`, see
[Karpenter NodeClasses](https://karpenter.sh/docs/concepts/nodeclasses/). AWS documents the
setting under
[change the PUT response hop limit](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-IMDS-existing-instances.html#modify-PUT-response-hop-limit).

## Spot nodes only

The node affinity in `daemonset.yml` matches every `amd64` and `arm64` node, On-Demand nodes
included. To keep the pods to Spot nodes, add the capacity type label of the node provisioner to
`matchExpressions`:

| Provisioner | Label |
| --- | --- |
| EKS managed node groups | `eks.amazonaws.com/capacityType: SPOT` |
| Karpenter | `karpenter.sh/capacity-type: spot` |

```yaml
- key: karpenter.sh/capacity-type
  operator: In
  values:
    - spot
```

## Taints

The DaemonSet sets no tolerations of its own. The DaemonSet controller adds tolerations for the
standard node condition taints, and any other taint keeps the pod off the node. A Spot node that
carries a custom taint needs a matching toleration in `daemonset.yml`, see
[taints and tolerations](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/#taints-and-tolerations).

## Image tag

The DaemonSet runs `docker.io/saidsef/k8s-spot-termination-notice:latest` with
`imagePullPolicy: Always`, so a pod that restarts pulls the newest image built from `main`. To pin
a monthly tag, set it in the kustomization:

```shell
kustomize edit set image docker.io/saidsef/k8s-spot-termination-notice:vYYYY.MM
```

[CI and releases](ci.md#image-tags) lists the tags.

## Release assets

Each GitHub release carries the files from `deployment/` as assets. Downloaded into one directory,
they apply the same way as a checkout, after the namespace and the Secret are set.

## Permissions

The service calls the Kubernetes API only to drain its node.

| Resource | Verb | Use |
| --- | --- | --- |
| `nodes` | `patch` | cordon the node |
| `pods` | `list` | find the pods on the node |
| `pods/eviction` | `create` | evict those pods |

The ClusterRole in `rbac.yml` grants these verbs and others that the service does not call.

## Pod

| Setting | Value |
| --- | --- |
| User | UID and GID 10001, non-root, with privilege escalation off |
| Filesystem | read-only root |
| Capabilities | all dropped, with the `RuntimeDefault` seccomp profile |
| Liveness probe | `pgrep python`, see [health](operations.md#health) |
| Service links | off |
| Service account token | mounted, for the drain |

`daemonset.yml` sets the CPU and memory requests and limits, and the termination grace period.
