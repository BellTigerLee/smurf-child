# smurf-child

Representative private development child for the SmurfX contract POC. This
repository owns namespace-neutral plain Kubernetes development manifests, local
contract tests, and inert promotion-request metadata. It does not own placement,
effective policy, reconciliation, signing, or federation runtime objects.

## Current state

The child boundary parses a frozen inert request, validates a strict plain-YAML
manifest inventory, proves an exact clean Git checkout, and emits deterministic
unsigned RFC 8785 evidence payload bytes. Signing and key storage remain external.

## Local validation

```console
uv sync --frozen
uv lock --check
uv run --frozen ruff format --check .
uv run --frozen ruff check .
uv run --frozen basedpyright
uv run --frozen pytest
uv run --frozen smurf-child --help
uv run --frozen smurf-child validate --root .
uv run --frozen smurf-child evidence-payload --root . --output /tmp/evidence.json
```

Validation reports typed nonzero categories without tracebacks. Evidence output
is written atomically and contains no signature, key ID, trust envelope, or key.
No build, publish, signing, deployment, or network control operation occurs.

## Child boundary

- `deploy/dev/` contains only namespace-neutral `Deployment`, `Service`, and
  `ConfigMap` resources.
- Container images are pinned by `sha256` digest.
- `smurfx/request.yaml` contains only inert identity, environment, and literal
  `b`, `c`, or `both` target metadata; CI will derive exact HEAD separately.
- Argo CD, Karmada, policy, cluster-scoped, secret, and generated resources are
  forbidden from the child bundle.
