#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf salida
mkdir -p salida
while IFS= read -r line; do
  [[ -z "${line}" || "${line}" == \#* ]] && continue
  python run.py "eventos/${line}"
done < eventos/orden.txt
