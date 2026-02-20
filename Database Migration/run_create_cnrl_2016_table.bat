@echo off
REM Fill these values before running
set "PGHOST=localhost"
set "PGPORT=5432"
set "PGDATABASE=ili"
set "PGUSER=postgres"
set "PGPASSWORD=RedPlums2025."

REM Optional: set full psql path if psql is not in PATH
set "PSQL_EXE=psql"
REM Example:
REM set "PSQL_EXE=C:\Program Files\PostgreSQL\17\bin\psql.exe"

"%PSQL_EXE%" -v ON_ERROR_STOP=1 -f "Scripts\create_cnrl_2016_table.sql"

if errorlevel 1 (
  echo Failed to create table.
  exit /b 1
)

echo Table created successfully.
exit /b 0

