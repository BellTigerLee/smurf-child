#!/usr/bin/env ruby
require "psych"
require "shellwords"

def load_workflow(path)
  document = Psych.safe_load_file(path, permitted_classes: [], permitted_symbols: [], aliases: false)
  abort "#{path}: expected a YAML mapping" unless document.is_a?(Hash)

  document
rescue Psych::Exception => error
  abort "#{path}: invalid YAML: #{error.message}"
end

def named_step(workflow, job_name, step_name)
  jobs = workflow["jobs"]
  abort "workflow jobs must be a mapping" unless jobs.is_a?(Hash)
  job = jobs[job_name]
  abort "workflow job is absent: #{job_name}" unless job.is_a?(Hash)
  steps = job["steps"]
  abort "workflow job steps must be a list: #{job_name}" unless steps.is_a?(Array)
  matches = steps.select { |step| step.is_a?(Hash) && step["name"] == step_name }
  abort "workflow step must exist exactly once: #{step_name}" unless matches.length == 1

  matches.fetch(0)
end

def exact_keys(mapping, expected, description)
  abort "#{description} must be a mapping" unless mapping.is_a?(Hash)
  abort "#{description} keys are not exact" unless mapping.keys.sort == expected.sort
end

def exact_mixed_keys(mapping, expected, description)
  abort "#{description} must be a mapping" unless mapping.is_a?(Hash)
  keys = mapping.keys
  exact = keys.length == expected.length && expected.all? { |key| mapping.key?(key) }
  abort "#{description} keys are not exact" unless exact
end

def secret_expression_locations(value, path = [], results = [])
  case value
  when Hash
    value.each { |key, child| secret_expression_locations(child, [*path, key], results) }
  when Array
    value.each_with_index { |child, index| secret_expression_locations(child, [*path, index], results) }
  when String
    expressions = value.scan(/\$\{\{.*?\}\}/m)
    results << [path, value] if expressions.any? { |expression| expression.match?(/\bsecrets\b/) }
  end
  results
end

def validate_job(job, keys, values, step_specs, description)
  exact_keys(job, keys, description)
  values.each do |key, expected|
    abort "#{description} #{key} is not exact" unless job[key] == expected
  end
  steps = job["steps"]
  abort "#{description} steps must be a list" unless steps.is_a?(Array)
  abort "#{description} step count is not exact" unless steps.length == step_specs.length
  steps.zip(step_specs, strict: true).each do |step, spec|
    name = spec.fetch(:values).fetch("name")
    exact_keys(step, spec.fetch(:keys), "#{description} step #{name}")
    spec.fetch(:values).each do |key, expected|
      abort "#{description} step #{name} #{key} is not exact" unless step[key] == expected
    end
    abort "custom shell is forbidden in #{description}" if step.key?("shell")
  end
end

def logical_shell_commands(script)
  abort "workflow step run must be a string" unless script.is_a?(String)

  commands = []
  pending = +""
  script.each_line do |raw_line|
    line = raw_line.strip
    next if line.empty? || line.start_with?("#")

    pending << " " unless pending.empty?
    pending << line
    if pending.end_with?("\\")
      pending.delete_suffix!("\\")
      pending.rstrip!
    else
      commands << pending
      pending = +""
    end
  end
  abort "workflow step has an unterminated shell continuation" unless pending.empty?

  commands
end

def exact_path_command(commands, prefix, suffix, expected_paths, description)
  matches = commands.select { |command| command.include?(prefix) }
  abort "#{description} must exist exactly once" unless matches.length == 1
  match = matches.fetch(0).match(/\A#{Regexp.escape(prefix)}(.+)#{Regexp.escape(suffix)}\z/)
  abort "invalid #{description} placement" unless match
  paths = Shellwords.shellsplit(match[1])
  abort "unexpected #{description} paths" unless paths == expected_paths
end

root = File.expand_path(ARGV.fetch(0, "."))
federation_url = "https://github.com/SJoon99/scalex-federation.git"
federation_slug = federation_url.delete_prefix("https://github.com/").delete_suffix(".git")
workflows = Dir[File.join(root, ".github/workflows/*.{yaml,yml}")].sort
abort "no workflows found" if workflows.empty?

workflows.each do |path|
  File.readlines(path).each_with_index do |line, index|
    match = line.match(/^\s*-?\s*uses:\s*([^\s]+)$/)
    next unless match

    action, reference = match[1].split("@", 2)
    unless action && reference&.match?(/\A[0-9a-f]{40}\z/)
      abort "#{path}:#{index + 1}: action is not pinned to a full commit"
    end
  end
end

validate_path = File.join(root, ".github/workflows/validate.yaml")
publish_path = File.join(root, ".github/workflows/publish-promote.yaml")
abort "validation workflow is absent" unless File.file?(validate_path)
abort "publish workflow is absent" unless File.file?(publish_path)

validate = File.read(validate_path)
publish = File.read(publish_path)
publish_workflow = load_workflow(publish_path)
exact_mixed_keys(
  publish_workflow,
  ["name", true, "permissions", "concurrency", "env", "jobs"],
  "publish workflow"
)
expected_workflow_environment = {
  "FLOW_IMAGE" => "ghcr.io/belltigerlee/smurf-child-flow",
  "WEB_IMAGE" => "ghcr.io/belltigerlee/smurf-child-web",
  "FEDERATION_GIT_URL" => federation_url
}
abort "publish workflow environment is not exact" unless publish_workflow["env"] == expected_workflow_environment
abort "workflow-level run defaults are forbidden" if publish_workflow.key?("defaults")
publish_jobs = publish_workflow["jobs"]
exact_keys(publish_jobs, %w[build-flow build-web package promote validate], "publish workflow jobs")
expected_secret_locations = [
  [["jobs", "build-flow", "steps", 2, "with", "password"], "${{ secrets.GITHUB_TOKEN }}"],
  [["jobs", "build-web", "steps", 2, "with", "password"], "${{ secrets.GITHUB_TOKEN }}"],
  [["jobs", "promote", "steps", 0, "with", "app-id"], "${{ secrets.SCALEX_PROMOTION_APP_ID }}"],
  [["jobs", "promote", "steps", 0, "with", "private-key"], "${{ secrets.SCALEX_PROMOTION_APP_PRIVATE_KEY }}"]
]
actual_secret_locations = secret_expression_locations(publish_workflow)
abort "publish workflow secret expression locations are not exact" unless actual_secret_locations == expected_secret_locations
checkout_action = "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683"
login_action = "docker/login-action@184bdaa0721073962dff0199f1fb9940f07167d1"
buildx_action = "docker/setup-buildx-action@e468171a9de216ec08956ac3ada2f0791b6bd435"
build_action = "docker/build-push-action@263435318d21b8e681c14492fe198d362a7d2c83"
python_install_run = <<~'SHELL'
  uv python install 3.13
  uv lock --check
  uv sync --frozen
SHELL
offline_gate_run = <<~'SHELL'
  uv run --frozen ruff format --check .
  uv run --frozen ruff check .
  uv run --frozen basedpyright
  actionlint
  ./scripts/rgw-analysis-web/validate_workflows.rb .
  tests/rgw-analysis-web/ci/test-workflows.sh
  tests/rgw-analysis-web/ci/test-promotion.sh
  ./scripts/test.sh
  ./scripts/rgw-analysis-web/compose-config.sh
  tests/rgw-analysis-web/ci/test-public-scan.sh
  ./scripts/rgw-analysis-web/scan-public-artifacts.sh
SHELL

validate_job(
  publish_jobs.fetch("validate"),
  %w[runs-on steps],
  { "runs-on" => "ubuntu-24.04" },
  [
    {
      keys: %w[name uses with],
      values: {
        "name" => "Check out the exact revision", "uses" => checkout_action,
        "with" => { "persist-credentials" => false }
      }
    },
    {
      keys: %w[name uses with],
      values: {
        "name" => "Install uv",
        "uses" => "astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e",
        "with" => { "enable-cache" => true }
      }
    },
    {
      keys: %w[name run],
      values: {
        "name" => "Install checksum-pinned CI tools",
        "run" => "./scripts/rgw-analysis-web/install-ci-tools.sh \"$RUNNER_TEMP/bin\""
      }
    },
    {
      keys: %w[name run],
      values: { "name" => "Install and sync Python 3.13", "run" => python_install_run }
    },
    {
      keys: %w[env name run],
      values: {
        "name" => "Run the complete offline gate",
        "env" => {
          "MINIO_IMAGE" => "quay.io/minio/minio@sha256:a1ea29fa28355559ef137d71fc570e508a214ec84ff8083e39bc5428980b015e",
          "MINIO_MC_IMAGE" => "quay.io/minio/mc@sha256:aead63c77f9db9107f1696fb08ecb0faeda23729cde94b0f663edf4fe09728e3",
          "MINIO_ROOT_USER" => "local-ci",
          "MINIO_ROOT_PASSWORD" => "${{ github.run_id }}"
        },
        "run" => offline_gate_run
      }
    }
  ],
  "validate job"
)

login_inputs = {
  "registry" => "ghcr.io",
  "username" => "${{ github.actor }}",
  "password" => "${{ secrets.GITHUB_TOKEN }}"
}
build_job_values = {
  "needs" => "validate",
  "runs-on" => "ubuntu-24.04",
  "permissions" => { "contents" => "read", "packages" => "write" },
  "outputs" => { "digest" => "${{ steps.build.outputs.digest }}" }
}
flow_contexts = <<~CONTEXTS
  flow-source=src/rgw-analysis-web/flow
  web-source=src/rgw-analysis-web/web
  project-source=.
CONTEXTS
tag_selection_run = <<~'SHELL'
  {
    echo 'value<<EOF'
    echo "${IMAGE}:sha-${GITHUB_SHA}"
    if [[ "${GITHUB_REF}" == 'refs/heads/main' ]]; then
      echo "${IMAGE}:latest"
    fi
    echo 'EOF'
  } >>"$GITHUB_OUTPUT"
SHELL
flow_step_specs = [
  {
    keys: %w[name uses with],
    values: {
      "name" => "Check out the exact revision", "uses" => checkout_action,
      "with" => { "persist-credentials" => false }
    }
  },
  { keys: %w[name uses], values: { "name" => "Set up Buildx", "uses" => buildx_action } },
  {
    keys: %w[name uses with],
    values: { "name" => "Log in to GHCR", "uses" => login_action, "with" => login_inputs }
  },
  {
    keys: %w[env id name run],
    values: {
      "name" => "Select immutable and convenience tags", "id" => "tags",
      "env" => { "IMAGE" => "${{ env.FLOW_IMAGE }}" }, "run" => tag_selection_run
    }
  },
  {
    keys: %w[id name uses with],
    values: {
      "name" => "Build and publish flow", "id" => "build", "uses" => build_action,
      "with" => {
        "context" => "images/rgw-analysis-web/flow",
        "file" => "images/rgw-analysis-web/flow/Containerfile",
        "build-contexts" => flow_contexts,
        "push" => true,
        "tags" => "${{ steps.tags.outputs.value }}",
        "provenance" => "mode=max",
        "sbom" => true
      }
    }
  }
]
validate_job(
  publish_jobs.fetch("build-flow"),
  %w[needs outputs permissions runs-on steps],
  build_job_values,
  flow_step_specs,
  "build-flow job"
)

web_contexts = "web-source=src/rgw-analysis-web/web\n"
web_step_specs = [
  {
    keys: %w[name uses with],
    values: {
      "name" => "Check out the exact revision", "uses" => checkout_action,
      "with" => { "persist-credentials" => false }
    }
  },
  { keys: %w[name uses], values: { "name" => "Set up Buildx", "uses" => buildx_action } },
  {
    keys: %w[name uses with],
    values: { "name" => "Log in to GHCR", "uses" => login_action, "with" => login_inputs }
  },
  {
    keys: %w[env id name run],
    values: {
      "name" => "Select immutable and convenience tags", "id" => "tags",
      "env" => { "IMAGE" => "${{ env.WEB_IMAGE }}" }, "run" => tag_selection_run
    }
  },
  {
    keys: %w[id name uses with],
    values: {
      "name" => "Build and publish web", "id" => "build", "uses" => build_action,
      "with" => {
        "context" => "images/rgw-analysis-web/web",
        "file" => "images/rgw-analysis-web/web/Containerfile",
        "build-contexts" => web_contexts,
        "push" => true,
        "tags" => "${{ steps.tags.outputs.value }}",
        "provenance" => "mode=max",
        "sbom" => true
      }
    }
  }
]
validate_job(
  publish_jobs.fetch("build-web"),
  %w[needs outputs permissions runs-on steps],
  build_job_values,
  web_step_specs,
  "build-web job"
)

package_environment = {
  "SOURCE_REVISION" => "${{ github.sha }}",
  "FLOW_IMAGE_TAG" => "sha-${{ github.sha }}",
  "FLOW_IMAGE_DIGEST" => "${{ needs.build-flow.outputs.digest }}",
  "WEB_IMAGE_TAG" => "sha-${{ github.sha }}",
  "WEB_IMAGE_DIGEST" => "${{ needs.build-web.outputs.digest }}",
  "CI_RUN_URL" => "https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }}"
}
package_run = <<~'SHELL'
  SOURCE_TREE="$(git rev-parse "${GITHUB_SHA}^{tree}")"
  export SOURCE_TREE
  SOURCE_DATE_EPOCH="$(git show -s --format=%ct "$GITHUB_SHA")"
  export SOURCE_DATE_EPOCH
  ./scripts/package-chart.sh
SHELL
validate_job(
  publish_jobs.fetch("package"),
  %w[needs outputs runs-on steps],
  {
    "needs" => %w[build-flow build-web],
    "runs-on" => "ubuntu-24.04",
    "outputs" => { "artifact-name" => "promotion-${{ github.sha }}" }
  },
  [
    {
      keys: %w[name uses with],
      values: {
        "name" => "Check out the exact revision", "uses" => checkout_action,
        "with" => { "fetch-depth" => 0, "persist-credentials" => false }
      }
    },
    {
      keys: %w[env name run],
      values: {
        "name" => "Package chart and truthful promotion metadata",
        "env" => package_environment,
        "run" => package_run
      }
    },
    {
      keys: %w[name uses with],
      values: {
        "name" => "Upload the promotion artifact",
        "uses" => "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
        "with" => {
          "name" => "promotion-${{ github.sha }}", "path" => "dist/rgw-analysis-web/",
          "if-no-files-found" => "error", "retention-days" => 30
        }
      }
    }
  ],
  "package job"
)

promote_job = publish_jobs["promote"]
exact_keys(promote_job, %w[if needs permissions runs-on steps], "promote job")
abort "unexpected promote job condition" unless promote_job["if"] == "github.event_name == 'push'"
abort "unexpected promote job dependencies" unless promote_job["needs"] == %w[build-flow build-web package]
abort "unexpected promote job runner" unless promote_job["runs-on"] == "ubuntu-24.04"
abort "unexpected promote job permissions" unless promote_job["permissions"] == { "contents" => "read" }
promote_steps = promote_job["steps"]
abort "promote job steps must be a list" unless promote_steps.is_a?(Array)
expected_promote_steps = [
  ["Create a short-lived ScaleX installation token", %w[id name uses with]],
  ["Check out child promotion logic", %w[name uses with]],
  ["Check out the Federation target", %w[name uses with]],
  ["Download immutable promotion metadata", %w[name uses with]],
  ["Render the renderer-specific release update", %w[env name run]],
  ["Create or update the bot-owned review PR", %w[env name run]]
]
abort "promote job step count is not exact" unless promote_steps.length == expected_promote_steps.length
promote_steps.zip(expected_promote_steps, strict: true).each do |step, (name, keys)|
  exact_keys(step, keys, "promote step #{name}")
  abort "promote job step order is not exact" unless step["name"] == name
  abort "custom shell is forbidden in promote steps" if step.key?("shell")
end
token_step, child_checkout_step, federation_checkout_step, download_step = promote_steps.first(4)
abort "unexpected promotion token step id" unless token_step["id"] == "app-token"
abort "unexpected promotion token action" unless token_step["uses"] == "actions/create-github-app-token@a8d616148505b5069dccd32f177bb87d7f39123b"
expected_token_inputs = {
  "app-id" => "${{ secrets.SCALEX_PROMOTION_APP_ID }}",
  "private-key" => "${{ secrets.SCALEX_PROMOTION_APP_PRIVATE_KEY }}",
  "owner" => "SJoon99",
  "repositories" => "scalex-federation",
  "permission-contents" => "write",
  "permission-pull-requests" => "write"
}
abort "promotion token action inputs are not exact" unless token_step["with"] == expected_token_inputs
abort "unexpected child checkout action" unless child_checkout_step["uses"] == checkout_action
expected_child_checkout_inputs = { "path" => "child", "persist-credentials" => false }
abort "child checkout inputs are not exact" unless child_checkout_step["with"] == expected_child_checkout_inputs
abort "unexpected Federation checkout action" unless federation_checkout_step["uses"] == checkout_action
expected_federation_checkout_inputs = {
  "repository" => "SJoon99/scalex-federation",
  "ref" => "main",
  "token" => "${{ steps.app-token.outputs.token }}",
  "path" => "federation",
  "fetch-depth" => 0
}
abort "Federation checkout inputs are not exact" unless federation_checkout_step["with"] == expected_federation_checkout_inputs
expected_download_action = "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093"
abort "unexpected promotion download action" unless download_step["uses"] == expected_download_action
expected_download_inputs = { "name" => "promotion-${{ github.sha }}", "path" => "promotion" }
abort "promotion download inputs are not exact" unless download_step["with"] == expected_download_inputs
publish_trigger = /^on:\n  push:\n    branches:\n      - main\n\npermissions:/
abort "publish workflow must run only on push to main" unless publish.match?(publish_trigger)
abort "publish workflow has an unsafe trigger" if publish.match?(/^\s+(pull_request|workflow_dispatch):/) || publish.include?("release/**")
masked_command_assignment = /^\s+(?:declare|export|local|readonly)\s+[A-Za-z_][A-Za-z0-9_]*=.*\$\(/
abort "workflow masks a command-substitution failure during declaration" if publish.match?(masked_command_assignment)

abort "validation workflow must run on pull requests" unless validate.match?(/^  pull_request:$/)
abort "pull-request workflow must not reference secrets" if validate.include?("${{ secrets.")
forbidden_pr_capabilities = ["packages: write", "docker/login-action@", "create-github-app-token@", "push: true"]
forbidden_pr_capabilities.each do |capability|
  abort "pull-request workflow has write capability: #{capability}" if validate.include?(capability)
end

app_inputs = /repositories: scalex-federation\n\s+permission-contents: write\n\s+permission-pull-requests: write/
abort "GitHub App token is not least privilege" unless publish.match?(app_inputs)
authority_inputs = [
  "FEDERATION_GIT_URL: #{federation_url}",
  "owner: SJoon99",
  "repository: #{federation_slug}",
  "TARGET_REPOSITORY: #{federation_slug}"
]
authority_inputs.each do |input|
  abort "promotion target does not match Federation authority: #{input}" unless publish.include?(input)
end
abort "same-repository PR branch model is required" unless publish.include?('--head "$BRANCH"')
abort "fork-owner PR branch model is forbidden" if publish.include?('BellTigerLee:${BRANCH}')
abort "promotion workflow must not target the legacy POC release" if publish.include?("releases/poc/rgw-analysis-web")
promotion_paths = [
  "releases/cuty/rgw-analysis-web/release.yaml",
  "releases/cuty/rgw-analysis-web/values.yaml"
]

render_step = named_step(publish_workflow, "promote", "Render the renderer-specific release update")
expected_render_environment = {
  "FLOW_DIGEST" => "${{ needs.build-flow.outputs.digest }}",
  "WEB_DIGEST" => "${{ needs.build-web.outputs.digest }}"
}
abort "promotion render digest environment is not exact" unless render_step["env"] == expected_render_environment
expected_render_run = <<~SHELL
  child/scripts/rgw-analysis-web/promote-release.sh \\
    --artifact promotion/promotion.yaml \\
    --federation-dir federation \\
    --flow-digest "$FLOW_DIGEST" \\
    --web-digest "$WEB_DIGEST" \\
    --write
SHELL
abort "promotion render command is not exact" unless render_step["run"] == expected_render_run
abort "build digest expression must not be embedded in run" if render_step["run"].include?("${{ needs.")

review_step_name = "Create or update the bot-owned review PR"
review_step = named_step(publish_workflow, "promote", review_step_name)
review_environment = review_step["env"]
expected_review_environment = {
  "GH_TOKEN" => "${{ steps.app-token.outputs.token }}",
  "TARGET_REPOSITORY" => federation_slug,
  "BRANCH" => "automation/cuty-rgw-analysis-web"
}
abort "promotion review environment is not exact" unless review_environment == expected_review_environment
expected_review_run = <<~SHELL
  cd federation
  if git diff --quiet -- \\
    releases/cuty/rgw-analysis-web/release.yaml \\
    releases/cuty/rgw-analysis-web/values.yaml; then
    echo 'Pinned mode or already current; no cross-repository mutation.'
    exit 0
  fi
  git config user.name 'scalex-promotion[bot]'
  git config user.email 'scalex-promotion[bot]@users.noreply.github.com'
  git fetch origin "$BRANCH" || true
  git checkout -B "$BRANCH"
  git add releases/cuty/rgw-analysis-web/release.yaml \\
    releases/cuty/rgw-analysis-web/values.yaml
  staged_paths="$(git diff --cached --name-only)"
  expected_paths=$'releases/cuty/rgw-analysis-web/release.yaml\\nreleases/cuty/rgw-analysis-web/values.yaml'
  if [[ "$staged_paths" != "$expected_paths" ]]; then
    echo 'Refusing to commit unexpected staged paths.' >&2
    exit 1
  fi
  git commit -m "promote rgw-analysis-web sha-${GITHUB_SHA}"
  git push --force-with-lease origin "HEAD:${BRANCH}"
  body='Immutable source and both component digests were generated by the child publish workflow. Manual protected merge is required.'
  number="$(gh pr list --repo "$TARGET_REPOSITORY" --head "$BRANCH" --state open --json number --jq '.[0].number // empty')"
  if [[ -z "$number" ]]; then
    gh pr create --repo "$TARGET_REPOSITORY" --base main --head "$BRANCH" \\
      --title 'Promote rgw-analysis-web immutable artifacts' --body "$body"
  else
    gh pr edit "$number" --repo "$TARGET_REPOSITORY" \\
      --title 'Promote rgw-analysis-web immutable artifacts' --body "$body"
  fi
SHELL
abort "promotion review command is not exact" unless review_step["run"] == expected_review_run
review_commands = logical_shell_commands(review_step["run"])
review_stage_commands = review_commands.select { |command| command.match?(/\bgit\s+(?:add|stage)\b/) }
abort "promotion stage must exist exactly once" unless review_stage_commands.length == 1
exact_path_command(
  review_commands,
  "if git diff --quiet -- ",
  "; then",
  promotion_paths,
  "promotion diff"
)
exact_path_command(review_commands, "git add ", "", promotion_paths, "promotion stage")

promote_steps.each do |step|
  next unless step.is_a?(Hash) && step["run"].is_a?(String)
  next if step["name"] == review_step_name

  commands = logical_shell_commands(step["run"])
  if commands.any? { |command| command.match?(/\bgit\s+(?:add|stage)\b/) || command.include?("git diff --quiet --") }
    abort "promotion diff/stage command is outside the review step"
  end
end
repository_inputs = publish.scan(/^\s+repositories:\s+.+$/).map(&:strip)
abort "GitHub App token repository set is not exact" unless repository_inputs == ["repositories: scalex-federation"]
permission_inputs = publish.scan(/^\s+permission-[a-z-]+:\s+.+$/).map(&:strip)
expected_permissions = ["permission-contents: write", "permission-pull-requests: write"]
abort "GitHub App token requests broader permissions" unless permission_inputs.sort == expected_permissions.sort

puts "workflow action pins: PASS"
