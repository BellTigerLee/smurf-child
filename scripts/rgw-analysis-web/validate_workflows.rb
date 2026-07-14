#!/usr/bin/env ruby

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
repository_inputs = publish.scan(/^\s+repositories:\s+.+$/).map(&:strip)
abort "GitHub App token repository set is not exact" unless repository_inputs == ["repositories: scalex-federation"]
permission_inputs = publish.scan(/^\s+permission-[a-z-]+:\s+.+$/).map(&:strip)
expected_permissions = ["permission-contents: write", "permission-pull-requests: write"]
abort "GitHub App token requests broader permissions" unless permission_inputs.sort == expected_permissions.sort

puts "workflow action pins: PASS"
