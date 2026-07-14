#!/usr/bin/env ruby
require "fileutils"
require "optparse"
require "pathname"
require "psych"
require "tempfile"

EXPECTED_REPOSITORY = "https://github.com/BellTigerLee/smurf-child.git"
EXPECTED_CHART = "charts/rgw-analysis-web"
EXPECTED_RENDERER = "helm/v1"
EXPECTED_COMPONENTS = {
  "flow" => "ghcr.io/belltigerlee/smurf-child-flow",
  "web" => "ghcr.io/belltigerlee/smurf-child-web"
}.freeze
EXPECTED_RELEASE = {
  "apiVersion" => "scalex.io/v1alpha1",
  "kind" => "FederationRelease",
  "name" => "rgw-analysis-web",
  "environment" => "poc",
  "namespace" => "scalex-rgw-analysis-web",
  "renderer" => EXPECTED_RENDERER
}.freeze
EXPECTED_PATHS = {
  "values" => "releases/poc/rgw-analysis-web/values.yaml",
  "dependencies" => "releases/poc/rgw-analysis-web/dependencies",
  "policy" => "releases/poc/rgw-analysis-web/karmada"
}.freeze
APPROVED_EXISTING_SOURCES = {
  "https://github.com/SJoon99/scalex-feature-poc.git" => "chart",
  EXPECTED_REPOSITORY => EXPECTED_CHART
}.freeze
FULL_SHA = /\A(?!0{40})[0-9a-f]{40}\z/
DIGEST = /\Asha256:[0-9a-f]{64}\z/

def load_mapping(path)
  document = Psych.safe_load_file(path, permitted_classes: [], permitted_symbols: [], aliases: false)
  abort "#{path}: expected a YAML mapping" unless document.is_a?(Hash)

  document
rescue Psych::Exception => error
  abort "#{path}: invalid YAML: #{error.message}"
end

def feature_contract(path)
  registry = load_mapping(path)
  features = registry.fetch("features")
  abort "#{path}: features must be a list" unless features.is_a?(Array)

  feature = features.find { |item| item.is_a?(Hash) && item["name"] == "rgw-analysis-web" }
  abort "#{path}: rgw-analysis-web is absent" unless feature.is_a?(Hash)
  renderer = feature.fetch("renderer")
  abort "unsupported renderer: #{renderer}" unless renderer == EXPECTED_RENDERER

  images = feature.fetch("images")
  abort "#{path}: images must be a mapping" unless images.is_a?(Hash)
  EXPECTED_COMPONENTS.each do |component, repository|
    image = images.fetch(component)
    abort "#{path}: invalid #{component} image" unless image.is_a?(Hash) && image["repository"] == repository
  end
end

def validate_artifact(path, expected_digests)
  artifact = load_mapping(path)
  abort "unexpected promotion identity" unless artifact["apiVersion"] == "scalex.io/promotion/v1" && artifact["kind"] == "PromotionArtifact"

  source = artifact.fetch("source")
  chart = artifact.fetch("chart")
  abort "invalid source repository" unless source["repository"] == EXPECTED_REPOSITORY
  abort "invalid chart path" unless chart["path"] == EXPECTED_CHART
  revision = source.fetch("revision")
  abort "invalid source revision" unless revision.is_a?(String) && revision.match?(FULL_SHA)

  components = artifact.fetch("components")
  abort "component set must be flow and web" unless components.is_a?(Hash) && components.keys.sort == EXPECTED_COMPONENTS.keys.sort
  EXPECTED_COMPONENTS.each_key do |component|
    coordinate = components.fetch(component)
    abort "invalid #{component} component" unless coordinate.is_a?(Hash)
    component_revision = coordinate.fetch("sourceRevision")
    repository = coordinate.fetch("repository")
    tag = coordinate.fetch("tag")
    digest = coordinate.fetch("digest")
    abort "invalid #{component} source revision" unless component_revision.is_a?(String) && component_revision.match?(FULL_SHA)
    abort "invalid #{component} repository" unless repository == EXPECTED_COMPONENTS.fetch(component)
    abort "#{component} source revision does not match the promotion source" unless component_revision == revision
    abort "invalid #{component} immutable tag" unless tag == "sha-#{component_revision}"
    abort "invalid #{component} digest" unless digest.is_a?(String) && digest.match?(DIGEST)
    abort "#{component} digest is not bound to its build output" unless digest == expected_digests.fetch(component)
  end

  artifact
rescue KeyError => error
  abort "#{path}: missing field: #{error.message}"
end

def validate_release(release)
  expected_keys = [*EXPECTED_RELEASE.keys, "source", *EXPECTED_PATHS.keys, "promotion"].sort
  abort "unexpected Federation release fields" unless release.keys.sort == expected_keys
  EXPECTED_RELEASE.each do |field, expected|
    abort "unexpected Federation release #{field}" unless release[field] == expected
  end

  EXPECTED_PATHS.each do |field, expected|
    value = release[field]
    abort "invalid Federation release #{field}" unless value == { "path" => expected }
  end

  source = release["source"]
  abort "invalid current Federation source" unless source.is_a?(Hash) && source.keys.sort == %w[path repoURL revision]
  approved_path = APPROVED_EXISTING_SOURCES[source["repoURL"]]
  abort "unapproved current Federation source" unless approved_path && source["path"] == approved_path
  revision = source["revision"]
  abort "invalid current Federation source revision" unless revision.is_a?(String) && revision.match?(FULL_SHA)

  promotion = release["promotion"]
  abort "invalid Federation promotion" unless promotion.is_a?(Hash) && promotion.keys == ["mode"]
  mode = promotion["mode"]
  abort "invalid promotion mode: #{mode}" unless %w[pinned tracked].include?(mode)

  mode
end

def migrate_poc_values(values, artifact)
  abort "unexpected legacy Federation values" unless values.keys.sort == %w[images releaseLabel resultWeb s3]

  s3 = values.fetch("s3")
  service = values.fetch("resultWeb").fetch("service")
  legacy_images = values.fetch("images")
  abort "unexpected legacy Federation images" unless legacy_images.keys.sort == %w[awsCli nginx]

  pull_policies = {
    "flow" => legacy_images.fetch("awsCli").fetch("pullPolicy"),
    "web" => legacy_images.fetch("nginx").fetch("pullPolicy")
  }
  images = EXPECTED_COMPONENTS.to_h do |component, repository|
    promoted = artifact.fetch("components").fetch(component)
    [component, {
      "repository" => repository,
      "tag" => promoted.fetch("tag"),
      "digest" => promoted.fetch("digest"),
      "sourceRevision" => promoted.fetch("sourceRevision"),
      "pullPolicy" => pull_policies.fetch(component)
    }]
  end
  {
    "runId" => "poc-rgw-analysis-web",
    "resultSync" => { "intervalSeconds" => s3.fetch("syncIntervalSeconds") },
    "storage" => {
      "endpointUrl" => s3.fetch("endpointUrl"), "bucket" => s3.fetch("bucket"),
      "region" => s3.fetch("region"), "waitSeconds" => s3.fetch("waitSeconds"),
      "pollIntervalSeconds" => s3.fetch("pollIntervalSeconds")
    },
    "credentials" => {
      "existingSecret" => s3.fetch("secretName"), "accessKeyIdKey" => "access-key-id",
      "secretAccessKeyKey" => "secret-access-key", "sessionTokenKey" => "session-token"
    },
    "images" => images,
    "service" => { "port" => service.fetch("port"), "annotations" => service.fetch("annotations") }
  }
rescue KeyError => error
  abort "legacy Federation values missing field: #{error.message}"
end

def release_paths(root)
  root_path = Pathname.new(root).expand_path
  abort "Federation checkout is absent" unless root_path.directory?

  base = root_path.join("releases/poc/rgw-analysis-web")
  [base.join("release.yaml"), base.join("values.yaml")].each do |path|
    abort "missing Federation target: #{path}" unless path.file?
  end
end

def render_documents(release, values, artifact)
  previous_source = release.fetch("source")
  release["renderer"] = EXPECTED_RENDERER
  release["source"] = {
    "repoURL" => EXPECTED_REPOSITORY,
    "path" => EXPECTED_CHART,
    "revision" => artifact.fetch("source").fetch("revision")
  }

  images = values["images"]
  abort "Federation values images must be a mapping" unless images.is_a?(Hash)
  if images.keys.sort == %w[awsCli nginx]
    abort "legacy values require the approved POC source" unless previous_source == {
      "repoURL" => "https://github.com/SJoon99/scalex-feature-poc.git", "path" => "chart",
      "revision" => previous_source["revision"]
    }
    values = migrate_poc_values(values, artifact)
  else
    abort "Federation values component set must be flow and web" unless images.keys.sort == EXPECTED_COMPONENTS.keys.sort
    EXPECTED_COMPONENTS.each do |component, repository|
      current = images.fetch(component)
      abort "invalid Federation values image: #{component}" unless current.is_a?(Hash)
      promoted = artifact.fetch("components").fetch(component)
      current["repository"] = repository
      current["tag"] = promoted.fetch("tag")
      current["digest"] = promoted.fetch("digest")
      current["sourceRevision"] = promoted.fetch("sourceRevision")
    end
  end

  [Psych.dump(release, line_width: -1), Psych.dump(values, line_width: -1)]
end

def replace_files(paths, contents)
  staged = paths.zip(contents, strict: true).map do |path, content|
    file = Tempfile.new([path.basename.to_s, ".tmp"], path.dirname.to_s)
    file.write(content)
    file.flush
    file.fsync
    file.close
    [path, file.path]
  end
  staged.each { |path, temporary| FileUtils.mv(temporary, path.to_s) }
ensure
  staged&.each { |_path, temporary| FileUtils.rm_f(temporary) }
end

options = { write: false }
parser = OptionParser.new do |arguments|
  arguments.banner = "Usage: promote-release.sh --artifact PATH --federation-dir PATH --flow-digest DIGEST --web-digest DIGEST [--write]"
  arguments.on("--artifact PATH") { |value| options[:artifact] = value }
  arguments.on("--federation-dir PATH") { |value| options[:federation_dir] = value }
  arguments.on("--flow-digest DIGEST") { |value| options[:flow_digest] = value }
  arguments.on("--web-digest DIGEST") { |value| options[:web_digest] = value }
  arguments.on("--write") { options[:write] = true }
end
parser.parse!
required_options = %i[artifact federation_dir flow_digest web_digest]
abort parser.to_s unless required_options.all? { |key| options[key] } && ARGV.empty?

expected_digests = {
  "flow" => options.fetch(:flow_digest),
  "web" => options.fetch(:web_digest)
}
expected_digests.each do |component, digest|
  abort "invalid expected #{component} digest" unless digest.match?(DIGEST)
end

features_path = ENV.fetch("FEATURES_FILE", File.expand_path("../../features.yaml", __dir__))
feature_contract(features_path)
artifact = validate_artifact(options.fetch(:artifact), expected_digests)
paths = release_paths(options.fetch(:federation_dir))
release = load_mapping(paths.fetch(0))
values = load_mapping(paths.fetch(1))
mode = validate_release(release)
if mode == "pinned"
  puts "promotion mode pinned: no Federation files changed"
  exit 0
end

documents = render_documents(release, values, artifact)
if options.fetch(:write)
  replace_files(paths, documents)
  puts "promotion mode tracked: release.yaml and values.yaml updated"
else
  puts "promotion dry-run: tracked release validated; no files changed"
end
