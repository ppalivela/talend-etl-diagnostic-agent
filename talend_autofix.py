#!/usr/bin/env python3
"""
Talend Auto-Fix & Re-Ingestion Agent
=====================================
Automatically detects truncation issues in ETL source files,
fixes every offending cell, and saves the corrected file —
ready for Talend re-ingestion with zero manual intervention.

Author  : ETL Team — MHA Inc.
Version : 1.0
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os, csv, re, json, threading, queue, io, subprocess, traceback
from datetime import datetime

# ── auto-install helper ───────────────────────────────────────────────────────
def _try_import(pkg, install_name=None):
    import importlib, sys
    try:
        return importlib.import_module(pkg)
    except ImportError:
        try:
            import subprocess as sp
            sp.check_call([sys.executable, "-m", "pip", "install",
                           install_name or pkg, "--quiet"],
                          stdout=sp.DEVNULL, stderr=sp.DEVNULL)
            return importlib.import_module(pkg)
        except Exception:
            return None

pd       = _try_import("pandas")
openpyxl = _try_import("openpyxl")
pyodbc   = _try_import("pyodbc")
oracledb = _try_import("oracledb")
mysql_c  = _try_import("mysql.connector", "mysql-connector-python")
psycopg2 = _try_import("psycopg2", "psycopg2-binary")

# ── MHA pre-configured DB profiles ───────────────────────────────────────────
MHA_PROFILES = {
    "FLO-DDW-DEV / Formulary_Data":  {"server": "FLO-DDW-DEV",    "db": "Formulary_Data", "auth": "windows"},
    "FLO-SQL-NAVDWP / NAVDW":        {"server": "FLO-SQL-NAVDWP", "db": "NAVDW",          "auth": "windows"},
    "FLO-SQL-NAVDWP / NavDWStage":   {"server": "FLO-SQL-NAVDWP", "db": "NavDWStage",     "auth": "windows"},
    "ROMULUS / GPOData":             {"server": "ROMULUS",         "db": "GPOData",        "auth": "windows"},
    "FLO-SQL-TDMU (SQL Auth)":       {"server": "FLO-SQL-TDMU",   "db": "",               "auth": "sql",
                                      "user": "SRVFLO-SQL-Talend"},
    "Custom...":                     None,
}

# ── colour palette ────────────────────────────────────────────────────────────
C = {
    "bg":      "#1e1e2e", "surface": "#313244", "overlay": "#45475a",
    "text":    "#cdd6f4", "subtext": "#a6adc8",
    "green":   "#a6e3a1", "yellow":  "#f9e2af", "red":     "#f38ba8",
    "blue":    "#89b4fa", "mauve":   "#cba6f7", "teal":    "#94e2d5",
    "peach":   "#fab387", "dark":    "#181825",
}


# ─────────────────────────────────────────────────────────────────────────────
class TalendAutoFixApp:

    def __init__(self, root):
        self.root = root
        self.root.title("⚡ Talend Auto-Fix & Re-Ingestion Agent  |  MHA Inc.")

        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h   = min(int(sw * 0.95), 1600), min(int(sh * 0.95), 1040)
        root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        root.minsize(1100, 720)
        root.configure(bg=C["bg"])
        root.resizable(True, True)

        # ── state ─────────────────────────────────────────────────────────────
        self._df          = None    # original DataFrame
        self._fixed_df    = None    # fixed DataFrame
        self._schema      = {}      # {col_lower: {"col": str, "limit": int, "type": str}}
        self._col_map        = {}   # {file_col: schema_key}  (auto + manual)
        self._manual_col_map = {}   # {file_col: schema_key}  (user overrides)
        self._col_strategy   = {}   # {file_col: "head"|"tail"} (user overrides)
        self._issues      = None    # None = not scanned yet; [] = scanned, no issues
        self._change_log  = []      # list of dicts
        self._file_path   = ""
        self._file_ext    = ""
        self._out_path    = ""
        self._fix_running = False
        self._q           = queue.Queue()

        self._build_styles()
        self._build_header()
        self._build_notebook()
        self._build_statusbar()
        self._poll_queue()

    # ── ttk styles ────────────────────────────────────────────────────────────
    def _build_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TNotebook",      background=C["bg"],      borderwidth=0)
        s.configure("TNotebook.Tab",  background=C["overlay"], foreground=C["subtext"],
                    padding=[16, 6],  font=("Segoe UI", 10))
        s.map("TNotebook.Tab",
              background=[("selected", C["surface"])],
              foreground=[("selected", C["mauve"])])
        s.configure("TFrame",         background=C["bg"])
        s.configure("Treeview",       background=C["surface"], fieldbackground=C["surface"],
                    foreground=C["text"], rowheight=22, font=("Consolas", 9))
        s.configure("Treeview.Heading", background=C["overlay"], foreground=C["blue"],
                    font=("Segoe UI", 9, "bold"))
        s.map("Treeview",             background=[("selected", "#585b70")])
        s.configure("TCombobox",      fieldbackground=C["overlay"], background=C["overlay"],
                    foreground=C["text"], selectbackground=C["overlay"])
        s.configure("Horizontal.TProgressbar", troughcolor=C["overlay"],
                    background=C["green"])

    # ── header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self.root, bg=C["dark"], pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚡ Talend Auto-Fix & Re-Ingestion Agent",
                 font=("Segoe UI", 15, "bold"), bg=C["dark"], fg=C["mauve"]).pack(side="left", padx=16)
        tk.Label(hdr, text="Detects  •  Fixes  •  Saves  —  Zero Manual Intervention",
                 font=("Segoe UI", 9), bg=C["dark"], fg=C["subtext"]).pack(side="left", padx=6)
        tk.Label(hdr, text="MHA Inc. ETL Team",
                 font=("Segoe UI", 8), bg=C["dark"], fg=C["overlay"]).pack(side="right", padx=16)

    # ── notebook ──────────────────────────────────────────────────────────────
    def _build_notebook(self):
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=8, pady=4)

        self.t_load = ttk.Frame(self.nb)
        self.t_scan = ttk.Frame(self.nb)
        self.t_fix  = ttk.Frame(self.nb)
        self.t_log  = ttk.Frame(self.nb)

        self.nb.add(self.t_load, text="① Load & Schema")
        self.nb.add(self.t_scan, text="② Compare & Fix")
        self.nb.add(self.t_fix,  text="③ Auto-Fix & Save")
        self.nb.add(self.t_log,  text="④ Change Log")

        self._build_tab_load()
        self._build_tab_scan()
        self._build_tab_fix()
        self._build_tab_log()

    # ── status bar ────────────────────────────────────────────────────────────
    def _build_statusbar(self):
        self._sv = tk.StringVar(value="Ready — load a file to begin.")
        bar = tk.Frame(self.root, bg=C["dark"])
        bar.pack(fill="x", side="bottom")
        tk.Label(bar, textvariable=self._sv, font=("Segoe UI", 9),
                 bg=C["dark"], fg=C["subtext"], anchor="w").pack(side="left", padx=12)
        self._prog = ttk.Progressbar(bar, length=180, mode="indeterminate",
                                     style="Horizontal.TProgressbar")
        self._prog.pack(side="right", padx=12, pady=3)

    def _status(self, msg): self._sv.set(msg); self.root.update_idletasks()
    def _prog_start(self):  self._prog.start(10)
    def _prog_stop(self):   self._prog.stop(); self._prog["value"] = 0

    def _poll_queue(self):
        try:
            while True:
                fn = self._q.get_nowait()
                try:
                    fn()
                except Exception as cb_err:
                    print(f"[queue-cb error] {cb_err}")
        except queue.Empty:
            pass
        except Exception as e:
            print(f"[poll_queue error] {e}")
        self.root.after(100, self._poll_queue)

    # ══ scrollable tab wrapper ═══════════════════════════════════════════════
    def _scrollable_tab(self, tab):
        """Wraps tab content in Canvas+Scrollbar so everything is reachable."""
        canvas = tk.Canvas(tab, bg=C["bg"], highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(tab, orient="vertical",   command=canvas.yview)
        hsb = ttk.Scrollbar(tab, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=C["bg"])
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        def _on_inner(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas(e):
            canvas.itemconfigure(win_id, width=e.width)
        inner.bind("<Configure>", _on_inner)
        canvas.bind("<Configure>", _on_canvas)
        canvas.bind("<Enter>",
            lambda e: canvas.bind_all("<MouseWheel>",
                lambda ev: canvas.yview_scroll(int(-1*(ev.delta/120)), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        return inner

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — LOAD & SCHEMA
    # ══════════════════════════════════════════════════════════════════════════
    def _build_tab_load(self):
        tab = self._scrollable_tab(self.t_load)

        # ── File section ──────────────────────────────────────────────────────
        lf = self._lf(tab, "📂  Step 1 — Load Source File")
        lf.pack(fill="x", padx=14, pady=(12, 6))

        r1 = tk.Frame(lf, bg=C["surface"]); r1.pack(fill="x", padx=10, pady=8)
        self._fv = tk.StringVar()
        tk.Entry(r1, textvariable=self._fv, width=68,
                 bg=C["overlay"], fg=C["text"], insertbackground=C["text"],
                 relief="flat", font=("Consolas", 9)).pack(side="left", padx=(0, 8), ipady=4)
        self._btn(r1, "Browse…", self._browse_file, C["blue"]).pack(side="left")

        r2 = tk.Frame(lf, bg=C["surface"]); r2.pack(fill="x", padx=10, pady=(0, 6))
        tk.Label(r2, text="Delimiter:", bg=C["surface"], fg=C["subtext"],
                 font=("Segoe UI", 9)).pack(side="left")
        self._delim_var = tk.StringVar(value="Auto-Detect")
        ttk.Combobox(r2, textvariable=self._delim_var, width=16, state="readonly",
                     values=["Auto-Detect", "Comma (,)", "Pipe (|)",
                             "Tab (\\t)", "Semicolon (;)", "Excel/XLSX"]).pack(side="left", padx=(4, 20))
        tk.Label(r2, text="Sheet (Excel):", bg=C["surface"], fg=C["subtext"],
                 font=("Segoe UI", 9)).pack(side="left")
        self._sheet_var = tk.StringVar(value="Sheet1")
        self._sheet_cb  = ttk.Combobox(r2, textvariable=self._sheet_var, width=18)
        self._sheet_cb.pack(side="left", padx=(4, 0))

        self._finfo_v = tk.StringVar(value="No file loaded.")
        tk.Label(lf, textvariable=self._finfo_v, bg=C["surface"], fg=C["green"],
                 font=("Consolas", 9)).pack(anchor="w", padx=10, pady=(0, 6))

        # ── Schema section ────────────────────────────────────────────────────
        slf = self._lf(tab, "🗄️  Step 2 — Column Schema / Max Lengths")
        slf.pack(fill="both", expand=True, padx=14, pady=6)

        src_row = tk.Frame(slf, bg=C["surface"]); src_row.pack(fill="x", padx=10, pady=8)
        tk.Label(src_row, text="Schema Source:", bg=C["surface"], fg=C["subtext"],
                 font=("Segoe UI", 9)).pack(side="left")
        self._schema_src = tk.StringVar(value="DDL")
        for val, lbl in [("DDL", "Paste DDL"), ("DB", "Live DB"), ("Manual", "Manual Entry")]:
            tk.Radiobutton(src_row, text=lbl, variable=self._schema_src, value=val,
                           bg=C["surface"], fg=C["text"], selectcolor=C["overlay"],
                           activebackground=C["surface"], font=("Segoe UI", 9),
                           command=self._switch_schema_frame).pack(side="left", padx=10)

        self._schema_frames = {}

        # DDL frame
        f_ddl = tk.Frame(slf, bg=C["surface"])
        tk.Label(f_ddl, text="Paste CREATE TABLE DDL:", bg=C["surface"], fg=C["subtext"],
                 font=("Segoe UI", 9)).pack(anchor="w", padx=8, pady=(4, 0))
        self._ddl_txt = scrolledtext.ScrolledText(
            f_ddl, height=9, bg=C["overlay"], fg=C["text"],
            insertbackground=C["text"], font=("Consolas", 9), relief="flat")
        self._ddl_txt.pack(fill="both", expand=True, padx=8, pady=4)
        self._ddl_txt.insert("1.0",
            "-- Paste your CREATE TABLE statement here\n"
            "-- Example:\n"
            "-- CREATE TABLE dbo.MyTable (\n"
            "--   CustomerName  NVARCHAR(100),\n"
            "--   Address       VARCHAR(255),\n"
            "--   Phone         VARCHAR(20)\n"
            "-- )")
        self._schema_frames["DDL"] = f_ddl

        # DB frame
        f_db = tk.Frame(slf, bg=C["surface"])

        # ── Row 1: Profile ───────────────────────────────────────────────────
        db1 = tk.Frame(f_db, bg=C["surface"]); db1.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(db1, text="Profile:", bg=C["surface"], fg=C["subtext"],
                 font=("Segoe UI", 9)).pack(side="left")
        self._db_prof = tk.StringVar(value=list(MHA_PROFILES.keys())[0])
        ttk.Combobox(db1, textvariable=self._db_prof, values=list(MHA_PROFILES.keys()),
                     width=36, state="readonly").pack(side="left", padx=4)
        self._db_prof.trace("w", lambda *_: self._fill_db_profile())

        # ── Row 2: Server / Database / Browse button ─────────────────────────
        db2 = tk.Frame(f_db, bg=C["surface"]); db2.pack(fill="x", padx=8, pady=2)
        self._db_server = tk.StringVar(); self._db_name = tk.StringVar()
        self._db_table  = tk.StringVar(); self._db_user = tk.StringVar()
        self._db_pass   = tk.StringVar()
        for lbl, var, w in [("Server:", self._db_server, 22), ("Database:", self._db_name, 20)]:
            tk.Label(db2, text=lbl, bg=C["surface"], fg=C["subtext"],
                     font=("Segoe UI", 9)).pack(side="left", padx=(6, 2))
            tk.Entry(db2, textvariable=var, width=w,
                     bg=C["overlay"], fg=C["text"], insertbackground=C["text"],
                     font=("Consolas", 9), relief="flat").pack(side="left", padx=(0, 4), ipady=3)
        self._btn(db2, "🔍 Browse All Tables", self._browse_tables,
                  C["blue"], padx=10).pack(side="left", padx=8)

        # ── Row 3: User / Password / Fetch Schema ────────────────────────────
        db3 = tk.Frame(f_db, bg=C["surface"]); db3.pack(fill="x", padx=8, pady=2)
        for lbl, var, w, show in [("User:", self._db_user, 18, ""),
                                    ("Password:", self._db_pass, 18, "*")]:
            tk.Label(db3, text=lbl, bg=C["surface"], fg=C["subtext"],
                     font=("Segoe UI", 9)).pack(side="left", padx=(6, 2))
            tk.Entry(db3, textvariable=var, width=w, show=show,
                     bg=C["overlay"], fg=C["text"], insertbackground=C["text"],
                     font=("Consolas", 9), relief="flat").pack(side="left", padx=(0, 4), ipady=3)
        tk.Label(db3, text="Table:", bg=C["surface"], fg=C["subtext"],
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 2))
        tk.Entry(db3, textvariable=self._db_table, width=22,
                 bg=C["overlay"], fg=C["yellow"], insertbackground=C["text"],
                 font=("Consolas", 9, "bold"), relief="flat").pack(side="left", padx=(0, 4), ipady=3)
        self._btn(db3, "✅ Load Schema", self._fetch_db_schema, C["teal"]).pack(side="left", padx=6)

        # ── Status line ──────────────────────────────────────────────────────
        self._db_sv = tk.StringVar(value="Enter server & database, then click 'Browse All Tables'.")
        tk.Label(f_db, textvariable=self._db_sv, bg=C["surface"], fg=C["yellow"],
                 font=("Consolas", 9)).pack(anchor="w", padx=8, pady=(2, 4))

        # ── Table Browser panel ──────────────────────────────────────────────
        browser_lf = tk.LabelFrame(f_db,
            text="  📋  All Tables in Database — click a table to select it  ",
            font=("Segoe UI", 9, "bold"), bg=C["surface"], fg=C["subtext"], relief="flat")
        browser_lf.pack(fill="both", expand=True, padx=8, pady=(2, 6))

        # Filter bar
        frow = tk.Frame(browser_lf, bg=C["surface"]); frow.pack(fill="x", padx=6, pady=4)
        tk.Label(frow, text="🔎 Filter:", bg=C["surface"], fg=C["subtext"],
                 font=("Segoe UI", 9)).pack(side="left")
        self._tbl_filter_v = tk.StringVar()
        self._tbl_filter_v.trace("w", lambda *_: self._filter_tables())
        tk.Entry(frow, textvariable=self._tbl_filter_v, width=30,
                 bg=C["overlay"], fg=C["text"], insertbackground=C["text"],
                 font=("Consolas", 9), relief="flat").pack(side="left", padx=(4, 16), ipady=3)
        self._tbl_count_v = tk.StringVar(value="No tables loaded.")
        tk.Label(frow, textvariable=self._tbl_count_v, bg=C["surface"],
                 fg=C["subtext"], font=("Segoe UI", 8)).pack(side="left")
        self._btn(frow, "🔄 Refresh", self._browse_tables,
                  C["overlay"], fg=C["text"], padx=8).pack(side="right")

        # Split: table list (left) + column preview (right)
        split = tk.Frame(browser_lf, bg=C["surface"]); split.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        split.columnconfigure(0, weight=2); split.columnconfigure(1, weight=3)
        split.rowconfigure(0, weight=1)

        # Table list
        tl_frame = tk.Frame(split, bg=C["bg"]); tl_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        tl_frame.rowconfigure(0, weight=1); tl_frame.columnconfigure(0, weight=1)
        tl_cols = ("schema", "table", "cols")
        self._tbl_tv = ttk.Treeview(tl_frame, columns=tl_cols, show="headings",
                                     selectmode="browse", height=8)
        for c, lbl, w in [("schema", "Schema", 70), ("table", "Table Name", 200), ("cols", "Cols", 45)]:
            self._tbl_tv.heading(c, text=lbl)
            self._tbl_tv.column(c, width=w, minwidth=30)
        tl_vsb = ttk.Scrollbar(tl_frame, orient="vertical", command=self._tbl_tv.yview)
        self._tbl_tv.configure(yscrollcommand=tl_vsb.set)
        self._tbl_tv.grid(row=0, column=0, sticky="nsew")
        tl_vsb.grid(row=0, column=1, sticky="ns")
        self._tbl_tv.tag_configure("selected_tbl", background="#1a2a4a", foreground=C["blue"])
        self._tbl_tv.bind("<<TreeviewSelect>>", self._on_table_click)

        # Column preview (right side)
        cp_frame = tk.Frame(split, bg=C["bg"]); cp_frame.grid(row=0, column=1, sticky="nsew")
        cp_frame.rowconfigure(0, weight=1); cp_frame.columnconfigure(0, weight=1)
        cp_hdr = tk.Frame(cp_frame, bg=C["surface"]); cp_hdr.pack(fill="x")
        self._col_prev_v = tk.StringVar(value="← Click a table to preview its columns")
        tk.Label(cp_hdr, textvariable=self._col_prev_v, bg=C["surface"],
                 fg=C["teal"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=6, pady=3)
        col_cols = ("col", "type", "maxlen", "nullable")
        self._col_tv = ttk.Treeview(cp_frame, columns=col_cols, show="headings",
                                     selectmode="none", height=8)
        for c, lbl, w in [("col", "Column Name", 180), ("type", "Data Type", 110),
                           ("maxlen", "Max Len", 70), ("nullable", "Nullable", 65)]:
            self._col_tv.heading(c, text=lbl)
            self._col_tv.column(c, width=w, minwidth=40)
        cp_vsb = ttk.Scrollbar(cp_frame, orient="vertical", command=self._col_tv.yview)
        self._col_tv.configure(yscrollcommand=cp_vsb.set)
        cp_inner = tk.Frame(cp_frame, bg=C["bg"]); cp_inner.pack(fill="both", expand=True)
        cp_inner.rowconfigure(0, weight=1); cp_inner.columnconfigure(0, weight=1)
        self._col_tv = ttk.Treeview(cp_inner, columns=col_cols, show="headings",
                                     selectmode="none", height=8)
        for c, lbl, w in [("col", "Column Name", 180), ("type", "Data Type", 110),
                           ("maxlen", "Max Len", 70), ("nullable", "Nullable", 65)]:
            self._col_tv.heading(c, text=lbl)
            self._col_tv.column(c, width=w, minwidth=40)
        cp_vsb2 = ttk.Scrollbar(cp_inner, orient="vertical", command=self._col_tv.yview)
        self._col_tv.configure(yscrollcommand=cp_vsb2.set)
        self._col_tv.grid(row=0, column=0, sticky="nsew")
        cp_vsb2.grid(row=0, column=1, sticky="ns")
        self._col_tv.tag_configure("haslimit",  background="#1a2a1a", foreground=C["green"])
        self._col_tv.tag_configure("nolimit",   background=C["surface"], foreground=C["subtext"])

        self._all_tables   = []   # [(schema, table, col_count)]
        self._schema_frames["DB"] = f_db

        # Manual frame
        f_man = tk.Frame(slf, bg=C["surface"])
        tk.Label(f_man,
                 text="One per line — format:  ColumnName=MaxLength  or  ColumnName,MaxLength",
                 bg=C["surface"], fg=C["subtext"], font=("Segoe UI", 9)).pack(anchor="w", padx=8)
        self._man_txt = scrolledtext.ScrolledText(
            f_man, height=9, bg=C["overlay"], fg=C["text"],
            insertbackground=C["text"], font=("Consolas", 9), relief="flat")
        self._man_txt.pack(fill="both", expand=True, padx=8, pady=4)
        self._man_txt.insert("1.0",
            "# Column=MaxLength\n"
            "CustomerName=100\n"
            "Address=255\n"
            "Phone=20\n"
            "Email=150")
        self._schema_frames["Manual"] = f_man

        self._switch_schema_frame()

        # Schema summary
        slf2 = self._lf(tab, "📋  Schema Loaded")
        slf2.pack(fill="x", padx=14, pady=(0, 6))
        self._schema_sv = tk.StringVar(value="No schema loaded yet.")
        tk.Label(slf2, textvariable=self._schema_sv, bg=C["surface"], fg=C["green"],
                 font=("Consolas", 9)).pack(anchor="w", padx=10, pady=4)

        # Buttons
        br = tk.Frame(tab, bg=C["bg"]); br.pack(fill="x", padx=14, pady=8)
        self._btn(br, "🔍  Load File & Scan for Issues", self._load_and_scan,
                  C["mauve"], size=11, padx=20, pady=6).pack(side="left", padx=(0, 12))
        self._btn(br, "📐 Parse Schema Only", self._parse_schema_only,
                  C["overlay"], padx=12, pady=6).pack(side="left")

    def _lf(self, parent, title):
        return tk.LabelFrame(parent, text=f"  {title}  ",
                             font=("Segoe UI", 10, "bold"),
                             bg=C["surface"], fg=C["blue"], relief="flat", bd=2)

    def _btn(self, parent, text, cmd, bg, fg="#11111b", size=9, padx=10, pady=4):
        return tk.Button(parent, text=text, command=cmd,
                         bg=bg, fg=fg, font=("Segoe UI", size, "bold"),
                         relief="flat", padx=padx, pady=pady, cursor="hand2",
                         activebackground=bg)

    def _switch_schema_frame(self):
        src = self._schema_src.get()
        for f in self._schema_frames.values():
            f.pack_forget()
        self._schema_frames[src].pack(fill="both", expand=True, padx=4, pady=4)

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select Source File for Talend Ingestion",
            filetypes=[
                ("All supported", "*.xlsx *.xls *.csv *.txt *.tsv *.psv"),
                ("Excel",         "*.xlsx *.xls"),
                ("CSV",           "*.csv"),
                ("Text/Pipe/Tab", "*.txt *.tsv *.psv"),
                ("All files",     "*.*"),
            ])
        if not path:
            return
        self._file_path = path
        self._file_ext  = os.path.splitext(path)[1].lower()
        self._fv.set(path)

        if self._file_ext in (".xlsx", ".xls"):
            try:
                import openpyxl as ox
                wb = ox.load_workbook(path, read_only=True)
                sheets = wb.sheetnames
                self._sheet_cb["values"] = sheets
                self._sheet_var.set(sheets[0])
                wb.close()
            except Exception:
                pass
            self._delim_var.set("Excel/XLSX")
        else:
            try:
                with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                    sample = f.read(8192)
                detected = csv.Sniffer().sniff(sample, delimiters=",|\t;")
                dm = {",": "Comma (,)", "|": "Pipe (|)", "\t": "Tab (\\t)", ";": "Semicolon (;)"}
                self._delim_var.set(dm.get(detected.delimiter, "Comma (,)"))
            except Exception:
                pass

        sz = os.path.getsize(path)
        self._finfo_v.set(
            f"✅  {os.path.basename(path)}   ({sz // 1024:,} KB)   {path}")
        self._status(f"File selected: {os.path.basename(path)}")

    def _fill_db_profile(self):
        p = MHA_PROFILES.get(self._db_prof.get())
        if not p:
            return
        self._db_server.set(p.get("server", ""))
        self._db_name.set(p.get("db", ""))
        if p.get("auth") == "sql":
            self._db_user.set(p.get("user", ""))

    # ── browse all tables ─────────────────────────────────────────────────────
    def _browse_tables(self):
        server = self._db_server.get().strip()
        db     = self._db_name.get().strip()
        user   = self._db_user.get().strip()
        pwd    = self._db_pass.get().strip()
        if not server:
            messagebox.showwarning("Missing Info", "Enter Server name first."); return

        def _run():
            self._q.put(self._prog_start)
            self._q.put(lambda: self._db_sv.set(f"Connecting to {server}…"))
            try:
                tables = self._db_get_all_tables(server, db, user, pwd)
                self._all_tables = tables
                self._q.put(lambda: self._populate_table_browser(tables))
                self._q.put(lambda: self._db_sv.set(
                    f"✅  Connected — {len(tables)} tables in {server}/{db}"))
                self._q.put(lambda: self._tbl_count_v.set(
                    f"{len(tables)} tables found"))
            except Exception as ex:
                self._q.put(lambda: self._db_sv.set(f"❌  {ex}"))
                self._q.put(lambda: messagebox.showerror("Connection Error", str(ex)))
            finally:
                self._q.put(self._prog_stop)

        threading.Thread(target=_run, daemon=True).start()

    def _db_get_all_tables(self, server, db, user, pwd):
        if not pyodbc:
            raise RuntimeError("pyodbc not installed")
        conn = self._db_connect(server, db, user, pwd)
        cur  = conn.cursor()
        # READ UNCOMMITTED prevents hangs on locked tables/pages
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        # sys catalog is 10-50x faster than INFORMATION_SCHEMA on large DBs
        cur.execute("""
            SELECT
                s.name          AS schema_name,
                t.name          AS table_name,
                COUNT(c.column_id) AS col_count
            FROM sys.tables  t
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            JOIN sys.columns c ON t.object_id = c.object_id
            GROUP BY s.name, t.name
            ORDER BY s.name, t.name
        """)
        rows = [(r[0], r[1], r[2]) for r in cur.fetchall()]
        conn.close()
        return rows

    def _populate_table_browser(self, tables):
        self._tbl_tv.delete(*self._tbl_tv.get_children())
        self._tbl_filter_v.set("")
        for schema, tbl, cnt in tables:
            self._tbl_tv.insert("", "end", iid=f"{schema}.{tbl}",
                                values=(schema, tbl, cnt))
        self._tbl_count_v.set(f"{len(tables)} tables  (click to select)")

    def _filter_tables(self):
        q = self._tbl_filter_v.get().lower().strip()
        self._tbl_tv.delete(*self._tbl_tv.get_children())
        filtered = [r for r in self._all_tables
                    if q in r[0].lower() or q in r[1].lower()] if q else self._all_tables
        for schema, tbl, cnt in filtered:
            self._tbl_tv.insert("", "end", iid=f"{schema}.{tbl}",
                                values=(schema, tbl, cnt))
        self._tbl_count_v.set(f"{len(filtered)} / {len(self._all_tables)} tables")

    def _on_table_click(self, event=None):
        sel = self._tbl_tv.selection()
        if not sel:
            return
        vals = self._tbl_tv.item(sel[0], "values")
        if not vals:
            return
        schema, tbl, col_cnt = vals
        # Auto-fill the Table field
        self._db_table.set(f"{schema}.{tbl}")
        self._col_prev_v.set(
            f"📋  {schema}.{tbl}  —  {col_cnt} columns  (loading…)")
        # Load column details in background
        server = self._db_server.get().strip()
        db     = self._db_name.get().strip()
        user   = self._db_user.get().strip()
        pwd    = self._db_pass.get().strip()

        def _run():
            try:
                cols = self._db_get_columns(server, db, schema, tbl, user, pwd)
                self._q.put(lambda: self._populate_col_preview(schema, tbl, cols))
            except Exception as ex:
                self._q.put(lambda: self._col_prev_v.set(f"❌ {ex}"))

        threading.Thread(target=_run, daemon=True).start()

    def _db_get_columns(self, server, db, schema, table, user, pwd):
        if not pyodbc:
            raise RuntimeError("pyodbc not installed")
        conn = self._db_connect(server, db, user, pwd)
        cur  = conn.cursor()
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        # sys.columns + sys.types is much faster than INFORMATION_SCHEMA.COLUMNS
        cur.execute("""
            SELECT
                c.name                              AS col_name,
                tp.name                             AS type_name,
                CASE
                    WHEN tp.name IN ('nvarchar','nchar') AND c.max_length = -1 THEN -1
                    WHEN tp.name IN ('nvarchar','nchar')                        THEN c.max_length / 2
                    WHEN tp.name IN ('varchar','char','binary','varbinary')
                         AND c.max_length = -1                                 THEN -1
                    WHEN tp.name IN ('varchar','char','binary','varbinary')     THEN c.max_length
                    ELSE NULL
                END                                 AS char_limit,
                CASE c.is_nullable WHEN 1 THEN 'YES' ELSE 'NO' END AS nullable
            FROM sys.columns  c
            JOIN sys.types    tp ON c.user_type_id = tp.user_type_id
            JOIN sys.tables   t  ON c.object_id    = t.object_id
            JOIN sys.schemas  s  ON t.schema_id    = s.schema_id
            WHERE s.name = ? AND t.name = ?
            ORDER BY c.column_id
        """, schema, table)
        rows = [(r[0], r[1], r[2], r[3]) for r in cur.fetchall()]
        conn.close()
        return rows

    def _populate_col_preview(self, schema, tbl, cols):
        self._col_tv.delete(*self._col_tv.get_children())
        has_limit = sum(1 for _, _, ml, _ in cols if ml and ml > 0)
        self._col_prev_v.set(
            f"📋  {schema}.{tbl}  —  {len(cols)} cols, {has_limit} with length limits")
        for col, dtype, ml, nullable in cols:
            limit = str(ml) if ml and ml > 0 else ("MAX" if ml == -1 else "—")
            tag   = "haslimit" if (ml and ml > 0) else "nolimit"
            self._col_tv.insert("", "end",
                                values=(col, dtype, limit, nullable), tags=(tag,))

    def _fetch_db_schema(self):
        server = self._db_server.get().strip()
        db     = self._db_name.get().strip()
        table  = self._db_table.get().strip()
        user   = self._db_user.get().strip()
        pwd    = self._db_pass.get().strip()
        if not server or not table:
            messagebox.showwarning("Missing Info",
                "Enter Server and Table name (or click a table in the browser)."); return

        def _run():
            self._q.put(self._prog_start)
            self._q.put(lambda: self._db_sv.set(f"Loading schema for {table}…"))
            try:
                schema = self._db_fetch(server, db, table, user, pwd)
                self._schema = schema
                self._q.put(lambda: self._db_sv.set(
                    f"✅  {len(schema)} columns loaded from {server} / {db} / {table}"))
                self._q.put(self._refresh_schema_summary)
            except Exception as ex:
                self._q.put(lambda: self._db_sv.set(f"❌  {ex}"))
            finally:
                self._q.put(self._prog_stop)

        threading.Thread(target=_run, daemon=True).start()

    def _db_fetch(self, server, db, table, user, pwd):
        if not pyodbc:
            raise RuntimeError("pyodbc not installed")
        conn = self._db_connect(server, db, user, pwd)
        cur  = conn.cursor()
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        sch, tbl = ("dbo", table) if "." not in table else table.split(".", 1)
        cur.execute("""
            SELECT
                c.name                              AS col_name,
                tp.name                             AS type_name,
                CASE
                    WHEN tp.name IN ('nvarchar','nchar') AND c.max_length = -1 THEN -1
                    WHEN tp.name IN ('nvarchar','nchar')                        THEN c.max_length / 2
                    WHEN tp.name IN ('varchar','char','binary','varbinary')
                         AND c.max_length = -1                                 THEN -1
                    WHEN tp.name IN ('varchar','char','binary','varbinary')     THEN c.max_length
                    ELSE NULL
                END AS char_limit
            FROM sys.columns  c
            JOIN sys.types    tp ON c.user_type_id = tp.user_type_id
            JOIN sys.tables   t  ON c.object_id    = t.object_id
            JOIN sys.schemas  s  ON t.schema_id    = s.schema_id
            WHERE s.name = ? AND t.name = ?
            ORDER BY c.column_id
        """, sch, tbl)
        result = {}
        for col, dtype, ml in cur.fetchall():
            lim = int(ml) if ml and ml > 0 else None
            result[col.lower()] = {"col": col, "limit": lim, "type": dtype}
        conn.close()
        return result

    def _db_connect(self, server, db, user, pwd):
        """Shared connection helper — connection timeout=10s, query timeout=30s."""
        if not pyodbc:
            raise RuntimeError("pyodbc not installed")
        drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
        if not drivers:
            raise RuntimeError("No SQL Server ODBC driver found on this machine")
        driver = next((d for d in drivers if "17" in d), drivers[0])
        # NOTE: ApplicationIntent=ReadOnly removed — can hang if no AG read replica
        if user:
            cs = (f"DRIVER={{{driver}}};SERVER={server};DATABASE={db};"
                  f"UID={user};PWD={pwd};TrustServerCertificate=yes;"
                  f"Connection Timeout=10")
        else:
            cs = (f"DRIVER={{{driver}}};SERVER={server};DATABASE={db};"
                  f"Trusted_Connection=yes;TrustServerCertificate=yes;"
                  f"Connection Timeout=10")
        conn = pyodbc.connect(cs, timeout=10)
        conn.timeout = 30   # query execution timeout (30s max per statement)
        return conn

    def _parse_schema_only(self):
        try:
            self._schema = self._parse_schema()
            self._refresh_schema_summary()
            messagebox.showinfo("Schema Parsed",
                                f"{len(self._schema)} columns loaded.")
        except Exception as ex:
            messagebox.showerror("Schema Error", str(ex))

    def _parse_schema(self):
        src = self._schema_src.get()
        if src == "DDL":
            return self._parse_ddl(self._ddl_txt.get("1.0", "end"))
        elif src == "DB":
            return self._schema
        else:
            return self._parse_manual(self._man_txt.get("1.0", "end"))

    def _parse_ddl(self, ddl):
        schema = {}
        # VARCHAR(n), NVARCHAR(n), CHAR(n), VARCHAR2(n)
        pat = re.compile(
            r'[\[\`"]?(\w+)[\]\`"]?\s+(?:N?VAR)?(?:CHAR|NCHAR|VARCHAR2|CLOB|STRING)'
            r'\s*\(\s*(\d+)\s*\)', re.IGNORECASE)
        for m in pat.finditer(ddl):
            schema[m.group(1).lower()] = {
                "col": m.group(1), "limit": int(m.group(2)), "type": "varchar"}
        if not schema:
            for m in re.finditer(r'(\w+)\s*[=,]\s*(\d+)', ddl):
                schema[m.group(1).lower()] = {
                    "col": m.group(1), "limit": int(m.group(2)), "type": "varchar"}
        return schema

    def _parse_manual(self, text):
        schema = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r'(\w+)\s*[=,]\s*(\d+)', line)
            if m:
                schema[m.group(1).lower()] = {
                    "col": m.group(1), "limit": int(m.group(2)), "type": "varchar"}
        return schema

    def _refresh_schema_summary(self):
        cols = [(v["col"], v["limit"]) for v in self._schema.values() if v.get("limit")]
        if not cols:
            self._schema_sv.set("Schema loaded but no length limits found.")
            return
        sample = ", ".join(f"{c}({l})" for c, l in cols[:10])
        extra  = f" … +{len(cols)-10} more" if len(cols) > 10 else ""
        self._schema_sv.set(
            f"✅  {len(self._schema)} columns, {len(cols)} with limits — {sample}{extra}")

    # ── load & scan ───────────────────────────────────────────────────────────
    def _load_and_scan(self):
        if not self._file_path:
            messagebox.showwarning("No File", "Browse and select a source file first."); return

        src = self._schema_src.get()

        # DB mode: auto-fetch schema if a table is selected but schema not loaded yet
        if src == "DB" and not self._schema:
            server = self._db_server.get().strip()
            table  = self._db_table.get().strip()
            db     = self._db_name.get().strip()
            user   = self._db_user.get().strip()
            pwd    = self._db_pass.get().strip()
            if not server or not table:
                messagebox.showwarning("No Schema",
                    "DB schema source selected but no table loaded.\n"
                    "Either:\n"
                    "  • Click '✅ Load Schema' on Tab ①, OR\n"
                    "  • Switch to DDL or Manual schema source."); return
            # Auto-fetch synchronously (blocking) with progress indicator
            self._status("Auto-loading schema before scan…"); self._prog_start()
            try:
                self._schema = self._db_fetch(server, db, table, user, pwd)
                self._refresh_schema_summary()
            except Exception as ex:
                self._prog_stop()
                messagebox.showerror("Schema Load Error",
                    f"Could not auto-load schema for '{table}':\n{ex}\n\n"
                    "Use the '✅ Load Schema' button on Tab ① first."); return
            finally:
                self._prog_stop()

        if src != "DB":
            try:
                self._schema = self._parse_schema()
            except Exception as ex:
                messagebox.showerror("Schema Error", str(ex)); return

        if not self._schema:
            messagebox.showwarning("No Schema", "Load or enter a column schema first."); return

        cols_with_limits = [k for k, v in self._schema.items() if v.get("limit")]
        if not cols_with_limits:
            messagebox.showwarning("No Limits",
                "Schema loaded but no column length limits found.\n"
                "Only VARCHAR / NVARCHAR columns are checked for truncation.\n"
                "Check your DDL or select the correct DB table."); return

        self._status("Loading file…"); self._prog_start()

        def _run():
            try:
                df = self._read_file()
                self._df = df
                issues   = self._scan(df)
                self._issues = issues
                self._q.put(lambda: self._populate_scan_tab(df, issues))
                self._q.put(lambda: self.nb.select(self.t_scan))
                self._q.put(lambda: self._status(
                    f"Scan done — {len(issues)} issues in "
                    f"{df.shape[0]:,} rows × {df.shape[1]} cols"))
            except Exception as ex:
                err = traceback.format_exc()
                self._q.put(lambda: messagebox.showerror("Load Error", f"{ex}\n\n{err}"))
                self._q.put(lambda: self._status(f"Error: {ex}"))
            finally:
                self._q.put(self._prog_stop)

        threading.Thread(target=_run, daemon=True).start()

    def _read_file(self):
        if not pd:
            raise RuntimeError(
                "pandas not installed.\nRun:  pip install pandas openpyxl")
        ext = self._file_ext
        if ext in (".xlsx", ".xls"):
            sheet = self._sheet_var.get() or 0
            return pd.read_excel(self._file_path, sheet_name=sheet,
                                 dtype=str, keep_default_na=False)
        dm = {"Comma (,)": ",", "Pipe (|)": "|",
              "Tab (\\t)": "\t", "Semicolon (;)": ";"}
        delim = dm.get(self._delim_var.get())
        if not delim:
            with open(self._file_path, "r", encoding="utf-8-sig", errors="replace") as f:
                sample = f.read(8192)
            try:
                delim = csv.Sniffer().sniff(sample, delimiters=",|\t;").delimiter
            except Exception:
                delim = ","
        return pd.read_csv(self._file_path, sep=delim, dtype=str,
                           keep_default_na=False, encoding="utf-8-sig",
                           on_bad_lines="skip")

    # ── Smart Truncation ──────────────────────────────────────────────────────

    _TAIL_SUFFIXES  = ["_id", "_code", "_num", "_nbr", "_ref", "_key",
                       "_no", "_acct", "_npi", "_rxcui", "_ndc", "_grp"]
    _TAIL_EQUALS    = ["id", "code", "num", "nbr", "ref", "key", "no", "acct"]
    _TAIL_CONTAINS  = ["newfin", "finid", "memid", "memno", "mbrno", "claimno",
                       "authno", "groupno", "groupid", "planid", "memberid",
                       "npi", "provid", "drugid", "rebate", "formulary", "rxcui",
                       "ndcid", "payer", "payid", "clientid", "vendorid",
                       "contid", "contractid", "enrollid", "subid", "batchid"]

    def _detect_strategy(self, col_name):
        """Return 'tail' for ID/code columns, 'head' for text/name columns.

        Tail strategy keeps the LAST N characters (strips leading prefixes
        like 'OR-', 'R', 'RX-' that Talend/upstream systems sometimes add).
        Head strategy keeps the FIRST N characters (natural for names/descriptions).
        """
        c = col_name.lower().replace(" ", "_").replace("-", "_")

        # Exact match
        if c in self._TAIL_EQUALS:
            return "tail"
        # Suffix match  (e.g. "newfin_id" ends with "_id")
        for sfx in self._TAIL_SUFFIXES:
            if c.endswith(sfx):
                return "tail"
        # Substring match (e.g. "claimno_2025" contains "claimno")
        for sub in self._TAIL_CONTAINS:
            if sub in c:
                return "tail"
        return "head"

    def _smart_truncate(self, col_name, value, limit):
        """Truncate value using the best strategy for this column type.

        Returns (proposed_str, mode_label).

        Strategy rules:
        - ID / code / number cols  → keep TAIL  (strip leading prefix, e.g. 'OR-')
        - Name / desc / text cols  → keep HEAD  (natural left-truncation)
        User can override via self._col_strategy[col_name] = 'head' | 'tail'
        """
        strategy = self._col_strategy.get(col_name) or self._detect_strategy(col_name)
        if strategy == "tail":
            return value[-limit:], "🎯 Auto-Tail"
        else:
            return value[:limit], "✂️ Auto-Head"

    def _scan(self, df):
        issues = []
        # Build column map (case-insensitive, also try replacing spaces↔underscores)
        self._col_map      = {}
        # Keep _col_strategy and _manual_col_map so user settings survive re-scan
        for fc in df.columns:
            key = fc.strip().lower()
            if key in self._schema:
                self._col_map[fc] = key
            else:
                # Try underscore↔space substitution for loose matching
                alt = key.replace(" ", "_")
                if alt in self._schema:
                    self._col_map[fc] = alt
                else:
                    alt2 = key.replace("_", " ")
                    if alt2 in self._schema:
                        self._col_map[fc] = alt2

        # Apply user-defined manual column overrides (survive re-scans)
        for fc, sk in self._manual_col_map.items():
            if sk in self._schema:
                self._col_map[fc] = sk

        if not self._col_map:
            # Surface a clear warning — file cols vs schema cols don't match
            file_cols   = [c.strip() for c in df.columns[:8]]
            schema_cols = [v["col"] for v in list(self._schema.values())[:8]]
            self._q.put(lambda: messagebox.showwarning(
                "No Column Matches",
                f"None of the file columns matched the DB schema.\n\n"
                f"File columns  :  {', '.join(file_cols)}\n"
                f"Schema columns:  {', '.join(schema_cols)}\n\n"
                "Check that you selected the correct table and sheet."))
            return issues

        for fc, sk in self._col_map.items():
            limit = self._schema[sk].get("limit")
            if not limit:
                continue
            for ridx, val in enumerate(df[fc]):
                if not val or (hasattr(pd, "isna") and pd.isna(val)):
                    continue
                s = str(val)
                if len(s) > limit:
                    proposed, trunc_mode = self._smart_truncate(fc, s, limit)
                    issues.append({
                        "row":      ridx + 2,
                        "row_idx":  ridx,
                        "col":      fc,
                        "original": s,
                        "length":   len(s),
                        "limit":    limit,
                        "over":     len(s) - limit,
                        "preview":  s[:100],
                        "proposed": proposed,
                        "mode":     trunc_mode,
                    })
        return issues

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — COMPARE & FIX
    # ══════════════════════════════════════════════════════════════════════════
    def _build_tab_scan(self):
        tab = self.t_scan

        # ── global header bar ─────────────────────────────────────────────────
        hdr = tk.Frame(tab, bg=C["surface"]); hdr.pack(fill="x", padx=0, pady=0)
        self._scan_sv = tk.StringVar(
            value="No scan yet — go to ① and click '🔍 Load File & Scan for Issues'.")
        tk.Label(hdr, textvariable=self._scan_sv, font=("Segoe UI", 10, "bold"),
                 bg=C["surface"], fg=C["yellow"]).pack(side="left", padx=12, pady=7)
        self._btn(hdr, "▶ Advanced Fix (Tab ③)",
                  self._proceed_to_autofix, C["green"]).pack(side="right", padx=(0, 10), pady=5)
        self._btn(hdr, "⚡ Fix All & Save",
                  self._one_click_fix_and_save, C["mauve"]).pack(side="right", padx=(0, 4), pady=5)
        self._btn(hdr, "🔄 Re-Run Scan",
                  self._load_and_scan, C["blue"]).pack(side="right", padx=(0, 4), pady=5)

        # ── vertical paned window: top = schema compare, bottom = row issues ──
        pane = tk.PanedWindow(tab, orient="vertical", sashwidth=7,
                              bg=C["overlay"], sashrelief="raised")
        pane.pack(fill="both", expand=True, padx=0, pady=0)

        # ╔══════════════════════════════════════════════════════╗
        # ║  TOP PANE — Schema Comparison                        ║
        # ╚══════════════════════════════════════════════════════╝
        top_outer = tk.Frame(pane, bg=C["bg"])
        pane.add(top_outer, minsize=140)

        top_hdr = tk.Frame(top_outer, bg=C["dark"]); top_hdr.pack(fill="x")
        tk.Label(top_hdr,
                 text="📊  Schema Comparison — File Columns vs DB Columns"
                      "   (click to filter issues · double-click ❓ to map column)",
                 font=("Segoe UI", 9, "bold"),
                 bg=C["dark"], fg=C["blue"]).pack(side="left", padx=10, pady=5)
        self._btn(top_hdr, "↩ Clear All Mappings",
                  self._clear_manual_mappings,
                  C["overlay"], fg=C["text"]).pack(side="right", padx=(0, 8), pady=4)
        # Legend
        for sym, clr, lbl in [
            ("■", "#a6e3a1", " ✅ Within limit "),
            ("■", "#f9e2af", " ⚠️ Over limit   "),
            ("■", "#f38ba8", " ❌ Critical      "),
            ("■", "#cba6f7", " 🔗 Manual match  "),
            ("■", "#fab387", " ❓ File col, no DB match (dbl-click to map) "),
            ("■", "#89b4fa", " ℹ️ DB col, not in file  "),
        ]:
            tk.Label(top_hdr, text=sym, fg=clr, bg=C["dark"],
                     font=("Consolas", 10)).pack(side="right")
            tk.Label(top_hdr, text=lbl, fg=C["subtext"], bg=C["dark"],
                     font=("Segoe UI", 8)).pack(side="right")

        tf_top = tk.Frame(top_outer, bg=C["bg"])
        tf_top.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        cmp_cols = ("status", "file_col", "file_max", "file_sample",
                    "db_col",  "db_type",  "db_limit", "issue_cnt", "strategy")
        self._cmp_tv = ttk.Treeview(tf_top, columns=cmp_cols, show="headings",
                                     selectmode="browse")
        for c, lbl, w in [
            ("status",      "Status",                          90),
            ("file_col",    "File Column",                    160),
            ("file_max",    "Max in File",                     85),
            ("file_sample", "Sample Value (first row)",        260),
            ("db_col",      "DB Column",                       160),
            ("db_type",     "DB Type",                          85),
            ("db_limit",    "DB Limit",                         75),
            ("issue_cnt",   "# Issues",                         70),
            ("strategy",    "Fix Strategy (right-click)",      150),
        ]:
            self._cmp_tv.heading(c, text=lbl)
            self._cmp_tv.column(c, width=w, minwidth=40)
        cvsb = ttk.Scrollbar(tf_top, orient="vertical",   command=self._cmp_tv.yview)
        chsb = ttk.Scrollbar(tf_top, orient="horizontal", command=self._cmp_tv.xview)
        self._cmp_tv.configure(yscrollcommand=cvsb.set, xscrollcommand=chsb.set)
        self._cmp_tv.grid(row=0, column=0, sticky="nsew")
        cvsb.grid(row=0, column=1, sticky="ns")
        chsb.grid(row=1, column=0, sticky="ew")
        tf_top.rowconfigure(0, weight=1); tf_top.columnconfigure(0, weight=1)
        # Tag colours for schema comparison rows
        self._cmp_tv.tag_configure("ok",       background="#0f2018", foreground="#a6e3a1")
        self._cmp_tv.tag_configure("near",     background="#2a2000", foreground="#f9e2af")
        self._cmp_tv.tag_configure("over",     background="#2D0A0A", foreground="#f38ba8")
        self._cmp_tv.tag_configure("fileonly", background="#2a1500", foreground="#fab387")
        self._cmp_tv.tag_configure("dbonly",   background="#0a1030", foreground="#89b4fa")
        self._cmp_tv.tag_configure("manual",   background="#0f1a2a", foreground="#cba6f7")
        self._cmp_tv.bind("<<TreeviewSelect>>", self._on_cmp_select)
        self._cmp_tv.bind("<Double-1>",         self._on_cmp_dblclick)
        self._cmp_tv.bind("<Button-3>",         self._cmp_context_menu)  # right-click

        # ╔══════════════════════════════════════════════════════╗
        # ║  BOTTOM PANE — Row-Level Issues                      ║
        # ╚══════════════════════════════════════════════════════╝
        bot_outer = tk.Frame(pane, bg=C["bg"])
        pane.add(bot_outer, minsize=180)

        bot_hdr = tk.Frame(bot_outer, bg=C["dark"]); bot_hdr.pack(fill="x")
        self._issues_filter_v = tk.StringVar(value="Showing: ALL columns")
        tk.Label(bot_hdr, textvariable=self._issues_filter_v,
                 font=("Segoe UI", 9, "bold"), bg=C["dark"], fg=C["teal"]).pack(
                 side="left", padx=10, pady=5)
        self._btn(bot_hdr, "Show All Columns",
                  lambda: self._filter_issues_by_col(None),
                  C["overlay"], fg=C["text"]).pack(side="left", padx=4, pady=4)
        tk.Label(bot_hdr,
                 text="  ↕ Double-click row to edit Proposed Fix",
                 font=("Segoe UI", 8, "italic"), bg=C["dark"],
                 fg=C["subtext"]).pack(side="left", padx=10)

        tf_bot = tk.Frame(bot_outer, bg=C["bg"])
        tf_bot.pack(fill="both", expand=True, padx=6, pady=(0, 0))
        iss_cols = ("row", "col", "db_limit", "orig_len", "over",
                    "original", "proposed", "mode")
        self._scan_tv = ttk.Treeview(tf_bot, columns=iss_cols, show="headings",
                                      selectmode="browse")
        for c, lbl, w in [
            ("row",      "Row #",                               56),
            ("col",      "Column",                             140),
            ("db_limit", "DB Limit",                            72),
            ("orig_len", "Actual Len",                          80),
            ("over",     "Over By",                             70),
            ("original", "Original Value (first 80 chars)",    290),
            ("proposed", "✏️ Proposed Fix (dbl-click to edit)", 290),
            ("mode",     "Mode",                                88),
        ]:
            self._scan_tv.heading(c, text=lbl)
            self._scan_tv.column(c, width=w, minwidth=40)
        svsb = ttk.Scrollbar(tf_bot, orient="vertical",   command=self._scan_tv.yview)
        shsb = ttk.Scrollbar(tf_bot, orient="horizontal", command=self._scan_tv.xview)
        self._scan_tv.configure(yscrollcommand=svsb.set, xscrollcommand=shsb.set)
        self._scan_tv.grid(row=0, column=0, sticky="nsew")
        svsb.grid(row=0, column=1, sticky="ns")
        shsb.grid(row=1, column=0, sticky="ew")
        tf_bot.rowconfigure(0, weight=1); tf_bot.columnconfigure(0, weight=1)
        self._scan_tv.tag_configure("critical",
            background="#2D0A0A", foreground="#f38ba8")
        self._scan_tv.tag_configure("warning",
            background="#2D1F00", foreground="#f9e2af")
        self._scan_tv.tag_configure("manual",
            background="#0A1A2D", foreground="#89b4fa")
        self._scan_tv.bind("<Double-1>", self._edit_proposed_fix)

        # ── bottom action bar ─────────────────────────────────────────────────
        bf = tk.Frame(bot_outer, bg=C["surface"]); bf.pack(fill="x")
        self._btn(bf, "💾 Export Issues Report", self._export_scan_report,
                  C["overlay"], fg=C["text"]).pack(side="left", padx=8, pady=5)
        self._btn(bf, "✏️ Edit Selected Fix", self._edit_proposed_fix_btn,
                  C["teal"]).pack(side="left", padx=4, pady=5)

    def _proceed_to_autofix(self):
        if not hasattr(self, '_issues') or self._issues is None:
            messagebox.showwarning("No Scan Run",
                "Please run a scan first.\n"
                "Click '🔄 Re-Run Scan' or go to Tab ① and click '🔍 Load File & Scan for Issues'.")
            return
        if not self._issues:
            if not messagebox.askyesno("No Issues Found",
                "The scan found NO truncation issues — the file appears clean.\n\n"
                "Do you still want to proceed to the Auto-Fix tab?"):
                return
        self.nb.select(self.t_fix)

    def _edit_proposed_fix_btn(self):
        """Triggered by the Edit Selected Fix button."""
        self._edit_proposed_fix()

    def _edit_proposed_fix(self, event=None):
        """Double-click or button handler — opens modal to edit a proposed fix."""
        sel = self._scan_tv.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Click a row to select it first."); return
        iid = sel[0]
        if not iid.startswith("iss_"):
            return
        idx = int(iid[4:])
        iss = self._issues[idx]

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Edit Proposed Fix — {iss['col']}  (DB Limit: {iss['limit']} chars)")
        dlg.geometry("820x500")
        dlg.configure(bg=C["bg"])
        dlg.resizable(True, True)
        dlg.grab_set()

        # Info bar
        info = tk.Frame(dlg, bg=C["surface"]); info.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(info, text=f"Column: {iss['col']}",
                 bg=C["surface"], fg=C["blue"],
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=10, pady=6)
        tk.Label(info,
                 text=(f"  DB Limit: {iss['limit']} chars   |"
                       f"   Original: {iss['length']} chars   |"
                       f"   Over by: +{iss['over']} chars"),
                 bg=C["surface"], fg=C["yellow"],
                 font=("Segoe UI", 9)).pack(side="left", padx=6, pady=6)

        # Original value (read-only)
        of = tk.LabelFrame(dlg, text="  Original Value (read-only)  ",
                           font=("Segoe UI", 9, "bold"),
                           bg=C["surface"], fg=C["red"], relief="flat")
        of.pack(fill="x", padx=10, pady=(0, 4))
        orig_txt = scrolledtext.ScrolledText(
            of, height=3, bg=C["dark"], fg=C["red"],
            font=("Consolas", 9), relief="flat", wrap="word")
        orig_txt.insert("1.0", iss["original"])
        orig_txt.configure(state="disabled")
        orig_txt.pack(fill="both", padx=8, pady=4)

        # Proposed fix (editable)
        pf = tk.LabelFrame(dlg,
                            text=f"  Proposed Fix  (max {iss['limit']} chars — edit freely)  ",
                            font=("Segoe UI", 9, "bold"),
                            bg=C["surface"], fg=C["green"], relief="flat")
        pf.pack(fill="both", expand=True, padx=10, pady=(0, 4))
        char_v = tk.StringVar()
        fix_txt = scrolledtext.ScrolledText(
            pf, height=4,
            bg=C["overlay"], fg=C["green"],
            insertbackground=C["text"], font=("Consolas", 9),
            relief="flat", wrap="word")
        cur_proposed = iss.get("proposed") or self._smart_truncate(iss["col"], iss["original"], iss["limit"])[0]
        fix_txt.insert("1.0", cur_proposed)
        fix_txt.pack(fill="both", expand=True, padx=8, pady=(4, 0))

        # Quick-fill buttons: Head / Tail
        qf = tk.Frame(pf, bg=C["surface"]); qf.pack(fill="x", padx=8, pady=(2, 0))
        tk.Label(qf, text="Quick-fill:", bg=C["surface"], fg=C["subtext"],
                 font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
        head_fix = iss["original"][:iss["limit"]]
        tail_fix = iss["original"][-iss["limit"]:]
        def _apply_head():
            fix_txt.delete("1.0", "end"); fix_txt.insert("1.0", head_fix); _update_count()
        def _apply_tail():
            fix_txt.delete("1.0", "end"); fix_txt.insert("1.0", tail_fix); _update_count()
        self._btn(qf, f"✂️ Head → '{head_fix[:30]}{'…' if len(head_fix)>30 else ''}'",
                  _apply_head, C["overlay"], fg=C["text"]).pack(side="left", padx=2)
        self._btn(qf, f"🎯 Tail → '{tail_fix[:30]}{'…' if len(tail_fix)>30 else ''}'",
                  _apply_tail, C["teal"]).pack(side="left", padx=2)

        def _update_count(e=None):
            n    = len(fix_txt.get("1.0", "end-1c"))
            over = n - iss["limit"]
            if over > 0:
                char_v.set(f"⚠️  {n} chars  —  {over} OVER limit! (will still save as-is)")
            else:
                char_v.set(f"✅  {n} / {iss['limit']} chars")
        fix_txt.bind("<KeyRelease>", _update_count)
        _update_count()

        tk.Label(pf, textvariable=char_v, bg=C["surface"], fg=C["teal"],
                 font=("Segoe UI", 9, "bold")).pack(anchor="e", padx=8, pady=(0, 4))

        def _save():
            new_val = fix_txt.get("1.0", "end-1c")
            iss["proposed"] = new_val
            iss["mode"]     = "✏️ Manual"
            self._scan_tv.item(f"iss_{idx}", values=(
                iss["row"], iss["col"], iss["limit"], iss["length"],
                f"+{iss['over']}", iss["original"][:80], new_val[:80], "✏️ Manual",
            ), tags=("manual",))
            dlg.destroy()

        def _reset():
            smart_fix, _ = self._smart_truncate(iss["col"], iss["original"], iss["limit"])
            fix_txt.delete("1.0", "end")
            fix_txt.insert("1.0", smart_fix)
            _update_count()

        btns = tk.Frame(dlg, bg=C["bg"]); btns.pack(fill="x", padx=10, pady=8)
        self._btn(btns, "✅ Save Fix", _save,
                  C["green"]).pack(side="left", padx=(0, 8))
        self._btn(btns, "↩ Reset to Auto-Truncate", _reset,
                  C["overlay"], fg=C["text"]).pack(side="left", padx=(0, 8))
        self._btn(btns, "❌ Cancel", dlg.destroy,
                  C["red"]).pack(side="left")
        dlg.wait_window()

    def _one_click_fix_and_save(self):
        """Apply all proposed fixes (auto + manual edits) and save in one click."""
        if self._issues is None:
            messagebox.showwarning("No Scan Run",
                "Run a scan first — go to Tab ① and click '🔍 Load File & Scan'."); return
        if not self._issues:
            messagebox.showinfo("File Is Clean",
                "No truncation issues found — nothing to fix!"); return
        if self._df is None:
            messagebox.showwarning("No File", "No file loaded."); return

        base, ext = os.path.splitext(self._file_path)
        out_path  = f"{base}_FIXED{ext}"

        manual_count = sum(1 for i in self._issues if i.get("mode") == "✏️ Manual")
        auto_count   = len(self._issues) - manual_count
        if not messagebox.askyesno("Confirm Fix & Save",
                f"Ready to fix {len(self._issues)} cell(s) and save:\n\n"
                f"  🤖 Auto-truncated : {auto_count}\n"
                f"  ✏️  Manually edited : {manual_count}\n\n"
                f"Output file:\n  {out_path}\n\n"
                f"Proceed?"):
            return

        def _run():
            self._q.put(self._prog_start)
            self._q.put(lambda: self._status("Applying fixes…"))
            try:
                df      = self._df.copy()
                changes = []
                total   = len(self._issues)
                for idx2, iss in enumerate(self._issues):
                    fc       = iss["col"]
                    ridx     = iss["row_idx"]
                    proposed = iss.get("proposed") or self._smart_truncate(iss["col"], iss["original"], iss["limit"])[0]
                    df.at[ridx, fc] = proposed
                    changes.append({
                        "row":      iss["row"],
                        "row_idx":  ridx,
                        "col":      fc,
                        "original": iss["original"],
                        "fixed":    proposed,
                        "orig_len": iss["length"],
                        "fix_len":  len(proposed),
                        "limit":    iss["limit"],
                        "mode":     iss.get("mode", "🤖 Auto"),
                    })
                    pct = int((idx2 + 1) / total * 100)
                    self._q.put(lambda p=pct: self._fix_prog.configure(value=p))
                self._fixed_df   = df
                self._change_log = changes
                self._save_file(df, out_path)
                self._out_path   = out_path
                self._q.put(lambda: self._show_fix_summary(changes, out_path))
                self._q.put(lambda: self._refresh_log_tab(changes))
                self._q.put(lambda: self.nb.select(self.t_log))
                self._q.put(lambda: self._status(
                    f"✅ {len(changes)} cells fixed → {out_path}"))
            except Exception as ex:
                err = traceback.format_exc()
                self._q.put(lambda: messagebox.showerror("Fix Error", f"{ex}\n\n{err}"))
                self._q.put(lambda: self._status(f"Error: {ex}"))
            finally:
                self._q.put(self._prog_stop)

        threading.Thread(target=_run, daemon=True).start()

    def _build_col_comparison(self, df):
        """Returns list of dicts describing each column's match status and stats."""
        rows = []
        schema     = self._schema
        col_map    = self._col_map     # {file_col: schema_key}
        issues_map = {}               # {file_col: count}
        if self._issues:
            for iss in self._issues:
                issues_map[iss["col"]] = issues_map.get(iss["col"], 0) + 1

        file_matched = set()
        db_matched   = set()

        # ── matched columns ───────────────────────────────────────────────────
        for fc, sk in col_map.items():
            file_matched.add(fc)
            db_matched.add(sk)
            sv       = schema[sk]
            db_limit = sv.get("limit")
            db_type  = sv.get("type", "?")
            db_col   = sv["col"]
            is_manual = fc in self._manual_col_map

            vals = df[fc].astype(str)
            max_len = int(vals.str.len().max()) if len(vals) > 0 else 0
            sample  = str(df[fc].iloc[0])[:60] if len(df) > 0 else ""
            n_issues = issues_map.get(fc, 0)

            if is_manual:
                status, tag = "🔗 Manually mapped", "manual"
            elif n_issues > 0 and max_len > (db_limit or 0) * 1.2:
                status, tag = "❌ Critical — values exceed limit", "over"
            elif n_issues > 0:
                status, tag = "⚠️ Over limit — truncation needed", "near"
            elif db_limit and max_len > db_limit * 0.9:
                status, tag = "⚡ Near limit — monitor closely", "near"
            else:
                status, tag = "✅ Within limit", "ok"

            rows.append({
                "status":      status,
                "file_col":    fc,
                "file_max":    str(max_len),
                "file_sample": sample,
                "db_col":      db_col,
                "db_type":     db_type,
                "db_limit":    str(db_limit) if db_limit else "—",
                "issue_cnt":   str(n_issues) if n_issues else "—",
                "strategy":    self._strategy_label(fc),
                "tag":         tag,
            })

        # ── file cols with no DB match ────────────────────────────────────────
        for fc in df.columns:
            if fc in file_matched:
                continue
            vals    = df[fc].astype(str)
            max_len = int(vals.str.len().max()) if len(vals) > 0 else 0
            sample  = str(df[fc].iloc[0])[:60] if len(df) > 0 else ""
            rows.append({
                "status":      "❓ File col — no matching DB column",
                "file_col":    fc,
                "file_max":    str(max_len),
                "file_sample": sample,
                "db_col":      "— (no DB match)",
                "db_type":     "—",
                "db_limit":    "—",
                "issue_cnt":   "—",
                "strategy":    "— (map column first)",
                "tag":         "fileonly",
            })

        # ── DB cols with no file match ────────────────────────────────────────
        for sk, sv in schema.items():
            if sk in db_matched:
                continue
            rows.append({
                "status":      "ℹ️ DB col — not present in file",
                "file_col":    "— (not in file)",
                "file_max":    "—",
                "file_sample": "—",
                "db_col":      sv["col"],
                "db_type":     sv.get("type", "?"),
                "db_limit":    str(sv.get("limit")) if sv.get("limit") else "—",
                "issue_cnt":   "—",
                "strategy":    "—",
                "tag":         "dbonly",
            })
        return rows

    def _strategy_label(self, col_name):
        """Human-readable label for the current truncation strategy of a column."""
        strat = self._col_strategy.get(col_name) or self._detect_strategy(col_name)
        auto  = "auto" not in (self._col_strategy.get(col_name) or "auto")
        prefix = "👤 " if col_name in self._col_strategy else "🤖 "
        if strat == "tail":
            return f"{prefix}Tail — keep last N chars (ID)"
        else:
            return f"{prefix}Head — keep first N chars (Text)"

    def _cmp_context_menu(self, event):
        """Right-click context menu on schema comparison row for strategy toggle."""
        iid = self._cmp_tv.identify_row(event.y)
        if not iid:
            return
        self._cmp_tv.selection_set(iid)
        vals = self._cmp_tv.item(iid, "values")
        if not vals:
            return
        file_col = vals[1].strip()
        if file_col.startswith("—"):
            return  # DB-only row, no strategy

        tags = self._cmp_tv.item(iid, "tags")
        current = self._col_strategy.get(file_col) or self._detect_strategy(file_col)

        menu = tk.Menu(self.root, tearoff=0)
        menu.configure(bg=C["surface"], fg=C["text"],
                       activebackground=C["mauve"], activeforeground=C["bg"],
                       font=("Segoe UI", 10))
        menu.add_command(
            label=f"Column: {file_col}",
            state="disabled",
            font=("Segoe UI", 9, "bold"))
        menu.add_separator()

        if current != "tail":
            menu.add_command(
                label="🎯 Use Tail Truncation (keep last N chars)  ← for ID/code columns",
                command=lambda: self._set_col_strategy(file_col, "tail"))
        if current != "head":
            menu.add_command(
                label="✂️ Use Head Truncation (keep first N chars) ← for name/text columns",
                command=lambda: self._set_col_strategy(file_col, "head"))

        if file_col in self._col_strategy:
            menu.add_separator()
            menu.add_command(
                label="↩ Reset to Auto-Detect",
                command=lambda: self._set_col_strategy(file_col, None))

        # Strategy preview
        if self._df is not None and file_col in self._df.columns:
            sk = self._col_map.get(file_col)
            if sk:
                limit = self._schema[sk].get("limit")
                if limit:
                    # Find first over-limit value for preview
                    col_data = self._df[file_col].astype(str)
                    over_vals = col_data[col_data.str.len() > limit]
                    if len(over_vals) > 0:
                        sample_val = str(over_vals.iloc[0])
                        head_fix   = sample_val[:limit]
                        tail_fix   = sample_val[-limit:]
                        menu.add_separator()
                        menu.add_command(
                            label=f"  Example: '{sample_val[:30]}...' (len={len(sample_val)})",
                            state="disabled")
                        menu.add_command(
                            label=f"  ✂️ Head → '{head_fix}'",
                            state="disabled")
                        menu.add_command(
                            label=f"  🎯 Tail → '{tail_fix}'",
                            state="disabled")

        menu.add_separator()
        menu.add_command(
            label="🔗 Map to Different DB Column...",
            command=lambda: self._map_column_dialog(file_col)
                    if "fileonly" in tags else None,
            state="normal" if "fileonly" in tags else "disabled")

        menu.tk_popup(event.x_root, event.y_root)

    def _set_col_strategy(self, file_col, strategy):
        """Set or clear the truncation strategy for a column and re-scan."""
        if strategy is None:
            self._col_strategy.pop(file_col, None)
            msg = f"'{file_col}' reset to auto-detect"
        else:
            self._col_strategy[file_col] = strategy
            label = "Tail (keep last N chars)" if strategy == "tail" else "Head (keep first N chars)"
            msg = f"'{file_col}' → {label}"
        self._rerun_comparison()
        self._status(f"Strategy updated: {msg}")

    def _on_cmp_dblclick(self, event=None):
        """Double-click on schema comparison row:
           - If ❓ file-only row: open column-mapping dialog
           - If 🔗 manual match: offer to remove the mapping
        """
        sel = self._cmp_tv.selection()
        if not sel:
            return
        item    = sel[0]
        tags    = self._cmp_tv.item(item, "tags")
        vals    = self._cmp_tv.item(item, "values")
        if not vals:
            return
        file_col = vals[1].strip()
        if "fileonly" in tags:
            self._map_column_dialog(file_col)
        elif "manual" in tags:
            if messagebox.askyesno("Remove Manual Mapping",
                f"Remove the manual mapping for '{file_col}'?\n\n"
                "The column will revert to ❓ (no DB match)."):
                self._manual_col_map.pop(file_col, None)
                self._rerun_comparison()

    def _map_column_dialog(self, file_col):
        """Show a dialog to manually map a file column to a DB column."""
        if not self._schema:
            messagebox.showwarning("No Schema", "Load a DB schema first."); return

        # DB columns NOT already mapped (to avoid duplicate mappings)
        already_mapped = set(self._col_map.values())
        available_db_cols = sorted(
            [v["col"] for k, v in self._schema.items()
             if k not in already_mapped or k == self._manual_col_map.get(file_col)],
            key=str.lower
        )
        if not available_db_cols:
            messagebox.showinfo("No Available Columns",
                "All DB columns are already mapped to file columns."); return

        # ── build dialog ────────────────────────────────────────────────────
        dlg = tk.Toplevel(self.root)
        dlg.title("🔗 Map File Column → DB Column")
        dlg.configure(bg=C["bg"])
        dlg.resizable(False, False)
        dlg.grab_set()

        # Center dialog
        dlg.update_idletasks()
        pw, ph = 540, 310
        sx = self.root.winfo_x() + (self.root.winfo_width()  - pw) // 2
        sy = self.root.winfo_y() + (self.root.winfo_height() - ph) // 2
        dlg.geometry(f"{pw}x{ph}+{sx}+{sy}")

        def lbl(parent, text, bold=False, fg=None):
            font = ("Segoe UI", 10, "bold") if bold else ("Segoe UI", 10)
            tk.Label(parent, text=text, font=font,
                     bg=C["bg"], fg=fg or C["text"]).pack(anchor="w", padx=16, pady=(8, 0))

        lbl(dlg, "File Column (source file):", bold=True)
        lbl(dlg, f"  {file_col}", fg=C["yellow"])

        # Show some stats for the file column
        if self._df is not None and file_col in self._df.columns:
            vals_ser = self._df[file_col].astype(str)
            max_len  = int(vals_ser.str.len().max())
            sample   = str(self._df[file_col].iloc[0])[:60] if len(self._df) > 0 else "—"
            lbl(dlg, f"  Max length: {max_len}   |   Sample: {sample}", fg=C["subtext"])

        lbl(dlg, "Map to DB Column:", bold=True)

        combo_var = tk.StringVar()
        # Pre-fill if already manually mapped
        current = self._manual_col_map.get(file_col)
        if current and current in self._schema:
            combo_var.set(self._schema[current]["col"])

        combo_frame = tk.Frame(dlg, bg=C["bg"])
        combo_frame.pack(fill="x", padx=16, pady=4)
        combo = ttk.Combobox(combo_frame, textvariable=combo_var,
                             values=available_db_cols, state="readonly",
                             font=("Segoe UI", 10), width=44)
        combo.pack(side="left", fill="x", expand=True)

        lbl(dlg, "Tip: Pick the DB column whose type/limit should apply to this file column.",
            fg=C["subtext"])

        btn_row = tk.Frame(dlg, bg=C["bg"]); btn_row.pack(pady=14)

        def do_map():
            chosen = combo_var.get().strip()
            if not chosen:
                messagebox.showwarning("No Selection", "Please pick a DB column.", parent=dlg)
                return
            # Find the schema_key for the chosen db_col name
            sk = next((k for k, v in self._schema.items()
                       if v["col"].lower() == chosen.lower()), None)
            if sk is None:
                messagebox.showerror("Not Found",
                    f"DB column '{chosen}' not found in schema.", parent=dlg); return
            self._manual_col_map[file_col] = sk
            dlg.destroy()
            self._rerun_comparison()

        self._btn(btn_row, "🔗 Map & Re-Scan", do_map, C["mauve"]).pack(
            side="left", padx=8)
        self._btn(btn_row, "Cancel", dlg.destroy, C["overlay"],
                  fg=C["text"]).pack(side="left", padx=4)

    def _rerun_comparison(self):
        """Re-run the scan with the current manual mappings and refresh Tab 2."""
        if self._df is None:
            return
        self._issues  = self._scan(self._df)
        self._populate_scan_tab(self._df, self._issues)
        n = len(self._manual_col_map)
        self._status(f"Re-scanned — {len(self._issues)} issues"
                     f"  |  {n} manual mapping{'s' if n != 1 else ''} active")

    def _clear_manual_mappings(self):
        """Remove all user-defined manual column mappings and re-scan."""
        if not self._manual_col_map:
            messagebox.showinfo("Nothing to Clear", "No manual mappings are active.")
            return
        n = len(self._manual_col_map)
        if not messagebox.askyesno("Clear Mappings",
            f"Remove all {n} manual column mapping{'s' if n != 1 else ''}?"):
            return
        self._manual_col_map.clear()
        self._rerun_comparison()

    def _on_cmp_select(self, event=None):
        """Filter row-level issues pane when user clicks a schema comparison row."""
        sel = self._cmp_tv.selection()
        if not sel:
            return
        vals = self._cmp_tv.item(sel[0], "values")
        if not vals:
            return
        # vals index 1 = file_col, index 4 = db_col
        file_col = vals[1].strip()
        if file_col.startswith("—"):
            self._filter_issues_by_col(None)
        else:
            self._filter_issues_by_col(file_col)

    def _filter_issues_by_col(self, file_col):
        """Show only issues for the given file_col, or all if None."""
        self._scan_tv.delete(*self._scan_tv.get_children())
        if self._issues is None:
            return
        if file_col:
            self._issues_filter_v.set(f"Showing: '{file_col}'  (click 'Show All' to reset)")
            filtered = [(i, iss) for i, iss in enumerate(self._issues)
                        if iss["col"] == file_col]
        else:
            self._issues_filter_v.set("Showing: ALL columns")
            filtered = list(enumerate(self._issues))

        for idx, iss in filtered:
            mode     = iss.get("mode", "🤖 Auto")
            proposed = iss.get("proposed") or self._smart_truncate(iss["col"], iss["original"], iss["limit"])[0]
            if mode == "✏️ Manual":
                tag = "manual"
            elif iss["over"] > 20:
                tag = "critical"
            else:
                tag = "warning"
            self._scan_tv.insert("", "end", iid=f"iss_{idx}", values=(
                iss["row"], iss["col"], iss["limit"], iss["length"],
                f"+{iss['over']}", iss["original"][:80], proposed[:80], mode,
            ), tags=(tag,))

    def _populate_scan_tab(self, df, issues):
        # ── populate schema comparison (top pane) ────────────────────────────
        self._cmp_tv.delete(*self._cmp_tv.get_children())
        cmp_rows = self._build_col_comparison(df)
        for r in cmp_rows:
            self._cmp_tv.insert("", "end", values=(
                r["status"], r["file_col"], r["file_max"], r["file_sample"],
                r["db_col"],  r["db_type"],  r["db_limit"], r["issue_cnt"],
                r.get("strategy", "—"),
            ), tags=(r["tag"],))

        # ── header status ─────────────────────────────────────────────────────
        n_over    = sum(1 for r in cmp_rows if r["tag"] in ("over", "near"))
        n_fileonly= sum(1 for r in cmp_rows if r["tag"] == "fileonly")
        n_dbonly  = sum(1 for r in cmp_rows if r["tag"] == "dbonly")
        if not issues:
            self._scan_sv.set(
                f"✅  ALL CLEAN — {df.shape[0]:,} rows × {df.shape[1]} cols  |  "
                f"{len(cmp_rows)} cols compared  |  0 truncation issues  "
                f"|  ❓ {n_fileonly} file-only  |  ℹ️ {n_dbonly} DB-only cols")
        else:
            col_c    = {}
            for iss in issues:
                col_c[iss["col"]] = col_c.get(iss["col"], 0) + 1
            affected = len({i["row_idx"] for i in issues})
            top = ", ".join(f"{c}({n})" for c, n in
                            sorted(col_c.items(), key=lambda x: -x[1])[:4])
            self._scan_sv.set(
                f"⚠️  {len(issues):,} issues  |  {len(col_c)} cols affected  |  "
                f"{affected:,} rows  |  Top: {top}  "
                f"|  ❓ {n_fileonly} file-only  |  ℹ️ {n_dbonly} DB-only")

        # ── populate row-level issues (bottom pane) ───────────────────────────
        self._issues_filter_v.set("Showing: ALL columns")
        self._filter_issues_by_col(None)

    def _export_scan_report(self):
        if not self._issues:
            messagebox.showinfo("Nothing to export", "Run a scan first."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Excel", "*.xlsx"), ("Text", "*.txt")])
        if not path: return
        ext = os.path.splitext(path)[1].lower()
        if ext == ".xlsx":
            self._xlsx_issues(path)
        elif ext == ".txt":
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"Talend Auto-Fix — Scan Report\n")
                f.write(f"File  : {self._file_path}\n")
                f.write(f"Issues: {len(self._issues)}\n")
                f.write(f"Date  : {datetime.now():%Y-%m-%d %H:%M}\n{'='*70}\n")
                for i in self._issues:
                    f.write(f"Row {i['row']:<6} {i['col']:<30} "
                            f"len={i['length']} limit={i['limit']} +{i['over']}\n")
        else:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["Row #", "Column", "Actual Len", "DB Limit", "Over By", "Value Preview"])
                for i in self._issues:
                    w.writerow([i["row"], i["col"], i["length"],
                                i["limit"], f"+{i['over']}", i["preview"]])
        messagebox.showinfo("Exported", f"Saved to:\n{path}")

    def _xlsx_issues(self, path):
        import openpyxl as ox
        from openpyxl.styles import Font, PatternFill
        wb = ox.Workbook(); ws = wb.active; ws.title = "Issues"
        hf = Font(bold=True, color="FFFFFF")
        hfill = PatternFill("solid", fgColor="C0392B")
        for ci, h in enumerate(["Row #", "Column", "Actual Len", "DB Limit", "Over By", "Value Preview"], 1):
            c = ws.cell(row=1, column=ci, value=h); c.font = hf; c.fill = hfill
        for ri, i in enumerate(self._issues, 2):
            ws.cell(row=ri, column=1, value=i["row"])
            ws.cell(row=ri, column=2, value=i["col"])
            ws.cell(row=ri, column=3, value=i["length"])
            ws.cell(row=ri, column=4, value=i["limit"])
            ws.cell(row=ri, column=5, value=f"+{i['over']}")
            ws.cell(row=ri, column=6, value=i["preview"][:500])
        wb.save(path)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — AUTO-FIX & SAVE
    # ══════════════════════════════════════════════════════════════════════════
    def _build_tab_fix(self):
        tab = self._scrollable_tab(self.t_fix)

        # Strategy
        lf1 = self._lf(tab, "✂️  Step 3a — Fix Strategy")
        lf1.pack(fill="x", padx=14, pady=(12, 6))
        self._strategy = tk.StringVar(value="exact")
        for val, lbl in [
            ("exact",  "Truncate to exact DB limit  (keeps first N chars, most common)"),
            ("buffer", "Truncate with safety buffer  (keeps N − buffer chars)"),
            ("word",   "Smart word-boundary truncate  (avoids cutting mid-word)"),
        ]:
            tk.Radiobutton(lf1, text=lbl, variable=self._strategy, value=val,
                           bg=C["surface"], fg=C["text"], selectcolor=C["overlay"],
                           activebackground=C["surface"],
                           font=("Segoe UI", 9)).pack(anchor="w", padx=14, pady=2)
        br = tk.Frame(lf1, bg=C["surface"]); br.pack(anchor="w", padx=30, pady=(0, 6))
        tk.Label(br, text="Buffer chars:", bg=C["surface"], fg=C["subtext"],
                 font=("Segoe UI", 9)).pack(side="left")
        self._buffer = tk.IntVar(value=5)
        tk.Spinbox(br, from_=1, to=50, textvariable=self._buffer, width=5,
                   bg=C["overlay"], fg=C["text"], font=("Segoe UI", 9)).pack(side="left", padx=6)
        tk.Label(br, text="(used only with 'buffer' strategy)",
                 bg=C["surface"], fg=C["subtext"], font=("Segoe UI", 8)).pack(side="left")

        # Output
        lf2 = self._lf(tab, "💾  Step 3b — Output / Save Options")
        lf2.pack(fill="x", padx=14, pady=6)
        self._out_mode = tk.StringVar(value="newfile")
        for val, lbl in [
            ("newfile",   "Save as new file  (original kept safe — recommended first run)"),
            ("overwrite", "Overwrite original file  (replaces in-place — use for Talend re-ingestion)"),
            ("custom",    "Save to custom path"),
        ]:
            tk.Radiobutton(lf2, text=lbl, variable=self._out_mode, value=val,
                           bg=C["surface"], fg=C["text"], selectcolor=C["overlay"],
                           activebackground=C["surface"], font=("Segoe UI", 9),
                           command=self._toggle_custom_path).pack(anchor="w", padx=14, pady=2)

        cp = tk.Frame(lf2, bg=C["surface"]); cp.pack(fill="x", padx=30, pady=(0, 6))
        self._out_path_v = tk.StringVar()
        self._out_entry = tk.Entry(cp, textvariable=self._out_path_v, width=55,
                                   bg=C["overlay"], fg=C["text"],
                                   insertbackground=C["text"],
                                   font=("Consolas", 9), relief="flat", state="disabled")
        self._out_entry.pack(side="left", padx=(0, 6), ipady=3)
        self._out_browse = tk.Button(cp, text="Browse…", command=self._browse_out,
                                     bg=C["overlay"], fg=C["text"], font=("Segoe UI", 9),
                                     relief="flat", state="disabled", cursor="hand2")
        self._out_browse.pack(side="left")

        fr = tk.Frame(lf2, bg=C["surface"]); fr.pack(fill="x", padx=14, pady=(0, 8))
        tk.Label(fr, text="Save format:", bg=C["surface"], fg=C["subtext"],
                 font=("Segoe UI", 9)).pack(side="left")
        self._out_fmt = tk.StringVar(value="Same as input")
        ttk.Combobox(fr, textvariable=self._out_fmt, width=22, state="readonly",
                     values=["Same as input", "CSV (,)", "Pipe (|)", "Tab (\\t)",
                             "Excel XLSX"]).pack(side="left", padx=6)

        # Execute
        lf3 = self._lf(tab, "⚡  Step 3c — Execute Auto-Fix")
        lf3.pack(fill="x", padx=14, pady=6)
        er = tk.Frame(lf3, bg=C["surface"]); er.pack(fill="x", padx=14, pady=10)
        self._btn(er, "⚡  AUTO-FIX & SAVE FILE",
                  self._execute_fix, "#a6e3a1", size=13, padx=24, pady=8).pack(side="left", padx=(0, 16))
        self._fix_sv = tk.StringVar(value="Ready — click to apply all fixes.")
        tk.Label(er, textvariable=self._fix_sv, bg=C["surface"], fg=C["text"],
                 font=("Segoe UI", 10)).pack(side="left")
        self._fix_prog = ttk.Progressbar(lf3, length=580, mode="determinate",
                                          style="Horizontal.TProgressbar")
        self._fix_prog.pack(fill="x", padx=14, pady=(0, 8))

        # Result
        lf4 = self._lf(tab, "📊  Fix Summary")
        lf4.pack(fill="both", expand=True, padx=14, pady=6)
        self._fix_out = scrolledtext.ScrolledText(
            lf4, height=8, bg=C["overlay"], fg=C["green"],
            font=("Consolas", 9), relief="flat", state="disabled")
        self._fix_out.pack(fill="both", expand=True, padx=8, pady=6)

    def _toggle_custom_path(self):
        s = "normal" if self._out_mode.get() == "custom" else "disabled"
        self._out_entry.configure(state=s)
        self._out_browse.configure(state=s)

    def _browse_out(self):
        path = filedialog.asksaveasfilename(
            defaultextension=self._file_ext or ".csv",
            filetypes=[("CSV", "*.csv"), ("Excel", "*.xlsx"),
                       ("Text/Pipe", "*.txt"), ("All", "*.*")])
        if path:
            self._out_path_v.set(path)

    def _resolve_out_path(self):
        mode = self._out_mode.get()
        if mode == "overwrite":
            return self._file_path
        if mode == "newfile":
            base, ext = os.path.splitext(self._file_path)
            return f"{base}_FIXED{ext}"
        path = self._out_path_v.get().strip()
        if not path:
            raise ValueError("Enter output file path for 'custom' mode.")
        return path

    def _execute_fix(self):
        if self._df is None:
            messagebox.showwarning("No Data", "Load and scan a file first."); return
        if not self._issues:
            messagebox.showinfo("Clean File",
                "No truncation issues were found — file is already clean!\n"
                "No changes needed for Talend re-ingestion."); return
        if self._fix_running:
            return

        try:
            out_path = self._resolve_out_path()
        except ValueError as ex:
            messagebox.showwarning("Missing Path", str(ex)); return

        self._fix_running = True
        self._fix_sv.set("Applying fixes…")
        self._fix_prog["value"] = 0
        self._prog_start()

        def _run():
            try:
                fixed_df, changes = self._apply_fixes(self._df.copy())
                self._fixed_df   = fixed_df
                self._change_log = changes
                self._q.put(lambda: self._fix_sv.set("Saving fixed file…"))
                self._save_file(fixed_df, out_path)
                self._q.put(lambda: self._show_fix_summary(changes, out_path))
                self._q.put(lambda: self._refresh_log_tab(changes))
                self._q.put(lambda: self.nb.select(self.t_log))
                self._out_path = out_path
                self._q.put(lambda: self._status(
                    f"✅ Auto-fix complete — {len(changes)} cells fixed → {os.path.basename(out_path)}"))
            except Exception as ex:
                err = traceback.format_exc()
                self._q.put(lambda: messagebox.showerror("Fix Error", f"{ex}\n\n{err}"))
                self._q.put(lambda: self._status(f"Error: {ex}"))
            finally:
                self._fix_running = False
                self._q.put(self._prog_stop)

        threading.Thread(target=_run, daemon=True).start()

    def _apply_fixes(self, df):
        strategy = self._strategy.get()
        buf      = self._buffer.get()
        changes  = []
        total    = len(self._issues)

        for idx, iss in enumerate(self._issues):
            fc       = iss["col"]
            ridx     = iss["row_idx"]
            limit    = iss["limit"]
            original = str(df.at[ridx, fc])

            # Honour manual edit; otherwise apply smart truncation + chosen strategy
            if iss.get("mode") == "✏️ Manual":
                fixed = iss.get("proposed", self._smart_truncate(fc, original, limit)[0])
            else:
                col_strat = self._col_strategy.get(fc) or self._detect_strategy(fc)
                if col_strat == "tail":
                    # ID/code column: always keep tail regardless of strategy selector
                    fixed = original[-limit:]
                elif strategy == "exact":
                    fixed = original[:limit]
                elif strategy == "buffer":
                    fixed = original[:max(1, limit - buf)]
                else:  # word boundary
                    trunc = original[:limit]
                    sp    = trunc.rfind(" ")
                    fixed = trunc[:sp] if sp > limit // 2 else trunc

            df.at[ridx, fc] = fixed
            changes.append({
                "row":      iss["row"],
                "row_idx":  ridx,
                "col":      fc,
                "original": original,
                "fixed":    fixed,
                "orig_len": len(original),
                "fix_len":  len(fixed),
                "limit":    limit,
                "mode":     iss.get("mode", "🤖 Auto"),
            })
            pct = int((idx + 1) / total * 100)
            self._q.put(lambda p=pct: self._fix_prog.configure(value=p))

        return df, changes

    def _save_file(self, df, path):
        fmt = self._out_fmt.get()
        ext = os.path.splitext(path)[1].lower()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

        if fmt == "Excel XLSX" or (fmt == "Same as input" and ext in (".xlsx", ".xls")):
            df.to_excel(path, index=False, engine="openpyxl")
        elif fmt == "Pipe (|)":
            df.to_csv(path, sep="|", index=False, encoding="utf-8-sig")
        elif fmt == "Tab (\\t)":
            df.to_csv(path, sep="\t", index=False, encoding="utf-8-sig")
        else:
            dm = {"Comma (,)": ",", "Pipe (|)": "|", "Tab (\\t)": "\t", "Semicolon (;)": ";"}
            delim = dm.get(self._delim_var.get(), ",")
            df.to_csv(path, sep=delim, index=False, encoding="utf-8-sig")

    def _show_fix_summary(self, changes, out_path):
        col_c = {}
        for c in changes:
            col_c[c["col"]] = col_c.get(c["col"], 0) + 1

        lines = [
            "=" * 62,
            "  ✅  AUTO-FIX COMPLETE — FILE READY FOR TALEND RE-INGESTION",
            "=" * 62,
            f"  Total cells fixed   : {len(changes):,}",
            f"  Columns affected    : {len(col_c)}",
            f"  Strategy used       : {self._strategy.get()}",
            f"  Output file         : {out_path}",
            f"  Completed at        : {datetime.now():%Y-%m-%d %H:%M:%S}",
            "",
            "  COLUMN BREAKDOWN:",
        ]
        for col, cnt in sorted(col_c.items(), key=lambda x: -x[1]):
            lines.append(f"    {col:<40}  {cnt:,} cell(s) fixed")
        lines += [
            "",
            "  ✅  Drop this file into your Talend job input path:",
            f"     {out_path}",
            "=" * 62,
        ]
        self._fix_out.configure(state="normal")
        self._fix_out.delete("1.0", "end")
        self._fix_out.insert("1.0", "\n".join(lines))
        self._fix_out.configure(state="disabled")
        self._fix_sv.set(
            f"✅  {len(changes):,} cells fixed — saved: {os.path.basename(out_path)}")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — CHANGE LOG
    # ══════════════════════════════════════════════════════════════════════════
    def _build_tab_log(self):
        tab = self.t_log

        hdr = tk.Frame(tab, bg=C["surface"]); hdr.pack(fill="x", padx=14, pady=(12, 4))
        self._log_sv = tk.StringVar(value="No fixes applied yet.")
        tk.Label(hdr, textvariable=self._log_sv, font=("Segoe UI", 10, "bold"),
                 bg=C["surface"], fg=C["green"]).pack(side="left", padx=10, pady=6)
        btn_row = tk.Frame(hdr, bg=C["surface"]); btn_row.pack(side="right", padx=6)
        self._btn(btn_row, "💾 Export Change Log", self._export_change_log,
                  C["overlay"], fg=C["text"]).pack(side="left", padx=4)
        self._btn(btn_row, "📂 Open Fixed File Location", self._open_output_dir,
                  C["teal"]).pack(side="left", padx=4)

        tf = tk.Frame(tab, bg=C["bg"]); tf.pack(fill="both", expand=True, padx=14, pady=4)
        cols = ("row", "col", "orig_len", "fix_len", "limit", "original", "fixed")
        self._log_tv = ttk.Treeview(tf, columns=cols, show="headings")
        for c, lbl, w in [
            ("row",      "Row #",              70),
            ("col",      "Column",            160),
            ("orig_len", "Was",                60),
            ("fix_len",  "Now",                60),
            ("limit",    "DB Limit",           80),
            ("original", "Original (was)",    310),
            ("fixed",    "Fixed (saved)",      310),
        ]:
            self._log_tv.heading(c, text=lbl)
            self._log_tv.column(c, width=w, minwidth=40)
        vsb = ttk.Scrollbar(tf, orient="vertical",   command=self._log_tv.yview)
        hsb = ttk.Scrollbar(tf, orient="horizontal", command=self._log_tv.xview)
        self._log_tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._log_tv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tf.rowconfigure(0, weight=1); tf.columnconfigure(0, weight=1)
        self._log_tv.tag_configure("changed", background="#0f2018", foreground=C["green"])

    def _refresh_log_tab(self, changes):
        self._log_tv.delete(*self._log_tv.get_children())
        col_c = {}
        for c in changes:
            col_c[c["col"]] = col_c.get(c["col"], 0) + 1
            self._log_tv.insert("", "end", values=(
                c["row"], c["col"], c["orig_len"], c["fix_len"], c["limit"],
                c["original"][:120], c["fixed"][:120],
            ), tags=("changed",))
        self._log_sv.set(
            f"✅  {len(changes):,} cells fixed across {len(col_c)} columns — "
            f"file ready for Talend re-ingestion")

    def _export_change_log(self):
        if not self._change_log:
            messagebox.showinfo("Nothing to export", "Apply a fix first."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Excel", "*.xlsx"), ("Text", "*.txt")])
        if not path: return
        ext = os.path.splitext(path)[1].lower()

        if ext == ".xlsx":
            import openpyxl as ox
            from openpyxl.styles import Font, PatternFill
            wb = ox.Workbook(); ws = wb.active; ws.title = "Change Log"
            hf = Font(bold=True, color="FFFFFF")
            hfill = PatternFill("solid", fgColor="1E6B3A")
            for ci, h in enumerate(
                    ["Row #", "Column", "Was Len", "Now Len", "DB Limit",
                     "Original Value", "Fixed Value"], 1):
                cl = ws.cell(row=1, column=ci, value=h)
                cl.font = hf; cl.fill = hfill
            for ri, c in enumerate(self._change_log, 2):
                ws.cell(row=ri, column=1, value=c["row"])
                ws.cell(row=ri, column=2, value=c["col"])
                ws.cell(row=ri, column=3, value=c["orig_len"])
                ws.cell(row=ri, column=4, value=c["fix_len"])
                ws.cell(row=ri, column=5, value=c["limit"])
                ws.cell(row=ri, column=6, value=c["original"][:500])
                ws.cell(row=ri, column=7, value=c["fixed"][:500])
            wb.save(path)
        elif ext == ".txt":
            with open(path, "w", encoding="utf-8") as f:
                f.write("Talend Auto-Fix — Change Log\n")
                f.write(f"File    : {self._file_path}\n")
                f.write(f"Changes : {len(self._change_log)}\n")
                f.write(f"Date    : {datetime.now():%Y-%m-%d %H:%M}\n{'='*70}\n\n")
                for c in self._change_log:
                    f.write(f"Row {c['row']:<6} {c['col']:<30} "
                            f"{c['orig_len']} → {c['fix_len']} chars\n")
                    f.write(f"  ORIG : {c['original'][:120]}\n")
                    f.write(f"  FIXED: {c['fixed'][:120]}\n\n")
        else:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["Row #", "Column", "Was Len", "Now Len", "DB Limit",
                             "Original Value", "Fixed Value"])
                for c in self._change_log:
                    w.writerow([c["row"], c["col"], c["orig_len"], c["fix_len"],
                                 c["limit"], c["original"], c["fixed"]])
        messagebox.showinfo("✅ Exported", f"Change log saved to:\n{path}")

    def _open_output_dir(self):
        path = self._out_path or self._file_path
        if path:
            subprocess.Popen(f'explorer /select,"{path}"')


# ── entry point ───────────────────────────────────────────────────────────────
def main():
    root = tk.Tk()
    TalendAutoFixApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
