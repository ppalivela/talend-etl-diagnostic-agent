-- =============================================================================
--  QA FIX — Patch errors from QA_incremental_load_setup.sql
--  Fixes: Date_Sent_MMIT column not in real table + RowCount reserved word
--  Run on: FLO-DDW-DEV / Formulary_Data
-- =============================================================================

USE Formulary_Data;
GO

-- See actual columns of MHA_Master_BPG so we match exactly
PRINT '=== Real MHA_Master_BPG columns ===';
SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'MHA_Master_BPG'
ORDER BY ORDINAL_POSITION;
GO

-- =============================================================================
--  STEP 1 — Re-seed MHA_Master_BPG with 30 EXISTING records
--           (Step 5 failed, so table is empty — fix that now)
--           Uses only columns confirmed to exist
-- =============================================================================

-- Clear in case any partial rows got in
DELETE FROM dbo.MHA_Master_BPG;
PRINT 'Cleared MHA_Master_BPG for clean re-seed';

INSERT INTO dbo.MHA_Master_BPG
    (BP_BIN, BP_PCN, BP_CHGRP, PB_NAME, BP_PLANTYPE,
     Sent_To_MMIT, MMIT_Status, Date_Added_To_Master, Is_New_Record)
SELECT DISTINCT
    a.BP_BIN,
    a.BP_PCN,
    a.BP_CHGRP,
    b.PB_NAME,
    b.BP_PLANTYPE,
    1           AS Sent_To_MMIT,
    'Processed' AS MMIT_Status,
    DATEADD(DAY, -30, GETDATE()) AS Date_Added_To_Master,
    0           AS Is_New_Record       -- Already processed in previous run
FROM dbo.BINPCN  a
INNER JOIN dbo.PBM b ON a.BP_PBID = b.PB_PBID
WHERE a.BP_END >= GETDATE()
  AND a.BP_BIN NOT IN ('810001','810002','820001','820002','830001','830002');

DECLARE @existCnt INT;
SELECT @existCnt = COUNT(*) FROM dbo.MHA_Master_BPG WHERE Is_New_Record = 0;
PRINT CONCAT('[STEP 1] Seeded ', @existCnt, ' existing records (Is_New_Record=0)');
GO

-- =============================================================================
--  STEP 2 — Verify QA state (fixed alias — no reserved words)
-- =============================================================================

SELECT
    'BINPCN active (tDBInput_1 source)'            AS Description,
    COUNT(*) AS Total_Rows
FROM dbo.BINPCN a
INNER JOIN dbo.PBM b ON a.BP_PBID = b.PB_PBID
WHERE a.BP_END >= GETDATE()
UNION ALL
SELECT 'MHA_BPG_Staging (empty — job fills this)',   COUNT(*) FROM dbo.MHA_BPG_Staging
UNION ALL
SELECT 'MHA_Master_BPG existing (Is_New_Record=0)',  COUNT(*) FROM dbo.MHA_Master_BPG WHERE Is_New_Record=0
UNION ALL
SELECT 'MHA_Master_BPG new (Is_New_Record=1)',        COUNT(*) FROM dbo.MHA_Master_BPG WHERE Is_New_Record=1
UNION ALL
SELECT 'EXPECTED new rows after SP runs',
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
PRINT '======================================================';
PRINT ' QA STATE READY. Now run the Talend job.';
PRINT ' Expected: tDBInput_2 returns 10 rows (new test BINs)';
PRINT '======================================================';
GO
