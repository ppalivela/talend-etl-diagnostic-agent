-- =============================================================================
--  DIAGNOSTIC: Run this in SSMS and share the output
--  It will tell us exactly why tDBInput_2 gets 0 rows
-- =============================================================================

USE Formulary_Data;
GO

PRINT '=== 1. TABLE EXISTS CHECK ===';
SELECT
    name AS TableName,
    create_date,
    modify_date
FROM sys.tables
WHERE name IN ('BINPCN','PBM','MHA_Master_BPG','MHA_BPG_Staging')
ORDER BY name;

PRINT '=== 2. ROW COUNTS ===';
SELECT 'dbo.BINPCN'         AS Tbl, COUNT(*) AS Total, SUM(CASE WHEN BP_END >= GETDATE() THEN 1 ELSE 0 END) AS Active FROM dbo.BINPCN
UNION ALL SELECT 'dbo.PBM', COUNT(*), NULL FROM dbo.PBM
UNION ALL SELECT 'dbo.MHA_Master_BPG Total', COUNT(*), NULL FROM dbo.MHA_Master_BPG
UNION ALL SELECT 'dbo.MHA_Master_BPG Is_New_Record=1', SUM(CASE WHEN Is_New_Record=1 THEN 1 ELSE 0 END), NULL FROM dbo.MHA_Master_BPG
UNION ALL SELECT 'dbo.MHA_Master_BPG Is_New_Record=0', SUM(CASE WHEN Is_New_Record=0 THEN 1 ELSE 0 END), NULL FROM dbo.MHA_Master_BPG;

PRINT '=== 3. MHA_BPG_STAGING ROW COUNT ===';
IF OBJECT_ID('dbo.MHA_BPG_Staging','U') IS NOT NULL
    SELECT COUNT(*) AS StagingRows FROM dbo.MHA_BPG_Staging;
ELSE
    PRINT 'MHA_BPG_Staging does NOT exist';

PRINT '=== 4. SP EXISTS CHECK ===';
SELECT name, create_date, modify_date
FROM sys.procedures
WHERE name = 'usp_MHA_BPG_LoadNewRecords';

PRINT '=== 5. SP DEFINITION (what it actually does) ===';
IF OBJECT_ID('dbo.usp_MHA_BPG_LoadNewRecords','P') IS NOT NULL
    EXEC sp_helptext 'dbo.usp_MHA_BPG_LoadNewRecords';
ELSE
    PRINT 'SP does NOT exist';

PRINT '=== 6. SAMPLE MHA_Master_BPG rows ===';
SELECT TOP 10 * FROM dbo.MHA_Master_BPG ORDER BY BPG_ID DESC;
GO
