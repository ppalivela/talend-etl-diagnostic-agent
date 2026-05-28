# -*- coding: utf-8 -*-
"""
Talend Ingestion Error Agent  v1.0
=====================================
• Paste error email → instant root-cause analysis
• Auto-detect file delimiter (csv, pipe, tab, xlsx, xls, semicolon…)
• Connect to live DB (SQL Server, Oracle, MySQL, PostgreSQL, SQLite)
• Read actual table schema & compare with file data
• Pinpoint exact rows/columns causing truncation or schema errors
• Generate a full diagnosis report
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import csv, re, json, os, threading, queue, statistics, io
from datetime import datetime
import sqlite3

# ─────────────────────────────────────────────────────────────────────────────
#  OPTIONAL DEPENDENCIES
# ─────────────────────────────────────────────────────────────────────────────
try:    import openpyxl;  OPENPYXL_OK = True
except ImportError: OPENPYXL_OK = False
try:    import xlrd;      XLRD_OK = True
except ImportError: XLRD_OK = False

PYODBC_OK = ORACLE_OK = MYSQL_OK = PG_OK = False

def _try_auto_install(package, import_name=None):
    """Silently install a package if not importable. Returns True if available."""
    name = import_name or package
    try:
        __import__(name)
        return True
    except ImportError:
        try:
            import subprocess, sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            __import__(name)
            return True
        except Exception:
            return False

try:    import pyodbc;    PYODBC_OK = True
except ImportError:
    if _try_auto_install("pyodbc"):
        try:    import pyodbc;  PYODBC_OK = True
        except: pass

try:
    import oracledb;     ORACLE_OK = True
except ImportError:
    if _try_auto_install("oracledb"):
        try:    import oracledb;  ORACLE_OK = True
        except: pass
    if not ORACLE_OK:
        try:    import cx_Oracle as oracledb;  ORACLE_OK = True
        except ImportError: pass

try:    import mysql.connector as _mysql; MYSQL_OK = True
except ImportError:
    if _try_auto_install("mysql-connector-python", "mysql.connector"):
        try:    import mysql.connector as _mysql; MYSQL_OK = True
        except: pass

try:    import psycopg2;  PG_OK = True
except ImportError:
    if _try_auto_install("psycopg2-binary", "psycopg2"):
        try:    import psycopg2;  PG_OK = True
        except: pass

APP_DIR   = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.join(APP_DIR, "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
#  FILE UTILITIES
# ─────────────────────────────────────────────────────────────────────────────
def detect_file_type(path):
    ext = os.path.splitext(path)[1].lower()
    return {".xlsx":"xlsx",".xls":"xls",".csv":"csv",".tsv":"tab",
            ".txt":"csv",".pipe":"custom",".tab":"custom"}.get(ext, "csv")

def auto_detect_delimiter(path, encoding="utf-8-sig"):
    """Return (delimiter_char, delimiter_name, avg_col_count, confidence_pct)."""
    candidates = [(",","Comma"),("|","Pipe"),("\t","Tab"),(";","Semicolon"),("~","Tilde"),("^","Caret")]
    try:
        with open(path, "r", encoding=encoding, errors="replace") as f:
            lines = [f.readline() for _ in range(40)]
        lines = [l for l in lines if l.strip()]
    except Exception:
        return ",", "Comma", 1, 0

    best_delim, best_name, best_cols, best_score = ",", "Comma", 1, -1
    for delim, name in candidates:
        counts = []
        for line in lines:
            try:
                row = next(csv.reader([line], delimiter=delim))
                if len(row) > 1:
                    counts.append(len(row))
            except Exception:
                pass
        if not counts:
            continue
        avg = statistics.mean(counts)
        std = statistics.stdev(counts) if len(counts) > 1 else 0
        score = avg / (1 + std)
        if score > best_score:
            best_score, best_delim, best_name, best_cols = score, delim, name, round(avg)

    # confidence: how consistent are the counts?
    all_counts = []
    for line in lines:
        try:
            row = next(csv.reader([line], delimiter=best_delim))
            all_counts.append(len(row))
        except Exception:
            pass
    if all_counts:
        mode_count = max(set(all_counts), key=all_counts.count)
        conf = int(100 * all_counts.count(mode_count) / len(all_counts))
    else:
        conf = 0
    return best_delim, best_name, best_cols, conf


def get_excel_sheets(path, ft):
    if ft == "xlsx" and OPENPYXL_OK:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        names = wb.sheetnames; wb.close(); return names
    if ft == "xls" and XLRD_OK:
        return xlrd.open_workbook(path).sheet_names()
    return []


def stream_file(path, file_type, opts):
    """Generator → yields ('__headers__', headers) then (row_num, [str_values])."""
    encoding = opts.get("encoding", "utf-8-sig")
    has_header = opts.get("has_header", True)
    sheet = opts.get("sheet")

    if file_type in ("csv", "pipe", "tab", "custom"):
        delim = opts.get("delimiter", ",")
        try:
            with open(path, "r", encoding=encoding, errors="replace", newline="") as fh:
                reader = csv.reader(fh, delimiter=delim)
                data_row = 0
                for i, row in enumerate(reader):
                    if i == 0 and has_header:
                        yield "__headers__", [c.strip() or f"Col{j+1}" for j, c in enumerate(row)]
                        continue
                    data_row += 1
                    yield data_row, [str(v) for v in row]
        except Exception as e:
            yield "__error__", str(e)
        return

    if file_type == "xlsx":
        if not OPENPYXL_OK:
            yield "__error__", "openpyxl not installed. Run: pip install openpyxl"; return
        try:
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            ws = wb[sheet] if sheet and sheet in wb.sheetnames else wb.active
            data_row = 0
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i == 0 and has_header:
                    yield "__headers__", [str(c).strip() if c is not None else f"Col{j+1}" for j, c in enumerate(row)]
                    continue
                data_row += 1
                yield data_row, ["" if v is None else str(v).rstrip() for v in row]
            wb.close()
        except Exception as e:
            yield "__error__", str(e)
        return

    if file_type == "xls":
        if not XLRD_OK:
            yield "__error__", "xlrd not installed. Run: pip install xlrd"; return
        try:
            wb = xlrd.open_workbook(path)
            ws = wb.sheet_by_name(sheet) if sheet else wb.sheet_by_index(0)
            data_row = 0
            for i in range(ws.nrows):
                row = [str(v).rstrip() for v in ws.row_values(i)]
                if i == 0 and has_header:
                    yield "__headers__", [c.strip() or f"Col{j+1}" for j, c in enumerate(row)]
                    continue
                data_row += 1
                yield data_row, row
        except Exception as e:
            yield "__error__", str(e)


def get_column_stats(path, file_type, opts, max_rows=10000):
    """Returns (headers, stats_dict, error_str_or_None).
    stats_dict = {col_idx: {max_len, min_len, null_count, sample, total}}"""
    headers = []
    stats   = {}
    row_count = 0
    for token, data in stream_file(path, file_type, opts):
        if token == "__headers__":
            headers = data
            for i in range(len(headers)):
                stats[i] = {"max_len": 0, "min_len": 99999, "null_count": 0, "sample": "", "total": 0}
            continue
        if token == "__error__":
            return headers, stats, str(data)
        _, values = token, data
        row_count += 1
        if row_count > max_rows:
            break
        for i, v in enumerate(values):
            if i not in stats:
                stats[i] = {"max_len": 0, "min_len": 99999, "null_count": 0, "sample": "", "total": 0}
            stats[i]["total"] += 1
            l = len(v)
            if l == 0:
                stats[i]["null_count"] += 1
            else:
                if l > stats[i]["max_len"]:
                    stats[i]["max_len"] = l
                    stats[i]["sample"] = v[:60]
                if l < stats[i]["min_len"]:
                    stats[i]["min_len"] = l
    for i in stats:
        if stats[i]["min_len"] == 99999:
            stats[i]["min_len"] = 0
    return headers, stats, None


def scan_truncations(path, file_type, opts, col_limits, result_q, cancel_event):
    total_rows = 0
    total_issues = 0
    headers = None
    try:
        for token, data in stream_file(path, file_type, opts):
            if cancel_event.is_set():
                break
            if token == "__headers__":
                headers = data; result_q.put(("header", data)); continue
            if token == "__error__":
                result_q.put(("error", data)); return
            row_num, values = token, data
            total_rows += 1
            for col_idx, raw_val in enumerate(values):
                col_name = headers[col_idx] if headers and col_idx < len(headers) else f"Col{col_idx+1}"
                limit = col_limits.get(col_idx, 0)
                if limit <= 0:
                    continue
                actual = len(raw_val)
                if actual > limit:
                    preview = raw_val[:80] + ("…" if len(raw_val) > 80 else "")
                    result_q.put(("issue", row_num, col_idx, col_name, actual, limit, preview))
                    total_issues += 1
            if total_rows % 500 == 0:
                result_q.put(("progress", total_rows))
    except Exception as e:
        result_q.put(("error", str(e))); return
    result_q.put(("done", total_rows, total_issues))


# ─────────────────────────────────────────────────────────────────────────────
#  EMAIL PARSER
# ─────────────────────────────────────────────────────────────────────────────
def parse_email(raw):
    ctx = {"time":"","project":"","job":"","file":"","file_ext":"","origin":"",
           "component_type":"","message":"","type":"","db_host":"","db_port":"",
           "db_name":"","db_table":"","raw":raw,"is_structured":False}

    # Structured Talend alert fields
    for field in ["Time","Project","Job","File","Type","Origin","Message"]:
        m = re.search(rf"(?im)^{field}\s*:\s*(.+)$", raw)
        if m:
            ctx[field.lower()] = m.group(1).strip()
            ctx["is_structured"] = True

    # Subject line extraction
    m = re.search(r"Subject\s*:\s*(.+)", raw, re.IGNORECASE)
    if m and not ctx["job"]:
        subj = m.group(1)
        jm = re.search(r"Job[:\s]+([A-Za-z0-9_\-]+)", subj, re.IGNORECASE)
        if jm: ctx["job"] = jm.group(1)

    # File extension
    for ext in ["xlsx","xls","csv","txt","tsv","pipe"]:
        if re.search(rf"\.{ext}\b", raw, re.IGNORECASE):
            ctx["file_ext"] = ext; break

    # Component from Origin
    origin = ctx.get("origin","")
    if not origin:
        m = re.search(r"\b(t[A-Z][a-zA-Z]+_\d+)\b", raw)
        if m: ctx["origin"] = origin = m.group(1)
    m = re.match(r"(t[A-Z][a-zA-Z]+)", origin)
    if m: ctx["component_type"] = m.group(1)

    # DB host:port from error messages
    m = re.search(r"(?:server|host)\s*[=:,]\s*([A-Za-z0-9.\-_\\]+)", raw, re.IGNORECASE)
    if m: ctx["db_host"] = m.group(1)
    m = re.search(r"(?:port)\s*[=:]\s*(\d{4,5})", raw, re.IGNORECASE)
    if m: ctx["db_port"] = m.group(1)
    m = re.search(r"([A-Za-z0-9.\-_]+):(\d{4,5})", raw)
    if m and not ctx["db_host"]: ctx["db_host"] = m.group(1); ctx["db_port"] = m.group(2)

    # Table from ORA/SQL error text
    m = re.search(r'"([A-Za-z0-9_$]+)"\."([A-Za-z0-9_$]+)"\."([A-Za-z0-9_$]+)"', raw)
    if m: ctx["db_table"] = m.group(2)
    for pat in [r"INSERT\s+INTO\s+([A-Za-z0-9_.]+)", r"INTO\s+([A-Za-z0-9_.]+)",
                r"table\s+['\"]([A-Za-z0-9_.$]+)['\"]"]:
        m = re.search(pat, raw, re.IGNORECASE)
        if m and not ctx["db_table"]:
            t = m.group(1)
            if "information_schema" not in t.lower():
                ctx["db_table"] = t; break

    # DB port defaults by DB type keyword
    if not ctx["db_port"]:
        rl = raw.lower()
        if "oracle" in rl or "ora-" in rl: ctx["db_port"] = "1521"
        elif any(k in rl for k in ["sqlserver","sql server","mssql"]): ctx["db_port"] = "1433"
        elif "mysql" in rl: ctx["db_port"] = "3306"
        elif "postgresql" in rl or "postgres" in rl: ctx["db_port"] = "5432"

    return ctx


# ─────────────────────────────────────────────────────────────────────────────
#  DIAGNOSIS ENGINE
# ─────────────────────────────────────────────────────────────────────────────
DIAG_PATTERNS = [
    {"id":"BATCH_TRUNCATION","cat":"Data Truncation","icon":"✂️",
     "patterns":[r"BatchUpdateException",r"Data\s+truncation",r"data.*truncat"],
     "ctx":{"comp":["tDBOutput","tDBInsert","tDBUpdate"],"boost":3},
     "needs":["file","db"],
     "cause":"One or more values written to the DB exceed the target column length (e.g., 120-char string into VARCHAR(50)).",
     "fixes":["► Load the error file in Tab 2, connect to DB in Tab 3, then click ⚡ Quick Compare — it will find the exact rows and columns",
              "In Talend job '{job}': open {origin} → Schema tab → compare 'Length' for each column vs DB DDL",
              "Add tLogRow BEFORE {origin} in job '{job}' to log all rows before they hit the DB",
              "In tMap before {origin}: trim with StringHandling.LEFT(row.colName, N) to enforce DB limit",
              "Set {origin} 'Die on error' = false → connect rejects output → tFileOutputDelimited to capture bad rows",
              "ALTER TABLE to widen the column: ALTER TABLE target MODIFY col VARCHAR2(500)"]},
    {"id":"XLSX_TRUNCATION","cat":"Data Truncation","icon":"📊✂️",
     "patterns":[r"truncat"],
     "ctx":{"ext":["xlsx","xls"],"comp":["tDBOutput","tDBInsert"],"boost":4,"require_all":True},
     "needs":["file","db"],
     "cause":"Excel file → DB truncation. Excel cells hold up to 32,767 chars; DB columns have fixed limits. A cell exceeds the mapped DB column width.",
     "fixes":["► Tab 2: load '{file_name}', Tab 3: connect to DB + fetch table schema, then click ⚡ Quick Compare",
              "In Excel: add a helper column =LEN(A1) and sort descending to find the longest values",
              "In tMap before {origin}: StringHandling.LEFT(row.col, DB_LIMIT)",
              "Set {origin} 'Die on error' = false → rejects → tFileOutputDelimited for business review"]},
    {"id":"ORA_TRUNCATION","cat":"Data Truncation","icon":"✂️",
     "patterns":[r"ORA-12899",r"ORA-01401",r"value too large for column",r"string or binary data would be truncated"],
     "needs":["file","db"],
     "cause":"Oracle ORA-12899 / SQL Server truncation: a value exceeds the declared column size.",
     "fixes":["Oracle full message names exact column: 'value too large for column SCHEMA.TABLE.COL (actual: N, maximum: M)'",
              "SQL Server 2019+: enable trace flag 460 for column-level detail",
              "Run in DB: SELECT column_name, character_maximum_length FROM information_schema.columns WHERE table_name='YOUR_TABLE'",
              "► Tab 3: connect to DB, enter table name, click Fetch Schema — then click ⚡ Compare with File"]},
    {"id":"WRONG_FIELDS","cat":"Delimiter Issue","icon":"📄",
     "patterns":[r"wrong number of fields",r"number of tokens is \d+",r"tFileInputDelimited.*wrong",r"too many.*col",r"not enough.*col",r"unexpected.*field"],
     "ctx":{"ext":["csv","txt"],"comp":["tFileInputDelimited"],"boost":2},
     "needs":["file"],
     "cause":"File has rows with a different number of columns than expected. Likely: wrong delimiter configured, or data field contains an unquoted delimiter.",
     "fixes":["► Tab 2: load the file → click Auto-Detect Delimiter — it will detect the actual separator",
              "In {origin} → 'Field Separator': change to the detected delimiter (e.g., from comma to pipe '|')",
              "Enable 'Enclosure character' (\") in {origin} so embedded delimiters inside quoted fields are ignored",
              "Open file in Notepad++ → View → Show All Characters to see actual separators"]},
    {"id":"XLSX_OPEN","cat":"Delimiter Issue","icon":"📊",
     "patterns":[r"poi.*exception",r"NotOfficeXmlFileException",r"org\.apache\.poi",r"XSSFWorkbook",r"cannot.*open.*xlsx"],
     "ctx":{"ext":["xlsx","xls"]},
     "needs":["file"],
     "cause":"Apache POI cannot open the Excel file: file is open/locked in Excel, wrong file format, POI version mismatch, or file is corrupt/password-protected.",
     "fixes":["Close '{file_name}' in Excel before running the job (file is locked)",
              "For .xls files: use 'Excel 97-2003' component; for .xlsx: use 'Excel 2007+'",
              "Check POI jars: poi-x.x.jar + poi-ooxml-x.x.jar must both be present and version-matched in Talend Studio",
              "Re-save the file in Excel as a fresh .xlsx copy to rule out corruption"]},
    {"id":"CONN_REFUSED","cat":"DB Connection","icon":"🔌",
     "patterns":[r"connection refused",r"ORA-12541",r"could not connect",r"connection.*refused",r"no listener",r"network.*unreachable"],
     "needs":["db_conn"],
     "cause":"DB server is refusing the TCP connection: service is down, wrong host/port, or firewall blocking.",
     "fixes":["► Tab 3: enter DB host ({db_host}) and port ({db_port}), click 🔌 Test Connection",
              "Windows test: Test-NetConnection -ComputerName {db_host} -Port {db_port}",
              "Check DB service: SQL Server → SQL Server Configuration Manager; Oracle → lsnrctl status",
              "Check firewall — Talend server IP must be allowed on port {db_port}",
              "Verify JDBC URL in {origin}: host and port must exactly match the actual server"]},
    {"id":"AUTH_FAILED","cat":"DB Connection","icon":"🔐",
     "patterns":[r"ORA-01017",r"authentication.*failed",r"login.*failed",r"access denied.*user",r"invalid username.*password",r"password.*incorrect",r"invalid credential"],
     "needs":["db_conn"],
     "cause":"DB authentication failed: wrong credentials, locked account, or expired password.",
     "fixes":["Verify username/password in {origin} (check for leading/trailing spaces)",
              "Test the same credentials in DBeaver or SQL Developer",
              "Oracle: check if account is locked: SELECT account_status FROM dba_users WHERE username=UPPER('user')",
              "SQL Server: verify if Windows auth vs SQL Server auth is configured in {origin}"]},
    {"id":"DRIVER_MISSING","cat":"DB Connection","icon":"🔧",
     "patterns":[r"ClassNotFoundException.*[Dd]river",r"no suitable driver",r"ClassNotFoundException.*[Jj]dbc",r"Unable to load.*driver"],
     "needs":[],
     "cause":"The JDBC driver .jar is missing from the Talend classpath.",
     "fixes":["Oracle: download ojdbc8.jar → Talend Studio: Window → Preferences → Talend → Libraries",
              "SQL Server: use mssql-jdbc.jar (Microsoft JDBC Driver for SQL Server)",
              "MySQL: use mysql-connector-j-x.x.jar",
              "Or add tLibraryLoad as the first component in job '{job}' pointing to the .jar file"]},
    {"id":"DB_TIMEOUT","cat":"DB Connection","icon":"⏱️",
     "patterns":[r"connection.*timed?\s*out",r"socket.*timeout",r"ORA-12170",r"lock wait timeout",r"query.*timed.*out",r"read timed out"],
     "needs":["db_conn"],
     "cause":"Connection or query timed out: overloaded DB, slow query, network latency, or lock contention.",
     "fixes":["Add connectTimeout=60000 to the JDBC URL in {origin}",
              "Check blocking locks: SQL Server → sys.dm_exec_requests; Oracle → V$SESSION WHERE status='ACTIVE'",
              "Add indexes to join/filter columns used by the query in {origin}",
              "Increase socket timeout and query timeout on the tDBConnection component"]},
    {"id":"FILE_NOT_FOUND","cat":"File Issue","icon":"🔍",
     "patterns":[r"file.*not found",r"FileNotFoundException",r"no such file",r"ENOENT",r"cannot find.*file",r"path.*does not exist"],
     "needs":[],
     "cause":"Input file does not exist at the configured path.",
     "fixes":["Verify the file path in {origin}: '{file}'",
              "Check if the upstream job/process generated the file and completed successfully",
              "Use tFileExist before the read component to handle missing files gracefully with a notification",
              "Check the Talend service account has READ permission on the directory"]},
    {"id":"FILE_LOCKED","cat":"File Issue","icon":"🚫",
     "patterns":[r"permission denied",r"access.*denied.*file",r"file.*locked",r"being used by another process",r"sharing.*violation"],
     "needs":[],
     "cause":"File is locked (open in Excel or another process) or Talend service account lacks file system permission.",
     "fixes":["Close '{file_name}' in Excel or any other application before running the job",
              "Windows: use Process Explorer (Sysinternals) to identify which process holds the lock",
              "Check file/directory ACL permissions for the Talend service account",
              "Add a tLoop + tFileExist + tSleep retry pattern to wait for the lock to release"]},
    {"id":"ENCODING","cat":"File Issue","icon":"🔡",
     "patterns":[r"MalformedInputException",r"unmappable character",r"encoding.*error",r"invalid.*byte.*sequence",r"codec.*decode"],
     "needs":["file"],
     "cause":"File encoding mismatch: file uses a different encoding than the job expects (e.g., file is Windows-1252 but job reads as UTF-8).",
     "fixes":["In {origin} → Encoding: try ISO-8859-1, Windows-1252, or UTF-16 (common for European/legacy files)",
              "Use Notepad++: Encoding menu → check the detected encoding",
              "Tab 2 File Scanner: change the Encoding dropdown to match",
              "Save source file as UTF-8 consistently for new files"]},
    {"id":"TYPE_CAST","cat":"Schema Mismatch","icon":"🔄",
     "patterns":[r"NumberFormatException",r"ClassCastException",r"For input string",r"invalid.*date.*format",r"cannot convert",r"invalid.*number"],
     "needs":["file"],
     "cause":"Value cannot be converted to the expected type: string 'N/A' in numeric column, wrong date format, null in numeric field.",
     "fixes":["Keep ALL input columns as String in the input component, convert in tMap with explicit Java expressions",
              "Integer: Integer.parseInt(row.field.trim())",
              "Date: TalendDate.parseDate(\"MM/dd/yyyy\", row.dateField)",
              "Use tFilterRow before conversion to route/remove unparseable rows"]},
    {"id":"NULL_VIOLATION","cat":"Schema Mismatch","icon":"⚠️",
     "patterns":[r"NOT NULL constraint",r"null value.*not-null",r"cannot insert null",r"Column.*cannot be null",r"ORA-01400"],
     "needs":["file","db"],
     "cause":"A required (NOT NULL) column is receiving a null/empty value from the source.",
     "fixes":["In tMap before {origin}: row.field != null ? row.field : \"DEFAULT_VALUE\"",
              "Use tFilterRow to route rows with null in mandatory columns to a reject output",
              "Tab 3: connect to DB, fetch schema → Nullable column shows required NOT NULL columns",
              "Check source file for blank cells in mandatory columns using Tab 2 File Scanner (shows null_count)"]},
    {"id":"DUPE_KEY","cat":"Schema Mismatch","icon":"🔑",
     "patterns":[r"Duplicate entry",r"unique constraint",r"ORA-00001",r"PRIMARY KEY violation",r"UNIQUE KEY.*constraint",r"duplicate key"],
     "needs":["db"],
     "cause":"Inserting a row with a duplicate primary key or unique constraint violation.",
     "fixes":["Add tAggregateRow or tUniqRow BEFORE {origin} to deduplicate on key columns",
              "Use tDBSCD or tDBUpsert (INSERT OR UPDATE) instead of plain INSERT",
              "Check source file for duplicate IDs: Tab 2 shows column stats; use Excel Conditional Formatting → Duplicate Values",
              "If this is a re-run, truncate the target table first or add a pre-job DELETE step"]},
    {"id":"OOM","cat":"Memory Issue","icon":"💾",
     "patterns":[r"OutOfMemoryError",r"java.*heap.*space",r"GC overhead limit",r"Not enough storage",r"heap size"],
     "needs":[],
     "cause":"JVM ran out of heap memory: large in-memory joins, huge lookup tables, or sorting millions of rows.",
     "fixes":["Increase heap: add -Xmx4g (or -Xmx8g) to Talend job VM arguments",
              "In tMap lookups: enable 'Store temp data on disk'",
              "Process data in batches: use SQL LIMIT/OFFSET or partition by date range",
              "Replace tSortRow with a DB-side ORDER BY clause"]},
    {"id":"NPE","cat":"Runtime Error","icon":"⚠️",
     "patterns":[r"NullPointerException"],
     "ctx":{"comp":["tMap","tJavaRow"],"boost":2},
     "needs":["file"],
     "cause":"Null value where non-null was expected — most common in tMap field expressions.",
     "fixes":["Wrap in {origin}: (row.field != null ? row.field : \"\")",
              "Use Relational.ISNULL(row.field) ? \"\" : row.field",
              "Add tFilterRow before {origin} to route/remove null records",
              "Enable 'Die on error' to get the exact line number in the Java expression"]},
]

CATEGORY_COLORS = {
    "Data Truncation": "#c0392b", "Delimiter Issue": "#1565c0",
    "DB Connection":   "#6a1b9a", "File Issue":      "#2e7d32",
    "Memory Issue":    "#e65100", "Schema Mismatch": "#0277bd",
    "Runtime Error":   "#880e4f",
}


def diagnose(ctx):
    """Returns sorted list of matching patterns with rendered text."""
    raw_lower = ctx["raw"].lower()
    results = []
    for pat in DIAG_PATTERNS:
        score, snippets = 0, []
        for regex in pat["patterns"]:
            try:
                m = re.search(regex, raw_lower, re.IGNORECASE)
                if m:
                    score += 1
                    s, e = max(0, m.start()-40), min(len(ctx["raw"]), m.end()+90)
                    snippets.append(ctx["raw"][s:e].replace("\n"," ").strip())
            except re.error:
                pass
        if score == 0:
            continue
        rules = pat.get("ctx", {})
        boost = rules.get("boost", 0)
        require_all = rules.get("require_all", False)
        ext_ok  = ctx["file_ext"]       in rules.get("ext",  []) if ctx["file_ext"]       else False
        comp_ok = ctx["component_type"] in rules.get("comp", []) if ctx["component_type"] else False
        if require_all:
            if ext_ok and comp_ok: score += boost
        else:
            if ext_ok:  score += boost // 2 + boost % 2
            if comp_ok: score += boost // 2
        fn = os.path.basename(ctx.get("file","") or "")
        subs = {"{origin}":   ctx.get("origin")   or "the failing component",
                "{job}":      ctx.get("job")       or "the job",
                "{file}":     ctx.get("file")      or "the input file",
                "{file_name}":fn                   or "the input file",
                "{db_host}":  ctx.get("db_host","") or "the DB host",
                "{db_port}":  ctx.get("db_port","") or "the DB port",
                "{table}":    ctx.get("db_table","") or "the target table"}
        def sub(t, _s=subs):
            for k, v in _s.items(): t = t.replace(k, v)
            return t
        results.append({**pat, "score": score, "snippets": snippets[:2],
                        "cause_r": sub(pat["cause"]), "fixes_r": [sub(f) for f in pat["fixes"]]})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  DB CONNECTOR
# ─────────────────────────────────────────────────────────────────────────────
SCHEMA_SQL = {
    # Only return CHARACTER_MAXIMUM_LENGTH for string types; NULL for all others.
    # -1 means varchar(max)/nvarchar(max) — no practical limit, treat as 0.
    "SQL Server": (
        "SELECT COLUMN_NAME, DATA_TYPE, "
        "  CASE WHEN DATA_TYPE IN ('varchar','nvarchar','char','nchar','text','ntext') "
        "       THEN NULLIF(CHARACTER_MAXIMUM_LENGTH, -1) ELSE NULL END AS MAX_LEN, "
        "  IS_NULLABLE "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME=? ORDER BY ORDINAL_POSITION", "?"),
    # Oracle: only char-length columns; NUMBER/DATE/etc → NULL
    "Oracle": (
        "SELECT COLUMN_NAME, DATA_TYPE, "
        "  CASE WHEN DATA_TYPE IN ('VARCHAR2','NVARCHAR2','CHAR','NCHAR') "
        "       THEN CHAR_LENGTH ELSE NULL END AS MAX_LEN, "
        "  NULLABLE FROM ALL_TAB_COLUMNS "
        "WHERE UPPER(TABLE_NAME)=UPPER(:1) ORDER BY COLUMN_ID", ":1"),
    # MySQL: only string types get CHARACTER_MAXIMUM_LENGTH; -1 = TEXT/BLOB, skip
    "MySQL": (
        "SELECT COLUMN_NAME, DATA_TYPE, "
        "  CASE WHEN DATA_TYPE IN ('varchar','char','nvarchar','nchar','tinytext') "
        "       THEN CHARACTER_MAXIMUM_LENGTH ELSE NULL END AS MAX_LEN, "
        "  IS_NULLABLE "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME=%s AND TABLE_SCHEMA=DATABASE() ORDER BY ORDINAL_POSITION", "%s"),
    "PostgreSQL": ("SELECT column_name, data_type, character_maximum_length, is_nullable "
                   "FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position", "%s"),
    "SQLite":     ("PRAGMA table_info(?)", "?"),
}


def db_connect(db_type, host, port, database, schema, user, password, extra=""):
    """Returns (conn, error_msg). conn=None on failure."""
    try:
        if db_type == "SQL Server":
            if not PYODBC_OK:
                return None, "pyodbc not installed. Run: pip install pyodbc"
            drivers = [d for d in pyodbc.drivers() if "SQL Server" in d] or \
                      ["ODBC Driver 17 for SQL Server", "ODBC Driver 18 for SQL Server", "SQL Server"]
            last_err = "No SQL Server ODBC driver found"
            for drv in drivers:
                try:
                    cs = (f"DRIVER={{{drv}}};SERVER={host},{port};DATABASE={database};"
                          f"UID={user};PWD={password};TrustServerCertificate=yes")
                    conn = pyodbc.connect(cs, timeout=10)
                    return conn, None
                except Exception as e:
                    last_err = str(e)
            return None, last_err

        elif db_type == "Oracle":
            if not ORACLE_OK:
                return None, "oracledb not installed. Run: pip install oracledb"
            dsn = extra or f"{host}:{port}/{database}"
            conn = oracledb.connect(user=user, password=password, dsn=dsn)
            return conn, None

        elif db_type == "MySQL":
            if not MYSQL_OK:
                return None, "mysql-connector-python not installed. Run: pip install mysql-connector-python"
            conn = _mysql.connect(host=host, port=int(port or 3306),
                                  database=database, user=user, password=password, connection_timeout=10)
            return conn, None

        elif db_type == "PostgreSQL":
            if not PG_OK:
                return None, "psycopg2 not installed. Run: pip install psycopg2-binary"
            conn = psycopg2.connect(host=host, port=int(port or 5432),
                                    dbname=database, user=user, password=password, connect_timeout=10)
            return conn, None

        elif db_type == "SQLite":
            db_path = database or extra
            if not os.path.exists(db_path):
                return None, f"SQLite file not found: {db_path}"
            conn = sqlite3.connect(db_path)
            return conn, None
        else:
            return None, f"Unsupported DB type: {db_type}"
    except Exception as e:
        return None, str(e)


def db_get_schema(conn, db_type, table):
    """Returns (cols_list, error_str). cols_list = [{name, type, max_len, nullable}]."""
    try:
        cur = conn.cursor()
        if db_type == "SQLite":
            cur.execute(f"PRAGMA table_info({table})")
            rows = cur.fetchall()
            result = []
            for r in rows:
                # cid, name, type, notnull, dflt_value, pk
                t = str(r[2])
                ml = 0
                m = re.search(r"\((\d+)", t)
                if m: ml = int(m.group(1))
                result.append({"name": str(r[1]), "type": t, "max_len": ml,
                                "nullable": "NO" if r[3] else "YES"})
            return result, None
        sql, ph = SCHEMA_SQL.get(db_type, SCHEMA_SQL["SQL Server"])
        cur.execute(sql, (table,))
        rows = cur.fetchall()
        result = []
        for r in rows:
            raw_len = r[2]
            # Negative means MAX (varchar(max)) — no practical char limit, skip for truncation
            if raw_len is not None and int(raw_len) < 0:
                raw_len = None
            max_len = int(raw_len) if raw_len is not None else 0
            result.append({"name": str(r[0]), "type": str(r[1]),
                            "max_len": max_len, "nullable": str(r[3])})
        return result, None
    except Exception as e:
        return [], str(e)


def db_list_tables(conn, db_type, schema=""):
    try:
        cur = conn.cursor()
        if db_type == "SQL Server":
            cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME")
        elif db_type == "Oracle":
            cur.execute("SELECT TABLE_NAME FROM ALL_TABLES WHERE OWNER=NVL(UPPER(:1),USER) ORDER BY TABLE_NAME",
                        (schema or None,))
        elif db_type == "MySQL":
            cur.execute("SHOW TABLES")
        elif db_type == "PostgreSQL":
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s ORDER BY tablename",
                        (schema or "public",))
        elif db_type == "SQLite":
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        else:
            return []
        return [str(r[0]) for r in cur.fetchall()]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
#  COLUMN MATCHING HELPERS  (MHA naming convention: file → tMap adds RD_ → DB)
# ─────────────────────────────────────────────────────────────────────────────
# ETL prefixes that Talend tMap adds to DB column names
_ETL_STRIP = ["rd", "ctl", "etl", "nav", "src", "stg", "dm"]
# Audit/runtime columns that are never in the source file — always skip
_RUNTIME_COLS = {"rdfilename","rdadduser","rdaddstmp","rdupduser","rdupdstmp",
                 "rdbatchid","rdrdid","rdloaddate","rdsource"}

def _norm_col(s: str) -> str:
    """Normalize column name: strip ALL non-alphanumeric chars, lowercase.
    Handles FIN.ID, FIN/ID, (FinID), FIN-ID, FIN_ID, 'Fin ID' etc."""
    return re.sub(r"[^a-z0-9]", "", s.lower())

def _camel_tokens(s: str) -> set:
    """Split a camelCase/PascalCase/ALLCAPS name into lowercase word tokens.
    FinID → {'fin','id'} | BusinessName → {'business','name'} | RD_FinID → {'rd','fin','id'}"""
    # Insert space between lowercase→uppercase and UPPER→Upperword boundaries
    s2 = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', s)
    s2 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', s2)
    tokens = re.split(r'[^a-zA-Z0-9]+', s2)
    return {t.lower() for t in tokens if len(t) > 1}

def match_file_to_schema(file_headers: list, db_schema: list,
                         col_map_overrides: dict = None) -> dict:
    """
    Return ({col_idx: max_len}, matched_names) matching file headers to DB schema columns.
    Handles MHA convention where Talend tMap adds prefixes like RD_, CTL_ etc.
    Matching levels (in order of priority):
      1. Exact normalized (BUSINESSNAME == BUSINESSNAME)
      2. DB column with ETL prefix stripped (RD_BusinessName → businessname)
      3. Manual overrides from col_map_overrides {db_col_norm: file_col_idx}
    Runtime/audit columns (rd_filename, rd_addstmp, etc.) are always skipped.
    """
    # Build lookup: normalized_name -> col dict
    lookup: dict = {}
    for col in db_schema:
        n = _norm_col(col["name"])
        if n in _RUNTIME_COLS:
            continue
        # Level 1: full normalized name
        lookup.setdefault(n, col)
        # Level 2: ETL-prefix-stripped variants
        for pfx in _ETL_STRIP:
            if n.startswith(pfx) and len(n) > len(pfx):
                stripped = n[len(pfx):]
                lookup.setdefault(stripped, col)

    limits: dict = {}
    matched_names: list = []
    for idx, hdr in enumerate(file_headers):
        n = _norm_col(hdr)
        db_col = lookup.get(n)
        if db_col and db_col.get("max_len", 0) > 0:
            limits[idx] = db_col["max_len"]
            matched_names.append(f"{hdr}→{db_col['name']}({db_col['max_len']})")

    # Level 3: apply manual overrides  {db_col_norm: file_col_idx}
    if col_map_overrides:
        # Build reverse: db_col_norm -> col dict
        db_col_lookup: dict = {}
        for col in db_schema:
            n = _norm_col(col["name"])
            db_col_lookup[n] = col
            for pfx in _ETL_STRIP:
                if n.startswith(pfx) and len(n) > len(pfx):
                    db_col_lookup.setdefault(n[len(pfx):], col)
        for db_norm, file_idx in col_map_overrides.items():
            if not (0 <= file_idx < len(file_headers)):
                continue
            col = db_col_lookup.get(db_norm)
            if col and col.get("max_len", 0) > 0 and file_idx not in limits:
                limits[file_idx] = col["max_len"]
                matched_names.append(
                    f"{file_headers[file_idx]}→{col['name']}({col['max_len']}) [manual]")
    return limits, matched_names


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN APP
# ─────────────────────────────────────────────────────────────────────────────
DB_TYPES = ["SQL Server", "Oracle", "MySQL", "PostgreSQL", "SQLite"]
DB_DEFAULT_PORTS = {"SQL Server": "1433", "Oracle": "1521", "MySQL": "3306",
                    "PostgreSQL": "5432", "SQLite": ""}
DB_DRIVER_STATUS = {
    "SQL Server": PYODBC_OK, "Oracle": ORACLE_OK, "MySQL": MYSQL_OK,
    "PostgreSQL": PG_OK, "SQLite": True
}

# ── Pre-configured MHA / Production DB profiles ──────────────────────────────
# All SQL Server instances use Windows Authentication (leave user/password blank)
# FLO-SQL-TDMU uses SQL Auth: user=SRVFLO-SQL-Talend (enter password at runtime)
DB_PRESETS = {
    "── Select a saved profile ──": {},
    "FLO-DDW-DEV  →  Formulary_Data": {
        "type": "SQL Server", "host": "FLO-DDW-DEV", "port": "1433",
        "db": "Formulary_Data", "schema": "dbo", "user": "", "pwd": "",
    },
    "FLO-SQL-NAVDWP  →  NAVDW": {
        "type": "SQL Server", "host": "FLO-SQL-NAVDWP", "port": "1433",
        "db": "NAVDW", "schema": "dbo", "user": "", "pwd": "",
    },
    "FLO-SQL-NAVDWP  →  NavDWStage": {
        "type": "SQL Server", "host": "FLO-SQL-NAVDWP", "port": "1433",
        "db": "NavDWStage", "schema": "dbo", "user": "", "pwd": "",
    },
    "FLO-SQL-NAVDWP  →  NAVMidas": {
        "type": "SQL Server", "host": "FLO-SQL-NAVDWP", "port": "1433",
        "db": "NAVMidas", "schema": "dbo", "user": "", "pwd": "",
    },
    "FLO-SQL-NAVDWP  →  MarketBaskets": {
        "type": "SQL Server", "host": "FLO-SQL-NAVDWP", "port": "1433",
        "db": "MarketBaskets", "schema": "dbo", "user": "", "pwd": "",
    },
    "ROMULUS  →  GPOData": {
        "type": "SQL Server", "host": "ROMULUS", "port": "1433",
        "db": "GPOData", "schema": "dbo", "user": "", "pwd": "",
    },
    "FLO-SQL-TDMU  →  talend_amc  (SQL Auth)": {
        "type": "SQL Server", "host": "FLO-SQL-TDMU", "port": "1433",
        "db": "talend_amc", "schema": "dbo", "user": "SRVFLO-SQL-Talend", "pwd": "",
    },
}

PLACEHOLDER = ("Paste the error email or Talend alert below...\n\n"
               "Time: Fri May 22 18:00:18 EDT 2026\n"
               "Project: NAV_DW_FORMULARY_OPTIMIZATION\n"
               "Job: Sysco_Rebate_Import\n"
               "File: \\\\server\\path\\4Q25 NAV OR RMD.xlsx\n"
               "Type: Java Exception\n"
               "Origin: tDBOutput_1\n"
               "Message: java.sql.BatchUpdateException:Data truncation\n\n"
               "-- OR paste any raw exception stack trace --")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Talend Ingestion Error Agent  v1.0")
        # Size window to 90% of screen, capped at 1300x860, then center it
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w  = min(int(sw * 0.90), 1300)
        h  = min(int(sh * 0.88), 860)
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(1000, 660)
        self.configure(bg="#1e1e2e")
        # Shared state
        self._ctx        = {}          # parsed email context
        self._file_stats = {}          # {col_idx: stats}
        self._file_headers = []
        self._file_path  = ""
        self._file_opts  = {}
        self._db_conn    = None
        self._db_type    = ""
        self._db_schema  = []          # [{name, type, max_len, nullable}]
        self._db_table   = ""
        self._col_map_overrides = {}   # {db_col_norm: file_col_idx}  — manual mappings
        self._map_vars   = {}          # {db_col_norm: StringVar}  — dropdown vars in mapping panel
        self._db_len_overrides = {}    # {col_name: int}  — manually edited DB column lengths
        self._scan_thread   = None
        self._cancel_event  = threading.Event()
        self._result_q      = queue.Queue()
        self._all_issues    = []
        self._diag_results  = []
        self._report_lines  = []
        self._setup_styles()
        self._build_ui()

    # ── STYLES ────────────────────────────────────────────────────────────────
    def _setup_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TNotebook", background="#1e1e2e", borderwidth=0)
        s.configure("TNotebook.Tab", background="#2a2a3e", foreground="#cdd6f4",
                    padding=[14, 6], font=("Segoe UI", 10, "bold"))
        s.map("TNotebook.Tab", background=[("selected","#89b4fa")],
              foreground=[("selected","#1e1e2e")])
        s.configure("TFrame", background="#1e1e2e")
        s.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 10))
        s.configure("H.TLabel", background="#1e1e2e", foreground="#89b4fa", font=("Segoe UI",12,"bold"))
        s.configure("TScrollbar", background="#313244", troughcolor="#1e1e2e", arrowcolor="#89b4fa")
        s.configure("Treeview", background="#181825", foreground="#cdd6f4",
                    fieldbackground="#181825", rowheight=24, font=("Segoe UI",10))
        s.configure("Treeview.Heading", background="#313244", foreground="#89b4fa",
                    font=("Segoe UI",10,"bold"))
        s.map("Treeview", background=[("selected","#45475a")], foreground=[("selected","#cdd6f4")])
        s.configure("TCombobox", fieldbackground="#181825", background="#313244",
                    foreground="#cdd6f4", selectbackground="#45475a")
        s.configure("TEntry", fieldbackground="#181825", foreground="#cdd6f4", insertcolor="#89b4fa")
        s.configure("TProgressbar", troughcolor="#313244", background="#89b4fa", thickness=14)

    # ── TOP-LEVEL UI ──────────────────────────────────────────────────────────
    def _build_ui(self):
        hdr = tk.Frame(self, bg="#181825", pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚙  Talend Ingestion Error Agent",
                 bg="#181825", fg="#89b4fa", font=("Segoe UI",16,"bold")).pack(side="left", padx=18)
        tk.Label(hdr, text="Email Analysis  •  Auto-Delimiter Detection  •  Live DB Connection  •  Schema Comparison",
                 bg="#181825", fg="#585b70", font=("Segoe UI",9)).pack(side="left", padx=4)

        # Driver status bar
        drv_bar = tk.Frame(hdr, bg="#181825")
        drv_bar.pack(side="right", padx=18)
        for dbtype, ok in DB_DRIVER_STATUS.items():
            color = "#a6e3a1" if ok else "#f38ba8"
            tk.Label(drv_bar, text=f"{'✓' if ok else '✗'} {dbtype}",
                     bg="#181825", fg=color, font=("Segoe UI",8)).pack(side="left", padx=4)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=(6,10))
        self._nb = nb

        self._t_email  = ttk.Frame(nb)
        self._t_file   = ttk.Frame(nb)
        self._t_db     = ttk.Frame(nb)
        self._t_report = ttk.Frame(nb)
        nb.add(self._t_email,  text="📧  Email Analysis")
        nb.add(self._t_file,   text="📂  File Scanner")
        nb.add(self._t_db,     text="🗄️  DB Inspector")
        nb.add(self._t_report, text="📊  Full Report")

        self._build_email_tab()
        self._build_file_tab()
        self._build_db_tab()
        self._build_report_tab()

    # ═══════════════════════════════════════════════════════════════════════════
    #  TAB 1 — EMAIL ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════
    def _build_email_tab(self):
        tab = self._t_email
        tab.columnconfigure(0, weight=2)
        tab.columnconfigure(1, weight=3)
        tab.rowconfigure(1, weight=1)

        # ── Left column: input ────────────────────────────────────────────────
        ttk.Label(tab, text="Paste Error Email / Alert:", style="H.TLabel"
                  ).grid(row=0, column=0, sticky="w", padx=14, pady=(10,2))

        inp_f = tk.Frame(tab, bg="#1e1e2e")
        inp_f.grid(row=1, column=0, sticky="nsew", padx=(14,4), pady=(0,4))
        inp_f.rowconfigure(0, weight=1); inp_f.columnconfigure(0, weight=1)

        self._email_input = scrolledtext.ScrolledText(
            inp_f, wrap="word", bg="#181825", fg="#585b70",
            insertbackground="#89b4fa", font=("Consolas", 10), relief="flat")
        self._email_input.grid(row=0, column=0, sticky="nsew")
        self._email_input.insert("1.0", PLACEHOLDER)
        self._email_input.bind("<FocusIn>",  self._email_clear_ph)
        self._email_input.bind("<FocusOut>", self._email_restore_ph)

        # Buttons
        btn_f = tk.Frame(tab, bg="#1e1e2e")
        btn_f.grid(row=2, column=0, sticky="ew", padx=14, pady=6)

        tk.Button(btn_f, text="🔍  Analyze Error", bg="#89b4fa", fg="#1e1e2e",
                   font=("Segoe UI",11,"bold"), relief="flat", cursor="hand2",
                   padx=18, pady=6, command=self._do_analysis).pack(side="left", padx=(0,8))
        tk.Button(btn_f, text="📂 Load .txt/.log", bg="#45475a", fg="#cdd6f4",
                   font=("Segoe UI",10), relief="flat", cursor="hand2",
                   padx=10, pady=6, command=self._email_load_file).pack(side="left", padx=(0,6))
        tk.Button(btn_f, text="🗑 Clear", bg="#45475a", fg="#cdd6f4",
                   font=("Segoe UI",10), relief="flat", cursor="hand2",
                   padx=10, pady=6, command=self._email_clear).pack(side="left")
        tk.Button(btn_f, text="💾 Save Report", bg="#45475a", fg="#cdd6f4",
                   font=("Segoe UI",10), relief="flat", cursor="hand2",
                   padx=10, pady=6, command=self._save_report).pack(side="right")

        # ── Right column: context chips + diagnosis ───────────────────────────
        ttk.Label(tab, text="Extracted Context:", style="H.TLabel"
                  ).grid(row=0, column=1, sticky="w", padx=(6,14), pady=(10,2))

        chips_f = tk.Frame(tab, bg="#181825", pady=6)
        chips_f.grid(row=0, column=1, sticky="ew", padx=(6,14), pady=(38,0))
        self._chips = {}
        for field, color in [("project","#89b4fa"),("job","#a6e3a1"),("file","#f9e2af"),
                              ("origin","#cba6f7"),("db_table","#89dceb"),("type","#f38ba8")]:
            cf = tk.Frame(chips_f, bg="#181825")
            cf.pack(side="left", padx=4)
            tk.Label(cf, text=field+":", bg="#181825", fg="#585b70",
                     font=("Segoe UI",8,"bold")).pack(anchor="w")
            lbl = tk.Label(cf, text="—", bg="#313244", fg="#a6adc8",
                           font=("Consolas",8), padx=4, pady=2, wraplength=150)
            lbl.pack()
            self._chips[field] = (lbl, color)

        res_f = tk.Frame(tab, bg="#1e1e2e")
        res_f.grid(row=1, column=1, rowspan=2, sticky="nsew", padx=(6,14), pady=(0,4))
        res_f.rowconfigure(0, weight=1); res_f.columnconfigure(0, weight=1)

        self._diag_canvas = tk.Canvas(res_f, bg="#181825", highlightthickness=0)
        dvsb = ttk.Scrollbar(res_f, orient="vertical", command=self._diag_canvas.yview)
        self._diag_canvas.configure(yscrollcommand=dvsb.set)
        self._diag_canvas.grid(row=0, column=0, sticky="nsew")
        dvsb.grid(row=0, column=1, sticky="ns")
        self._diag_inner = tk.Frame(self._diag_canvas, bg="#181825")
        _dcw = self._diag_canvas.create_window((0,0), window=self._diag_inner, anchor="nw")
        self._diag_inner.bind("<Configure>",
            lambda e: self._diag_canvas.configure(scrollregion=self._diag_canvas.bbox("all")))
        self._diag_canvas.bind("<Configure>",
            lambda e: self._diag_canvas.itemconfig(_dcw, width=e.width))
        self._diag_canvas.bind_all("<MouseWheel>",
            lambda e: self._diag_canvas.yview_scroll(int(-1*(e.delta/120)),"units"))
        self._show_diag_placeholder()

    def _email_clear_ph(self, _):
        if self._email_input.get("1.0","end-1c").startswith("Paste the error"):
            self._email_input.delete("1.0","end")
            self._email_input.config(fg="#cdd6f4")

    def _email_restore_ph(self, _):
        if not self._email_input.get("1.0","end-1c").strip():
            self._email_input.insert("1.0", PLACEHOLDER)
            self._email_input.config(fg="#585b70")

    def _email_clear(self):
        self._email_input.delete("1.0","end")
        self._email_input.insert("1.0", PLACEHOLDER)
        self._email_input.config(fg="#585b70")
        for lbl, _ in self._chips.values(): lbl.config(text="—", fg="#a6adc8")
        self._show_diag_placeholder()

    def _email_load_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Log/text files","*.txt *.log *.out *.eml"),("All files","*.*")])
        if path:
            try:
                content = open(path,"r",encoding="utf-8",errors="replace").read()
                self._email_input.delete("1.0","end")
                self._email_input.insert("1.0", content)
                self._email_input.config(fg="#cdd6f4")
            except Exception as ex:
                messagebox.showerror("Error", str(ex))

    def _show_diag_placeholder(self):
        for w in self._diag_inner.winfo_children(): w.destroy()
        tk.Label(self._diag_inner,
                 text="Paste an error email above and click  🔍 Analyze Error",
                 bg="#181825", fg="#585b70", font=("Segoe UI",11)).pack(pady=50)

    def _do_analysis(self):
        raw = self._email_input.get("1.0","end").strip()
        if not raw or raw.startswith("Paste the error"):
            messagebox.showwarning("No Input","Paste an error email first."); return

        ctx = parse_email(raw)
        self._ctx = ctx

        # Update chips
        chip_map = {"project":ctx.get("project",""),"job":ctx.get("job",""),
                    "file":os.path.basename(ctx.get("file","") or ""),
                    "origin":ctx.get("origin",""),"db_table":ctx.get("db_table",""),
                    "type":ctx.get("type","")}
        for field, (lbl, color) in self._chips.items():
            v = chip_map.get(field,"")
            lbl.config(text=(v[:22]+"…") if len(v)>22 else (v or "—"),
                       fg=color if v else "#585b70")

        results = diagnose(ctx)
        self._diag_results = results
        for w in self._diag_inner.winfo_children(): w.destroy()

        if not results:
            tk.Label(self._diag_inner,
                     text="⚠️  No matching patterns found.\nInclude more of the stack trace or error message.",
                     bg="#181825", fg="#f38ba8", font=("Segoe UI",11), justify="center").pack(pady=50)
            return

        if ctx["is_structured"]:
            b = tk.Frame(self._diag_inner, bg="#1e3a5f", pady=4)
            b.pack(fill="x", padx=10, pady=(10,4))
            tk.Label(b, text="✅  Structured Talend alert detected — context-aware analysis active",
                     bg="#1e3a5f", fg="#89b4fa", font=("Segoe UI",10,"bold")).pack(padx=10)

        tk.Label(self._diag_inner,
                 text=f"  {len(results)} possible cause(s) — highest confidence first",
                 bg="#181825", fg="#a6e3a1", font=("Segoe UI",10,"bold")).pack(anchor="w", padx=10, pady=(6,4))

        for r in results:
            self._render_diag_card(r)

        # Auto-populate other tabs
        if ctx.get("file"):
            self._file_path_var.set(ctx["file"])
        if ctx.get("db_host"):
            self._db_host_var.set(ctx["db_host"])
        if ctx.get("db_port"):
            self._db_port_var.set(ctx["db_port"])
        if ctx.get("db_table"):
            self._db_table_var.set(ctx["db_table"])

        self._update_report()

    def _render_diag_card(self, r):
        hdr_c = CATEGORY_COLORS.get(r["cat"], "#37474f")
        outer = tk.Frame(self._diag_inner, bg="#313244", relief="flat", bd=1)
        outer.pack(fill="x", padx=10, pady=5)

        # Header
        ch = tk.Frame(outer, bg=hdr_c)
        ch.pack(fill="x")
        tk.Label(ch, text=f"  {r['icon']}  {r['cat']} — {r['id'].replace('_',' ')}",
                 bg=hdr_c, fg="white", font=("Segoe UI",11,"bold"), anchor="w"
                 ).pack(side="left", padx=6, pady=6)
        stars = "★"*min(r["score"],5)+"☆"*max(0,5-r["score"])
        tk.Label(ch, text=f"{stars}  ", bg=hdr_c, fg="#ffffffbb",
                 font=("Segoe UI",9)).pack(side="right", pady=6)

        # Needs info badges
        needs = r.get("needs",[])
        if needs:
            nb_f = tk.Frame(outer, bg="#2a2a3e")
            nb_f.pack(fill="x", padx=2)
            tk.Label(nb_f, text="  To confirm:", bg="#2a2a3e", fg="#585b70",
                     font=("Segoe UI",9)).pack(side="left", padx=(6,4), pady=3)
            if "file" in needs:
                tk.Button(nb_f, text="📂 Load File (Tab 2)", bg="#2d3a2d", fg="#a6e3a1",
                           font=("Segoe UI",9), relief="flat", cursor="hand2", padx=6,
                           command=lambda: self._nb.select(1)).pack(side="left", padx=2, pady=2)
            if "db" in needs or "db_conn" in needs:
                tk.Button(nb_f, text="🗄️ DB Inspector (Tab 3)", bg="#2a2340", fg="#cba6f7",
                           font=("Segoe UI",9), relief="flat", cursor="hand2", padx=6,
                           command=lambda: self._nb.select(2)).pack(side="left", padx=2, pady=2)

        body = tk.Frame(outer, bg="#2a2a3e")
        body.pack(fill="x", padx=2, pady=2)

        if r.get("snippets"):
            sf = tk.Frame(body, bg="#181825")
            sf.pack(fill="x", padx=8, pady=(8,2))
            tk.Label(sf, text="Matched text:", bg="#181825", fg="#89dceb",
                     font=("Segoe UI",9,"bold")).pack(anchor="w")
            for s in r["snippets"]:
                tk.Label(sf, text=f"  …{s}…", bg="#181825", fg="#a6adc8",
                         font=("Consolas",9), wraplength=700, justify="left").pack(anchor="w", pady=1)

        rc = tk.Frame(body, bg="#2a2a3e")
        rc.pack(fill="x", padx=8, pady=(8,2))
        tk.Label(rc, text="🔎 Root Cause:", bg="#2a2a3e", fg="#f9e2af",
                 font=("Segoe UI",10,"bold")).pack(anchor="w")
        tk.Label(rc, text=r["cause_r"], bg="#2a2a3e", fg="#cdd6f4",
                 font=("Segoe UI",10), wraplength=720, justify="left").pack(anchor="w", padx=8, pady=3)

        ff = tk.Frame(body, bg="#2a2a3e")
        ff.pack(fill="x", padx=8, pady=(4,8))
        tk.Label(ff, text="🛠 Fix Steps:", bg="#2a2a3e", fg="#a6e3a1",
                 font=("Segoe UI",10,"bold")).pack(anchor="w")
        for i, fx in enumerate(r["fixes_r"], 1):
            fr = tk.Frame(ff, bg="#2a2a3e")
            fr.pack(fill="x", pady=2)
            tk.Label(fr, text=f"  {i}.", bg="#2a2a3e", fg="#89b4fa",
                     font=("Segoe UI",10,"bold"), width=3, anchor="e").pack(side="left")
            tk.Label(fr, text=fx, bg="#2a2a3e", fg="#cdd6f4",
                     font=("Segoe UI",10), wraplength=640, justify="left", anchor="w"
                     ).pack(side="left", padx=4, fill="x", expand=True)
            tk.Button(fr, text="📋", bg="#313244", fg="#89b4fa", font=("Segoe UI",8),
                       relief="flat", cursor="hand2", padx=2,
                       command=lambda t=fx: (self.clipboard_clear(), self.clipboard_append(t))
                       ).pack(side="right", padx=4)

    # ═══════════════════════════════════════════════════════════════════════════
    #  TAB 2 — FILE SCANNER
    # ═══════════════════════════════════════════════════════════════════════════
    def _build_file_tab(self):
        tab = self._t_file
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        # ── File Config ───────────────────────────────────────────────────────
        cfg = tk.LabelFrame(tab, text=" 1 · File ", bg="#1e1e2e", fg="#89b4fa",
                             font=("Segoe UI",10,"bold"), bd=1, relief="groove")
        cfg.grid(row=0, column=0, sticky="ew", padx=12, pady=(10,4))
        cfg.columnconfigure(1, weight=1)

        tk.Label(cfg, text="File Path:", bg="#1e1e2e", fg="#cdd6f4",
                 font=("Segoe UI",10)).grid(row=0, column=0, sticky="e", padx=8, pady=6)
        self._file_path_var = tk.StringVar()
        tk.Entry(cfg, textvariable=self._file_path_var, bg="#181825", fg="#cdd6f4",
                 insertbackground="#89b4fa", relief="flat",
                 font=("Consolas",10), bd=1).grid(row=0, column=1, sticky="ew", padx=4, pady=6)
        tk.Button(cfg, text="📂 Browse", bg="#45475a", fg="#cdd6f4",
                   font=("Segoe UI",9), relief="flat", cursor="hand2", padx=8,
                   command=self._browse_file).grid(row=0, column=2, padx=4, pady=6)
        tk.Button(cfg, text="🔎 Auto-Detect & Analyze", bg="#89dceb", fg="#1e1e2e",
                   font=("Segoe UI",9,"bold"), relief="flat", cursor="hand2", padx=10,
                   command=self._auto_analyze_file).grid(row=0, column=3, padx=4, pady=6)

        opts_row = tk.Frame(cfg, bg="#1e1e2e")
        opts_row.grid(row=1, column=0, columnspan=4, sticky="ew", padx=4, pady=(0,8))
        def lbl(t): return tk.Label(opts_row, text=t, bg="#1e1e2e", fg="#a6adc8", font=("Segoe UI",9))
        def cbx(var, vals, w=12):
            return ttk.Combobox(opts_row, textvariable=var, values=vals, state="readonly",
                                width=w, font=("Segoe UI",9))

        lbl("Type:").pack(side="left", padx=(8,2))
        self._ftype_var = tk.StringVar(value="xlsx")
        cbx(self._ftype_var, ["xlsx","xls","csv","custom"], 7).pack(side="left", padx=(0,10))

        lbl("Delimiter:").pack(side="left", padx=(0,2))
        self._delim_var = tk.StringVar(value=",")
        self._delim_name_var = tk.StringVar(value="Comma")
        delim_lbl = tk.Label(opts_row, textvariable=self._delim_name_var,
                              bg="#313244", fg="#f9e2af", font=("Consolas",10,"bold"),
                              padx=8, pady=2, width=12)
        delim_lbl.pack(side="left", padx=(0,4))

        lbl("Custom:").pack(side="left", padx=(4,2))
        self._custom_delim = tk.StringVar()
        tk.Entry(opts_row, textvariable=self._custom_delim, bg="#181825", fg="#cdd6f4",
                 insertbackground="#89b4fa", relief="flat", font=("Consolas",10), width=4
                 ).pack(side="left", padx=(0,10))

        lbl("Sheet:").pack(side="left", padx=(0,2))
        self._sheet_var = tk.StringVar()
        self._sheet_cb = ttk.Combobox(opts_row, textvariable=self._sheet_var,
                                       values=[], state="normal", width=14, font=("Segoe UI",9))
        self._sheet_cb.pack(side="left", padx=(0,10))

        lbl("Encoding:").pack(side="left", padx=(0,2))
        self._enc_var = tk.StringVar(value="utf-8-sig")
        cbx(self._enc_var, ["utf-8-sig","utf-8","utf-16","latin-1","windows-1252","cp1252"], 12
            ).pack(side="left", padx=(0,10))

        self._hdr_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opts_row, text="First row is header", variable=self._hdr_var,
                        bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244",
                        activebackground="#1e1e2e", font=("Segoe UI",9)
                        ).pack(side="left", padx=(4,0))

        # ── Detection status bar ──────────────────────────────────────────────
        self._file_status_var = tk.StringVar(value="No file loaded")
        tk.Label(cfg, textvariable=self._file_status_var,
                 bg="#1e1e2e", fg="#a6adc8", font=("Segoe UI",9)
                 ).grid(row=2, column=0, columnspan=4, sticky="w", padx=8, pady=(0,4))

        # ── Column Stats + DB Comparison table ───────────────────────────────
        comp_lf = tk.LabelFrame(tab, text=" 2 · Column Stats vs DB Schema (load DB schema from Tab 3) ",
                                 bg="#1e1e2e", fg="#f9e2af",
                                 font=("Segoe UI",10,"bold"), bd=1, relief="groove")
        comp_lf.grid(row=1, column=0, sticky="ew", padx=12, pady=4)
        comp_lf.columnconfigure(0, weight=1)
        comp_lf.rowconfigure(1, weight=1)

        ctrl_row = tk.Frame(comp_lf, bg="#1e1e2e")
        ctrl_row.pack(fill="x", padx=8, pady=(4,2))

        self._scan_btn = tk.Button(ctrl_row, text="▶  Scan for Truncation Issues",
                                    bg="#a6e3a1", fg="#1e1e2e", font=("Segoe UI",11,"bold"),
                                    relief="flat", cursor="hand2", padx=20, pady=6,
                                    command=self._start_scan)
        self._scan_btn.pack(side="left", padx=(0,8))
        tk.Button(ctrl_row, text="⚡ Quick Compare (uses DB Schema from Tab 3)",
                   bg="#cba6f7", fg="#1e1e2e", font=("Segoe UI",10,"bold"),
                   relief="flat", cursor="hand2", padx=12, pady=6,
                   command=self._quick_compare).pack(side="left", padx=(0,8))
        self._stop_btn = tk.Button(ctrl_row, text="⬛ Stop", bg="#f38ba8", fg="#1e1e2e",
                                    font=("Segoe UI",10,"bold"), relief="flat", cursor="hand2",
                                    padx=12, pady=6, state="disabled", command=self._stop_scan)
        self._stop_btn.pack(side="left", padx=(0,10))
        self._scan_status_var = tk.StringVar(value="Ready")
        tk.Label(ctrl_row, textvariable=self._scan_status_var, bg="#1e1e2e",
                 fg="#a6adc8", font=("Segoe UI",10)).pack(side="left")
        tk.Button(ctrl_row, text="💾 Export Report (CSV/XLSX/TXT)", bg="#45475a", fg="#cdd6f4",
                   font=("Segoe UI",9), relief="flat", cursor="hand2", padx=10,
                   command=self._export_issues).pack(side="right")

        self._progress = ttk.Progressbar(comp_lf, mode="indeterminate", length=400)
        self._progress.pack(fill="x", padx=8, pady=(2,4))

        # Column comparison tree
        tree_f = tk.Frame(comp_lf, bg="#1e1e2e")
        tree_f.pack(fill="x", padx=8, pady=(0,4))
        tree_f.columnconfigure(0, weight=1)

        cols = ("col_num","col_name","file_max","db_limit","status","sample")
        self._comp_tree = ttk.Treeview(tree_f, columns=cols, show="headings",
                                        selectmode="browse", height=8)
        for c, t, w in [("col_num","#",40),("col_name","File Column",180),("file_max","File Max Len",95),
                         ("db_limit","DB Limit",80),("status","Status / Match",160),("sample","Longest Sample Value",350)]:
            self._comp_tree.heading(c, text=t)
            self._comp_tree.column(c, width=w, stretch=(c=="sample"))
        self._comp_tree.tag_configure("ok",      background="#0d2010", foreground="#a6e3a1")
        self._comp_tree.tag_configure("over",    background="#2d0a0a", foreground="#f38ba8")
        self._comp_tree.tag_configure("warn",    background="#2d1f00", foreground="#f9e2af")
        self._comp_tree.tag_configure("numeric", background="#0d1a2d", foreground="#74c7ec")  # int/bit/date — no char limit
        self._comp_tree.tag_configure("no_match",background="#211a30", foreground="#cba6f7") # file col not in DB
        vsb = ttk.Scrollbar(tree_f, orient="vertical", command=self._comp_tree.yview)
        self._comp_tree.configure(yscrollcommand=vsb.set)
        self._comp_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # Color legend
        legend_f = tk.Frame(comp_lf, bg="#1e1e2e")
        legend_f.pack(fill="x", padx=8, pady=(0,6))
        for txt, bg, fg in [
            ("🔴 OVERFLOW — exceeds DB limit",       "#2d0a0a","#f38ba8"),
            ("🟡 Near limit (>80%)",                  "#2d1f00","#f9e2af"),
            ("🟢 OK — fits within DB limit",          "#0d2010","#a6e3a1"),
            ("🔵 Numeric/date — no char check",       "#0d1a2d","#74c7ec"),
            ("🟣 No DB column match found",           "#211a30","#cba6f7"),
        ]:
            tk.Label(legend_f, text=txt, bg=bg, fg=fg,
                     font=("Segoe UI",8), padx=6, pady=1,
                     relief="flat").pack(side="left", padx=(0,4))

        # ── Scan Results ──────────────────────────────────────────────────────
        res_lf = tk.LabelFrame(tab, text=" 3 · Truncation Scan Results ",
                                bg="#1e1e2e", fg="#f38ba8",
                                font=("Segoe UI",10,"bold"), bd=1, relief="groove")
        res_lf.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4,10))
        res_lf.columnconfigure(0, weight=1)
        res_lf.rowconfigure(1, weight=1)

        res_ctrl = tk.Frame(res_lf, bg="#1e1e2e")
        res_ctrl.grid(row=0, column=0, sticky="ew", padx=8, pady=(4,2))
        self._res_summary_var = tk.StringVar(value="No scan run yet")
        tk.Label(res_ctrl, textvariable=self._res_summary_var, bg="#1e1e2e",
                 fg="#a6adc8", font=("Segoe UI",10,"bold")).pack(side="left")

        res_f = tk.Frame(res_lf, bg="#1e1e2e")
        res_f.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0,8))
        res_f.rowconfigure(0, weight=1); res_f.columnconfigure(0, weight=1)

        rcols = ("row_num","col_name","actual_len","db_limit","over_by","preview")
        self._res_tree = ttk.Treeview(res_f, columns=rcols, show="headings", selectmode="browse")
        for c, t, w in [("row_num","Row #",65),("col_name","Column",160),
                         ("actual_len","Actual Len",85),("db_limit","DB Limit",80),
                         ("over_by","Over By",70),("preview","Value Preview",500)]:
            self._res_tree.heading(c, text=t)
            self._res_tree.column(c, width=w, stretch=(c=="preview"))
        self._res_tree.tag_configure("error", background="#2d0a0a", foreground="#f38ba8")
        self._res_tree.tag_configure("warn",  background="#2d1f00", foreground="#f9e2af")
        rvsb = ttk.Scrollbar(res_f, orient="vertical", command=self._res_tree.yview)
        rhsb = ttk.Scrollbar(res_f, orient="horizontal", command=self._res_tree.xview)
        self._res_tree.configure(yscrollcommand=rvsb.set, xscrollcommand=rhsb.set)
        self._res_tree.grid(row=0, column=0, sticky="nsew")
        rvsb.grid(row=0, column=1, sticky="ns")
        rhsb.grid(row=1, column=0, sticky="ew")

    def _browse_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("All supported","*.xlsx *.xls *.csv *.txt *.tsv *.pipe *.tab"),
                        ("Excel","*.xlsx *.xls"), ("Delimited","*.csv *.tsv *.txt *.pipe"),
                        ("All files","*.*")])
        if path:
            self._file_path_var.set(path)
            self._auto_analyze_file()

    def _get_file_opts(self):
        ft = self._ftype_var.get()
        custom = self._custom_delim.get()
        delim = custom if custom else self._delim_var.get() or ","
        opts = {"delimiter": delim, "sheet": self._sheet_var.get() or None,
                "has_header": self._hdr_var.get(), "encoding": self._enc_var.get()}
        if ft in ("pipe","tab"):
            opts["delimiter"] = "|" if ft == "pipe" else "\t"
            ft = "custom"
        return ft, opts

    def _auto_analyze_file(self):
        path = self._file_path_var.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showwarning("File Not Found", f"File not found:\n{path}"); return

        ft = detect_file_type(path)
        self._ftype_var.set(ft)

        if ft in ("xlsx","xls"):
            sheets = get_excel_sheets(path, ft)
            self._sheet_cb.configure(values=sheets)
            if sheets: self._sheet_var.set(sheets[0])
        else:
            # Auto-detect delimiter
            delim, dname, ncols, conf = auto_detect_delimiter(path, self._enc_var.get())
            self._delim_var.set(delim)
            self._delim_name_var.set(f"{dname}  ({conf}% consistent)")

        self._file_status_var.set("Analyzing columns…")
        self.update()

        ft2, opts = self._get_file_opts()
        self._file_path = path
        self._file_opts = opts

        def _run():
            headers, stats, err = get_column_stats(path, ft2, opts)
            self.after(0, lambda: self._show_column_stats(headers, stats, err))

        threading.Thread(target=_run, daemon=True).start()

    def _show_column_stats(self, headers, stats, err):
        if err:
            self._file_status_var.set(f"⚠ Error reading file: {err[:80]}"); return
        self._file_headers = headers
        self._file_stats   = stats

        row_est = max((s.get("total",0) for s in stats.values()), default=0)
        delim_txt = self._delim_name_var.get()

        # Build col_limits using fuzzy matching (handles RD_ prefix etc.)
        limits, matched_names = (match_file_to_schema(headers, self._db_schema, self._col_map_overrides)
                                  if self._db_schema else ({}, []))

        # Build reverse map: col_idx → matched DB col dict
        db_col_by_idx: dict = {}
        if self._db_schema:
            lookup_norm: dict = {}
            for col in self._db_schema:
                n = _norm_col(col["name"])
                lookup_norm.setdefault(n, col)
                for pfx in _ETL_STRIP:
                    if n.startswith(pfx) and len(n) > len(pfx):
                        lookup_norm.setdefault(n[len(pfx):], col)
            for idx, hdr in enumerate(headers):
                m = lookup_norm.get(_norm_col(hdr))
                if m:
                    db_col_by_idx[idx] = m

        match_count = len(db_col_by_idx)
        schema_note = (f"   DB matched: {match_count}/{len(headers)} columns"
                       if self._db_schema else "   (load DB schema in Tab 3 for comparison)")
        self._file_status_var.set(
            f"✓  {len(headers)} columns   ~{row_est:,} rows sampled   Delimiter: {delim_txt}{schema_note}")

        # Refresh comparison tree
        self._comp_tree.delete(*self._comp_tree.get_children())
        overflow_cols = []

        for idx, col in enumerate(headers):
            s = stats.get(idx, {})
            file_max = s.get("max_len", 0)
            sample   = (s.get("sample") or "")[:80]
            db_col   = db_col_by_idx.get(idx)

            if db_col:
                db_lim    = db_col["max_len"]
                db_name   = db_col["name"]
                if db_lim <= 0:
                    status, tag = f"numeric/date — skip", "numeric"
                elif file_max > db_lim:
                    over = file_max - db_lim
                    status, tag = f"⚠ OVERFLOW +{over} chars", "over"
                    overflow_cols.append(f"{col} (max={file_max}, limit={db_lim}, over={over})")
                elif file_max > db_lim * 0.8:
                    status, tag = f"⚠ Near limit ({file_max}/{db_lim})", "warn"
                else:
                    status, tag = f"✓ OK ({file_max}/{db_lim})", "ok"
            else:
                db_lim, db_name = "—", "—"
                status, tag = "no DB match", "no_match"

            self._comp_tree.insert("","end", tag=tag,
                values=(idx+1, col, file_max, db_lim, status, sample))

        # Show overflow summary banner
        if overflow_cols:
            self._scan_status_var.set(
                f"⚠ {len(overflow_cols)} column(s) exceed DB limits — run ⚡ Quick Compare for row detail!")
        elif match_count > 0:
            self._scan_status_var.set(
                f"✓ {match_count} columns matched — run ⚡ Quick Compare to find exact rows")

        self._update_report()

    # ── Scan execution ────────────────────────────────────────────────────────
    def _start_scan(self):
        path = self._file_path_var.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showwarning("No File","Enter a valid file path first."); return

        # Build col_limits from comp_tree or prompt user
        col_limits = self._get_col_limits_from_schema()
        if not col_limits:
            if self._db_schema:
                # Schema loaded but no columns matched — show debug info
                db_names  = [c["name"] for c in self._db_schema[:8]]
                file_hdrs = self._file_headers[:8] if self._file_headers else []
                messagebox.showwarning("No Column Matches",
                    "DB schema is loaded but no file columns matched DB columns.\n\n"
                    f"File headers (first 8): {file_hdrs}\n\n"
                    f"DB columns  (first 8): {db_names}\n\n"
                    "The app auto-strips prefixes like RD_, CTL_, ETL_.\n"
                    "Example: file 'Affiliate ID' matches DB 'RD_AffiliateID'.\n\n"
                    "If your DB uses a different prefix, the columns may need\n"
                    "manual mapping. Check table name is correct in Tab 3.")
            else:
                messagebox.showwarning("No DB Schema",
                    "No DB column limits available.\n\n"
                    "Go to Tab 3 → select a profile → Connect → enter table name → Fetch Schema.\n"
                    "Then click ⚡ Quick Compare.")
            return

        self._res_tree.delete(*self._res_tree.get_children())
        self._all_issues = []
        self._res_summary_var.set("Scanning…")
        ft, opts = self._get_file_opts()
        self._cancel_event.clear()
        self._result_q = queue.Queue()
        self._scan_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._progress.start(10)
        self._scan_status_var.set("Scanning file…")

        self._scan_thread = threading.Thread(
            target=scan_truncations,
            args=(path, ft, opts, col_limits, self._result_q, self._cancel_event),
            daemon=True)
        self._scan_thread.start()
        self.after(100, self._poll_results)

    def _quick_compare(self):
        """Use DB schema limits to scan the file — one-click full comparison."""
        if not self._db_schema:
            messagebox.showwarning("No DB Schema",
                "No database schema loaded.\n\nGo to Tab 3 (DB Inspector), connect to your DB,\n"
                "enter the table name, and click 'Fetch Schema'. Then come back here."); return
        path = self._file_path_var.get().strip()
        if not path:
            if self._ctx.get("file"):
                self._file_path_var.set(self._ctx["file"])
                path = self._ctx["file"]
        if not path or not os.path.exists(path):
            messagebox.showwarning("No File","Enter a valid file path first."); return

        if not self._file_headers:
            self._auto_analyze_file()
            self.after(2000, self._quick_compare)  # retry after analysis
            return

        self._start_scan()

    def _get_col_limits_from_schema(self):
        """Build {col_idx: max_len} from DB schema matched to file headers.
        Uses MHA-aware prefix-stripped fuzzy matching."""
        if not self._db_schema or not self._file_headers:
            return {}
        limits, matched = match_file_to_schema(self._file_headers, self._db_schema,
                                                self._col_map_overrides)
        if matched:
            self._scan_status_var.set(
                f"Matched {len(matched)}/{len(self._file_headers)} columns from DB schema")
        return limits

    def _stop_scan(self):
        self._cancel_event.set()
        self._scan_status_var.set("Stopping…")

    def _poll_results(self):
        try:
            while True:
                msg = self._result_q.get_nowait()
                kind = msg[0]
                if kind == "header":
                    self._file_headers = msg[1]
                elif kind == "issue":
                    _, row_num, col_idx, col_name, actual, limit, preview = msg
                    over = actual - limit
                    tag = "error" if over > 20 else "warn"
                    self._res_tree.insert("","end", tag=tag,
                        values=(row_num, col_name, actual, limit, f"+{over}", preview))
                    self._all_issues.append((row_num, col_name, actual, limit, over, preview))
                    if len(self._all_issues) % 25 == 0:
                        self._res_summary_var.set(f"Found {len(self._all_issues)} issues so far…")
                elif kind == "progress":
                    self._scan_status_var.set(f"Scanned {msg[1]:,} rows…")
                elif kind == "done":
                    self._scan_done(msg[1], msg[2]); return
                elif kind == "error":
                    self._scan_error(msg[1]); return
        except queue.Empty:
            pass
        if self._scan_thread and self._scan_thread.is_alive():
            self.after(100, self._poll_results)
        else:
            self._scan_done_ui()

    def _scan_done(self, total_rows, total_issues):
        self._scan_done_ui()

        # Find unmatched DB varchar cols — these were NOT scanned
        unmatched_warning = ""
        if self._db_schema:
            limits_checked, _ = match_file_to_schema(self._file_headers or [], self._db_schema,
                                                      self._col_map_overrides)
            unmatched_varchar = [
                c["name"] for c in self._db_schema
                if c.get("max_len", 0) > 0  # varchar
                and _norm_col(c["name"]) not in _RUNTIME_COLS
            ]
            # A varchar col is checked if its DB max_len appears in limits_checked values
            # (approximate: check by name matching)
            checked_db_names = set()
            for col in self._db_schema:
                db_n = _norm_col(col["name"])
                for pfx in [""] + _ETL_STRIP:
                    stripped = db_n[len(pfx):] if pfx and db_n.startswith(pfx) and len(db_n)>len(pfx) else db_n
                    for idx in limits_checked:
                        if _norm_col(self._file_headers[idx]) == stripped:
                            checked_db_names.add(col["name"]); break
            actually_unmatched = [n for n in unmatched_varchar if n not in checked_db_names]
            if actually_unmatched:
                unmatched_warning = (f"  ⚠ {len(actually_unmatched)} varchar column(s) NOT checked "
                                     f"(no file match): {', '.join(actually_unmatched[:4])}"
                                     + (" …" if len(actually_unmatched)>4 else "")
                                     + " — use Column Mapping Override in Tab 3")

        if total_issues == 0:
            limits, _ = match_file_to_schema(self._file_headers or [], self._db_schema or [],
                                              self._col_map_overrides)
            checked = ", ".join(
                f"{self._file_headers[i]}(limit={v})"
                for i, v in sorted(limits.items())[:6]
            ) if limits else "no columns matched"
            if len(limits) > 6:
                checked += f" …+{len(limits)-6} more"
            self._res_summary_var.set(
                f"✅  No truncation issues found in {total_rows:,} rows!"
                + ("\n" + unmatched_warning if unmatched_warning else ""))
            self._scan_status_var.set(
                f"✅ Done — 0 issues in {len(limits)} checked columns: {checked}"
                + (unmatched_warning if unmatched_warning else ""))
        else:
            col_counts: dict = {}
            for _, col_name, actual, limit, over, _ in self._all_issues:
                if col_name not in col_counts:
                    col_counts[col_name] = {"count": 0, "max_over": 0}
                col_counts[col_name]["count"] += 1
                col_counts[col_name]["max_over"] = max(col_counts[col_name]["max_over"], over)
            breakdown = "  |  ".join(
                f"{c}: {v['count']} row(s), max +{v['max_over']} over"
                for c, v in sorted(col_counts.items(), key=lambda x: -x[1]["max_over"])[:4]
            )
            self._res_summary_var.set(
                f"⚠️  {total_issues} truncation issue(s) across {len(col_counts)} column(s) "
                f"in {total_rows:,} rows — see rows below"
                + ("\n" + unmatched_warning if unmatched_warning else ""))
            self._scan_status_var.set(f"⚠ {breakdown}"
                + (unmatched_warning if unmatched_warning else ""))
        self._update_report()


    def _scan_error(self, msg):
        self._scan_done_ui()
        self._res_summary_var.set(f"Error: {msg[:80]}")
        messagebox.showerror("Scan Error", msg)

    def _scan_done_ui(self):
        self._progress.stop()
        self._scan_btn.config(state="normal")
        self._stop_btn.config(state="disabled")

    def _export_issues(self):
        if not self._all_issues:
            messagebox.showinfo("No Results", "No issues to export."); return

        path = filedialog.asksaveasfilename(
            title="Export Truncation Report",
            defaultextension=".csv",
            filetypes=[
                ("CSV  (Excel-ready)",  "*.csv"),
                ("Excel Workbook",      "*.xlsx"),
                ("Text Report",         "*.txt"),
                ("All files",           "*.*"),
            ])
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".xlsx":
                # ── Excel export ──────────────────────────────────────────────
                try:
                    import openpyxl
                    from openpyxl.styles import Font, PatternFill, Alignment
                except ImportError:
                    messagebox.showerror("Missing Package",
                        "openpyxl is required for Excel export.\nRun: pip install openpyxl")
                    return
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Truncation Issues"

                # Header row
                headers = ["Row #", "Column Name", "Actual Len", "DB Limit",
                           "Over By", "Value Preview"]
                hdr_fill = PatternFill("solid", fgColor="C0392B")
                hdr_font = Font(bold=True, color="FFFFFF")
                for ci, h in enumerate(headers, 1):
                    cell = ws.cell(row=1, column=ci, value=h)
                    cell.fill = hdr_fill
                    cell.font = hdr_font
                    cell.alignment = Alignment(horizontal="center")

                # Column widths
                ws.column_dimensions["A"].width = 8
                ws.column_dimensions["B"].width = 28
                ws.column_dimensions["C"].width = 12
                ws.column_dimensions["D"].width = 10
                ws.column_dimensions["E"].width = 10
                ws.column_dimensions["F"].width = 60

                # Data rows
                warn_fill  = PatternFill("solid", fgColor="2D1F00")
                error_fill = PatternFill("solid", fgColor="2D0A0A")
                warn_font  = Font(color="F9E2AF")
                error_font = Font(color="F38BA8")
                for ri, issue in enumerate(self._all_issues, 2):
                    row_num, col_name, actual, limit, over, preview = issue
                    ws.cell(row=ri, column=1, value=row_num)
                    ws.cell(row=ri, column=2, value=col_name)
                    ws.cell(row=ri, column=3, value=actual)
                    ws.cell(row=ri, column=4, value=limit)
                    ws.cell(row=ri, column=5, value=f"+{over}")
                    ws.cell(row=ri, column=6, value=preview[:500])
                    fill = error_fill if over > 20 else warn_fill
                    font = error_font if over > 20 else warn_font
                    for ci in range(1, 7):
                        ws.cell(row=ri, column=ci).fill = fill
                        ws.cell(row=ri, column=ci).font = font

                # Summary sheet
                ws2 = wb.create_sheet("Summary")
                ws2["A1"] = "Truncation Report Summary"
                ws2["A1"].font = Font(bold=True, size=14)
                ws2["A3"] = "File:"
                ws2["B3"] = self._file_path
                ws2["A4"] = "Table:"
                ws2["B4"] = self._db_table or "N/A"
                ws2["A5"] = "Total Issues:"
                ws2["B5"] = len(self._all_issues)
                ws2["A6"] = "Generated:"
                ws2["B6"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                col_counts = {}
                for _, col_name, _, _, _, _ in self._all_issues:
                    col_counts[col_name] = col_counts.get(col_name, 0) + 1
                ws2["A8"] = "Column"
                ws2["B8"] = "Issue Count"
                ws2["A8"].font = Font(bold=True)
                ws2["B8"].font = Font(bold=True)
                for ri, (col, cnt) in enumerate(sorted(col_counts.items(),
                                                        key=lambda x: -x[1]), 9):
                    ws2.cell(row=ri, column=1, value=col)
                    ws2.cell(row=ri, column=2, value=cnt)

                wb.save(path)

            elif ext == ".txt":
                # ── Text report ───────────────────────────────────────────────
                with open(path, "w", encoding="utf-8") as f:
                    f.write("=" * 70 + "\n")
                    f.write("  TALEND ETL DIAGNOSTIC AGENT — TRUNCATION REPORT\n")
                    f.write("=" * 70 + "\n")
                    f.write(f"  File    : {self._file_path or 'N/A'}\n")
                    f.write(f"  Table   : {self._db_table or 'N/A'}\n")
                    f.write(f"  Issues  : {len(self._all_issues)}\n")
                    f.write(f"  Created : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 70 + "\n\n")

                    col_counts = {}
                    for _, col_name, _, _, _, _ in self._all_issues:
                        col_counts[col_name] = col_counts.get(col_name, 0) + 1
                    f.write("COLUMN SUMMARY:\n")
                    for col, cnt in sorted(col_counts.items(), key=lambda x: -x[1]):
                        f.write(f"  {col:<35}  {cnt} issue(s)\n")
                    f.write("\n" + "-" * 70 + "\n")
                    f.write(f"  {'Row':<8} {'Column':<30} {'Actual':>8} {'Limit':>8} {'Over':>6}\n")
                    f.write("-" * 70 + "\n")
                    for row_num, col_name, actual, limit, over, preview in self._all_issues:
                        f.write(f"  {str(row_num):<8} {col_name:<30} {str(actual):>8}"
                                f" {str(limit):>8} {f'+{over}':>6}\n")
                        if preview:
                            f.write(f"    Value: {preview[:100]}"
                                    f"{'...' if len(preview) > 100 else ''}\n")

            else:
                # ── CSV export (default) ──────────────────────────────────────
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(["Row #", "Column", "Actual Len", "DB Limit",
                                "Over By", "Preview"])
                    for row_num, col_name, actual, limit, over, preview in self._all_issues:
                        w.writerow([row_num, col_name, actual, limit, f"+{over}", preview])

            messagebox.showinfo("✅ Exported",
                f"Saved {len(self._all_issues)} issue(s) to:\n{path}")
        except Exception as ex:
            messagebox.showerror("Export Error", str(ex))

    # ═══════════════════════════════════════════════════════════════════════════
    #  TAB 3 — DB INSPECTOR
    # ═══════════════════════════════════════════════════════════════════════════
    def _build_db_tab(self):
        tab = self._t_db
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)

        # ── Scrollable wrapper for entire DB tab ──────────────────────────────
        db_canvas = tk.Canvas(tab, bg="#1e1e2e", highlightthickness=0)
        db_vsb = ttk.Scrollbar(tab, orient="vertical", command=db_canvas.yview)
        db_canvas.configure(yscrollcommand=db_vsb.set)
        db_canvas.grid(row=0, column=0, sticky="nsew")
        db_vsb.grid(row=0, column=1, sticky="ns")
        inner = tk.Frame(db_canvas, bg="#1e1e2e")
        db_cw = db_canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: db_canvas.configure(
            scrollregion=db_canvas.bbox("all")))
        db_canvas.bind("<Configure>", lambda e: db_canvas.itemconfig(db_cw, width=e.width))
        def _db_scroll(event):
            db_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        db_canvas.bind("<MouseWheel>", _db_scroll)
        inner.bind("<MouseWheel>", _db_scroll)
        inner.columnconfigure(0, weight=1)

        # ── Saved Profiles ──
        prof_lf = tk.LabelFrame(inner, text=" ⭐ Saved MHA Profiles — Click to Load ",
                                 bg="#1e1e2e", fg="#a6e3a1",
                                 font=("Segoe UI",10,"bold"), bd=1, relief="groove")
        prof_lf.grid(row=0, column=0, sticky="ew", padx=12, pady=(10,2))

        prow = tk.Frame(prof_lf, bg="#1e1e2e")
        prow.pack(fill="x", padx=8, pady=6)
        tk.Label(prow, text="Profile:", bg="#1e1e2e", fg="#a6e3a1",
                 font=("Segoe UI",10,"bold")).pack(side="left", padx=(0,6))
        self._profile_var = tk.StringVar(value=list(DB_PRESETS.keys())[0])
        profile_cb = ttk.Combobox(prow, textvariable=self._profile_var,
                                   values=list(DB_PRESETS.keys()),
                                   state="readonly", width=46, font=("Segoe UI",10))
        profile_cb.pack(side="left", padx=(0,8))
        tk.Button(prow, text="✅ Load Profile", bg="#a6e3a1", fg="#1e1e2e",
                   font=("Segoe UI",10,"bold"), relief="flat", cursor="hand2",
                   padx=14, pady=5, command=self._load_profile).pack(side="left", padx=(0,8))
        tk.Label(prow, text="(Windows Auth = no password needed)",
                 bg="#1e1e2e", fg="#6c7086", font=("Segoe UI",9,"italic")).pack(side="left")

        # ── Connection Form ───────────────────────────────────────────────────
        conn_lf = tk.LabelFrame(inner, text=" 1 · Database Connection ",
                                 bg="#1e1e2e", fg="#89b4fa",
                                 font=("Segoe UI",10,"bold"), bd=1, relief="groove")
        conn_lf.grid(row=1, column=0, sticky="ew", padx=12, pady=(2,4))

        row0 = tk.Frame(conn_lf, bg="#1e1e2e")
        row0.pack(fill="x", padx=8, pady=4)
        def lbl(t, f=row0): return tk.Label(f, text=t, bg="#1e1e2e", fg="#a6adc8", font=("Segoe UI",9))
        def ent(var, w=18, f=row0): return tk.Entry(f, textvariable=var, bg="#181825", fg="#cdd6f4",
             insertbackground="#89b4fa", relief="flat", font=("Consolas",10), width=w)
        def cbx(var, vals, w=14, f=row0):
            return ttk.Combobox(f, textvariable=var, values=vals, state="readonly",
                                width=w, font=("Segoe UI",9))

        lbl("DB Type:").pack(side="left", padx=(0,4))
        self._db_type_var = tk.StringVar(value="SQL Server")
        db_type_cb = cbx(self._db_type_var, DB_TYPES, 12)
        db_type_cb.pack(side="left", padx=(0,14))
        db_type_cb.bind("<<ComboboxSelected>>", self._on_db_type_change)

        lbl("Host / Server:").pack(side="left", padx=(0,4))
        self._db_host_var = tk.StringVar()
        ent(self._db_host_var, 22).pack(side="left", padx=(0,8))

        lbl("Port:").pack(side="left", padx=(0,4))
        self._db_port_var = tk.StringVar(value="1433")
        ent(self._db_port_var, 6).pack(side="left", padx=(0,8))

        lbl("Database:").pack(side="left", padx=(0,4))
        self._db_name_var = tk.StringVar()
        ent(self._db_name_var, 18).pack(side="left", padx=(0,8))

        lbl("Schema:").pack(side="left", padx=(0,4))
        self._db_schema_var = tk.StringVar(value="dbo")
        ent(self._db_schema_var, 10).pack(side="left", padx=(0,8))

        row1 = tk.Frame(conn_lf, bg="#1e1e2e")
        row1.pack(fill="x", padx=8, pady=(0,6))
        def lbl1(t): return tk.Label(row1, text=t, bg="#1e1e2e", fg="#a6adc8", font=("Segoe UI",9))
        def ent1(var, w=22, show=""):
            return tk.Entry(row1, textvariable=var, bg="#181825", fg="#cdd6f4",
                            insertbackground="#89b4fa", relief="flat", font=("Consolas",10),
                            width=w, show=show)
        lbl1("User:").pack(side="left", padx=(0,4))
        self._db_user_var = tk.StringVar()
        ent1(self._db_user_var).pack(side="left", padx=(0,8))
        lbl1("Password:").pack(side="left", padx=(0,4))
        self._db_pwd_var = tk.StringVar()
        ent1(self._db_pwd_var, show="●").pack(side="left", padx=(0,8))

        # Extra (SQLite path / Oracle DSN)
        self._db_extra_lbl = tk.Label(row1, text="SQLite File/Oracle DSN:", bg="#1e1e2e",
                                       fg="#a6adc8", font=("Segoe UI",9))
        self._db_extra_lbl.pack(side="left", padx=(8,4))
        self._db_extra_var = tk.StringVar()
        self._db_extra_entry = ent1(self._db_extra_var, 34)
        self._db_extra_entry.pack(side="left", padx=(0,4))

        # Driver status badge
        self._drv_status_var = tk.StringVar(value="")
        tk.Label(row1, textvariable=self._drv_status_var, bg="#1e1e2e",
                 fg="#a6e3a1", font=("Segoe UI",9)).pack(side="left", padx=8)

        btn_row = tk.Frame(conn_lf, bg="#1e1e2e")
        btn_row.pack(fill="x", padx=8, pady=(0,8))
        tk.Button(btn_row, text="🔌 Test Connection", bg="#89b4fa", fg="#1e1e2e",
                   font=("Segoe UI",10,"bold"), relief="flat", cursor="hand2", padx=14, pady=6,
                   command=self._test_connection).pack(side="left", padx=(0,8))
        tk.Button(btn_row, text="🔌 Connect", bg="#45475a", fg="#cdd6f4",
                   font=("Segoe UI",10), relief="flat", cursor="hand2", padx=12, pady=6,
                   command=self._do_connect).pack(side="left", padx=(0,8))

        self._conn_status_var = tk.StringVar(value="Not connected")
        tk.Label(btn_row, textvariable=self._conn_status_var, bg="#1e1e2e",
                 fg="#f38ba8", font=("Segoe UI",10,"bold")).pack(side="left", padx=8)
        tk.Button(btn_row, text="🔌 Disconnect", bg="#45475a", fg="#f38ba8",
                   font=("Segoe UI",9), relief="flat", cursor="hand2", padx=8, pady=6,
                   command=self._disconnect).pack(side="right")

        # ── Table Inspector ───────────────────────────────────────────────────
        tbl_lf = tk.LabelFrame(inner, text=" 2 · Table Schema Inspector ",
                                bg="#1e1e2e", fg="#f9e2af",
                                font=("Segoe UI",10,"bold"), bd=1, relief="groove")
        tbl_lf.grid(row=2, column=0, sticky="ew", padx=12, pady=4)

        tbl_ctrl = tk.Frame(tbl_lf, bg="#1e1e2e")
        tbl_ctrl.pack(fill="x", padx=8, pady=(6,4))

        tk.Label(tbl_ctrl, text="Table Name:", bg="#1e1e2e", fg="#a6adc8",
                 font=("Segoe UI",10)).pack(side="left", padx=(0,6))
        self._db_table_var = tk.StringVar()
        self._table_entry = tk.Entry(tbl_ctrl, textvariable=self._db_table_var,
                                      bg="#181825", fg="#cdd6f4", insertbackground="#89b4fa",
                                      relief="flat", font=("Consolas",11,"bold"), width=28)
        self._table_entry.pack(side="left", padx=(0,8))

        tk.Button(tbl_ctrl, text="📋 Fetch Schema", bg="#f9e2af", fg="#1e1e2e",
                   font=("Segoe UI",10,"bold"), relief="flat", cursor="hand2", padx=14, pady=6,
                   command=self._fetch_schema).pack(side="left", padx=(0,8))
        tk.Button(tbl_ctrl, text="📄 List Tables", bg="#313244", fg="#89dceb",
                   font=("Segoe UI",10), relief="flat", cursor="hand2", padx=10, pady=6,
                   command=self._list_tables).pack(side="left", padx=(0,8))
        tk.Button(tbl_ctrl, text="→ Send to File Scanner", bg="#313244", fg="#a6e3a1",
                   font=("Segoe UI",10), relief="flat", cursor="hand2", padx=10, pady=6,
                   command=self._send_schema_to_scanner).pack(side="left", padx=(0,4))
        tk.Button(tbl_ctrl, text="🔗 Fix Unmatched Columns", bg="#2d1a00", fg="#fab387",
                   font=("Segoe UI",10,"bold"), relief="flat", cursor="hand2", padx=10, pady=6,
                   command=self._open_mapping_dialog).pack(side="left", padx=(8,4))

        self._schema_status_var = tk.StringVar(value="No schema loaded")
        tk.Label(tbl_ctrl, textvariable=self._schema_status_var, bg="#1e1e2e",
                 fg="#a6adc8", font=("Segoe UI",9)).pack(side="left", padx=8)

        # Schema treeview
        schema_f = tk.Frame(tbl_lf, bg="#1e1e2e")
        schema_f.pack(fill="both", expand=True, padx=8, pady=(2,8))
        schema_f.rowconfigure(0, weight=1); schema_f.columnconfigure(0, weight=1)

        scols = ("s_num","s_name","s_type","s_max","s_null","s_file_max","s_overlap")
        self._schema_tree = ttk.Treeview(schema_f, columns=scols, show="headings",
                                          selectmode="browse", height=10)
        for c, t, w in [("s_num","#",45),("s_name","Column Name",200),
                         ("s_type","Data Type",120),("s_max","DB Max Len",90),
                         ("s_null","Nullable",80),("s_file_max","File Max Len",100),
                         ("s_overlap","Status",130)]:
            self._schema_tree.heading(c, text=t)
            self._schema_tree.column(c, width=w, stretch=(c=="s_name"))
        self._schema_tree.tag_configure("ok",      background="#0d2010", foreground="#a6e3a1")
        self._schema_tree.tag_configure("over",    background="#2d0a0a", foreground="#f38ba8")
        self._schema_tree.tag_configure("warn",    background="#2d1f00", foreground="#f9e2af")
        self._schema_tree.tag_configure("none",    background="#0d1a2d", foreground="#74c7ec")   # numeric/no char limit
        self._schema_tree.tag_configure("no_match",background="#211a30", foreground="#cba6f7")  # not in file
        self._schema_tree.tag_configure("manual",  background="#2d1a00", foreground="#fab387")  # manually edited length
        svsb = ttk.Scrollbar(schema_f, orient="vertical",   command=self._schema_tree.yview)
        shsb = ttk.Scrollbar(schema_f, orient="horizontal", command=self._schema_tree.xview)
        self._schema_tree.configure(yscrollcommand=svsb.set, xscrollcommand=shsb.set)
        self._schema_tree.grid(row=0, column=0, sticky="nsew")
        svsb.grid(row=0, column=1, sticky="ns")
        shsb.grid(row=1, column=0, sticky="ew")

        # Hint label + double-click to edit DB length
        tk.Label(tbl_lf, text="💡 Double-click any row to manually set DB column length",
                 bg="#1e1e2e", fg="#6c7086", font=("Segoe UI",8,"italic")).pack(anchor="w", padx=12)
        self._schema_tree.bind("<Double-1>",    self._edit_db_length)
        self._schema_tree.bind("<Return>",       self._edit_db_length)
        # Right-click context menu
        self._schema_ctx = tk.Menu(self, tearoff=0, bg="#313244", fg="#cdd6f4",
                                    activebackground="#89b4fa", activeforeground="#1e1e2e",
                                    font=("Segoe UI",10))
        self._schema_ctx.add_command(label="✏ Edit DB Column Length",
                                      command=self._edit_db_length)
        self._schema_ctx.add_command(label="🔄 Reset to Original Length",
                                      command=self._reset_db_length)
        self._schema_ctx.add_separator()
        self._schema_ctx.add_command(label="🗑 Clear ALL Manual Lengths",
                                      command=self._clear_db_length_overrides)
        self._schema_tree.bind("<Button-3>", self._schema_ctx_popup)

        # ── Column Mapping Override ───────────────────────────────────────────
        map_lf = tk.LabelFrame(inner, text=" 3 · Column Mapping Override — fix 'no file data' columns ",
                                bg="#1e1e2e", fg="#cba6f7",
                                font=("Segoe UI",10,"bold"), bd=1, relief="groove")
        map_lf.grid(row=3, column=0, sticky="ew", padx=12, pady=(4,14))
        map_lf.columnconfigure(0, weight=1)

        tk.Label(map_lf,
                 text=("If any DB varchar column shows 'no file data', select the matching "
                       "file column here and click Apply. Only needed when auto-match fails."),
                 bg="#1e1e2e", fg="#a6adc8", font=("Segoe UI",9),
                 wraplength=900, justify="left").grid(row=0, column=0, sticky="w", padx=8, pady=(4,2))

        # Scrollable inner frame
        map_outer = tk.Frame(map_lf, bg="#181825", relief="flat")
        map_outer.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0,4))
        map_outer.columnconfigure(0, weight=1); map_outer.rowconfigure(0, weight=1)
        self._map_canvas = tk.Canvas(map_outer, bg="#181825", highlightthickness=0, height=110)
        map_vsb = ttk.Scrollbar(map_outer, orient="vertical", command=self._map_canvas.yview)
        self._map_canvas.configure(yscrollcommand=map_vsb.set)
        self._map_canvas.grid(row=0, column=0, sticky="nsew")
        map_vsb.grid(row=0, column=1, sticky="ns")
        self._map_inner = tk.Frame(self._map_canvas, bg="#181825")
        self._map_canvas_win = self._map_canvas.create_window((0,0), window=self._map_inner, anchor="nw")
        self._map_inner.bind("<Configure>", lambda e: self._map_canvas.configure(
            scrollregion=self._map_canvas.bbox("all")))
        self._map_canvas.bind("<Configure>", lambda e: self._map_canvas.itemconfig(
            self._map_canvas_win, width=e.width))
        # Placeholder text
        self._map_placeholder = tk.Label(self._map_inner,
            text="Fetch a table schema first. Unmatched varchar columns will appear here.",
            bg="#181825", fg="#585b70", font=("Segoe UI",9,"italic"), pady=10)
        self._map_placeholder.pack()

        # Apply row
        map_btn_row = tk.Frame(map_lf, bg="#1e1e2e")
        map_btn_row.grid(row=2, column=0, sticky="ew", padx=8, pady=(2,6))
        tk.Button(map_btn_row, text="✅ Apply Manual Mappings", bg="#cba6f7", fg="#1e1e2e",
                   font=("Segoe UI",10,"bold"), relief="flat", cursor="hand2", padx=14, pady=5,
                   command=self._apply_col_overrides).pack(side="left", padx=(0,8))
        tk.Button(map_btn_row, text="🗑 Clear All Overrides", bg="#45475a", fg="#f38ba8",
                   font=("Segoe UI",9), relief="flat", cursor="hand2", padx=10, pady=5,
                   command=self._clear_col_overrides).pack(side="left", padx=(0,8))
        self._map_status_var = tk.StringVar(value="")
        tk.Label(map_btn_row, textvariable=self._map_status_var,
                 bg="#1e1e2e", fg="#a6e3a1", font=("Segoe UI",9)).pack(side="left", padx=8)

        # Bind mousewheel to ALL widgets inside the DB tab scroll canvas
        def _bind_scroll(widget):
            widget.bind("<MouseWheel>", _db_scroll)
            for child in widget.winfo_children():
                _bind_scroll(child)
        self.after(100, lambda: _bind_scroll(inner))

        # Set initial driver status immediately on app open
        self.after(50, self._on_db_type_change)

    def _load_profile(self):
        """Populate connection fields from a saved MHA DB profile."""
        name = self._profile_var.get()
        p = DB_PRESETS.get(name, {})
        if not p:
            return
        self._db_type_var.set(p.get("type", "SQL Server"))
        self._db_host_var.set(p.get("host", ""))
        self._db_port_var.set(p.get("port", "1433"))
        self._db_name_var.set(p.get("db", ""))
        self._db_schema_var.set(p.get("schema", "dbo"))
        self._db_user_var.set(p.get("user", ""))
        self._db_pwd_var.set(p.get("pwd", ""))
        self._db_extra_var.set("")
        self._on_db_type_change()
        note = (" — enter password then click Connect" if p.get("user")
                else " — Windows Auth (no password needed)")
        self._conn_status_var.set(f"Profile loaded: {p['host']} / {p['db']}{note}")

    # ── DB Length Override helpers ─────────────────────────────────────────────
    def _schema_ctx_popup(self, event):
        """Show right-click context menu on schema tree."""
        row = self._schema_tree.identify_row(event.y)
        if row:
            self._schema_tree.selection_set(row)
            self._schema_ctx.tk_popup(event.x_root, event.y_root)

    def _edit_db_length(self, event=None):
        """Open a dialog to manually set DB column length for the selected row."""
        sel = self._schema_tree.selection()
        if not sel:
            return
        item = sel[0]
        vals = self._schema_tree.item(item, "values")
        if not vals:
            return
        col_name = vals[1]   # Column Name
        cur_len  = vals[3]   # DB Max Len

        # Build dialog
        dlg = tk.Toplevel(self)
        dlg.title(f"Edit DB Length — {col_name}")
        dlg.configure(bg="#1e1e2e")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.geometry("400x170")

        tk.Label(dlg, text=f"Column:  {col_name}", bg="#1e1e2e", fg="#89b4fa",
                 font=("Segoe UI",11,"bold"), anchor="w").pack(padx=20, pady=(16,2), fill="x")
        tk.Label(dlg, text=f"Current DB Max Len:  {cur_len}",
                 bg="#1e1e2e", fg="#a6adc8", font=("Segoe UI",9), anchor="w").pack(padx=20, fill="x")

        row_f = tk.Frame(dlg, bg="#1e1e2e")
        row_f.pack(padx=20, pady=(10,4), fill="x")
        tk.Label(row_f, text="New DB Max Len:", bg="#1e1e2e", fg="#cdd6f4",
                 font=("Segoe UI",10)).pack(side="left", padx=(0,8))
        len_var = tk.StringVar(value=str(cur_len) if str(cur_len).isdigit() else "")
        len_entry = tk.Entry(row_f, textvariable=len_var, bg="#181825", fg="#cdd6f4",
                             insertbackground="#89b4fa", font=("Consolas",12,"bold"),
                             width=10, relief="flat")
        len_entry.pack(side="left")
        len_entry.select_range(0, "end")
        len_entry.focus_set()

        err_var = tk.StringVar()
        tk.Label(dlg, textvariable=err_var, bg="#1e1e2e", fg="#f38ba8",
                 font=("Segoe UI",9)).pack(padx=20)

        def _apply():
            val = len_var.get().strip()
            if not val.isdigit() or int(val) <= 0:
                err_var.set("Enter a positive integer (e.g. 50)"); return
            new_len = int(val)
            self._db_len_overrides[col_name] = new_len
            # Update db_schema in-place; preserve original for reset
            for col in self._db_schema:
                if col["name"] == col_name:
                    if not col.get("_manual"):
                        col["_orig_len"] = col.get("max_len", 0)  # save original
                    col["max_len"] = new_len
                    col["_manual"] = True
                    break
            dlg.destroy()
            self._refresh_schema_view(self._db_schema)
            if self._file_headers and self._file_stats:
                self._show_column_stats(self._file_headers, self._file_stats, None)
            self._schema_status_var.set(
                f"✏ Manual length set: {col_name} = {new_len}  "
                f"(orange rows = manually edited)")

        tk.Button(dlg, text="✅ Apply", bg="#a6e3a1", fg="#1e1e2e",
                   font=("Segoe UI",10,"bold"), relief="flat", cursor="hand2",
                   padx=16, pady=6, command=_apply).pack(pady=(2,6))
        len_entry.bind("<Return>", lambda _: _apply())
        dlg.bind("<Escape>", lambda _: dlg.destroy())

    def _reset_db_length(self, event=None):
        """Reset the selected row's DB length to the original fetched value."""
        sel = self._schema_tree.selection()
        if not sel:
            return
        vals = self._schema_tree.item(sel[0], "values")
        col_name = vals[1]
        if col_name in self._db_len_overrides:
            del self._db_len_overrides[col_name]
        # Remove _manual flag and restore original length if we stored it
        for col in self._db_schema:
            if col["name"] == col_name and col.get("_manual"):
                col.pop("_manual", None)
                # Revert to stored original if available
                if "_orig_len" in col:
                    col["max_len"] = col["_orig_len"]
                break
        self._refresh_schema_view(self._db_schema)
        if self._file_headers and self._file_stats:
            self._show_column_stats(self._file_headers, self._file_stats, None)

    def _clear_db_length_overrides(self):
        """Remove ALL manual DB length edits."""
        self._db_len_overrides.clear()
        for col in self._db_schema:
            if col.get("_manual"):
                col.pop("_manual", None)
                if "_orig_len" in col:
                    col["max_len"] = col["_orig_len"]
        self._refresh_schema_view(self._db_schema)
        if self._file_headers and self._file_stats:
            self._show_column_stats(self._file_headers, self._file_stats, None)
        self._schema_status_var.set("All manual length edits cleared.")


        """Fill the mapping panel with unmatched DB varchar columns for manual assignment."""
        for w in self._map_inner.winfo_children():
            w.destroy()
        self._map_vars.clear()

        file_choices = ["(skip)"] + list(self._file_headers or [])
        if not unmatched_cols:
            tk.Label(self._map_inner,
                     text="✅ All DB varchar columns auto-matched to file columns!",
                     bg="#181825", fg="#a6e3a1", font=("Segoe UI",9), pady=8).pack()
            self._map_status_var.set("")
            return

        # Header row
        hdr = tk.Frame(self._map_inner, bg="#313244")
        hdr.pack(fill="x", padx=2, pady=(2,0))
        for txt, w in [("DB Column Name",200),("DB Limit",70),("→",24),("Map to File Column →",280),("Hint",200)]:
            tk.Label(hdr, text=txt, bg="#313244", fg="#89b4fa", font=("Segoe UI",8,"bold"),
                     width=w//7, anchor="w", padx=4).pack(side="left", padx=1)

        for col in unmatched_cols:
            db_norm = _norm_col(col["name"])
            # Suggest closest-matching file col by substring
            hint = ""
            if self._file_headers:
                stripped = db_norm
                for pfx in _ETL_STRIP:
                    if stripped.startswith(pfx) and len(stripped) > len(pfx):
                        stripped = stripped[len(pfx):]; break
                candidates = [(h, _norm_col(h)) for h in self._file_headers]
                scored = [(h, hn) for h,hn in candidates if stripped in hn or hn in stripped]
                hint = scored[0][0] if scored else ""

            row_f = tk.Frame(self._map_inner, bg="#181825")
            row_f.pack(fill="x", padx=2, pady=1)
            tk.Label(row_f, text=col["name"], bg="#211a30", fg="#cba6f7",
                     font=("Consolas",9), width=28, anchor="w", padx=4).pack(side="left", padx=1)
            tk.Label(row_f, text=str(col["max_len"]), bg="#211a30", fg="#cba6f7",
                     font=("Consolas",9), width=8, anchor="center").pack(side="left", padx=1)
            tk.Label(row_f, text="→", bg="#181825", fg="#6c7086",
                     font=("Segoe UI",10)).pack(side="left", padx=4)

            var = tk.StringVar()
            # Pre-populate from existing overrides first, then hint
            if db_norm in self._col_map_overrides:
                idx = self._col_map_overrides[db_norm]
                if 0 <= idx < len(file_choices)-1:
                    var.set(file_choices[idx+1])
            elif hint:
                var.set(hint)
            else:
                var.set("(skip)")

            cb = ttk.Combobox(row_f, textvariable=var, values=file_choices,
                              state="readonly", width=32, font=("Segoe UI",9))
            cb.pack(side="left", padx=4)
            self._map_vars[db_norm] = var

            status_txt = "🔧 manual" if db_norm in self._col_map_overrides else ("💡 suggested" if hint else "⚠ no match")
            status_fg  = "#a6e3a1"  if db_norm in self._col_map_overrides else ("#f9e2af" if hint else "#f38ba8")
            tk.Label(row_f, text=status_txt, bg="#181825", fg=status_fg,
                     font=("Segoe UI",9)).pack(side="left", padx=8)

        n = len(unmatched_cols)
        self._map_status_var.set(
            f"⚠ {n} column(s) need manual mapping — select file columns then click Apply")

    def _populate_mapping_panel(self, unmatched_cols: list):
        """Fill the mapping panel with unmatched DB varchar columns for manual assignment."""
        for w in self._map_inner.winfo_children():
            w.destroy()
        self._map_vars.clear()

        file_choices = ["(skip)"] + list(self._file_headers or [])
        if not unmatched_cols:
            tk.Label(self._map_inner,
                     text="✅ All DB varchar columns auto-matched to file columns!",
                     bg="#181825", fg="#a6e3a1", font=("Segoe UI",9), pady=8).pack()
            self._map_status_var.set("")
            return

        # Header
        hdr = tk.Frame(self._map_inner, bg="#313244")
        hdr.pack(fill="x", padx=2, pady=(2,0))
        for txt, w in [("DB Column Name",200),("DB Limit",70),("→",24),("Map to File Column →",280),("Hint",200)]:
            tk.Label(hdr, text=txt, bg="#313244", fg="#89b4fa", font=("Segoe UI",8,"bold"),
                     width=w//7, anchor="w", padx=4).pack(side="left", padx=1)

        for col in unmatched_cols:
            db_norm = _norm_col(col["name"])
            hint = ""
            if self._file_headers:
                stripped = db_norm
                for pfx in _ETL_STRIP:
                    if stripped.startswith(pfx) and len(stripped) > len(pfx):
                        stripped = stripped[len(pfx):]; break
                candidates = [(h, _norm_col(h)) for h in self._file_headers]
                scored = [(h, hn) for h, hn in candidates if stripped in hn or hn in stripped]
                hint = scored[0][0] if scored else ""

            row_f = tk.Frame(self._map_inner, bg="#181825")
            row_f.pack(fill="x", padx=2, pady=1)
            tk.Label(row_f, text=col["name"], bg="#211a30", fg="#cba6f7",
                     font=("Consolas",9), width=28, anchor="w", padx=4).pack(side="left", padx=1)
            tk.Label(row_f, text=str(col["max_len"]), bg="#211a30", fg="#cba6f7",
                     font=("Consolas",9), width=8, anchor="center").pack(side="left", padx=1)
            tk.Label(row_f, text="→", bg="#181825", fg="#6c7086",
                     font=("Segoe UI",10)).pack(side="left", padx=4)

            var = tk.StringVar()
            if db_norm in self._col_map_overrides:
                idx = self._col_map_overrides[db_norm]
                if 0 <= idx < len(file_choices)-1:
                    var.set(file_choices[idx+1])
            elif hint:
                var.set(hint)
            else:
                var.set("(skip)")

            cb = ttk.Combobox(row_f, textvariable=var, values=file_choices,
                              state="readonly", width=32, font=("Segoe UI",9))
            cb.pack(side="left", padx=4)
            self._map_vars[db_norm] = var

            status_txt = "🔧 manual" if db_norm in self._col_map_overrides else ("💡 suggested" if hint else "⚠ no match")
            status_fg  = "#a6e3a1"  if db_norm in self._col_map_overrides else ("#f9e2af" if hint else "#f38ba8")
            tk.Label(row_f, text=status_txt, bg="#181825", fg=status_fg,
                     font=("Segoe UI",9)).pack(side="left", padx=8)

        self._map_status_var.set(
            f"⚠ {len(unmatched_cols)} column(s) need manual mapping — or use '🔗 Fix Unmatched Columns' button above")

    def _apply_col_overrides(self):
        """Save dropdown selections to _col_map_overrides and refresh views."""
        if not self._map_vars:
            self._map_status_var.set("No mappings to apply — fetch schema first."); return
        count = 0
        for db_norm, var in self._map_vars.items():
            sel = var.get()
            if sel and sel != "(skip)" and self._file_headers and sel in self._file_headers:
                self._col_map_overrides[db_norm] = self._file_headers.index(sel)
                count += 1
            elif sel == "(skip)" and db_norm in self._col_map_overrides:
                del self._col_map_overrides[db_norm]
        self._map_status_var.set(f"✅ {count} manual override(s) active — schema + scanner refreshed")
        # Refresh both views
        if self._db_schema:
            self._refresh_schema_view(self._db_schema)
        if self._file_headers and self._file_stats:
            self._show_column_stats(self._file_headers, self._file_stats, None)

    def _clear_col_overrides(self):
        """Remove all manual mappings and refresh."""
        self._col_map_overrides.clear()
        self._map_status_var.set("All manual overrides cleared.")
        if self._db_schema:
            self._refresh_schema_view(self._db_schema)
        if self._file_headers and self._file_stats:
            self._show_column_stats(self._file_headers, self._file_stats, None)

    def _refresh_schema_view(self, cols: list):
        """Re-render the schema treeview and mapping panel without querying the DB."""
        file_max_by_norm: dict = {}
        if self._file_headers and self._file_stats:
            for idx, hdr in enumerate(self._file_headers):
                fstats = self._file_stats.get(idx, {})
                if fstats and "max_len" in fstats:
                    file_max_by_norm[_norm_col(hdr)] = fstats["max_len"]

        # Also inject manual-override file cols into file_max_by_norm keyed by db_norm
        # so the display shows the mapped file data correctly
        override_norm_to_fmax: dict = {}
        for db_norm, file_idx in self._col_map_overrides.items():
            if 0 <= file_idx < len(self._file_headers or []):
                fstats = self._file_stats.get(file_idx, {})
                if fstats and "max_len" in fstats:
                    override_norm_to_fmax[db_norm] = fstats["max_len"]

        self._schema_tree.delete(*self._schema_tree.get_children())
        unmatched_varchar = []
        for i, col in enumerate(cols):
            db_norm = _norm_col(col["name"])
            # Try direct match, then ETL-prefix-stripped match
            fmax = file_max_by_norm.get(db_norm)
            if fmax is None:
                for pfx in _ETL_STRIP:
                    if db_norm.startswith(pfx) and len(db_norm) > len(pfx):
                        fmax = file_max_by_norm.get(db_norm[len(pfx):])
                        if fmax is not None:
                            break
            # Then manual override
            if fmax is None and db_norm in override_norm_to_fmax:
                fmax = override_norm_to_fmax[db_norm]

            db_lim = col["max_len"]
            is_manual = col.get("_manual", False)
            if db_lim <= 0:
                status, tag = "numeric/date", "none"
            elif fmax is not None and isinstance(fmax, int):
                if fmax > db_lim:
                    status, tag = (f"⚠ OVERFLOW +{fmax-db_lim} chars" +
                                   (" ✏" if is_manual else ""), "over")
                elif fmax > db_lim * 0.8:
                    status, tag = (f"⚠ Near limit ({fmax}/{db_lim})" +
                                   (" ✏" if is_manual else ""), "warn")
                else:
                    status, tag = (f"✓ OK ({fmax}/{db_lim})" +
                                   (" ✏" if is_manual else ""), "ok" if not is_manual else "manual")
            else:
                status, tag = ("no file data" + (" ✏" if is_manual else ""),
                               "manual" if is_manual else "no_match")
                if db_lim > 0:
                    unmatched_varchar.append(col)
            db_lim_display = (f"{col['max_len']} ✏" if is_manual else col["max_len"]) or "—"
            self._schema_tree.insert("","end", tag=tag,
                values=(i+1, col["name"], col["type"],
                        db_lim_display, col["nullable"],
                        fmax if fmax is not None else "—", status))

        self._populate_mapping_panel(unmatched_varchar)

        # If there are unmatched varchar cols AND a file is loaded, prompt user to map them
        if unmatched_varchar and self._file_headers:
            self.after(200, lambda: self._open_mapping_dialog(unmatched_varchar))

    def _open_mapping_dialog(self, unmatched_cols: list = None):
        """Popup dialog to manually map unmatched DB varchar cols to file columns."""
        if unmatched_cols is None:
            # Rebuild list from current schema
            unmatched_cols = [c for c in self._db_schema
                              if c.get("max_len", 0) > 0
                              and _norm_col(c["name"]) not in _RUNTIME_COLS
                              and self._get_fmax_for_col(c) is None]
        if not unmatched_cols:
            messagebox.showinfo("All Matched",
                "All DB varchar columns are matched to file columns!"); return
        if not self._file_headers:
            messagebox.showwarning("No File Loaded",
                "Load a file in Tab 2 first, then come back and fetch the schema."); return

        dlg = tk.Toplevel(self)
        dlg.title(f"Column Mapping — {len(unmatched_cols)} unmatched DB varchar column(s)")
        dlg.configure(bg="#1e1e2e")
        dlg.geometry("820x520")
        dlg.grab_set()
        dlg.resizable(True, True)

        # Header
        hdr_f = tk.Frame(dlg, bg="#2d1a00")
        hdr_f.pack(fill="x")
        tk.Label(hdr_f,
                 text=f"⚠  {len(unmatched_cols)} DB varchar column(s) could not be auto-matched to any file column.",
                 bg="#2d1a00", fg="#fab387", font=("Segoe UI",10,"bold"), pady=6).pack(side="left", padx=12)

        tk.Label(dlg,
                 text="Select which file column corresponds to each DB column. Use the sample values to identify the correct one.",
                 bg="#1e1e2e", fg="#a6adc8", font=("Segoe UI",9), pady=4).pack(fill="x", padx=12)

        # File column choices with sample data
        file_choices = ["(skip — not in file)"]
        for idx, hdr in enumerate(self._file_headers):
            sample = ""
            if self._file_stats:
                s = self._file_stats.get(idx, {})
                sample = s.get("sample", "") or ""
                if sample:
                    sample = f'  e.g. "{sample[:30]}"'
            mlen = (self._file_stats.get(idx, {}) or {}).get("max_len", 0)
            file_choices.append(f"{hdr}  [max={mlen}{sample}]")

        # Scrollable mapping area
        canvas = tk.Canvas(dlg, bg="#181825", highlightthickness=0)
        vsb   = ttk.Scrollbar(dlg, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        inner = tk.Frame(canvas, bg="#181825")
        win_id = canvas.create_window((0,0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.pack(side="left", fill="both", expand=True, padx=(8,0), pady=8)
        vsb.pack(side="right", fill="y", pady=8, padx=(0,4))

        # Column header row
        hr = tk.Frame(inner, bg="#313244")
        hr.pack(fill="x", padx=4, pady=(4,2))
        for txt, w in [("DB Column (varchar)", 18), ("DB Limit", 8), ("Map to File Column  (shows max length + sample)", 55)]:
            tk.Label(hr, text=txt, bg="#313244", fg="#89b4fa",
                     font=("Segoe UI",9,"bold"), width=w, anchor="w", padx=6).pack(side="left")

        map_vars: dict = {}
        for col in unmatched_cols:
            db_norm = _norm_col(col["name"])
            row_f = tk.Frame(inner, bg="#181825")
            row_f.pack(fill="x", padx=4, pady=2)

            tk.Label(row_f, text=col["name"], bg="#211a30", fg="#fab387",
                     font=("Consolas",9,"bold"), width=22, anchor="w", padx=6).pack(side="left")
            tk.Label(row_f, text=str(col["max_len"]), bg="#211a30", fg="#fab387",
                     font=("Consolas",9), width=8, anchor="center").pack(side="left")

            var = tk.StringVar(value="(skip — not in file)")
            # Pre-fill from existing override
            if db_norm in self._col_map_overrides:
                fi = self._col_map_overrides[db_norm]
                if 0 <= fi < len(self._file_headers):
                    for fc in file_choices:
                        if fc.startswith(self._file_headers[fi]):
                            var.set(fc); break
            # Try to auto-suggest best substring match
            else:
                stripped = db_norm
                for pfx in _ETL_STRIP:
                    if stripped.startswith(pfx) and len(stripped) > len(pfx):
                        stripped = stripped[len(pfx):]; break
                best = None; best_score = 0
                for fi, hdr in enumerate(self._file_headers):
                    hn = _norm_col(hdr)
                    score = (3 if stripped == hn else
                             2 if stripped in hn or hn in stripped else
                             1 if any(t in hn for t in _camel_tokens(col["name"])) else 0)
                    if score > best_score:
                        best_score, best = score, fi
                if best is not None and best_score > 0:
                    for fc in file_choices:
                        if fc.startswith(self._file_headers[best]):
                            var.set(fc); break

            cb = ttk.Combobox(row_f, textvariable=var, values=file_choices,
                              state="readonly", width=68, font=("Segoe UI",9))
            cb.pack(side="left", padx=(6,4))
            map_vars[db_norm] = (var, col)

        # Bottom buttons
        btn_f = tk.Frame(dlg, bg="#1e1e2e")
        btn_f.pack(fill="x", padx=12, pady=(4,10))
        status_var = tk.StringVar()
        tk.Label(btn_f, textvariable=status_var, bg="#1e1e2e", fg="#a6e3a1",
                 font=("Segoe UI",9)).pack(side="left", padx=(0,12))

        def _apply():
            count = 0
            for db_norm, (var, col) in map_vars.items():
                sel = var.get()
                if sel.startswith("(skip"):
                    if db_norm in self._col_map_overrides:
                        del self._col_map_overrides[db_norm]
                    continue
                # Extract file column name (before the [max=...] annotation)
                file_col_name = sel.split("  [max=")[0].strip()
                if file_col_name in self._file_headers:
                    self._col_map_overrides[db_norm] = self._file_headers.index(file_col_name)
                    count += 1
            status_var.set(f"✅ {count} mapping(s) applied — refreshing…")
            dlg.update()
            self._populate_mapping_panel([])   # clear the bottom panel
            self._refresh_schema_view(self._db_schema)
            if self._file_headers and self._file_stats:
                self._show_column_stats(self._file_headers, self._file_stats, None)
            dlg.destroy()

        tk.Button(btn_f, text="✅ Apply Mappings & Close", bg="#a6e3a1", fg="#1e1e2e",
                   font=("Segoe UI",11,"bold"), relief="flat", cursor="hand2",
                   padx=20, pady=8, command=_apply).pack(side="right", padx=(8,0))
        tk.Button(btn_f, text="Skip All / Close", bg="#45475a", fg="#cdd6f4",
                   font=("Segoe UI",10), relief="flat", cursor="hand2",
                   padx=12, pady=8, command=dlg.destroy).pack(side="right")

    def _get_fmax_for_col(self, col: dict):
        """Return the file max length for a DB column, or None if not matched."""
        if not self._file_headers or not self._file_stats:
            return None
        file_max_by_norm: dict = {}
        for idx, hdr in enumerate(self._file_headers):
            fstats = self._file_stats.get(idx, {})
            if fstats and "max_len" in fstats:
                file_max_by_norm[_norm_col(hdr)] = fstats["max_len"]
        db_norm = _norm_col(col["name"])
        fmax = file_max_by_norm.get(db_norm)
        if fmax is None:
            for pfx in _ETL_STRIP:
                if db_norm.startswith(pfx) and len(db_norm) > len(pfx):
                    fmax = file_max_by_norm.get(db_norm[len(pfx):])
                    if fmax is not None:
                        break
        if fmax is None and db_norm in self._col_map_overrides:
            fi = self._col_map_overrides[db_norm]
            fstats = self._file_stats.get(fi, {})
            if fstats and "max_len" in fstats:
                fmax = fstats["max_len"]
        return fmax


        name = self._profile_var.get()
        p = DB_PRESETS.get(name, {})
        if not p:
            return  # placeholder row selected
        self._db_type_var.set(p.get("type", "SQL Server"))
        self._db_host_var.set(p.get("host", ""))
        self._db_port_var.set(p.get("port", "1433"))
        self._db_name_var.set(p.get("db", ""))
        self._db_schema_var.set(p.get("schema", "dbo"))
        self._db_user_var.set(p.get("user", ""))
        self._db_pwd_var.set(p.get("pwd", ""))
        self._db_extra_var.set("")
        self._on_db_type_change()
        note = " — enter password then click Connect" if p.get("user") else " — Windows Auth (no password needed)"
        self._conn_status_var.set(f"Profile loaded: {p['host']} / {p['db']}{note}")

    def _on_db_type_change(self, event=None):
        db_type = self._db_type_var.get()
        # Only reset port when triggered by user changing the dropdown (not programmatic calls)
        if event is not None:
            self._db_port_var.set(DB_DEFAULT_PORTS.get(db_type, ""))
        ok = DB_DRIVER_STATUS.get(db_type, False)
        self._drv_status_var.set(f"{'✓ driver ready' if ok else '✗ driver missing — restart the app to auto-install'}")
        if db_type == "SQLite":
            self._db_extra_lbl.config(text="SQLite File:")
        elif db_type == "Oracle":
            self._db_extra_lbl.config(text="Oracle DSN (optional):")
        else:
            self._db_extra_lbl.config(text="")

    def _test_connection(self):
        db_type = self._db_type_var.get()
        conn, err = db_connect(db_type, self._db_host_var.get(), self._db_port_var.get(),
                                self._db_name_var.get(), self._db_schema_var.get(),
                                self._db_user_var.get(), self._db_pwd_var.get(),
                                self._db_extra_var.get())
        if conn:
            try: conn.close()
            except Exception: pass
            messagebox.showinfo("✅ Connection Successful",
                f"Successfully connected to {db_type}!\n\n"
                f"Host: {self._db_host_var.get()}\n"
                f"Database: {self._db_name_var.get()}")
        else:
            messagebox.showerror("❌ Connection Failed",
                f"Could not connect to {db_type}:\n\n{err}\n\n"
                "Check host, port, credentials, and firewall.")

    def _do_connect(self):
        db_type = self._db_type_var.get()
        self._conn_status_var.set("Connecting…")
        self.update()
        if self._db_conn:
            try: self._db_conn.close()
            except Exception: pass
            self._db_conn = None

        conn, err = db_connect(db_type, self._db_host_var.get(), self._db_port_var.get(),
                                self._db_name_var.get(), self._db_schema_var.get(),
                                self._db_user_var.get(), self._db_pwd_var.get(),
                                self._db_extra_var.get())
        if conn:
            self._db_conn  = conn
            self._db_type  = db_type
            self._conn_status_var.set(
                f"✅ Connected: {db_type} → {self._db_host_var.get()}/{self._db_name_var.get()}")
            tk.Label(self._t_db, textvariable=self._conn_status_var,
                     bg="#1e1e2e").update_idletasks()
        else:
            self._conn_status_var.set(f"❌ Failed: {err[:80]}")
            messagebox.showerror("Connection Failed",
                f"Could not connect:\n\n{err}\n\n"
                "• Check host / port\n• Check username / password\n"
                "• Check firewall / VPN\n• Verify DB service is running")

    def _disconnect(self):
        if self._db_conn:
            try: self._db_conn.close()
            except Exception: pass
            self._db_conn = None
        self._conn_status_var.set("Disconnected")
        self._db_schema = []
        self._schema_status_var.set("Disconnected")
        self._schema_tree.delete(*self._schema_tree.get_children())

    def _fetch_schema(self):
        if not self._db_conn:
            messagebox.showwarning("Not Connected","Connect to a database first."); return
        table = self._db_table_var.get().strip()
        if not table:
            messagebox.showwarning("No Table","Enter a table name."); return
        self._schema_status_var.set("Fetching schema…")
        self.update()

        cols, err = db_get_schema(self._db_conn, self._db_type, table)
        if err:
            self._schema_status_var.set(f"Error: {err[:80]}")
            messagebox.showerror("Schema Error",
                f"Could not fetch schema for '{table}':\n\n{err}\n\n"
                "• Check table name (case-sensitive in some DBs)\n"
                "• Try including schema prefix: dbo.TableName\n"
                "• Verify user has SELECT permission on INFORMATION_SCHEMA")
            return
        if not cols:
            self._schema_status_var.set(f"Table '{table}' not found or no columns returned.")
            messagebox.showwarning("Not Found",
                f"No columns found for table '{table}'.\n\n"
                "Tip: table names may be case-sensitive. Try UPPER_CASE or exact case.")
            return

        self._db_schema = cols
        self._db_table  = table

        # Show match count in status bar
        if self._file_headers:
            limits, matched = match_file_to_schema(self._file_headers, cols,
                                                    self._col_map_overrides)
            match_note = (f" — {len(matched)}/{len(self._file_headers)} file cols matched"
                          if matched else " — ⚠ 0 file cols matched (check table name)")
        else:
            match_note = ""
        self._schema_status_var.set(
            f"✓  {len(cols)} columns fetched from {self._db_type} '{table}'{match_note}")

        # Render schema tree + mapping panel
        self._refresh_schema_view(cols)
        # Refresh file scanner comparison too
        if self._file_headers:
            self._show_column_stats(self._file_headers, self._file_stats, None)
        self._update_report()

    def _list_tables(self):
        if not self._db_conn:
            messagebox.showwarning("Not Connected","Connect first."); return
        tables = db_list_tables(self._db_conn, self._db_type, self._db_schema_var.get())
        if not tables:
            messagebox.showinfo("No Tables","No tables found."); return

        win = tk.Toplevel(self)
        win.title("Tables"); win.geometry("400x500")
        win.configure(bg="#1e1e2e"); win.grab_set()
        tk.Label(win, text=f"{len(tables)} tables in {self._db_name_var.get()}",
                 bg="#1e1e2e", fg="#89b4fa", font=("Segoe UI",11,"bold")).pack(padx=14, pady=8)
        lb_f = tk.Frame(win, bg="#1e1e2e"); lb_f.pack(fill="both", expand=True, padx=14)
        lb = tk.Listbox(lb_f, bg="#181825", fg="#cdd6f4", font=("Consolas",10),
                         selectbackground="#45475a", relief="flat")
        vsb = ttk.Scrollbar(lb_f, command=lb.yview)
        lb.configure(yscrollcommand=vsb.set)
        lb.pack(side="left", fill="both", expand=True); vsb.pack(side="right", fill="y")
        for t in sorted(tables): lb.insert("end", t)
        def use_table():
            sel = lb.curselection()
            if sel:
                self._db_table_var.set(lb.get(sel[0]))
                win.destroy()
                self._fetch_schema()
        tk.Button(win, text="Use Selected Table", bg="#89b4fa", fg="#1e1e2e",
                   font=("Segoe UI",10,"bold"), relief="flat", cursor="hand2",
                   padx=14, pady=6, command=use_table).pack(pady=(4,12))
        lb.bind("<Double-Button-1>", lambda _: use_table())

    def _send_schema_to_scanner(self):
        if not self._db_schema:
            messagebox.showwarning("No Schema","Fetch a table schema first."); return
        if not self._file_path_var.get():
            messagebox.showinfo("Tip","Schema loaded. Now load a file in Tab 2, click '⚡ Quick Compare'.")
        self._nb.select(1)
        self.after(300, self._quick_compare)

    # ═══════════════════════════════════════════════════════════════════════════
    #  TAB 4 — FULL REPORT
    # ═══════════════════════════════════════════════════════════════════════════
    def _build_report_tab(self):
        tab = self._t_report
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        hdr_row = tk.Frame(tab, bg="#1e1e2e")
        hdr_row.grid(row=0, column=0, sticky="ew", padx=14, pady=(10,4))
        ttk.Label(hdr_row, text="Full Diagnosis Report", style="H.TLabel").pack(side="left")
        tk.Button(hdr_row, text="🔄 Refresh Report", bg="#45475a", fg="#cdd6f4",
                   font=("Segoe UI",9), relief="flat", cursor="hand2", padx=10, pady=4,
                   command=self._update_report).pack(side="right", padx=4)
        tk.Button(hdr_row, text="💾 Save Report (.txt)", bg="#89b4fa", fg="#1e1e2e",
                   font=("Segoe UI",9,"bold"), relief="flat", cursor="hand2", padx=10, pady=4,
                   command=self._save_report).pack(side="right", padx=4)

        self._report_txt = scrolledtext.ScrolledText(
            tab, wrap="word", bg="#181825", fg="#cdd6f4",
            font=("Consolas",10), relief="flat", insertbackground="#89b4fa",
            state="disabled")
        self._report_txt.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0,10))
        self._report_txt.tag_config("h1", foreground="#89b4fa", font=("Segoe UI",13,"bold"))
        self._report_txt.tag_config("h2", foreground="#f9e2af", font=("Segoe UI",11,"bold"))
        self._report_txt.tag_config("ok",   foreground="#a6e3a1", font=("Consolas",10))
        self._report_txt.tag_config("bad",  foreground="#f38ba8", font=("Consolas",10,"bold"))
        self._report_txt.tag_config("code", foreground="#cba6f7", font=("Consolas",10))

    def _update_report(self):
        lines = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines.append(("TALEND INGESTION ERROR AGENT — FULL REPORT\n", "h1"))
        lines.append((f"Generated: {now}\n\n", ""))
        lines.append(("═" * 70 + "\n\n", ""))

        # Email context
        if self._ctx:
            lines.append(("EMAIL / ALERT CONTEXT\n", "h2"))
            for k, v in [("Time", self._ctx.get("time","")), ("Project", self._ctx.get("project","")),
                          ("Job", self._ctx.get("job","")), ("File", self._ctx.get("file","")),
                          ("Origin", self._ctx.get("origin","")), ("Error Type", self._ctx.get("type","")),
                          ("Message", self._ctx.get("message","")), ("DB Table", self._ctx.get("db_table",""))]:
                if v:
                    lines.append((f"  {k}: {v}\n", "code"))
            lines.append(("\n", ""))

        # Diagnosis
        if self._diag_results:
            lines.append(("DIAGNOSIS RESULTS\n", "h2"))
            for r in self._diag_results:
                lines.append((f"\n  [{r['icon']} {r['cat']}] {r['id']}  (score: {r['score']})\n", ""))
                lines.append((f"  Root Cause: {r['cause_r']}\n", ""))
                lines.append(("  Fix Steps:\n", ""))
                for i, fx in enumerate(r["fixes_r"], 1):
                    lines.append((f"    {i}. {fx}\n", ""))
            lines.append(("\n", ""))

        # DB Schema
        if self._db_schema:
            lines.append(("DATABASE SCHEMA\n", "h2"))
            lines.append((f"  DB: {self._db_type}  |  Table: {self._db_table}\n", "code"))
            lines.append((f"  {'#':<4} {'Column':<30} {'Type':<20} {'MaxLen':<10} {'Nullable':<10} {'File Max':<10} {'Status'}\n", ""))
            lines.append(("  " + "─"*95 + "\n", ""))
            file_stats = {self._file_headers[i].upper(): self._file_stats.get(i, {})
                          for i in range(len(self._file_headers))} if self._file_headers else {}
            for i, col in enumerate(self._db_schema):
                fstats = file_stats.get(col["name"].upper(), {})
                fmax = fstats.get("max_len","—") if fstats else "—"
                db_lim = col["max_len"]
                status = ""
                tag = ""
                if fstats and isinstance(fmax, int) and db_lim > 0:
                    if fmax > db_lim:
                        status = f"⚠ OVERFLOW +{fmax-db_lim}"
                        tag = "bad"
                    elif fmax > db_lim * 0.8:
                        status = "⚠ Near limit"
                        tag = ""
                    else:
                        status = "✓ OK"
                        tag = "ok"
                lines.append((f"  {i+1:<4} {col['name']:<30} {col['type']:<20} "
                               f"{str(col['max_len'] or 'N/A'):<10} {col['nullable']:<10} "
                               f"{str(fmax):<10} {status}\n", tag))
            lines.append(("\n", ""))

        # Scan Issues
        if self._all_issues:
            lines.append(("TRUNCATION ISSUES FOUND\n", "h2"))
            lines.append((f"  {len(self._all_issues)} issue(s) detected\n\n", "bad"))
            lines.append((f"  {'Row':<8} {'Column':<25} {'Actual':<10} {'Limit':<10} {'Over':<8} Preview\n", ""))
            lines.append(("  " + "─"*90 + "\n", ""))
            for row_num, col_name, actual, limit, over, preview in self._all_issues[:200]:
                lines.append((f"  {str(row_num):<8} {col_name:<25} {str(actual):<10} "
                               f"{str(limit):<10} {str(over):<8} {preview[:50]}\n", "bad"))
            if len(self._all_issues) > 200:
                lines.append((f"  ... and {len(self._all_issues)-200} more. Export CSV for full list.\n", ""))
        else:
            lines.append(("Scan Results: Not yet run — use Tab 2 to scan the file.\n", ""))

        self._report_lines = lines
        self._report_txt.configure(state="normal")
        self._report_txt.delete("1.0","end")
        for text, tag in lines:
            self._report_txt.insert("end", text, tag if tag else "")
        self._report_txt.configure(state="disabled")

    def _save_report(self):
        if not self._report_lines:
            self._update_report()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        job = re.sub(r"[^\w]","_", self._ctx.get("job","report") or "report")
        default_name = f"TalendReport_{job}_{ts}.txt"
        path = filedialog.asksaveasfilename(
            initialfile=default_name, defaultextension=".txt",
            filetypes=[("Text report","*.txt"),("All","*.*")])
        if path:
            try:
                with open(path,"w",encoding="utf-8") as f:
                    for text, _ in self._report_lines:
                        f.write(text)
                messagebox.showinfo("Saved",f"Report saved:\n{path}")
            except Exception as ex:
                messagebox.showerror("Error",str(ex))


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
