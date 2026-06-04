-- =============================================================================
--  QA TEST SETUP — Proper Incremental Load Logic
--  Job: Reload_MHA_BPG_Staging
--
--  Flow being tested:
--    tDBInput_1  → SELECT active rows from BINPCN × PBM (source)
--    tMap_1      → Map fields
--    tDBOutput_1 → TRUNCATE + INSERT into dbo.MHA_BPG_Staging
--    tDBRow_1    → EXEC usp_MHA_BPG_LoadNewRecords
--                   (compares staging vs master, inserts NEW with Is_New_Record=1)
--    tDBInput_2  → SELECT WHERE Is_New_Record=1  ← should return NEW rows only
--    tFileOutput → Write to MMIT file
--    tDBRow_2    → UPDATE Is_New_Record=0, Sent_To_MMIT=1 (after sending)
--
--  QA Scenario:
--    - MHA_Master_BPG has 20 already-processed records (Is_New_Record=0)
--    - BINPCN has 10 NEW records not yet in master
--    - Job run: staging gets 30 rows, SP finds 10 new → Is_New_Record=1
--    - tDBInput_2 returns exactly 10 rows ← QA PASS
--    - Re-run job: SP finds 0 new (all already in master) → tDBInput_2 = 0
--      This verifies the deduplication logic works too
--
--  Run on: FLO-DDW-DEV / Formulary_Data
--  Pre-req: BINPCN_dummy_data.sql already run (PBM + BINPCN populated)
--  Created: 2026-06-03
-- =============================================================================

USE Formulary_Data;
GO

PRINT '====================================================';
PRINT ' QA SETUP: MHA BPG Incremental Load Test';
PRINT '====================================================';

-- =============================================================================
--  STEP 1 — Create MHA_BPG_Staging if not exists
--           (tDBOutput_1 TRUNCATE+INSERTs into this every run)
-- =============================================================================

IF OBJECT_ID('dbo.MHA_BPG_Staging', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MHA_BPG_Staging (
        STG_ID      INT          NOT NULL IDENTITY(1,1) PRIMARY KEY,
        BP_BIN      VARCHAR(10)  NOT NULL,
        BP_PCN      VARCHAR(20)  NOT NULL,
        BP_CHGRP    VARCHAR(30)  NOT NULL,
        PB_NAME     VARCHAR(100) NOT NULL,
        BP_PLANTYPE VARCHAR(50)  NOT NULL,
        STG_ADDSTMP DATETIME     NOT NULL DEFAULT GETDATE()
    );
    PRINT '[STEP 1] Created dbo.MHA_BPG_Staging';
END
ELSE
    PRINT '[STEP 1] dbo.MHA_BPG_Staging already exists';
GO

-- =============================================================================
--  STEP 2 — Create MHA_Master_BPG if not exists
-- =============================================================================

IF OBJECT_ID('dbo.MHA_Master_BPG', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MHA_Master_BPG (
        BPG_ID               INT          NOT NULL IDENTITY(1,1) PRIMARY KEY,
        BP_BIN               VARCHAR(10)  NOT NULL,
        BP_PCN               VARCHAR(20)  NOT NULL,
        BP_CHGRP             VARCHAR(30)  NOT NULL,
        PB_NAME              VARCHAR(100) NOT NULL,
        BP_PLANTYPE          VARCHAR(50)  NOT NULL,
        Sent_To_MMIT         BIT          NOT NULL DEFAULT 0,
        MMIT_Status          VARCHAR(50)  NULL,
        Date_Added_To_Master DATETIME     NOT NULL DEFAULT GETDATE(),
        Is_New_Record        BIT          NOT NULL DEFAULT 1,
        Date_Sent_MMIT       DATETIME     NULL,
        BPG_ADDSTMP          DATETIME     NOT NULL DEFAULT GETDATE(),
        BPG_UPDSTMP          DATETIME     NULL
    );
    PRINT '[STEP 2] Created dbo.MHA_Master_BPG';
END
ELSE
    PRINT '[STEP 2] dbo.MHA_Master_BPG already exists';
GO

-- =============================================================================
--  STEP 3 — CLEAN STATE: Reset both tables for clean QA run
-- =============================================================================

TRUNCATE TABLE dbo.MHA_BPG_Staging;
DELETE  FROM   dbo.MHA_Master_BPG;
PRINT '[STEP 3] Cleared MHA_BPG_Staging and MHA_Master_BPG';
GO

-- =============================================================================
--  STEP 4 — Add 10 NEW BINPCN records to the source
--           These use unique BINs (TEST prefix) not yet in master
--           When the job runs, tDBInput_1 will pick them up too
-- =============================================================================

-- Remove any previously added test BINs before re-inserting (safe re-run)
DELETE FROM dbo.BINPCN WHERE BP_BIN IN ('810001','810002','820001','820002','830001','830002');

-- First ensure PBM has entries for our test PBIDs
MERGE dbo.PBM AS tgt
USING (VALUES
    (21, 'TEST - Anthem Blue Cross PBM',   'Commercial'),
    (22, 'TEST - Cigna Express Scripts',   'Commercial'),
    (23, 'TEST - Aetna CVS Health',        'Medicare Part D')
) AS src (PB_PBID, PB_NAME, BP_PLANTYPE)
ON tgt.PB_PBID = src.PB_PBID
WHEN NOT MATCHED THEN
    INSERT (PB_PBID, PB_NAME, BP_PLANTYPE)
    VALUES (src.PB_PBID, src.PB_NAME, src.BP_PLANTYPE);

-- Insert 10 new BINPCN rows with unique BINs (will appear in tDBInput_1 source)
INSERT INTO dbo.BINPCN (BP_PBID, BP_BIN,    BP_PCN,       BP_CHGRP,          BP_START,    BP_END)
VALUES
(21, '810001', 'ANTHEM',    'ANT_COM_Q1',  '2026-01-01', '2027-12-31'),
(21, '810001', 'ANTHEM',    'ANT_COM_Q2',  '2026-01-01', '2027-12-31'),
(21, '810002', 'BXBS',      'ANT_MED_Q1',  '2026-03-01', '2027-06-30'),
(22, '820001', 'CIGNA',     'CIG_COM_Q1',  '2026-01-01', '2028-12-31'),
(22, '820001', 'CIGNA',     'CIG_COM_Q2',  '2026-04-01', '2027-12-31'),
(22, '820002', 'CIGNAESI',  'CIG_MED_Q1',  '2026-01-01', '2027-06-30'),
(23, '830001', 'AETNA',     'AET_MED_Q1',  '2026-01-01', '2026-12-31'),
(23, '830001', 'AETNA',     'AET_MED_Q2',  '2026-01-01', '2027-12-31'),
(23, '830002', 'AETNACVS',  'AET_COM_Q1',  '2026-06-01', '2028-12-31'),
(23, '830002', 'AETNACVS',  'AET_COM_Q2',  '2026-06-01', '2028-12-31');

DECLARE @newBin INT;
SELECT @newBin = COUNT(*) FROM dbo.BINPCN WHERE BP_BIN IN ('810001','810002','820001','820002','830001','830002');
PRINT CONCAT('[STEP 4] Added ', @newBin, ' new BINPCN rows with test BINs (810xxx/820xxx/830xxx)');
GO

-- =============================================================================
--  STEP 5 — Seed MHA_Master_BPG with EXISTING (already processed) records
--           These are the 30 original BINPCN rows from first script
--           Is_New_Record=0, Sent_To_MMIT=1 (simulates previous run completed)
-- =============================================================================

INSERT INTO dbo.MHA_Master_BPG
    (BP_BIN, BP_PCN, BP_CHGRP, PB_NAME, BP_PLANTYPE,
     Sent_To_MMIT, MMIT_Status, Date_Added_To_Master, Is_New_Record)
SELECT DISTINCT
    a.BP_BIN, a.BP_PCN, a.BP_CHGRP, b.PB_NAME, b.BP_PLANTYPE,
    1           AS Sent_To_MMIT,
    'Processed' AS MMIT_Status,
    DATEADD(DAY, -30, GETDATE()) AS Date_Added_To_Master,
    0           AS Is_New_Record           -- Already processed
FROM dbo.BINPCN  a
INNER JOIN dbo.PBM b ON a.BP_PBID = b.PB_PBID
WHERE a.BP_END >= GETDATE()
  AND a.BP_BIN NOT IN ('810001','810002','820001','820002','830001','830002');  -- exclude new test BINs

DECLARE @existCnt INT;
SELECT @existCnt = COUNT(*) FROM dbo.MHA_Master_BPG WHERE Is_New_Record = 0;
PRINT CONCAT('[STEP 5] Seeded MHA_Master_BPG with ', @existCnt, ' existing processed records (Is_New_Record=0)');
GO

-- =============================================================================
--  STEP 6 — Rebuild SP: reads MHA_BPG_Staging, inserts NEW vs master
--           "New" = in staging but NOT already in master (by BIN+PCN+CHGRP)
-- =============================================================================

IF OBJECT_ID('dbo.usp_MHA_BPG_LoadNewRecords', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_MHA_BPG_LoadNewRecords;
GO

CREATE PROCEDURE dbo.usp_MHA_BPG_LoadNewRecords
AS
BEGIN
    SET NOCOUNT ON;

    -- Insert rows from staging that do not already exist in master
    INSERT INTO dbo.MHA_Master_BPG
        (BP_BIN, BP_PCN, BP_CHGRP, PB_NAME, BP_PLANTYPE,
         Sent_To_MMIT, MMIT_Status, Date_Added_To_Master, Is_New_Record)
    SELECT
        s.BP_BIN,
        s.BP_PCN,
        s.BP_CHGRP,
        s.PB_NAME,
        s.BP_PLANTYPE,
        0         AS Sent_To_MMIT,
        'Pending' AS MMIT_Status,
        GETDATE() AS Date_Added_To_Master,
        1         AS Is_New_Record            -- FLAG: new, not yet sent to MMIT
    FROM dbo.MHA_BPG_Staging s
    WHERE NOT EXISTS (
        SELECT 1 FROM dbo.MHA_Master_BPG m
        WHERE m.BP_BIN   = s.BP_BIN
          AND m.BP_PCN   = s.BP_PCN
          AND m.BP_CHGRP = s.BP_CHGRP
    );

    DECLARE @cnt INT = @@ROWCOUNT;
    PRINT CONCAT('SP: Inserted ', @cnt, ' new record(s) into MHA_Master_BPG with Is_New_Record=1');
    SELECT @cnt AS NewRecordsLoaded;
END;
GO

PRINT '[STEP 6] SP usp_MHA_BPG_LoadNewRecords rebuilt (reads from MHA_BPG_Staging)';
GO

-- =============================================================================
--  STEP 7 — Verify QA state BEFORE running the job
-- =============================================================================

PRINT '=== QA STATE BEFORE JOB RUN ===';
SELECT
    'BINPCN active rows (tDBInput_1 source)'         AS Description,
    COUNT(*) AS Total_Rows
FROM dbo.BINPCN a
INNER JOIN dbo.PBM b ON a.BP_PBID = b.PB_PBID
WHERE a.BP_END >= GETDATE()
UNION ALL
SELECT 'MHA_BPG_Staging rows (empty — job will fill)', COUNT(*) FROM dbo.MHA_BPG_Staging
UNION ALL
SELECT 'MHA_Master_BPG existing (Is_New_Record=0)',    COUNT(*) FROM dbo.MHA_Master_BPG WHERE Is_New_Record=0
UNION ALL
SELECT 'MHA_Master_BPG new pending (Is_New_Record=1)', COUNT(*) FROM dbo.MHA_Master_BPG WHERE Is_New_Record=1
UNION ALL
SELECT 'EXPECTED new rows after job run (new BINs)',
    COUNT(*)
FROM dbo.BINPCN a
INNER JOIN dbo.PBM b ON a.BP_PBID = b.PB_PBID
WHERE a.BP_END >= GETDATE()
  AND NOT EXISTS (
    SELECT 1 FROM dbo.MHA_Master_BPG m
    WHERE m.BP_BIN=a.BP_BIN AND m.BP_PCN=a.BP_PCN AND m.BP_CHGRP=a.BP_CHGRP
  );
GO

PRINT '';
PRINT '====================================================';
PRINT ' NOW RUN THE TALEND JOB (Reload_MHA_BPG_Staging)';
PRINT ' Expected results:';
PRINT '   tDBInput_1  → 30+ rows from BINPCN x PBM';
PRINT '   tDBOutput_1 → loads into MHA_BPG_Staging';
PRINT '   tDBRow_1    → SP inserts NEW rows with Is_New_Record=1';
PRINT '   tDBInput_2  → 10 rows (the new test BINs)';
PRINT '   tFileOutput → 10 rows written to MMIT file';
PRINT '   tDBRow_2    → marks those 10 as Is_New_Record=0';
PRINT '   Re-run job  → 0 new rows (all already in master)';
PRINT '====================================================';
GO

-- =============================================================================
--  STEP 8 — POST-JOB VERIFICATION QUERY (run after job completes)
--           Copy this block and run it after the job finishes
-- =============================================================================
/*
-- Run this AFTER the Talend job completes:

SELECT 'POST-JOB RESULTS' AS Check_Point;

SELECT
    'tDBInput_2 would have returned' AS Description,
    COUNT(*) AS Rows
FROM dbo.MHA_Master_BPG
WHERE Is_New_Record = 1
UNION ALL
SELECT 'New records sent (Is_New_Record=0, Sent=1 today)', COUNT(*)
FROM dbo.MHA_Master_BPG
WHERE Is_New_Record = 0
  AND Sent_To_MMIT = 1
  AND CAST(Date_Sent_MMIT AS DATE) = CAST(GETDATE() AS DATE);

-- Verify new BINs are now in master
SELECT BP_BIN, BP_PCN, BP_CHGRP, PB_NAME, Is_New_Record, MMIT_Status, Date_Sent_MMIT
FROM dbo.MHA_Master_BPG
WHERE BP_BIN IN ('810001','810002','820001','820002','830001','830002')
ORDER BY BP_BIN, BP_PCN;
*/
