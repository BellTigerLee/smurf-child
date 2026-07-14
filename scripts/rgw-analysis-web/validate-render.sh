#!/usr/bin/env bash
set -euo pipefail

rendered=${1:?rendered manifest path is required}
chart_dir=${2:?chart directory is required}
command -v ruby >/dev/null 2>&1 || { echo "ruby is required for manifest validation" >&2; exit 1; }

if rg -n '^(kind: (Secret|ExternalSecret|Namespace|ClusterRole|ClusterRoleBinding|CustomResourceDefinition|PropagationPolicy|ClusterPropagationPolicy)|apiVersion: .*karmada\.io/)' "$rendered" "$chart_dir"; then
  echo "forbidden secret or federation object" >&2
  exit 1
fi

ruby -ryaml -e '
  docs = File.read(ARGV.fetch(0)).split(/^---\s*$/).filter_map do |source|
    YAML.safe_load(source, permitted_classes: [], permitted_symbols: [], aliases: false)
  end
  service = docs.find { |doc| doc["kind"] == "Service" } or abort "Service is absent"
  deployment = docs.find { |doc| doc["kind"] == "Deployment" } or abort "Deployment is absent"
  release = service.dig("metadata", "labels", "app.kubernetes.io/instance")
  expected = {
    "ConfigMap" => ["#{release}-runtime"],
    "Deployment" => ["#{release}-result-web"],
    "Job" => ["#{release}-analyzer", "#{release}-dataset-seeder"],
    "Service" => ["#{release}-result-web"]
  }
  expected.each do |kind, names|
    actual = docs.select { |doc| doc["kind"] == kind }.map { |doc| doc.dig("metadata", "name") }.sort
    abort "unexpected #{kind} identities" unless actual == names
  end
  abort "Service is not ClusterIP" unless service.dig("spec", "type") == "ClusterIP"
  annotations = service.dig("metadata", "annotations")
  abort "Service annotations are empty" unless annotations.is_a?(Hash) && annotations.values.all? { |value| value.is_a?(String) && !value.empty? }
  selector = service.dig("spec", "selector")
  pod_labels = deployment.dig("spec", "template", "metadata", "labels")
  abort "Service selector is empty" unless selector.is_a?(Hash) && !selector.empty?
  abort "Service selector does not match web pods" unless selector.all? { |key, value| pod_labels[key] == value } && selector["app.kubernetes.io/component"] == "web"
  docs.select { |doc| ["Deployment", "Job", "Service", "ConfigMap"].include?(doc["kind"]) }.each do |doc|
    labels = doc.dig("metadata", "labels")
    abort "missing ScaleX release label" unless labels["scalex.io/release"] == release
    abort "missing ScaleX component label" unless labels["scalex.io/component"].is_a?(String) && !labels["scalex.io/component"].empty?
  end
  [deployment, *docs.select { |doc| doc["kind"] == "Job" }].each do |workload|
    labels = workload.dig("spec", "template", "metadata", "labels")
    abort "missing ScaleX pod release label" unless labels["scalex.io/release"] == release
    abort "missing ScaleX pod component label" unless labels["scalex.io/component"].is_a?(String) && !labels["scalex.io/component"].empty?
  end
  annotations = deployment.dig("metadata", "annotations")
  component_containers = {
    "flow" => deployment.dig("spec", "template", "spec", "containers").find { |container| container["name"] == "result-sync" },
    "web" => deployment.dig("spec", "template", "spec", "containers").find { |container| container["name"] == "web" }
  }
  component_containers.each do |component, container|
    revision = annotations["scalex.io/#{component}-source-revision"]
    abort "invalid #{component} source revision" unless revision.is_a?(String) && revision.match?(/\A[0-9a-f]{40}\z/)
    expected_tag = ":sha-#{revision}@sha256:"
    abort "#{component} image is not bound to its source revision" unless container["image"].include?(expected_tag)
  end
  specs = [deployment.dig("spec", "template", "spec")]
  jobs = docs.select { |doc| doc["kind"] == "Job" }
  job_components = jobs.map { |job| job.dig("metadata", "labels", "app.kubernetes.io/component") }.sort
  abort "expected immutable dataset-seeder and analyzer Jobs" unless jobs.length == 2 && job_components == ["analyzer", "dataset-seeder"]
  jobs.each do |job|
    abort "Job replacement sync option is absent" unless job.dig("metadata", "annotations", "argocd.argoproj.io/sync-options") == "Force=true,Replace=true"
    specs << job.dig("spec", "template", "spec")
  end
  specs.each do |spec|
    abort "service account token automount is enabled" unless spec["automountServiceAccountToken"] == false
    abort "unsafe pod context" unless spec.dig("securityContext", "runAsNonRoot") == true && spec.dig("securityContext", "seccompProfile", "type") == "RuntimeDefault"
    [*spec["initContainers"], *spec["containers"]].each do |container|
      security = container["securityContext"]
      safe = security["readOnlyRootFilesystem"] == true && security["allowPrivilegeEscalation"] == false && security.dig("capabilities", "drop") == ["ALL"]
      abort "unsafe container context" unless safe
    end
  end
' "$rendered"

for label in app.kubernetes.io/name app.kubernetes.io/instance app.kubernetes.io/managed-by app.kubernetes.io/part-of; do
  grep -q "$label:" "$rendered"
done

test "$(grep -c 'readOnlyRootFilesystem: true' "$rendered")" -ge 5
test "$(grep -c 'allowPrivilegeEscalation: false' "$rendered")" -ge 5
test "$(grep -c 'type: RuntimeDefault' "$rendered")" -ge 3
test "$(grep -c 'drop:' "$rendered")" -ge 5

if rg -n 'image: .*:(latest|sha-[0-9a-f]{1,39})(@|$)|image: .*sha256:[0-9a-f]{0,63}([^0-9a-f]|$)' "$rendered"; then
  echo "mutable or malformed image coordinate" >&2
  exit 1
fi

for revision in $(rg -o 'scalex.io/(flow-|web-)?source-revision: "[0-9a-f]{40}"' "$rendered" | rg -o '[0-9a-f]{40}' | sort -u); do
  grep -q ":sha-${revision}@sha256:" "$rendered" || {
    echo "source revision is not paired with its immutable tag" >&2
    exit 1
  }
done

echo "render contracts: PASS"
