#!/usr/bin/env bash
# Scan or inventory the built images (docs/09 section 8).
#
#   image_scan.sh scan [SEVERITIES]   Trivy; exit 1 on findings of these severities
#   image_scan.sh report              Trivy; list HIGH and CRITICAL, never fail on them
#   image_scan.sh sbom                syft; CycloneDX files in reports/
#
# The scanners read saved tarballs: they never get the Docker socket, which is root on the host.
set -euo pipefail

TRIVY="aquasec/trivy:0.76.2@sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb"
SYFT="anchore/syft@sha256:e97e20b6e6d1699c60296b66ab337941724f9bd06ac279d893eda89601fc4b2a" # 1.57.2

root="$(cd "$(dirname "$0")/.." && pwd)"
mode="${1:-scan}"
severities="${2:-HIGH,CRITICAL}"
cache="$root/.cache/trivy"
mkdir -p "$cache" "$root/reports"
# On disk, not a RAM /tmp: the API image is several GB saved and again unpacked.
work="$(mktemp -d "$root/.cache/scan.XXXXXX")"
scratch="$(mktemp -d "$root/.cache/scan-tmp.XXXXXX")"
trap 'rm -rf "$work" "$scratch"' EXIT
as_me=(--rm --user "$(id -u):$(id -g)" -v "$scratch:/tmp" -e HOME=/tmp --cap-drop ALL --security-opt no-new-privileges:true)

status=0
for name in ehr-mip-api ehr-mip-web; do
  docker save -o "$work/$name.tar" "$name:local"
  case "$mode" in
    scan | report)
      code=1
      if [[ "$mode" == report ]]; then code=0; fi
      docker run "${as_me[@]}" -v "$work:/work:ro" -v "$cache:/cache" \
        -v "$root/.trivyignore.yaml:/ignore.yaml:ro" -e TRIVY_CACHE_DIR=/cache "$TRIVY" \
        image --quiet --input "/work/$name.tar" --scanners vuln --ignorefile /ignore.yaml \
        --severity "$severities" --exit-code "$code" || status=1
      ;;
    sbom)
      docker run "${as_me[@]}" --network none -v "$work:/work:ro" -e SYFT_CHECK_FOR_APP_UPDATE=false \
        "$SYFT" scan "docker-archive:/work/$name.tar" --output cyclonedx-json --quiet \
        > "$work/sbom.json"
      mv "$work/sbom.json" "$root/reports/sbom-$name.cdx.json" # only a complete file lands
      echo "wrote reports/sbom-$name.cdx.json"
      ;;
    *)
      echo "usage: $0 scan [SEVERITIES] | report | sbom" >&2
      exit 2
      ;;
  esac
  rm -f "$work/$name.tar"
done
exit "$status"
