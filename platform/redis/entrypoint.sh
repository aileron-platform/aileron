#!/bin/sh

set -eu

umask 0007
exec redis-server "$@"
