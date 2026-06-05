MMIT_MHA_Data_Ingestion_Final — End-to-End Test Data Files
============================================================

Pipe-delimited (|) flat files for all 11 Talend child ingestion jobs.
Place these files in the input directory configured in your Talend context variables.

FILE MAPPING TO TALEND CHILD JOBS:
===================================
Talend Child Job                    | Input File                      | Records
------------------------------------|----------------------------------|--------
Drugs_Data_Ingestion_Job            | Drugs_Data.txt                  | 20 drugs
PansController_Data_Ingestion_Job   | PansController_Data.txt         | 15 PAN records
Medopen_Bridge_Data_Ingestion_Job   | Medopen_Bridge_Data.txt         | 15 bridge records
NDC_Bridge_Data_Ingestion_Job       | NDC_Bridge_Data.txt             | 20 NDC records
Restrictions_Data_Ingestion_Job     | Restrictions_Data.txt           | 20 restrictions
Statuses_Data_Ingestion_Job         | Statuses_Data.txt               | 15 status codes
IDSAs_Data_Ingestion_Job            | IDSAs_Data.txt                  | 20 IDSA records
PanDetails_Data_Ingestion_Job       | PanDetails_Data.txt             | 20 PA criteria
States_Data_Ingestion_Job           | States_Data.txt                 | 51 states+DC
Zip_Code_Data_Ingestion_Job         | ZipCode_Data.txt                | 20 ZIP codes
PansControllerNCD_Data_Ingestion_Job| PansControllerNCD_Data.txt      | 10 NCD records

MASTER JOB FLOW (MMIT_MHA_Data_Ingestion_Final):
=================================================
PREJOB:
  tDBRow_1  → EXEC dbo.sp_MMIT_Prep         (auto-cleans _Holding tables)
  tDBRow_2  → additional prep step
  OnSubjobError → tDBRow_16 → EXEC dbo.sp_MMIT_Recover

WAVE 1 (tParallelize_1 — runs simultaneously):
  ├── Drugs_Data_Ingestion_Job          ─OnSubjobError→ tDBRow_5 (sp_MMIT_Recover)
  └── PansController_Data_Ingestion_Job ─OnSubjobError→ tDBRow_6 (sp_MMIT_Recover)
  [Synchronize - wait for all]

SEQUENTIAL:
  Medopen_Bridge_Data_Ingestion_Job      ─OnSubjobError→ tDBRow_4 (sp_MMIT_Recover)

WAVE 2 (tParallelize_2 — runs simultaneously):
  ├── NDC_Bridge_Data_Ingestion_Job          ─OnSubjobError→ tDBRow_7
  ├── Restrictions_Data_Ingestion_Job        ─OnSubjobError→ tDBRow_8
  ├── Statuses_Data_Ingestion_Job            ─OnSubjobError→ tDBRow_9
  ├── IDSAs_Data_Ingestion_Job               ─OnSubjobError→ tDBRow_10
  ├── PanDetails_Data_Ingestion_Job          ─OnSubjobError→ tDBRow_11
  ├── States_Data_Ingestion_Job              ─OnSubjobError→ tDBRow_12
  ├── Zip_Code_Data_Ingestion_Job            ─OnSubjobError→ tDBRow_13
  └── PansControllerNCD_Data_Ingestion_Job   ─OnSubjobError→ tDBRow_14
  [Synchronize - wait for all]

POSTJOB:
  tDBRow_15 → EXEC dbo.sp_MMIT_Finalize     (drops _Holding tables, marks run complete)
  OnSubjobError → tDBRow_3 → EXEC dbo.sp_MMIT_Recover

3 SPs REQUIRED IN DB (run MMIT_automated_pipeline_SPs.sql):
============================================================
  dbo.sp_MMIT_Prep      — Prejob: auto-cleans _Holding tables, logs run start
  dbo.sp_MMIT_Recover   — OnSubjobError: cleanup + marks run as Failed
  dbo.sp_MMIT_Finalize  — Postjob: drops _Holding tables, marks run Complete

FILE FORMAT:
============
  Delimiter : pipe (|)
  Header    : Yes (first row)
  Encoding  : UTF-8
  Date fmt  : YYYY-MM-DD

HOW TO USE:
===========
1. Run MMIT_automated_pipeline_SPs.sql in SSMS (Formulary_Data) — one-time setup
2. Copy these .txt files to the input file path in your Talend context
3. Run MMIT_MHA_Data_Ingestion_Final from TAC or Talend Studio
4. Monitor: check dbo.MMIT_RunLog for run status after job completes
