-- =============================================================================
--  DUMMY TEST DATA — Formulary_Data
--  Table:  dbo.MHA_Master_BPG
--  Query:  SELECT BP_BIN, BP_PCN, BP_CHGRP, PB_NAME, BP_PLANTYPE,
--                 Sent_To_MMIT, MMIT_Status, Date_Added_To_Master
--          FROM dbo.MHA_Master_BPG
--          WHERE Is_New_Record = 1
--          ORDER BY Date_Added_To_Master DESC, BP_BIN, BP_PCN
--
--  Run on: FLO-DDW-DEV / Formulary_Data
--  Created: 2026-06-03
-- =============================================================================

USE Formulary_Data;
GO

-- =============================================================================
--  STEP 1 — Create table (only if it does not already exist)
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
        Sent_To_MMIT            BIT           NOT NULL DEFAULT 0,   -- 0=No 1=Yes
        MMIT_Status             VARCHAR(50)   NULL,                 -- 'Pending','Sent','Processed','Error'
        Date_Added_To_Master    DATETIME      NOT NULL DEFAULT GETDATE(),
        Is_New_Record           BIT           NOT NULL DEFAULT 1,   -- 1=New 0=Existing
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
--  STEP 2 — Insert NEW records (Is_New_Record = 1)
--           These are what the Talend job will pick up and send to MMIT
-- =============================================================================

INSERT INTO dbo.MHA_Master_BPG
    (BP_BIN, BP_PCN,       BP_CHGRP,        PB_NAME,                     BP_PLANTYPE,       Sent_To_MMIT, MMIT_Status, Date_Added_To_Master, Is_New_Record)
VALUES
-- ── Brand-new BIN/PCN combinations added this cycle (Sent_To_MMIT=0, Pending) ──
('610014', 'ESI',        'COMMERC_NEW1',   'Express Scripts (ESI)',      'Commercial',       0, 'Pending',    DATEADD(DAY, -1, GETDATE()), 1),
('610014', 'ESI',        'COMMERC_NEW2',   'Express Scripts (ESI)',      'Commercial',       0, 'Pending',    DATEADD(DAY, -1, GETDATE()), 1),
('610014', 'MEDCO',      'MEDCO_NEW1',     'Express Scripts (ESI)',      'Commercial',       0, 'Pending',    DATEADD(DAY, -2, GETDATE()), 1),
('610014', 'ESI',        'MEDB_NEW26',     'Express Scripts (ESI)',      'Medicare Part D',  0, 'Pending',    DATEADD(DAY, -1, GETDATE()), 1),
('004336', 'ADV',        'CVS_NEW01',      'CVS Caremark',               'Commercial',       0, 'Pending',    DATEADD(DAY, -3, GETDATE()), 1),
('004336', 'PBMADV',     'CVS_NEW02',      'CVS Caremark',               'Commercial',       0, 'Pending',    DATEADD(DAY, -3, GETDATE()), 1),
('610502', 'ADV',        'CVS_MED_NEW',    'CVS Caremark',               'Medicare Part D',  0, 'Pending',    DATEADD(DAY, -2, GETDATE()), 1),
('610591', 'ADV',        'OPT_NEW01',      'OptumRx',                    'Commercial',       0, 'Pending',    DATEADD(DAY, -4, GETDATE()), 1),
('610591', 'OPTUMRX',    'OPT_NEW02',      'OptumRx',                    'Commercial',       0, 'Pending',    DATEADD(DAY, -4, GETDATE()), 1),
('610591', 'ADV',        'OPT_MED_NEW',    'OptumRx',                    'Medicare Part D',  0, 'Pending',    DATEADD(DAY, -1, GETDATE()), 1),
('610020', 'MEDIMPACT',  'MEDI_NEW1',      'MedImpact Healthcare Systems','Commercial',      0, 'Pending',    DATEADD(DAY, -5, GETDATE()), 1),
('610020', 'MEDIMPACT',  'MEDI_NEW2',      'MedImpact Healthcare Systems','Medicaid',        0, 'Pending',    DATEADD(DAY, -5, GETDATE()), 1),
('610649', 'NAVITUS',    'NAV_NEW01',      'Navitus Health Solutions',   'Commercial',       0, 'Pending',    DATEADD(DAY, -2, GETDATE()), 1),
('610649', 'NAVITUS',    'NAV_MED_NEW',    'Navitus Health Solutions',   'Medicare Part D',  0, 'Pending',    DATEADD(DAY, -2, GETDATE()), 1),
('015581', 'HUMRX',      'HUM_MED_NEW',    'Humana Pharmacy Solutions',  'Medicare Part D',  0, 'Pending',    DATEADD(DAY, -1, GETDATE()), 1),
('015581', 'HUMANA',     'HUM_COM_NEW',    'Humana Pharmacy Solutions',  'Commercial',       0, 'Pending',    DATEADD(DAY, -1, GETDATE()), 1),
('600428', 'PRIMETP',    'PRI_NEW01',      'Prime Therapeutics',         'Commercial',       0, 'Pending',    DATEADD(DAY, -6, GETDATE()), 1),
('600428', 'PRIMETP',    'PRI_MCAID_NEW',  'Prime Therapeutics',         'Medicaid',         0, 'Pending',    DATEADD(DAY, -6, GETDATE()), 1),
('610011', 'SXC',        'SXC_NEW01',      'SXC Health Solutions',       'Commercial',       0, 'Pending',    DATEADD(DAY, -3, GETDATE()), 1),
('010540', 'MAGELLAN',   'MAG_NEW01',      'Magellan Rx Management',     'Commercial',       0, 'Pending',    DATEADD(DAY, -7, GETDATE()), 1),
('010540', 'MAGELLAN',   'MAG_MCAID_NEW',  'Magellan Rx Management',     'Medicaid',         0, 'Pending',    DATEADD(DAY, -7, GETDATE()), 1),
('011779', 'WELLDYNE',   'WDR_NEW01',      'WellDyneRx',                 'Commercial',       0, 'Pending',    DATEADD(DAY, -2, GETDATE()), 1),
('610460', 'ZINC',       'ZINC_NEW1',      'Zinc Health Services',       'Commercial',       0, 'Pending',    DATEADD(DAY, -1, GETDATE()), 1),
-- ── A few already-sent rows (Is_New_Record = 1 but Sent_To_MMIT = 1) ──────────
--   These still appear in the query (Is_New_Record=1 not yet flipped to 0)
('610014', 'ESI',        'COMMERC_SENT',   'Express Scripts (ESI)',      'Commercial',       1, 'Sent',       DATEADD(DAY, -10, GETDATE()), 1),
('004336', 'ADV',        'CVS_SENT01',     'CVS Caremark',               'Commercial',       1, 'Processed',  DATEADD(DAY, -12, GETDATE()), 1);

DECLARE @newCnt INT;
SELECT @newCnt = COUNT(*) FROM dbo.MHA_Master_BPG WHERE Is_New_Record = 1;
PRINT CONCAT('New records (Is_New_Record=1): ', @newCnt);
GO

-- =============================================================================
--  STEP 3 — Insert EXISTING records (Is_New_Record = 0)
--           These should NOT appear in the Talend job query — used to verify filter
-- =============================================================================

INSERT INTO dbo.MHA_Master_BPG
    (BP_BIN, BP_PCN,       BP_CHGRP,        PB_NAME,                     BP_PLANTYPE,       Sent_To_MMIT, MMIT_Status,  Date_Added_To_Master, Is_New_Record)
VALUES
('610014', 'ESI',        'OLD_COMM01',     'Express Scripts (ESI)',      'Commercial',       1, 'Processed',  DATEADD(MONTH, -3, GETDATE()), 0),
('004336', 'ADV',        'OLD_CVS01',      'CVS Caremark',               'Commercial',       1, 'Processed',  DATEADD(MONTH, -6, GETDATE()), 0),
('610591', 'ADV',        'OLD_OPT01',      'OptumRx',                    'Commercial',       1, 'Processed',  DATEADD(MONTH, -4, GETDATE()), 0),
('610649', 'NAVITUS',    'OLD_NAV01',      'Navitus Health Solutions',   'Commercial',       1, 'Processed',  DATEADD(MONTH, -2, GETDATE()), 0),
('015581', 'HUMRX',      'OLD_HUM01',      'Humana Pharmacy Solutions',  'Medicare Part D',  1, 'Processed',  DATEADD(MONTH, -5, GETDATE()), 0);

DECLARE @existCnt INT;
SELECT @existCnt = COUNT(*) FROM dbo.MHA_Master_BPG WHERE Is_New_Record = 0;
PRINT CONCAT('Existing records (Is_New_Record=0): ', @existCnt);
GO

-- =============================================================================
--  STEP 4 — Run the EXACT Talend job query
-- =============================================================================

PRINT '=== TALEND JOB QUERY RESULTS (Is_New_Record = 1) ===';

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
    'Total rows'             AS Category, COUNT(*)                                  AS RowCount FROM dbo.MHA_Master_BPG
UNION ALL
SELECT 'Is_New_Record = 1',  COUNT(*) FROM dbo.MHA_Master_BPG WHERE Is_New_Record = 1
UNION ALL
SELECT 'Is_New_Record = 0',  COUNT(*) FROM dbo.MHA_Master_BPG WHERE Is_New_Record = 0
UNION ALL
SELECT 'Sent_To_MMIT = 0',   COUNT(*) FROM dbo.MHA_Master_BPG WHERE Sent_To_MMIT = 0
UNION ALL
SELECT 'Sent_To_MMIT = 1',   COUNT(*) FROM dbo.MHA_Master_BPG WHERE Sent_To_MMIT = 1
UNION ALL
SELECT 'Status = Pending',   COUNT(*) FROM dbo.MHA_Master_BPG WHERE MMIT_Status = 'Pending'
UNION ALL
SELECT 'Status = Sent',      COUNT(*) FROM dbo.MHA_Master_BPG WHERE MMIT_Status = 'Sent'
UNION ALL
SELECT 'Status = Processed', COUNT(*) FROM dbo.MHA_Master_BPG WHERE MMIT_Status = 'Processed';
GO

-- =============================================================================
--  CLEANUP HELPER — run ONLY to remove test data (commented out by default)
-- =============================================================================
/*
DROP TABLE IF EXISTS dbo.MHA_Master_BPG;
PRINT 'Table dropped.';
*/
