@echo off
setlocal

REM If GNU make isn't installed on Windows, run manually:
REM   py -3.11 -m venv .venv
REM   call .venv\Scripts\activate.bat
REM   python -m pip install -U pip
REM   pip install -r requirements.txt -r requirements-dev.txt
REM   pip install -e .
REM   python -m ruff check .
REM   python -m pytest -q
REM   python -m complaints_pipeline backup --sp-upload --sp-upload-log

make install
make test
make lint
make run

endlocal
