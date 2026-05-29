import sys, os, csv, queue, threading, re, tempfile, statistics
import unittest.mock as m
sys.modules["tkinter"] = m.MagicMock()
sys.modules["tkinter.ttk"] = m.MagicMock()
sys.modules["tkinter.scrolledtext"] = m.MagicMock()
sys.modules["tkinter.messagebox"] = m.MagicMock()
sys.modules["tkinter.filedialog"] = m.MagicMock()
os.chdir(r"C:\Users\prasanthp\TalendEmailAgent")
import importlib.util
spec = importlib.util.spec_from_file_location("agent", "talend_agent.py")
mod  = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

tmpdir = tempfile.mkdtemp()

# T1: auto_detect_delimiter
csv_path = os.path.join(tmpdir,"t.csv")
pipe_path = os.path.join(tmpdir,"t.pipe")
tab_path  = os.path.join(tmpdir,"t.tsv")
with open(csv_path,"w",newline="",encoding="utf-8") as f:
    csv.writer(f).writerows([["A","B","C"],["1","hello","world"],["2","foo","bar"]])
with open(pipe_path,"w",newline="",encoding="utf-8") as f:
    csv.writer(f,delimiter="|").writerows([["CODE","VALUE","DESC"],["A001","test","ok"],["A002","thing","yes"]])
with open(tab_path,"w",newline="",encoding="utf-8") as f:
    csv.writer(f,delimiter="\t").writerows([["X","Y","Z"],["1","2","3"],["4","5","6"]])

d1,n1,_,c1 = mod.auto_detect_delimiter(csv_path)
d2,n2,_,c2 = mod.auto_detect_delimiter(pipe_path)
d3,n3,_,c3 = mod.auto_detect_delimiter(tab_path)
assert d1==",",  f"CSV: expected comma, got '{n1}'"
assert d2=="|",  f"Pipe: expected |, got '{n2}'"
assert d3=="\t", f"Tab: expected tab, got '{n3}'"
print(f"T1 DELIMITER DETECTION PASS: csv='{n1}'({c1}%), pipe='{n2}'({c2}%), tab='{n3}'({c3}%)")

# T2: get_column_stats
import openpyxl
xlsx_path = os.path.join(tmpdir,"t.xlsx")
wb=openpyxl.Workbook(); ws=wb.active
ws.append(["PRODUCT_CODE","VENDOR_NAME","DESCRIPTION"])
ws.append(["P001","Short","OK"])
ws.append(["P002","A"*30,"This is a long description that exceeds normal limits"])
wb.save(xlsx_path)
headers, stats, err = mod.get_column_stats(xlsx_path,"xlsx",{"sheet":None,"has_header":True,"encoding":"utf-8-sig"})
assert not err, f"col stats error: {err}"
assert headers[1]=="VENDOR_NAME"
assert stats[1]["max_len"]==30, f"vendor max={stats[1]['max_len']}"
print(f"T2 COL STATS PASS: headers={headers}, vendor_max={stats[1]['max_len']}")

# T3: parse_email - truncation email
raw = """From: talend-alerts@company.com
Subject: JOB FAILED: Sysco_Rebate_Import
Time: Fri May 22 18:00:18 EDT 2026
Project: NAV_DW_FORMULARY_OPTIMIZATION
Job: Sysco_Rebate_Import
File: \\\\FLO-IIS-MID-P1\\ProdLevelFiles\\InputFiles\\4Q25 NAV OR RMD ORM_part I.xlsx
Type: Java Exception
Origin: tDBOutput_1
Message: java.sql.BatchUpdateException:Data truncation"""
ctx = mod.parse_email(raw)
assert ctx["job"]=="Sysco_Rebate_Import", f"job={ctx['job']}"
assert ctx["file_ext"]=="xlsx", f"ext={ctx['file_ext']}"
assert ctx["component_type"]=="tDBOutput", f"comp={ctx['component_type']}"
assert ctx["is_structured"]==True
print(f"T3 EMAIL PARSE PASS: job={ctx['job']}, ext={ctx['file_ext']}, comp={ctx['component_type']}")

# T4: diagnose - truncation (xlsx+tDBOutput → XLSX_TRUNCATION is the more specific match, both are valid)
results = mod.diagnose(ctx)
TRUNC_IDS = {"BATCH_TRUNCATION","XLSX_TRUNCATION","ORA_TRUNCATION"}
assert results and results[0]["id"] in TRUNC_IDS, f"expected truncation pattern, got top={results[0]['id'] if results else 'none'}"
assert "needs" in results[0] and "file" in results[0]["needs"]
top_ids = [r["id"] for r in results[:3]]
assert any(i in TRUNC_IDS for i in top_ids), f"no truncation pattern in top-3: {top_ids}"
print(f"T4 DIAGNOSIS PASS: top={results[0]['id']}, score={results[0]['score']}, top3={top_ids}")

# T5: parse_email - connection refused
raw2 = "Job: ETL_Job  FAILED\nMessage: java.net.ConnectException: Connection refused\nJDBC URL: jdbc:sqlserver://PROD-DB-01:1433;databaseName=FORMULARY_DB"
ctx2 = mod.parse_email(raw2)
results2 = mod.diagnose(ctx2)
assert results2 and results2[0]["id"]=="CONN_REFUSED", f"top={results2[0]['id'] if results2 else 'none'}"
print(f"T5 CONN_REFUSED PASS: top={results2[0]['id']}, db_port={ctx2['db_port']}")

# T6: parse_email - delimiter issue
raw3 = "tFileInputDelimited_1 - Wrong number of fields in record, expected 12 but found 14\nFile: data.csv"
ctx3 = mod.parse_email(raw3)
results3 = mod.diagnose(ctx3)
assert results3 and results3[0]["id"]=="WRONG_FIELDS", f"top={results3[0]['id'] if results3 else 'none'}"
print(f"T6 WRONG_FIELDS PASS: top={results3[0]['id']}")

# T7: scan_truncations with DB-like limits
scan_path = os.path.join(tmpdir,"scan.csv")
with open(scan_path,"w",newline="",encoding="utf-8") as f:
    csv.writer(f).writerows([
        ["PRODUCT_CODE","VENDOR_NAME","DESCRIPTION"],
        ["P001","ShortVendor","OK desc"],
        ["P002","A"*30,"This description is way too long and exceeds the DB VARCHAR(50) limit exactly"],
        ["P003","Normal","Fine"],
    ])
q=queue.Queue(); ev=threading.Event()
t=threading.Thread(target=mod.scan_truncations,args=(scan_path,"csv",
    {"delimiter":",","has_header":True,"encoding":"utf-8-sig"},{1:20,2:50},q,ev),daemon=True)
t.start(); t.join(timeout=10)
issues=[]
while not q.empty():
    msg=q.get_nowait()
    if msg[0]=="issue": issues.append(msg)
assert len(issues)>=2, f"T7: expected >=2 issues, got {len(issues)}"
print(f"T7 SCAN PASS: {len(issues)} issues, rows={[i[1] for i in issues]}")

# T8: MHA prefix-stripped column matching
# File headers: plain names (as in source files)
# DB columns:   RD_ prefixed (as Talend tMap maps them)
file_headers = ["Rebate Type","MEM ID","BUSINESS NAME","Affiliate ID","CHECK AMOUNT","Salesperson"]
db_schema = [
    {"name":"RD_RebateType",   "type":"varchar","max_len":100, "nullable":"YES"},
    {"name":"RD_MemID",        "type":"varchar","max_len":10,  "nullable":"YES"},
    {"name":"RD_BusinessName", "type":"varchar","max_len":50,  "nullable":"YES"},
    {"name":"RD_AffiliateID",  "type":"varchar","max_len":10,  "nullable":"YES"},
    {"name":"RD_CheckAmount",  "type":"decimal","max_len":0,   "nullable":"YES"},  # no char limit
    {"name":"RD_Salesperson",  "type":"varchar","max_len":30,  "nullable":"YES"},
    {"name":"rd_filename",     "type":"varchar","max_len":200, "nullable":"YES"},  # runtime — skip
    {"name":"rd_addstmp",      "type":"datetime","max_len":0,  "nullable":"YES"},  # runtime — skip
]
limits8, matched8 = mod.match_file_to_schema(file_headers, db_schema)
assert len(limits8) == 5, f"T8: expected 5 varchar matches, got {len(limits8)}: {matched8}"
assert limits8[0] == 100, f"T8: RebateType should be 100, got {limits8.get(0)}"
assert limits8[1] == 10,  f"T8: MemID should be 10, got {limits8.get(1)}"
assert limits8[2] == 50,  f"T8: BusinessName should be 50, got {limits8.get(2)}"
assert limits8[3] == 10,  f"T8: AffiliateID should be 10, got {limits8.get(3)}"
assert limits8[5] == 30,  f"T8: Salesperson should be 30, got {limits8.get(5)}"
# CHECK AMOUNT is decimal (max_len=0) — should NOT be in limits
assert 4 not in limits8,  f"T8: CHECK AMOUNT (decimal) should not be in limits"
# runtime cols should NOT appear in limits
for name in ["rd_filename","rd_addstmp"]:
    for m in matched8:
        assert name not in m.lower(), f"T8: runtime col '{name}' leaked into matches: {m}"
print(f"T8 MHA PREFIX MATCH PASS: {len(limits8)} cols matched, limits={limits8}")
print(f"   Matched: {matched8}")

print("\nALL 8 TESTS PASSED ✓")
