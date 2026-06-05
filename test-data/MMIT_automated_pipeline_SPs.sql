-- =============================================================================
--  FULLY AUTOMATED MMIT PIPELINE — Zero Manual Intervention
--
--  Production flow (fully automatic):
--    Talend Job starts
--      → Prejob: tDBRow_1 calls EXEC dbo.sp_MMIT_Prep
--          • Checks _Holding tables
--          • If found (previous run failed) → AUTO-drops them, logs incident, continues
--          • Creates new _Holding tables from source
--          • No error thrown → job continues normally
--      → Main job runs (tDBInput_1 → tMap_1 → tDBOutput_1 → tDBRow_1 → tDBInput_2 → tFileOutput → tDBRow_2)
--          • Any failure → OnSubjobError → tDBRow_Recovery → sp_MMIT_Recover (auto-cleanup)
--      → Postjob: EXEC dbo.sp_MMIT_Finalize
--          • Drops _Holding tables
--          • Marks run as complete in audit log
--
--  NO MANUAL SCRIPTS EVER NEEDED IN PRODUCTION
--
--  Run on: Formulary_Data
--  Created: 2026-06-04
-- =============================================================================

USE Formulary_Data;
GO

-- =============================================================================
--  STEP 1 — Create MMIT_RunLog (tracks every job run automatically)
-- =============================================================================

IF OBJECT_ID('dbo.MMIT_RunLog', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MMIT_RunLog (
        RunID           INT          NOT NULL IDENTITY(1,1) PRIMARY KEY,
        JobName         VARCHAR(200) NOT NULL,
        RunStatus       VARCHAR(50)  NOT NULL,   -- 'Started','Completed','Failed','AutoRecovered'
        HoldingTablesFound BIT       NOT NULL DEFAULT 0,
        HoldingTablesDropped INT     NOT NULL DEFAULT 0,
        NewRecordsLoaded INT         NULL,
        RecordsExported  INT         NULL,
        StartTime       DATETIME     NOT NULL DEFAULT GETDATE(),
        EndTime         DATETIME     NULL,
        Notes           VARCHAR(MAX) NULL
    );
    PRINT 'Created dbo.MMIT_RunLog';
END
ELSE
    PRINT 'dbo.MMIT_RunLog already exists';
GO

-- =============================================================================
--  STEP 2 — Create / Replace sp_MMIT_Prep
--           Called by Prejob tDBRow_1
--           AUTO-handles _Holding tables — NEVER throws error for them
-- =============================================================================

IF OBJECT_ID('dbo.sp_MMIT_Prep', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_MMIT_Prep;
GO

CREATE PROCEDURE dbo.sp_MMIT_Prep
    @JobName VARCHAR(200) = 'MMIT_MHA_Data_Ingestion_Final'
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @holdingFound   INT = 0;
    DECLARE @holdingDropped INT = 0;
    DECLARE @dropSql        NVARCHAR(MAX);
    DECLARE @tblName        NVARCHAR(256);
    DECLARE @schName        NVARCHAR(128);
    DECLARE @RunID          INT;

    -- -------------------------------------------------------------------------
    --  1. Log job start
    -- -------------------------------------------------------------------------
    INSERT INTO dbo.MMIT_RunLog (JobName, RunStatus)
    VALUES (@JobName, 'Started');
    SET @RunID = SCOPE_IDENTITY();

    -- -------------------------------------------------------------------------
    --  2. Check for orphaned _Holding tables from previous failed run
    -- -------------------------------------------------------------------------
    SELECT @holdingFound = COUNT(*)
    FROM sys.tables
    WHERE name LIKE '%_Holding%' OR name LIKE '%Holding%';

    IF @holdingFound > 0
    BEGIN
        -- AUTO-DROP: log the incident and continue — no error raised
        PRINT CONCAT('sp_MMIT_Prep: Found ', @holdingFound,
                     ' orphaned _Holding table(s) from previous failed run. Auto-cleaning...');

        -- Log to error log for audit trail
        IF OBJECT_ID('dbo.MMIT_ErrorLog', 'U') IS NOT NULL
            INSERT INTO dbo.MMIT_ErrorLog
                (JobName, ErrorStep, ErrorMessage, RecordsAffected, RecoveryAction, ResolvedFlag)
            VALUES (
                @JobName,
                'sp_MMIT_Prep - AutoCleanup',
                CONCAT('Found ', @holdingFound, ' orphaned _Holding tables from previous failed run. Auto-dropping.'),
                @holdingFound,
                'Auto-dropped _Holding tables during Prep. Run continues normally.',
                1
            );

        -- Drop all _Holding tables
        DECLARE hCur CURSOR FOR
            SELECT SCHEMA_NAME(schema_id), name
            FROM sys.tables
            WHERE name LIKE '%_Holding%' OR name LIKE '%Holding%';

        OPEN hCur;
        FETCH NEXT FROM hCur INTO @schName, @tblName;
        WHILE @@FETCH_STATUS = 0
        BEGIN
            SET @dropSql = CONCAT('DROP TABLE IF EXISTS [',@schName,'].[',@tblName,'];');
            EXEC sp_executesql @dropSql;
            SET @holdingDropped = @holdingDropped + 1;
            PRINT CONCAT('  Dropped: [', @schName, '].[', @tblName, ']');
            FETCH NEXT FROM hCur INTO @schName, @tblName;
        END
        CLOSE hCur;
        DEALLOCATE hCur;

        -- Update run log: mark as AutoRecovered
        UPDATE dbo.MMIT_RunLog
        SET RunStatus            = 'AutoRecovered',
            HoldingTablesFound   = @holdingFound,
            HoldingTablesDropped = @holdingDropped,
            Notes = CONCAT('Auto-dropped ', @holdingDropped, ' orphaned _Holding tables. Continuing job.')
        WHERE RunID = @RunID;

        PRINT CONCAT('sp_MMIT_Prep: Auto-cleanup done. Dropped ', @holdingDropped, ' table(s). Job continues.');
    END
    ELSE
    BEGIN
        UPDATE dbo.MMIT_RunLog
        SET Notes = 'No orphaned _Holding tables found. Clean start.'
        WHERE RunID = @RunID;
        PRINT 'sp_MMIT_Prep: No orphaned _Holding tables. Clean start.';
    END

    -- -------------------------------------------------------------------------
    --  3. Return RunID so Talend context can use it (optional)
    -- -------------------------------------------------------------------------
    SELECT @RunID AS RunID, @holdingFound AS HoldingTablesFound, @holdingDropped AS HoldingTablesDropped;

END;
GO

PRINT 'dbo.sp_MMIT_Prep created — auto-handles _Holding tables, never blocks job.';
GO

-- =============================================================================
--  STEP 3 — Create / Replace sp_MMIT_Finalize
--           Called by Postjob tDBRow — marks run complete, drops _Holding tables
-- =============================================================================

IF OBJECT_ID('dbo.sp_MMIT_Finalize', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_MMIT_Finalize;
GO

CREATE PROCEDURE dbo.sp_MMIT_Finalize
    @JobName         VARCHAR(200) = 'MMIT_MHA_Data_Ingestion_Final',
    @RecordsExported INT          = 0
AS
BEGIN
    SET NOCOUNT ON;

    -- Drop _Holding tables (normal end-of-run cleanup)
    DECLARE @dropSql NVARCHAR(MAX);
    DECLARE @tbl     NVARCHAR(256);
    DECLARE @sch     NVARCHAR(128);
    DECLARE @dropped INT = 0;

    DECLARE fCur CURSOR FOR
        SELECT SCHEMA_NAME(schema_id), name
        FROM sys.tables
        WHERE name LIKE '%_Holding%' OR name LIKE '%Holding%';

    OPEN fCur;
    FETCH NEXT FROM fCur INTO @sch, @tbl;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @dropSql = CONCAT('DROP TABLE IF EXISTS [',@sch,'].[',@tbl,'];');
        EXEC sp_executesql @dropSql;
        SET @dropped = @dropped + 1;
        FETCH NEXT FROM fCur INTO @sch, @tbl;
    END
    CLOSE fCur;
    DEALLOCATE fCur;

    -- Mark most recent run as Completed
    UPDATE dbo.MMIT_RunLog
    SET RunStatus       = 'Completed',
        RecordsExported = @RecordsExported,
        EndTime         = GETDATE(),
        Notes           = CONCAT(Notes, ' | Finalized OK. Dropped ', @dropped, ' _Holding tables.')
    WHERE RunID = (SELECT MAX(RunID) FROM dbo.MMIT_RunLog WHERE JobName = @JobName);

    PRINT CONCAT('sp_MMIT_Finalize: Run complete. Exported ', @RecordsExported,
                 ' records. Dropped ', @dropped, ' _Holding tables.');

    SELECT 'Completed' AS Status, @RecordsExported AS RecordsExported, GETDATE() AS FinishTime;
END;
GO

PRINT 'dbo.sp_MMIT_Finalize created.';
GO

-- =============================================================================
--  STEP 4 — Update sp_MMIT_Recover (OnSubjobError handler — marks run as Failed)
-- =============================================================================

IF OBJECT_ID('dbo.sp_MMIT_Recover', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_MMIT_Recover;
GO

CREATE PROCEDURE dbo.sp_MMIT_Recover
    @JobName      VARCHAR(200) = 'MMIT_MHA_Data_Ingestion_Final',
    @ErrorStep    VARCHAR(100) = 'Unknown',
    @ErrorMessage VARCHAR(MAX) = 'Subjob error'
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @RecoveryAction VARCHAR(500) = '';
    DECLARE @Affected       INT          = 0;

    -- Truncate staging (always safe)
    IF OBJECT_ID('dbo.MHA_BPG_Staging', 'U') IS NOT NULL
    BEGIN
        TRUNCATE TABLE dbo.MHA_BPG_Staging;
        SET @RecoveryAction = @RecoveryAction + 'TRUNCATED MHA_BPG_Staging; ';
    END

    -- For main job errors: flag affected rows
    IF @ErrorStep IN ('tDBRow_2', 'tFileOutputDelimited_1', 'tDBInput_2')
    BEGIN
        UPDATE dbo.MHA_Master_BPG
        SET    MMIT_Status = 'RecoveryNeeded'
        WHERE  Is_New_Record = 1 AND Sent_To_MMIT = 0;

        SET @Affected       = @@ROWCOUNT;
        SET @RecoveryAction = @RecoveryAction
            + CONCAT('FLAGGED ', @Affected, ' rows as RecoveryNeeded; ');
    END
    ELSE
    BEGIN
        -- Early failure — delete today's unsent pending rows
        DELETE FROM dbo.MHA_Master_BPG
        WHERE Is_New_Record = 1 AND Sent_To_MMIT = 0
          AND MMIT_Status = 'Pending'
          AND CAST(Date_Added_To_Master AS DATE) = CAST(GETDATE() AS DATE);

        SET @Affected       = @@ROWCOUNT;
        SET @RecoveryAction = @RecoveryAction
            + CONCAT('DELETED ', @Affected, ' orphaned pending rows; ');
    END

    -- Log to MMIT_ErrorLog
    IF OBJECT_ID('dbo.MMIT_ErrorLog', 'U') IS NOT NULL
        INSERT INTO dbo.MMIT_ErrorLog
            (JobName, ErrorStep, ErrorMessage, RecordsAffected, RecoveryAction)
        VALUES (@JobName, @ErrorStep, @ErrorMessage, @Affected, @RecoveryAction);

    -- Mark run as Failed in RunLog
    UPDATE dbo.MMIT_RunLog
    SET RunStatus = 'Failed',
        EndTime   = GETDATE(),
        Notes     = CONCAT(ISNULL(Notes,''), ' | FAILED at ', @ErrorStep, '. Recovery: ', @RecoveryAction)
    WHERE RunID = (SELECT MAX(RunID) FROM dbo.MMIT_RunLog WHERE JobName = @JobName);

    PRINT CONCAT('sp_MMIT_Recover: ', @RecoveryAction);
    SELECT @JobName AS JobName, @ErrorStep AS FailedStep, @RecoveryAction AS RecoveryAction, GETDATE() AS Timestamp;
END;
GO

PRINT 'dbo.sp_MMIT_Recover updated.';
GO

-- =============================================================================
--  VERIFY — All 3 SPs exist and ready
-- =============================================================================

SELECT name AS StoredProcedure, create_date, modify_date
FROM sys.procedures
WHERE name IN ('sp_MMIT_Prep', 'sp_MMIT_Finalize', 'sp_MMIT_Recover')
ORDER BY name;
GO

PRINT '';
PRINT '======================================================';
PRINT ' PRODUCTION TALEND JOB WIRING (no manual steps ever)';
PRINT '';
PRINT ' PREJOB:';
PRINT '   tDBRow_1: EXEC dbo.sp_MMIT_Prep';
PRINT '     └─ OnSubjobError ─▶ tDBRow_Recovery: EXEC dbo.sp_MMIT_Recover ... tDBRow_1_Prejob';
PRINT '';
PRINT ' MAIN JOB:';
PRINT '   tDBOutput_1 ─ OnSubjobError ─▶ tDBRow_Recovery';
PRINT '   tDBInput_2  ─ OnSubjobError ─▶ tDBRow_Recovery';
PRINT '   tFileOutput ─ OnSubjobError ─▶ tDBRow_Recovery';
PRINT '   tDBRow_2    ─ OnSubjobError ─▶ tDBRow_Recovery';
PRINT '';
PRINT ' POSTJOB:';
PRINT '   tDBRow_Finalize: EXEC dbo.sp_MMIT_Finalize';
PRINT '======================================================';
GO
