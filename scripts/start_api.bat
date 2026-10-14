@echo off
REM SENTINEL-911 — start API (demo mode)
REM Research prototype only — not for real emergency dispatch.
cd /d "%~dp0"
set PYTHONPATH=%CD%
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
