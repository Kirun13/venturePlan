#!/bin/sh
set -eu
umask 077
mkdir -p /backups
trap 'exit 0' TERM INT
while true; do
  name="/backups/ventureplan-$(date -u +%Y%m%dT%H%M%SZ).dump"
  if pg_dump --format=custom --file="$name.partial"; then
    mv "$name.partial" "$name"
    echo "Database backup completed"
  else
    echo "Database backup failed" >&2
    exit 1
  fi
  sleep 86400 &
  wait $! || exit 0
done
