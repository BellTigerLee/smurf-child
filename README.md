# smurf-child

Representative private development child for the SmurfX contract POC. This
repository owns namespace-neutral plain Kubernetes development manifests, local
contract tests, and inert promotion-request metadata. It does not own placement,
effective policy, reconciliation, signing, or federation runtime objects.

## Current state

Task 2 is deliberately RED. The public parser and validator entry points are
nonfunctional scaffolding that report `PLANNED_UNIMPLEMENTED:<category>` until
Task 4 implements the contract. A nonzero contract-test result is expected;
Ruff, basedpyright, package setup, and CLI help must remain green.

## Local validation

```console
uv sync --frozen
uv run --frozen ruff format --check .
uv run --frozen ruff check .
uv run --frozen basedpyright
just red-contract
uv run --frozen smurf-child --help
uv run --frozen smurf-child validate --root .
```

The final command currently exits with code 2 and a planned-unimplemented
category without a traceback. No build, publish, signing, or deployment occurs.

## Child boundary

- `deploy/dev/` contains only namespace-neutral `Deployment`, `Service`, and
  `ConfigMap` resources.
- Container images are pinned by `sha256` digest.
- `smurfx/request.yaml` contains only inert identity, environment, and literal
  `b`, `c`, or `both` target metadata; CI will derive exact HEAD separately.
- Argo CD, Karmada, policy, cluster-scoped, secret, and generated resources are
  forbidden from the child bundle.
