#!/usr/bin/env bash
set -euo pipefail
python -m training.prepare
python -m training.train_local
