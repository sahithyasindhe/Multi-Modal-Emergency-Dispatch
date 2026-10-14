@echo off
REM SENTINEL-911 — start Streamlit dashboard
cd /d "%~dp0.."
set PYTHONPATH=%CD%
set SENTINEL_API_URL=http://127.0.0.1:8000
streamlit run frontend/app.py
