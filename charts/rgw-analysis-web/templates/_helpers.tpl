{{- define "rgw-analysis-web.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "rgw-analysis-web.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "rgw-analysis-web.labels" -}}
app.kubernetes.io/name: {{ include "rgw-analysis-web.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
app.kubernetes.io/part-of: rgw-analysis-web
scalex.io/release: {{ .Release.Name }}
{{- end -}}

{{- define "rgw-analysis-web.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rgw-analysis-web.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: web
scalex.io/release: {{ .Release.Name }}
scalex.io/component: result-web
{{- end -}}

{{- define "rgw-analysis-web.image" -}}
{{- $expectedTag := printf "sha-%s" .sourceRevision -}}
{{- if ne .tag $expectedTag -}}
{{- fail (printf "image tag %s must equal %s for sourceRevision %s" .tag $expectedTag .sourceRevision) -}}
{{- end -}}
{{- printf "%s:%s@%s" .repository .tag .digest -}}
{{- end -}}

{{- define "rgw-analysis-web.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: 65532
runAsGroup: 65532
fsGroup: 65532
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "rgw-analysis-web.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop:
    - ALL
{{- end -}}

{{- define "rgw-analysis-web.storageEnv" -}}
- name: S3_ENDPOINT_URL
  valueFrom:
    configMapKeyRef:
      name: {{ include "rgw-analysis-web.fullname" . }}-runtime
      key: S3_ENDPOINT_URL
- name: S3_BUCKET
  valueFrom:
    configMapKeyRef:
      name: {{ include "rgw-analysis-web.fullname" . }}-runtime
      key: S3_BUCKET
- name: AWS_DEFAULT_REGION
  valueFrom:
    configMapKeyRef:
      name: {{ include "rgw-analysis-web.fullname" . }}-runtime
      key: AWS_DEFAULT_REGION
- name: S3_WAIT_SECONDS
  valueFrom:
    configMapKeyRef:
      name: {{ include "rgw-analysis-web.fullname" . }}-runtime
      key: S3_WAIT_SECONDS
- name: S3_POLL_INTERVAL_SECONDS
  valueFrom:
    configMapKeyRef:
      name: {{ include "rgw-analysis-web.fullname" . }}-runtime
      key: S3_POLL_INTERVAL_SECONDS
- name: AWS_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: {{ .Values.credentials.existingSecret }}
      key: {{ .Values.credentials.accessKeyIdKey }}
- name: AWS_SECRET_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.credentials.existingSecret }}
      key: {{ .Values.credentials.secretAccessKeyKey }}
- name: AWS_SESSION_TOKEN
  valueFrom:
    secretKeyRef:
      name: {{ .Values.credentials.existingSecret }}
      key: {{ .Values.credentials.sessionTokenKey }}
      optional: true
{{- end -}}
