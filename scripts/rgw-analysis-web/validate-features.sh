#!/usr/bin/env bash
set -euo pipefail

registry=${1:-features.yaml}
root=${2:-.}
command -v ruby >/dev/null 2>&1 || { echo "ruby is required for registry validation" >&2; exit 1; }

ruby -ryaml -e '
  registry = YAML.safe_load(File.read(ARGV.fetch(0)), aliases: false)
  root = File.expand_path(ARGV.fetch(1))
  abort "invalid registry root" unless registry.is_a?(Hash) && registry.keys.sort == ["apiVersion", "features", "kind"]
  abort "invalid registry identity" unless registry["apiVersion"] == "scalex.io/features/v1" && registry["kind"] == "FeatureRegistry"
  features = registry["features"]
  abort "features must be non-empty" unless features.is_a?(Array) && !features.empty?
  names = features.map do |feature|
    keys = ["chart", "images", "name", "renderer", "source", "tests"]
    abort "unknown or missing feature field" unless feature.is_a?(Hash) && feature.keys.sort == keys
    abort "unsupported renderer" unless feature["renderer"] == "helm/v1"
    abort "invalid image components" unless feature["images"].keys.sort == ["flow", "web"]
    abort "invalid source components" unless feature["source"].keys.sort == ["flow", "web"]
    paths = [feature["chart"], feature["tests"], *feature["source"].values, *feature["images"].values.map { |image| image["context"] }]
    paths.each do |path|
      abort "unsafe registry path" unless path.is_a?(String) && !path.start_with?("/") && !path.split("/").include?("..")
      abort "registry path does not exist" unless File.exist?(File.join(root, path))
    end
    feature["images"].each_value do |image|
      abort "invalid image contract" unless image.keys.sort == ["context", "repository"] && image["repository"].match?(%r{\Aghcr\.io/[a-z0-9-]+/[a-z0-9-]+\z})
    end
    feature["name"]
  end
  abort "feature names must be unique" unless names.uniq.length == names.length
' "$registry" "$root"

echo "feature registry: PASS"
