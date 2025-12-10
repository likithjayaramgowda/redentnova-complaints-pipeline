#!/usr/bin/env bash
set -euo pipefail

make install
make test
make lint
make run
