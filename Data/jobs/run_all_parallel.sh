#!/bin/sh
set -e
find Data/jobs -path "*/chunk_*.sh" -print | sort | xargs -n 1 -P 16 sh
