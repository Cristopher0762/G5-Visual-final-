#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo 'Primero instala las dependencias siguiendo README.md'
  exit 1
fi
exec .venv/bin/python main.py
