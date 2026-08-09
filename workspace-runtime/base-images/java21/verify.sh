#!/usr/bin/env bash
# Build-time sanity check for the base-java image.
# Fails the build if Java 21 or Maven 3.9.x is missing.
set -euo pipefail

JAVA_OUTPUT="$(java -version 2>&1 || true)"
if ! grep -q '"21\.' <<<"${JAVA_OUTPUT}"; then
    echo "verify.sh: java -version did not report Java 21" >&2
    echo "${JAVA_OUTPUT}" >&2
    exit 1
fi

MVN_OUTPUT="$(mvn -version 2>&1 || true)"
if ! grep -q 'Apache Maven 3\.9\.' <<<"${MVN_OUTPUT}"; then
    echo "verify.sh: mvn -version did not report Apache Maven 3.9.x" >&2
    echo "${MVN_OUTPUT}" >&2
    exit 1
fi

echo "verify.sh: Java 21 and Maven 3.9.x are present"
