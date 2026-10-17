# CI and releases

Three GitHub Actions workflows build, tag and release the project.

## CI

`.github/workflows/docker.yml`, named CI, runs on pushes and pull requests to `main` that touch the
`Dockerfile`, `deployment/`, the Python files at the repository root, `pyproject.toml`, `uv.lock`
or the workflow itself. Changes to the documentation alone do not start it.

| Job | Runs for | Does |
| --- | --- | --- |
| `python-test` | every run | runs flake8 and pytest under coverage on each Python version in its matrix, and uploads the coverage report to Codecov |
| `build` | every run | builds the image for `linux/amd64` and `linux/arm64`, pushes it to Docker Hub, and scans it with Trivy |
| `k8s-test` | pull requests | builds the image, loads it into a kind cluster for each Kubernetes version in its matrix, applies `deployment/`, and waits for the `watcher started` log line |
| `auto-approve` | pull requests | approves the pull request once `build` and `k8s-test` pass |
| `auto-preview` | pull requests | adds the `preview` label once `auto-approve` passes |

flake8 runs with `--exit-zero`, so its findings never fail the job. Trivy sends its results to
GitHub code scanning and does not fail the job either. The kind nodes have no instance metadata
service, so `k8s-test` checks that the pod starts and nothing more.

Pull requests from Dependabot and from forks have no access to the Docker Hub secrets, so `build`
fails at the login step on them.

## Image tags

The `build` job pushes to `docker.io/saidsef/k8s-spot-termination-notice`:

| Tag | Pushed by |
| --- | --- |
| `latest` | builds of `main` |
| `vYYYY.MM` | builds of `main`, overwritten by each build in that month |
| the last segment of the Git ref | every other build, such as `merge` for a pull request |

The `BUILD_ID` environment variable in the image holds the `vYYYY.MM` of the month it was built
in. The manifests use `latest`, see [image tag](deploying.md#image-tag).

## Tagging and releases

`.github/workflows/tagging.yml` runs after each CI run on `main` completes, and tags only when
that run passed. It creates the Git tag `vYYYY.MM` for the current month at the commit CI built,
or moves the tag there if it exists.

`.github/workflows/release.yml` runs after tagging passes on `main`. It creates a GitHub release
for the month's tag with generated release notes, and replaces the assets of that release with the
files in `deployment/` at the tagged commit. When the month's release exists, the workflow replaces
the assets of the latest release instead. Both workflows can also run by hand.

## Documentation

Read the Docs builds this site from `mkdocs.yml` and `.readthedocs.yaml`. It installs the `docs`
dependency group from `uv.lock`, and MkDocs runs in strict mode, so a broken link or anchor fails
the build. To build the site locally:

```shell
uv run --only-group docs mkdocs serve
```

## Local checks

```shell
uv sync --group dev
uv run pytest
```
