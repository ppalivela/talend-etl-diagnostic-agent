-- =============================================================================
--  dbo.sp_MMIT_Recover
--  Purpose : Error-recovery SP — called by Talend tDBRow on OnSubjobError
--
--  Talend wiring (add these connections in the job designer):
--    tDBOutput_1        --OnSubjobError--> tDBRow_Recovery (calls this SP)
--    tDBRow_1 (load SP) --OnSubjobError--> tDBRow_Recovery
--    tDBInput_2         --OnSubjobError--> tDBRow_Recovery
--    tFileOutputDelimited_1 --OnSubjobError--> tDBRow_Recovery
--    tDBRow_2           --OnSubjobError--> tDBRow_Recovery
--
--  Recovery logic by failure point:
--    1. STAGING PARTIAL LOAD (tDBOutput_1 fails)
--       → TRUNCATE MHA_BPG_Staging so next run starts clean
--    2. SP FAILED (tDBRow_1 fails)
--       → DELETE any Is_New_Record=1 rows inserted today but not yet sent
--       → TRUNCATE staging
--    3. FILE WRITE FAILED (tDBInput_2 / tFileOutput fails)
--       → Leave Is_New_Record=1 rows in place — next run will retry them
--       → Log the failure
--    4. POST-SEND UPDATE FAILED (tDBRow_2 fails)
--       → Records are in Is_New_Record=1 state but file was already written
--       → Mark them MMIT_Status='RecoveryNeeded' so analyst can review
--       → Log for manual follow-up
--
--  Run on: FLO-DDW-DEV / Formulary_Data
--  Created: 2026-06-04
-- =============================================================================

USE Formulary_Data;
GO

-- =============================================================================
--  Create MMIT Error Log table (audit trail for all recovery events)
-- =============================================================================

IF OBJECT_ID('dbo.MMIT_ErrorLog', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MMIT_ErrorLog (
        LogID           INT           NOT NULL IDENTITY(1,1) PRIMARY KEY,
        JobName         VARCHAR(200)  NULL,
        ErrorStep       VARCHAR(100)  NULL,      -- Which subjob failed
        ErrorMessage    VARCHAR(MAX)  NULL,
        RecordsAffected INT           NULL,
        RecoveryAction  VARCHAR(500)  NULL,
        LogTimestamp    DATETIME      NOT NULL DEFAULT GETDATE(),
        ResolvedFlag    BIT           NOT NULL DEFAULT 0,
        ResolvedBy      VARCHAR(100)  NULL,
        ResolvedDate    DATETIME      NULL
    );
    PRINT 'Created dbo.MMIT_ErrorLog';
END
ELSE
    PRINT 'dbo.MMIT_ErrorLog already exists';
GO

-- =============================================================================
--  Create / Replace sp_MMIT_Recover
-- =============================================================================

IF OBJECT_ID('dbo.sp_MMIT_Recover', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_MMIT_Recover;
GO

CREATE PROCEDURE dbo.sp_MMIT_Recover
    @JobName        VARCHAR(200) = 'MMIT_MHA_Data_Ingestion_Final',
    @ErrorStep      VARCHAR(100) = 'Unknown',   -- Pass the component name from Talend context
    @ErrorMessage   VARCHAR(MAX) = 'Subjob error'
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @RecoveryAction VARCHAR(500) = '';
    DECLARE @Affected       INT          = 0;
    DECLARE @LogMsg         VARCHAR(MAX);

    -- -------------------------------------------------------------------------
    --  RECOVERY ACTION 0 (PREJOB):
    --  If sp_MMIT_Prep failed because _Holding tables already exist
    --  → Drop all orphaned _Holding tables so next run can start clean
    -- -------------------------------------------------------------------------
    IF @ErrorStep IN ('tDBRow_1_Prejob', 'sp_MMIT_Prep', 'Prejob', 'tDBRow_1')
    BEGIN
        DECLARE @dropSql    NVARCHAR(MAX);
        DECLARE @tblName    NVARCHAR(256);
        DECLARE @schName    NVARCHAR(128);
        DECLARE @holdingCnt INT = 0;

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
            SET @holdingCnt = @holdingCnt + 1;
            FETCH NEXT FROM hCur INTO @schName, @tblName;
        END
        CLOSE hCur;
        DEALLOCATE hCur;

        SET @RecoveryAction = @RecoveryAction
            + CONCAT('DROPPED ', @holdingCnt, ' orphaned _Holding table(s); ');
        SET @Affected = @holdingCnt;

        PRINT CONCAT('sp_MMIT_Recover [Prejob]: Dropped ', @holdingCnt, ' _Holding tables. Job can now re-run.');
    END

    -- -------------------------------------------------------------------------
    --  RECOVERY ACTION 1:
    --  Always truncate staging — prevents stale/partial data on next run
    -- -------------------------------------------------------------------------
    IF OBJECT_ID('dbo.MHA_BPG_Staging', 'U') IS NOT NULL
    BEGIN
        TRUNCATE TABLE dbo.MHA_BPG_Staging;
        SET @RecoveryAction = @RecoveryAction + 'TRUNCATED MHA_BPG_Staging; ';
    END

    -- -------------------------------------------------------------------------
    --  RECOVERY ACTION 2:
    --  If the SP (tDBRow_1 main) or staging load (tDBOutput_1) failed:
    --    → DELETE records inserted TODAY with Is_New_Record=1 and NOT YET SENT
    --      (these are orphaned inserts from the failed run)
    --  If file output or post-send update (tDBRow_2) failed:
    --    → Do NOT delete — keep Is_New_Record=1 so next run retries
    --    → Instead flag MMIT_Status='RecoveryNeeded' for analyst review
    -- -------------------------------------------------------------------------

    IF @ErrorStep IN ('tDBOutput_1', 'tDBInput_1', 'Unknown')
    BEGIN
        -- Safe to delete: these rows were never sent to MMIT
        DELETE FROM dbo.MHA_Master_BPG
        WHERE Is_New_Record  = 1
          AND Sent_To_MMIT   = 0
          AND MMIT_Status    = 'Pending'
          AND CAST(Date_Added_To_Master AS DATE) = CAST(GETDATE() AS DATE);

        SET @Affected       = @@ROWCOUNT;
        SET @RecoveryAction = @RecoveryAction
            + CONCAT('DELETED ', @Affected, ' orphaned Is_New_Record=1 rows added today; ');
    END
    ELSE IF @ErrorStep IN ('tDBRow_2', 'tFileOutputDelimited_1', 'tDBInput_2')
    BEGIN
        -- File may already have been written — flag for manual review
        UPDATE dbo.MHA_Master_BPG
        SET    MMIT_Status  = 'RecoveryNeeded'
        WHERE  Is_New_Record = 1
          AND  Sent_To_MMIT  = 0;

        SET @Affected       = @@ROWCOUNT;
        SET @RecoveryAction = @RecoveryAction
            + CONCAT('FLAGGED ', @Affected,
                     ' rows as RecoveryNeeded (file may have been written — check MMIT); ');
    END

    -- -------------------------------------------------------------------------
    --  LOG the recovery event
    -- -------------------------------------------------------------------------
    INSERT INTO dbo.MMIT_ErrorLog
        (JobName, ErrorStep, ErrorMessage, RecordsAffected, RecoveryAction)
    VALUES
        (@JobName, @ErrorStep, @ErrorMessage, @Affected, @RecoveryAction);

    -- Print for Talend console log
    SET @LogMsg = CONCAT(
        'sp_MMIT_Recover completed | Job: ', @JobName,
        ' | Step: ', @ErrorStep,
        ' | Action: ', @RecoveryAction
    );
    PRINT @LogMsg;

    -- Return result set for Talend tDBRow logging (optional)
    SELECT
        @JobName        AS JobName,
        @ErrorStep      AS FailedStep,
        @ErrorMessage   AS ErrorMessage,
        @RecoveryAction AS RecoveryAction,
        @Affected       AS RecordsAffected,
        GETDATE()       AS RecoveryTimestamp;
END;
GO

PRINT 'dbo.sp_MMIT_Recover created successfully.';
GO

-- =============================================================================
--  TEST — Simulate tDBRow_1 failure and verify recovery
-- =============================================================================

PRINT '=== TEST: Simulate tDBRow_1 failure ===';

-- Insert a fake "orphaned" pending row (as if SP ran partially)
INSERT INTO dbo.MHA_Master_BPG
    (BP_BIN, BP_PCN, BP_CHGRP, PB_NAME, BP_PLANTYPE,
     Sent_To_MMIT, MMIT_Status, Date_Added_To_Master, Is_New_Record)
VALUES ('999999','TEST','TEST_GRP','TEST PBM','Commercial', 0,'Pending', GETDATE(), 1);

DECLARE @beforeCnt INT;
SELECT @beforeCnt = COUNT(*) FROM dbo.MHA_Master_BPG WHERE Is_New_Record=1 AND MMIT_Status='Pending';
PRINT CONCAT('Before recovery: Is_New_Record=1 Pending rows = ', @beforeCnt);

-- Call recovery SP as Talend would on tDBRow_1 error
EXEC dbo.sp_MMIT_Recover
    @JobName      = 'Reload_MHA_BPG_Staging',
    @ErrorStep    = 'tDBRow_1',
    @ErrorMessage = 'TEST: Simulated subjob error on usp_MHA_BPG_LoadNewRecords';

DECLARE @afterCnt INT;
SELECT @afterCnt = COUNT(*) FROM dbo.MHA_Master_BPG WHERE Is_New_Record=1 AND MMIT_Status='Pending';
PRINT CONCAT('After recovery:  Is_New_Record=1 Pending rows = ', @afterCnt);
DECLARE @stgCnt INT;
SELECT @stgCnt = COUNT(*) FROM dbo.MHA_BPG_Staging;
PRINT CONCAT('Staging rows after recovery: ', @stgCnt);
GO

-- Show error log
PRINT '=== MMIT_ErrorLog ===';
SELECT * FROM dbo.MMIT_ErrorLog ORDER BY LogTimestamp DESC;
GO

-- =============================================================================
--  TALEND WIRING INSTRUCTIONS
-- =============================================================================
/*
In Talend Studio — Job: MMIT_MHA_Data_Ingestion_Final

STRUCTURE:
  ┌─────────────────────────────────────────────────────────────┐
  │  PREJOB                                                      │
  │  tDBRow_1 (EXEC dbo.sp_MMIT_Prep)                           │
  │       │                                                      │
  │       └──OnSubjobError──▶  tDBRow_Recovery                  │
  │              (EXEC dbo.sp_MMIT_Recover                       │
  │               'MMIT_MHA_Data_Ingestion_Final',               │
  │               'tDBRow_1_Prejob',                             │
  │               '_Holding tables exist - cleaned up')          │
  └─────────────────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────────────────┐
  │  MAIN JOB                                                    │
  │  tDBOutput_1  ──OnSubjobError──▶  tDBRow_Recovery           │
  │  tDBInput_2   ──OnSubjobError──▶  tDBRow_Recovery           │
  │  tFileOutputDelimited_1 ─OnSubjobError──▶ tDBRow_Recovery   │
  │  tDBRow_2     ──OnSubjobError──▶  tDBRow_Recovery           │
  └─────────────────────────────────────────────────────────────┘

STEPS TO WIRE IN TALEND STUDIO:
1. Add tDBRow_Recovery component (use same DB connection as tDBRow_1)
   SQL (use the static version — Talend passes @ErrorStep per connection):

   FOR PREJOB tDBRow_1:
       EXEC [dbo].[sp_MMIT_Recover]
           'MMIT_MHA_Data_Ingestion_Final',
           'tDBRow_1_Prejob',
           'sp_MMIT_Prep failed - _Holding tables exist'

   FOR MAIN JOB (one tDBRow_Recovery per component, or one shared):
       EXEC [dbo].[sp_MMIT_Recover]
           'MMIT_MHA_Data_Ingestion_Final',
           'tDBRow_2',          ← change per component
           'Subjob failed'

2. Draw OnSubjobError arrows:
   PREJOB:
     tDBRow_1 (sp_MMIT_Prep) ──OnSubjobError──▶ tDBRow_Recovery_Prejob

   MAIN JOB:
     tDBOutput_1              ──OnSubjobError──▶ tDBRow_Recovery
     tDBInput_2               ──OnSubjobError──▶ tDBRow_Recovery
     tFileOutputDelimited_1   ──OnSubjobError──▶ tDBRow_Recovery
     tDBRow_2                 ──OnSubjobError──▶ tDBRow_Recovery

3. Recovery behavior by failure point:
   Prejob tDBRow_1 fails (_Holding exists) → DROPS _Holding tables → re-run OK
   tDBOutput_1 fails   → staging truncated + orphan rows deleted → re-run OK
   tDBInput_2 fails    → rows flagged RecoveryNeeded → analyst checks MMIT
   tFileOutput fails   → rows flagged RecoveryNeeded → analyst checks MMIT
   tDBRow_2 fails      → rows flagged RecoveryNeeded → analyst checks MMIT

NOTE: tDBRow_Recovery in PREJOB is separate from tDBRow_Recovery in MAIN JOB
      because Prejob and Main Job are different subjob scopes in Talend.
      You can use ONE shared tDBRow_Recovery if you place it outside both scopes
      and connect OnSubjobError from both.
*/
