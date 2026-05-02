# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a small Python service that runs as a Kubernetes DaemonSet on AWS EC2 Spot Instances. It polls the EC2 instance metadata service (`http://169.254.169.254/latest/meta-data/spot/instance-action`) via IMDSv2 in a loop; when AWS marks the instance for interruption (endpoint returns a JSON action of `terminate` or `stop`), it can optionally drain the node via the Kubernetes Python client and sends a notification to Slack via `slack_sdk.WebClient`.

## Repository Structure

- `spot.py` — Main application. Single `Spot` class with methods: `instance_details()`, `payload()`, `slackit()`, `drain()`, `watcher()`. Entry point runs `spot.watcher()` which loops until the termination endpoint returns 200, then optionally drains the node and notifies Slack.
- `spot_test.py` — Unit tests using `unittest` and `unittest.mock`. Patches `os.environ.get`, `requests.get`, and `slack_sdk.WebClient`.
- `Dockerfile` — Multi-stage-ready Alpine-based image (`python:3.14-alpine3.22`), runs as non-root UID 10001.
- `deployment/` — Kubernetes manifests:
  - `daemonset.yml` — DaemonSet with node affinity for `amd64`, security-hardened container context, liveness probe via `pgrep python`.
  - `secret.yml` — Base64-encoded Slack token and channel (placeholder values).
  - `rbac.yml` — ServiceAccount + ClusterRole (pods, deployments, replicaset read access) + ClusterRoleBinding.
  - `kustomization.yml` — Kustomize overlay; references the above resources and sets image tag to `vYYYY.MM`.

## Development Commands

Install dependencies:
```bash
pip install -r requirements.txt
```

Run tests:
```bash
python -m unittest spot_test.py
# or
python -m pytest .
```

Run a single test class or method:
```bash
python -m unittest spot_test.TestSpotInstanceNotifier.test_initialization
```

Lint:
```bash
flake8 . --count --show-source --statistics --ignore=E111,E501 --exit-zero
```

Coverage:
```bash
pip install coverage pytest
pytest .
```

Build container:
```bash
docker build -t k8s-spot-termination-notice .
```

Deploy to a cluster:
```bash
kubectl apply -k deployment/
```

## Dependencies

- `requests>=2.32.0`
- `slack-sdk>=3.39.0`

Managed via both `Pipfile`/`Pipfile.lock` and `requirements.txt`. Update both when changing dependencies.

## CI/CD (GitHub Actions)

- `.github/workflows/docker.yml` — On push/PR to `main` (when relevant paths change): runs Python tests across 3.11 and 3.12, lints with `flake8`, runs coverage + Codecov, builds and pushes Docker image to DockerHub (`docker.io/saidsef/k8s-spot-termination-notice`), runs Trivy vulnerability scan, spins up a Kind cluster to validate K8s manifests, auto-approves PRs, and adds a `preview` label.
- `.github/workflows/tagging.yml` — Triggered after CI completes on `main`; creates or updates a monthly tag (`vYYYY.MM`).
- `.github/workflows/release.yml` — Triggered after Tagging completes; creates a GitHub release and uploads all files from `./deployment/` as release assets.
- `.github/dependabot.yaml` — Weekly updates for GitHub Actions, Docker, and pip.

## Important Notes

- The Python runtime in CI tests is 3.11/3.12, but the Dockerfile uses `python:3.14-alpine3.22`. The `Pipfile` also specifies `python_version = "3.14"`.
- The `spot.py` script is designed to run inside a pod on an EC2 instance; locally it will fail to reach the EC2 metadata endpoints (which is expected).
- The RBAC manifest grants read access to pods, deployments, and replicasets. When node draining is enabled (`DRAIN_NODE=true`), it also requires `patch` on `nodes` and `create` on `pods/eviction`.
- The Docker image includes the `kubernetes` Python client to support the drain feature.
- Environment variables consumed at runtime: `SLACK_API_TOKEN`, `SLACK_CHANNEL`, `CLUSTER`, `NODE_NAME`, `DRAIN_NODE`.
- Version numbering in releases and kustomization image tags uses a calendar scheme (`vYYYY.MM`), managed by the tagging workflow — do not manually bump.
