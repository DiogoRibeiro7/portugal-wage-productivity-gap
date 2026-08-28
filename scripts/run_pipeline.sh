#!/usr/bin/env bash
set -euo pipefail

# Execution verifies the prospectively created lock. It never rewrites the lock
# immediately before data retrieval.
poetry run pt-wage-gap verify-design-lock --config configs/study.yml
poetry run pt-wage-gap fetch-eurostat --config configs/study.yml
poetry run pt-wage-gap prepare --config configs/study.yml
poetry run pt-wage-gap analyse --config configs/study.yml
poetry run pt-wage-gap figures --config configs/study.yml
poetry run pt-wage-gap finalise-primary-release --config configs/study.yml
