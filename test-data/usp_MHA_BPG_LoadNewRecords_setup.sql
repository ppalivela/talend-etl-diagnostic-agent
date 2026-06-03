-- =============================================================================
--  FULL PIPELINE TEST SETUP — Formulary_Data
--
--  Flow reproduced here:
--    1. EXEC [dbo].[usp_MHA_BPG_LoadNewRecords]
--       → reads BINPCN x PBM → inserts new combos into MHA_Master_BPG (Is_New_Record=1)
--    2. SELECT ... FROM MHA_Master_BPG WHERE Is_New_Record = 1
--       → Talend job reads these rows and sends to MMIT
--
--  Run on: FLO-DDW-DEV / Formulary_Data
--  Pre-req: BINPCN_dummy_data.sql must have been run first (dbo.BINPCN + dbo.PBM loaded)
--  Created: 2026-06-03
-- =============================================================================

USE Formulary_Data;
GO

-- =============================================================================
--  STEP 1 — Create MHA_Master_BPG (if not exists)
-- =============================================================================

IF OBJECT_ID('dbo.MHA_Master_BPG', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MHA_Master_BPG (
        BPG_ID                  INT           NOT NULL IDENTITY(1,1) PRIMARY KEY,
        BP_BIN                  VARCHAR(10)   NOT NULL,
        BP_PCN                  VARCHAR(20)   NOT NULL,
        BP_CHGRP                VARCHAR(30)   NOT NULL,
        PB_NAME                 VARCHAR(100)  NOT NULL,
        BP_PLANTYPE             VARCHAR(50)   NOT NULL,
        Sent_To_MMIT            BIT           NOT NULL DEFAULT 0,
        MMIT_Status             VARCHAR(50)   NULL,
        Date_Added_To_Master    DATETIME      NOT NULL DEFAULT GETDATE(),
        Is_New_Record           BIT           NOT NULL DEFAULT 1,
        Date_Sent_MMIT          DATETIME      NULL,
        BPG_ADDSTMP             DATETIME      NOT NULL DEFAULT GETDATE(),
        BPG_UPDSTMP             DATETIME      NULL
    );
    PRINT 'Created dbo.MHA_Master_BPG';
END
ELSE
    PRINT 'dbo.MHA_Master_BPG already exists — skipping CREATE';
GO

-- =============================================================================
--  STEP 2 — Create (or replace) the stored procedure
--           usp_MHA_BPG_LoadNewRecords
--
--  Logic:
--    - Query BINPCN x PBM (same query as the Talend source job uses)
--    - For each distinct BIN/PCN/CHGRP/PBM/PlanType combination that is
--      currently ACTIVE (BP_END >= GETDATE())
--    - If that combo does NOT already exist in MHA_Master_BPG → INSERT it
--      with Is_New_Record=1, Sent_To_MMIT=0, MMIT_Status='Pending'
--    - Returns the count of newly inserted rows
-- =============================================================================

IF OBJECT_ID('dbo.usp_MHA_BPG_LoadNewRecords', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_MHA_BPG_LoadNewRecords;
GO

CREATE PROCEDURE dbo.usp_MHA_BPG_LoadNewRecords
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @InsertedCount INT = 0;

    -- Insert active BIN/PCN combos that do not yet exist in the master table
    INSERT INTO dbo.MHA_Master_BPG
        (BP_BIN, BP_PCN, BP_CHGRP, PB_NAME, BP_PLANTYPE,
         Sent_To_MMIT, MMIT_Status, Date_Added_To_Master, Is_New_Record)
    SELECT DISTINCT
        a.BP_BIN,
        a.BP_PCN,
        a.BP_CHGRP,
        b.PB_NAME,
        b.BP_PLANTYPE,
        0           AS Sent_To_MMIT,
        'Pending'   AS MMIT_Status,
        GETDATE()   AS Date_Added_To_Master,
        1           AS Is_New_Record
    FROM dbo.BINPCN  a
    INNER JOIN dbo.PBM b ON a.BP_PBID = b.PB_PBID
    WHERE a.BP_END >= GETDATE()                     -- active records only
      AND NOT EXISTS (
            SELECT 1
            FROM dbo.MHA_Master_BPG m
            WHERE m.BP_BIN   = a.BP_BIN
              AND m.BP_PCN   = a.BP_PCN
              AND m.BP_CHGRP = a.BP_CHGRP
              AND m.PB_NAME  = b.PB_NAME
      );

    SET @InsertedCount = @@ROWCOUNT;

    PRINT CONCAT('usp_MHA_BPG_LoadNewRecords: inserted ', @InsertedCount, ' new record(s) into MHA_Master_BPG');

    -- Return summary result set (optional — Talend can ignore this)
    SELECT @InsertedCount AS NewRecordsLoaded;
END;
GO

PRINT 'Stored procedure usp_MHA_BPG_LoadNewRecords created.';
GO

-- =============================================================================
--  STEP 3 — Run the stored procedure (same as Talend job does)
-- =============================================================================

PRINT '>>> Running EXEC [dbo].[usp_MHA_BPG_LoadNewRecords] ...';
EXEC [dbo].[usp_MHA_BPG_LoadNewRecords];
GO

-- =============================================================================
--  STEP 4 — Run the exact Talend job SELECT query
-- =============================================================================

PRINT '>>> Talend job SELECT query (Is_New_Record = 1):';

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
--  STEP 5 — Summary counts
-- =============================================================================

SELECT
    'MHA_Master_BPG Total'      AS Category, COUNT(*) AS RowCount FROM dbo.MHA_Master_BPG
UNION ALL
SELECT 'Is_New_Record = 1 (job picks up)', COUNT(*) FROM dbo.MHA_Master_BPG WHERE Is_New_Record = 1
UNION ALL
SELECT 'Is_New_Record = 0 (already processed)', COUNT(*) FROM dbo.MHA_Master_BPG WHERE Is_New_Record = 0
UNION ALL
SELECT 'MMIT_Status = Pending',  COUNT(*) FROM dbo.MHA_Master_BPG WHERE MMIT_Status = 'Pending';
GO

-- =============================================================================
--  STEP 6 — (OPTIONAL) Simulate Talend job completing: mark records as sent
--           Run this AFTER your Talend job processes the rows, to test re-runs
-- =============================================================================
/*
UPDATE dbo.MHA_Master_BPG
SET
    Is_New_Record   = 0,
    Sent_To_MMIT    = 1,
    MMIT_Status     = 'Sent',
    Date_Sent_MMIT  = GETDATE(),
    BPG_UPDSTMP     = GETDATE()
WHERE Is_New_Record = 1
  AND Sent_To_MMIT  = 0;

PRINT 'Marked pending rows as Sent. Re-run SP to load any new records.';
*/

-- =============================================================================
--  CLEANUP HELPER (commented out by default)
-- =============================================================================
/*
DROP TABLE  IF EXISTS dbo.MHA_Master_BPG;
DROP PROCEDURE IF EXISTS dbo.usp_MHA_BPG_LoadNewRecords;
PRINT 'Cleaned up.';
*/
