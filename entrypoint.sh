#!/bin/sh
set -eu

python -m localguide_assistant.indexer --skip-if-exists
exec streamlit run localguide_assistant/app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true
