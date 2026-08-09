# workspace-runtime-base-java

Workspace runtime base image with Eclipse Temurin JDK 21 (LTS) and Apache
Maven 3.9.x.

This image extends `workspace-runtime-base-lite` via Docker's `--build-context`
mechanism. The developer toolchain (bash, build-essential, curl, git, Node.js
LTS, uv, etc.) is inherited from the lite image; only Java and Maven are
installed on top.

## Build

```bash
# Make sure the lite image is available locally first.
docker build -t workspace-runtime-base-lite workspace-runtime/base-images/lite

# Build the Java base image, supplying the lite image as a build context.
docker build \
    --build-context workspace-runtime-base-lite=docker-image://workspace-runtime-base-lite \
    -t workspace-runtime-base-java \
    workspace-runtime/base-images/java21
```

In CI the lite image is pulled from Docker Hub
(`ailerondocker/workspace-runtime-base-lite:<channel>-<arch>`).

## Verification

`verify.sh` runs during build and asserts:

- `java -version` reports Java `21.x`
- `mvn -version` reports `Apache Maven 3.9.x`

The build fails if either check fails.

## Environment

| Variable          | Value                              |
| ----------------- | ---------------------------------- |
| `JAVA_HOME`       | `/opt/java-21` (symlink to JDK)    |
| `PATH`            | `${JAVA_HOME}/bin` is prepended    |

Maven uses its standard `${HOME}/.m2` location. Runtime provisioning persists
the complete user home instead of configuring a separate Maven-specific path.
