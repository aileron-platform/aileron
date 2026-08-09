#!/bin/sh

set -eu

source_dir="${CANVAS_SOURCE_DIR:-/workspace}"
output_dir="${CANVAS_OUTPUT_DIR:-/output}"
build_dir="$(mktemp -d /tmp/aileron-canvas-build.XXXXXX)"

cleanup() {
    rm -rf "${build_dir}"
}
trap cleanup EXIT INT TERM

if [ ! -f "${source_dir}/package.json" ]; then
    echo "Next.js source is missing package.json." >&2
    exit 1
fi

cp -a "${source_dir}/." "${build_dir}/"
rm -rf "${build_dir}/node_modules" "${build_dir}/.next"
cp -a /opt/canvas-builder/node_modules "${build_dir}/node_modules"

cd "${build_dir}"
npx next build

if [ ! -f ".next/standalone/server.js" ]; then
    echo "Next.js build did not produce standalone/server.js." >&2
    echo "Set output: 'standalone' in next.config.js." >&2
    exit 1
fi

rm -rf "${output_dir:?}/"*
cp -a .next/standalone/. "${output_dir}/"
mkdir -p "${output_dir}/.next"
cp -a .next/static "${output_dir}/.next/static"
if [ -d public ]; then
    cp -a public "${output_dir}/public"
fi
