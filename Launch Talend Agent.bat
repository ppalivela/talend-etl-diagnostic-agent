@echo off
title Talend Ingestion Error Agent
cd /d "%~dp0"

set PYTHON="C:\Users\prasanthp\AppData\Local\Microsoft\WindowsApps\python.exe"

echo Checking required packages...
%PYTHON% -c "import pyodbc" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing pyodbc (SQL Server)...
    %PYTHON% -m pip install pyodbc --quiet
)
%PYTHON% -c "import oracledb" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing oracledb (Oracle)...
    %PYTHON% -m pip install oracledb --quiet
)
%PYTHON% -c "import mysql.connector" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing mysql-connector-python (MySQL)...
    %PYTHON% -m pip install mysql-connector-python --quiet
)
%PYTHON% -c "import psycopg2" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing psycopg2-binary (PostgreSQL)...
    %PYTHON% -m pip install psycopg2-binary --quiet
)
%PYTHON% -c "import openpyxl" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing openpyxl (Excel support)...
    %PYTHON% -m pip install openpyxl --quiet
)
%PYTHON% -c "import customtkinter" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing customtkinter...
    %PYTHON% -m pip install customtkinter --quiet
)
echo All packages OK.
echo.
echo Starting Talend Ingestion Error Agent...
%PYTHON% talend_agent.py
if errorlevel 1 (
    echo.
    echo ERROR: Could not start the app.
    pause
)
