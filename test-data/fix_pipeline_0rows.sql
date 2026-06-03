-- =============================================================================
--  FIX: Full Pipeline Reset for Job "Reload_MHA_BPG_Staging"
--
--  ROOT CAUSE of 0 rows in tDBInput_2:
--    - tDBOutput_1 writes 30 rows to dbo.MHA_BPG_Staging (staging table)
--    - SP usp_MHA_BPG_LoadNewRecords was reading from BINPCN/PBM directly
--      instead of from MHA_BPG_Staging
--    - All 30 rows already existed in MHA_Master_BPG → SP inserted 0 new rows
--    - tDBInput_2 (SELECT WHERE Is_New_Record=1) → 0 rows
--
--  FIX:
--    1. Create MHA_BPG_Staging table (same schema tDBOutput_1 writes to)
--    2. Rebuild SP to read from MHA_BPG_Staging vs MHA_Master_BPG
--    3. Clear MHA_Master_BPG so all staging rows are "new" on next run
--    4. Verify by running SP manually and confirming Is_New_Record=1 rows appear
--
--  Run on: FLO-DDW-DEV / Formulary_Data
--  Created: 2026-06-03
-- =============================================================================

USE Formulary_Data;
GO

-- =============================================================================
--  STEP 1 — Create MHA_BPG_Staging (this is where tDBOutput_1 writes)
--           Matches the tMap_1 / Data_Load output schema
-- =============================================================================

IF OBJECT_ID('dbo.MHA_BPG_Staging', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MHA_BPG_Staging (
        STG_ID       INT          NOT NULL IDENTITY(1,1) PRIMARY KEY,
        BP_BIN       VARCHAR(10)  NOT NULL,
        BP_PCN       VARCHAR(20)  NOT NULL,
        BP_CHGRP     VARCHAR(30)  NOT NULL,
        PB_NAME      VARCHAR(100) NOT NULL,
        BP_PLANTYPE  VARCHAR(50)  NOT NULL,
        STG_ADDSTMP  DATETIME     NOT NULL DEFAULT GETDATE()
    );
    PRINT 'Created dbo.MHA_BPG_Staging';
END
ELSE
    PRINT 'dbo.MHA_BPG_Staging already exists — skipping CREATE';
GO

-- =============================================================================
--  STEP 2 — Ensure MHA_Master_BPG exists
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
    PRINT 'Created dbo.MHA_Master_BPG';
END
ELSE
    PRINT 'dbo.MHA_Master_BPG already exists — skipping CREATE';
GO

-- =============================================================================
--  STEP 3 — RESET: Clear MHA_Master_BPG so ALL staging rows are "new"
--           (Safe for dev/test — DO NOT run on production)
-- =============================================================================

-- First clear the FK-dependent staging manually
TRUNCATE TABLE dbo.MHA_BPG_Staging;
PRINT 'Cleared MHA_BPG_Staging';

DELETE FROM dbo.MHA_Master_BPG;
PRINT 'Cleared MHA_Master_BPG — all rows from next job run will be Is_New_Record=1';
GO

-- =============================================================================
--  STEP 4 — Pre-load MHA_BPG_Staging from BINPCN x PBM
--           (Simulates what tDBInput_1 + tMap_1 + tDBOutput_1 does)
--           The Talend job will OVERWRITE this again — this is just for
--           testing the SP without running the full job first
-- =============================================================================

INSERT INTO dbo.MHA_BPG_Staging (BP_BIN, BP_PCN, BP_CHGRP, PB_NAME, BP_PLANTYPE)
SELECT DISTINCT
    a.BP_BIN,
    a.BP_PCN,
    a.BP_CHGRP,
    b.PB_NAME,
    b.BP_PLANTYPE
FROM dbo.BINPCN  a
INNER JOIN dbo.PBM b ON a.BP_PBID = b.PB_PBID
WHERE a.BP_END >= GETDATE();

DECLARE @stgCnt INT;
SELECT @stgCnt = COUNT(*) FROM dbo.MHA_BPG_Staging;
PRINT CONCAT('MHA_BPG_Staging loaded: ', @stgCnt, ' rows');
GO

-- =============================================================================
--  STEP 5 — Rebuild SP to read from MHA_BPG_Staging (the CORRECT source)
-- =============================================================================

IF OBJECT_ID('dbo.usp_MHA_BPG_LoadNewRecords', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_MHA_BPG_LoadNewRecords;
GO

CREATE PROCEDURE dbo.usp_MHA_BPG_LoadNewRecords
AS
BEGIN
    SET NOCOUNT ON;

    -- Insert rows from staging that do NOT already exist in master
    INSERT INTO dbo.MHA_Master_BPG
        (BP_BIN, BP_PCN, BP_CHGRP, PB_NAME, BP_PLANTYPE,
         Sent_To_MMIT, MMIT_Status, Date_Added_To_Master, Is_New_Record)
    SELECT
        s.BP_BIN,
        s.BP_PCN,
        s.BP_CHGRP,
        s.PB_NAME,
        s.BP_PLANTYPE,
        0           AS Sent_To_MMIT,
        'Pending'   AS MMIT_Status,
        GETDATE()   AS Date_Added_To_Master,
        1           AS Is_New_Record
    FROM dbo.MHA_BPG_Staging s
    WHERE NOT EXISTS (
        SELECT 1
        FROM dbo.MHA_Master_BPG m
        WHERE m.BP_BIN   = s.BP_BIN
          AND m.BP_PCN   = s.BP_PCN
          AND m.BP_CHGRP = s.BP_CHGRP
          AND m.PB_NAME  = s.PB_NAME
    );

    DECLARE @cnt INT = @@ROWCOUNT;
    PRINT CONCAT('usp_MHA_BPG_LoadNewRecords: inserted ', @cnt, ' new record(s)');
    SELECT @cnt AS NewRecordsLoaded;
END;
GO

PRINT 'SP usp_MHA_BPG_LoadNewRecords rebuilt — now reads from MHA_BPG_Staging';
GO

-- =============================================================================
--  STEP 6 — Run the SP to verify (same as tDBRow_1 does)
-- =============================================================================

PRINT '>>> Running SP...';
EXEC [dbo].[usp_MHA_BPG_LoadNewRecords];
GO

-- =============================================================================
--  STEP 7 — Confirm tDBInput_2 query now returns rows
-- =============================================================================

PRINT '>>> tDBInput_2 query (should now return rows):';

SELECT
    BP_BIN,
    BP_PCN,
    BP_CHGRP,
    PB_NAME,
    BP_PLANTYPE,
    Sent_To_MMIT,
    MMIT_Status,
    Date_Added_To_Master
FROM [dbo].[MHA_Master_BPG]
WHERE Is_New_Record = 1
ORDER BY Date_Added_To_Master DESC, BP_BIN, BP_PCN;
GO

-- =============================================================================
--  STEP 8 — Row counts summary
-- =============================================================================

SELECT 'MHA_BPG_Staging'        AS TableName, COUNT(*) AS Rows FROM dbo.MHA_BPG_Staging
UNION ALL
SELECT 'MHA_Master_BPG Total',   COUNT(*) FROM dbo.MHA_Master_BPG
UNION ALL
SELECT 'Is_New_Record=1 (job picks up)', COUNT(*) FROM dbo.MHA_Master_BPG WHERE Is_New_Record=1
UNION ALL
SELECT 'Is_New_Record=0',        COUNT(*) FROM dbo.MHA_Master_BPG WHERE Is_New_Record=0;
GO

-- =============================================================================
--  NOTE: After confirming rows appear above, re-run the Talend job.
--        The job will:
--          1. tDBOutput_1  → overwrite MHA_BPG_Staging (30 rows from BINPCN/PBM)
--          2. tDBRow_1     → EXEC SP → inserts into MHA_Master_BPG with Is_New_Record=1
--          3. tDBInput_2   → SELECT WHERE Is_New_Record=1 → should return 30 rows
--          4. tFileOutput  → writes to delimited file
--          5. tDBRow_2     → marks Is_New_Record=0 / Sent_To_MMIT=1
-- =============================================================================
