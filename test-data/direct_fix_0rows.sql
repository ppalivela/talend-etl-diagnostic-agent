-- =============================================================================
--  DIRECT FIX — Bypass SP, force Is_New_Record=1 rows into MHA_Master_BPG
--
--  Run this in SSMS on FLO-DDW-DEV / Formulary_Data
--  Then re-run only tDBInput_2 SELECT to confirm rows appear
-- =============================================================================

USE Formulary_Data;
GO

-- STEP 1: See current state
SELECT 'Before fix' AS Step,
       SUM(CASE WHEN Is_New_Record=1 THEN 1 ELSE 0 END) AS New_Records,
       SUM(CASE WHEN Is_New_Record=0 THEN 1 ELSE 0 END) AS Existing_Records,
       COUNT(*) AS Total
FROM dbo.MHA_Master_BPG;
GO

-- STEP 2: If any rows exist with Is_New_Record=0, flip them to 1 first
-- (these are already-inserted rows that just need their flag reset for testing)
UPDATE dbo.MHA_Master_BPG
SET Is_New_Record = 1,
    MMIT_Status   = 'Pending',
    Sent_To_MMIT  = 0,
    BPG_UPDSTMP   = GETDATE()
WHERE Is_New_Record = 0;

DECLARE @flipped INT = @@ROWCOUNT;
PRINT CONCAT('Flipped ', @flipped, ' existing rows to Is_New_Record=1');
GO

-- STEP 3: If MHA_Master_BPG is still empty, insert directly from BINPCN x PBM
DECLARE @masterCnt INT;
SELECT @masterCnt = COUNT(*) FROM dbo.MHA_Master_BPG;

IF @masterCnt = 0
BEGIN
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
    WHERE a.BP_END >= GETDATE();

    DECLARE @inserted INT = @@ROWCOUNT;
    PRINT CONCAT('Direct insert: ', @inserted, ' rows with Is_New_Record=1');
END
ELSE
    PRINT CONCAT('MHA_Master_BPG has ', @masterCnt, ' rows after flip — no direct insert needed');
GO

-- STEP 4: Confirm — run the EXACT tDBInput_2 SELECT
PRINT '>>> tDBInput_2 query result (should now return rows):';

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

-- STEP 5: Final count
SELECT 'After fix' AS Step,
       SUM(CASE WHEN Is_New_Record=1 THEN 1 ELSE 0 END) AS New_Records,
       SUM(CASE WHEN Is_New_Record=0 THEN 1 ELSE 0 END) AS Existing_Records,
       COUNT(*) AS Total
FROM dbo.MHA_Master_BPG;
GO

PRINT 'Done. Now re-run the Talend job — tDBInput_2 will pick up these rows.';
