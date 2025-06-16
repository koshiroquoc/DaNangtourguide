#!/bin/bash
python localguide_assistant/Indexing.py
python3 -m http.server 8888 --directory . &
streamlit run localguide_assistant/app_final_version.py --server.port=8501 --server.address=0.0.0.0
