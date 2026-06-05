-- =============================================================================
--  CLEANUP: Drop orphaned _Holding tables from failed MMIT weekly load
--
--  Error:  _Holding tables already exist. The previous MMIT weekly load
--          may have failed before sp_MMIT_Finalize was called.
--  Job:    MMIT_MHA_Data_Ingestion_Final
--  Component: tDBRow_1
--
--  This script:
--    1. Shows all _Holding tables currently in the database
--    2. Drops them safely (with existence check)
--    3. Logs the cleanup to MMIT_ErrorLog (if it exists)
--    4. Confirms the job can now re-run cleanly
--
--  Run on: Formulary_Data (or whichever DB the MMIT job uses)
--  Created: 2026-06-04
-- =============================================================================

USE Formulary_Data;
GO

-- =============================================================================
--  STEP 1 — Show all _Holding tables that exist (investigate before dropping)
-- =============================================================================

PRINT '=== ORPHANED _Holding TABLES FOUND ===';

SELECT
    t.name                  AS TableName,
    t.create_date           AS Created,
    t.modify_date           AS LastModified,
    p.rows                  AS RowCount,
    SCHEMA_NAME(t.schema_id) AS SchemaName
FROM sys.tables t
INNER JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0,1)
WHERE t.name LIKE '%_Holding%'
   OR t.name LIKE '%Holding%'
ORDER BY t.create_date DESC;
GO

-- =============================================================================
--  STEP 2 — Drop all _Holding tables dynamically
-- =============================================================================

PRINT '=== DROPPING _Holding TABLES ===';

DECLARE @sql        NVARCHAR(MAX) = '';
DECLARE @tableName  NVARCHAR(256);
DECLARE @schemaName NVARCHAR(128);
DECLARE @dropped    INT = 0;

DECLARE cur CURSOR FOR
    SELECT SCHEMA_NAME(schema_id), name
    FROM sys.tables
    WHERE name LIKE '%_Holding%'
       OR name LIKE '%Holding%'
    ORDER BY name;

OPEN cur;
FETCH NEXT FROM cur INTO @schemaName, @tableName;

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @sql = CONCAT('DROP TABLE IF EXISTS [', @schemaName, '].[', @tableName, '];');
    PRINT CONCAT('Dropping: [', @schemaName, '].[', @tableName, ']');
    EXEC sp_executesql @sql;
    SET @dropped = @dropped + 1;
    FETCH NEXT FROM cur INTO @schemaName, @tableName;
END

CLOSE cur;
DEALLOCATE cur;

PRINT CONCAT('Done. Dropped ', @dropped, ' _Holding table(s).');
GO

-- =============================================================================
--  STEP 3 — Verify all _Holding tables are gone
-- =============================================================================

DECLARE @remaining INT;
SELECT @remaining = COUNT(*)
FROM sys.tables
WHERE name LIKE '%_Holding%' OR name LIKE '%Holding%';

IF @remaining = 0
    PRINT '✅ All _Holding tables removed. Job can now re-run safely.';
ELSE
BEGIN
    PRINT CONCAT('⚠️  WARNING: ', @remaining, ' _Holding table(s) still exist — check permissions.');
    SELECT name AS RemainingTable, SCHEMA_NAME(schema_id) AS SchemaName
    FROM sys.tables
    WHERE name LIKE '%_Holding%' OR name LIKE '%Holding%';
END
GO

-- =============================================================================
--  STEP 4 — Log cleanup to MMIT_ErrorLog (if table exists)
-- =============================================================================

IF OBJECT_ID('dbo.MMIT_ErrorLog', 'U') IS NOT NULL
BEGIN
    INSERT INTO dbo.MMIT_ErrorLog
        (JobName, ErrorStep, ErrorMessage, RecordsAffected, RecoveryAction, ResolvedFlag)
    VALUES (
        'MMIT_MHA_Data_Ingestion_Final',
        'tDBRow_1 - Manual Cleanup',
        '_Holding tables already exist. Previous MMIT weekly load failed before sp_MMIT_Finalize was called.',
        0,
        'Manually dropped all _Holding tables. Job is clear to re-run.',
        1
    );
    PRINT 'Cleanup logged to MMIT_ErrorLog.';
END
GO

PRINT '';
PRINT '======================================================';
PRINT ' NEXT STEPS:';
PRINT ' 1. Re-run the Talend job MMIT_MHA_Data_Ingestion_Final';
PRINT ' 2. Monitor tDBRow_1 — should pass the _Holding check';
PRINT ' 3. If job fails again, sp_MMIT_Recover will auto-cleanup';
PRINT '======================================================';
GO
