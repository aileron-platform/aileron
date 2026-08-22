#!/bin/sh
set -eu

install -d -m 0755 /run/ganesha
install -d -m 0755 /run/dbus
install -d -m 2770 -g 2000 \
  /exports/knowledge-bases \
  /exports/manager-state \
  /exports/runtime-homes \
  /exports/workspaces \
  /exports/workspaces/11111111-1111-4111-8111-111111111111 \
  /exports/runtime-homes/11111111-1111-4111-8111-111111111111

/usr/bin/dbus-daemon --system --fork
/sbin/rpcbind -w
exec /usr/bin/ganesha.nfsd -F -L STDOUT -f /etc/ganesha/ganesha.conf
