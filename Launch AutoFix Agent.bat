@echo off
title Talend Auto-Fix & Re-Ingestion Agent
cd /d "%~dp0"

set PYTHON="C:\Users\prasanthp\AppData\Local\Microsoft\WindowsApps\python.exe"

echo ============================================================
echo   Talend Auto-Fix ^& Re-Ingestion Agent  ^|  MHA Inc.
echo ============================================================
echo Checking required packages...

%PYTHON% -c "import pandas" >nul 2>&1
if %errorlevel% neq 0 (
    echo   Installing pandas...
    %PYTHON% -m pip install pandas --quiet
)
%PYTHON% -c "import openpyxl" >nul 2>&1
if %errorlevel% neq 0 (
    echo   Installing openpyxl...
    %PYTHON% -m pip install openpyxl --quiet
)
%PYTHON% -c "import pyodbc" >nul 2>&1
if %errorlevel% neq 0 (
    echo   Installing pyodbc (SQL Server)...
    %PYTHON% -m pip install pyodbc --quiet
)
%PYTHON% -c "import oracledb" >nul 2>&1
if %errorlevel% neq 0 (
    echo   Installing oracledb (Oracle)...
    %PYTHON% -m pip install oracledb --quiet
)
%PYTHON% -c "import mysql.connector" >nul 2>&1
if %errorlevel% neq 0 (
    echo   Installing mysql-connector-python (MySQL)...
    %PYTHON% -m pip install mysql-connector-python --quiet
)
%PYTHON% -c "import psycopg2" >nul 2>&1
if %errorlevel% neq 0 (
    echo   Installing psycopg2-binary (PostgreSQL)...
    %PYTHON% -m pip install psycopg2-binary --quiet
)

echo All packages OK.
echo.
echo Starting Talend Auto-Fix Agent...
%PYTHON% talend_autofix.py
if errorlevel 1 (
    echo.
    echo ERROR: Application failed to start.
    pause
)
