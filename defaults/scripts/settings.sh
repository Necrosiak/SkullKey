#!/usr/bin/env bash

if [[ -z "${DECKY_PLUGIN_DIR}" ]]; then
    export DECKY_PLUGIN_DIR="${HOME}/homebrew/plugins/SkeletonKey"
fi
if [[ -z "${DECKY_PLUGIN_RUNTIME_DIR}" ]]; then
    export DECKY_PLUGIN_RUNTIME_DIR="${HOME}/homebrew/data/SkeletonKey"
fi
if [[ -z "${DECKY_PLUGIN_LOG_DIR}" ]]; then
    export DECKY_PLUGIN_LOG_DIR="${HOME}/homebrew/logs/SkeletonKey"
fi

Extensions="Extensions"







