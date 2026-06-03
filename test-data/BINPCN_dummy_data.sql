-- =============================================================================
--  DUMMY TEST DATA — Formulary_Data  (Talend Job Testing)
--  Tables: dbo.BINPCN  x  dbo.PBM
--  Query:  SELECT DISTINCT BP_BIN, BP_PCN, BP_CHGRP, PB_NAME, BP_PLANTYPE
--          FROM dbo.BINPCN a INNER JOIN dbo.PBM b ON a.BP_PBID = b.PB_PBID
--          WHERE a.BP_END >= GETDATE()
--
--  Run this on: FLO-DDW-DEV / Formulary_Data   (or any test SQL Server)
--  Created:     2026-06-03
-- =============================================================================

USE Formulary_Data;
GO

-- =============================================================================
--  STEP 1 — Create tables (only if they do not already exist)
-- =============================================================================

IF OBJECT_ID('dbo.PBM', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.PBM (
        PB_PBID         INT           NOT NULL PRIMARY KEY,
        PB_NAME         VARCHAR(100)  NOT NULL,
        BP_PLANTYPE     VARCHAR(50)   NOT NULL,
        PB_STATUS       CHAR(1)       NOT NULL DEFAULT 'A',   -- A=Active
        PB_ADDSTMP      DATETIME      NOT NULL DEFAULT GETDATE(),
        PB_UPDSTMP      DATETIME      NULL
    );
    PRINT 'Created dbo.PBM';
END
ELSE
    PRINT 'dbo.PBM already exists — skipping CREATE';
GO

IF OBJECT_ID('dbo.BINPCN', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.BINPCN (
        BP_ID           INT           NOT NULL IDENTITY(1,1) PRIMARY KEY,
        BP_PBID         INT           NOT NULL REFERENCES dbo.PBM(PB_PBID),
        BP_BIN          VARCHAR(10)   NOT NULL,
        BP_PCN          VARCHAR(20)   NOT NULL,
        BP_CHGRP        VARCHAR(30)   NOT NULL,
        BP_START        DATE          NOT NULL,
        BP_END          DATE          NOT NULL,
        BP_ADDSTMP      DATETIME      NOT NULL DEFAULT GETDATE(),
        BP_UPDSTMP      DATETIME      NULL
    );
    PRINT 'Created dbo.BINPCN';
END
ELSE
    PRINT 'dbo.BINPCN already exists — skipping CREATE';
GO

-- =============================================================================
--  STEP 2 — Insert PBM (Pharmacy Benefit Manager) reference data
--           Uses MERGE so it is safe to re-run (no duplicate key errors)
-- =============================================================================

MERGE dbo.PBM AS tgt
USING (VALUES
    -- PB_PBID  PB_NAME                          BP_PLANTYPE
    (1,  'Express Scripts (ESI)',              'Commercial'),
    (2,  'Express Scripts (ESI)',              'Medicare Part D'),
    (3,  'CVS Caremark',                       'Commercial'),
    (4,  'CVS Caremark',                       'Medicare Part D'),
    (5,  'OptumRx',                            'Commercial'),
    (6,  'OptumRx',                            'Medicare Part D'),
    (7,  'MedImpact Healthcare Systems',       'Commercial'),
    (8,  'MedImpact Healthcare Systems',       'Medicaid'),
    (9,  'Navitus Health Solutions',           'Commercial'),
    (10, 'Navitus Health Solutions',           'Medicare Part D'),
    (11, 'Humana Pharmacy Solutions',          'Medicare Part D'),
    (12, 'Humana Pharmacy Solutions',          'Commercial'),
    (13, 'Prime Therapeutics',                 'Commercial'),
    (14, 'Prime Therapeutics',                 'Medicaid'),
    (15, 'SXC Health Solutions',               'Commercial'),
    (16, 'Magellan Rx Management',             'Commercial'),
    (17, 'Magellan Rx Management',             'Medicaid'),
    (18, 'WellDyneRx',                         'Commercial'),
    (19, 'InfuSystem / HealthDrive',           'Commercial'),
    (20, 'Zinc Health Services',               'Commercial')
) AS src (PB_PBID, PB_NAME, BP_PLANTYPE)
ON tgt.PB_PBID = src.PB_PBID
WHEN NOT MATCHED THEN
    INSERT (PB_PBID, PB_NAME, BP_PLANTYPE)
    VALUES (src.PB_PBID, src.PB_NAME, src.BP_PLANTYPE);

PRINT CONCAT('PBM rows after merge: ', (SELECT COUNT(*) FROM dbo.PBM));
GO

-- =============================================================================
--  STEP 3 — Insert BINPCN records (active + a few expired for testing)
--           BP_END >= GETDATE() rows = 28   |   expired = 5  (won't appear in query)
-- =============================================================================

-- Clear only test rows if re-running (identified by BP_ID range we will insert)
-- For a fresh DB just insert; for existing DB this is safe with the identity column.

INSERT INTO dbo.BINPCN (BP_PBID, BP_BIN, BP_PCN,   BP_CHGRP,          BP_START,    BP_END)
VALUES
-- ── Express Scripts Commercial ──────────────────────────────────────────────
(1,  '610014', 'ESI',        'COMMERC01',        '2024-01-01', '2027-12-31'),
(1,  '610014', 'ESI',        'COMMERC02',        '2024-01-01', '2027-12-31'),
(1,  '610014', 'MEDCO',      'MEDCO_GRP1',       '2024-06-01', '2026-12-31'),
(1,  '610014', 'ESI',        'GOVTPLAN',         '2025-01-01', '2028-06-30'),
-- ── Express Scripts Medicare Part D ─────────────────────────────────────────
(2,  '610014', 'ESI',        'MEDB2026',         '2026-01-01', '2026-12-31'),
(2,  '610011', 'SXC',        'PARTD_ESI',        '2025-01-01', '2027-12-31'),
-- ── CVS Caremark Commercial ──────────────────────────────────────────────────
(3,  '004336', 'ADV',        'CVS_COM01',        '2024-01-01', '2027-12-31'),
(3,  '004336', 'PBMADV',     'CVS_COM02',        '2024-03-01', '2026-12-31'),
(3,  '610502', 'ADV',        'SILV_COM',         '2025-01-01', '2028-12-31'),
-- ── CVS Caremark Medicare Part D ─────────────────────────────────────────────
(4,  '004336', 'ADV',        'CVS_MED26',        '2026-01-01', '2026-12-31'),
(4,  '610502', 'PBMADV',     'CVS_MED27',        '2026-01-01', '2027-12-31'),
-- ── OptumRx Commercial ───────────────────────────────────────────────────────
(5,  '610591', 'ADV',        'OPT_COM01',        '2024-01-01', '2027-12-31'),
(5,  '610591', 'OPTUMRX',    'OPT_COM02',        '2024-07-01', '2026-12-31'),
-- ── OptumRx Medicare Part D ──────────────────────────────────────────────────
(6,  '610591', 'ADV',        'OPT_MED26',        '2026-01-01', '2026-12-31'),
-- ── MedImpact Commercial ─────────────────────────────────────────────────────
(7,  '610020', 'MEDIMPACT',  'MEDI_COM1',        '2024-01-01', '2027-12-31'),
(7,  '610020', 'MEDIMPACT',  'MEDI_COM2',        '2025-06-01', '2028-12-31'),
-- ── MedImpact Medicaid ───────────────────────────────────────────────────────
(8,  '610020', 'MEDIMPACT',  'MEDI_MCAID',       '2024-01-01', '2027-12-31'),
-- ── Navitus Commercial ───────────────────────────────────────────────────────
(9,  '610649', 'NAVITUS',    'NAV_COM01',        '2024-01-01', '2027-12-31'),
(9,  '610649', 'NAVITUS',    'NAV_COM02',        '2025-01-01', '2028-12-31'),
-- ── Navitus Medicare Part D ──────────────────────────────────────────────────
(10, '610649', 'NAVITUS',    'NAV_MED26',        '2026-01-01', '2026-12-31'),
-- ── Humana Medicare Part D ───────────────────────────────────────────────────
(11, '015581', 'HUMRX',      'HUM_MED26',        '2026-01-01', '2026-12-31'),
(11, '015581', 'HUMANA',     'HUM_MED27',        '2026-01-01', '2027-12-31'),
-- ── Humana Commercial ────────────────────────────────────────────────────────
(12, '015581', 'HUMRX',      'HUM_COM01',        '2024-01-01', '2027-12-31'),
-- ── Prime Therapeutics Commercial ────────────────────────────────────────────
(13, '600428', 'PRIMETP',    'PRI_COM01',        '2024-01-01', '2027-12-31'),
-- ── Prime Therapeutics Medicaid ──────────────────────────────────────────────
(14, '600428', 'PRIMETP',    'PRI_MCAID',        '2024-01-01', '2027-12-31'),
-- ── SXC Health Commercial ────────────────────────────────────────────────────
(15, '610011', 'SXC',        'SXC_COM01',        '2024-01-01', '2027-12-31'),
-- ── Magellan Commercial ──────────────────────────────────────────────────────
(16, '010540', 'MAGELLAN',   'MAG_COM01',        '2024-01-01', '2027-12-31'),
-- ── Magellan Medicaid ────────────────────────────────────────────────────────
(17, '010540', 'MAGELLAN',   'MAG_MCAID',        '2024-01-01', '2027-12-31'),
-- ── WellDyneRx Commercial ────────────────────────────────────────────────────
(18, '011779', 'WELLDYNE',   'WDR_COM01',        '2025-01-01', '2028-12-31'),
-- ── Zinc Health (newer) ──────────────────────────────────────────────────────
(20, '610460', 'ZINC',       'ZINC_COM1',        '2025-06-01', '2028-12-31'),

-- ── EXPIRED rows (intentionally old BP_END — should NOT appear in the query) ──
(1,  '610014', 'ESI_OLD',    'EXPIRED_G1',       '2020-01-01', '2022-12-31'),
(3,  '004336', 'ADV_OLD',    'EXPIRED_G2',       '2019-01-01', '2021-06-30'),
(5,  '610591', 'OPT_OLD',    'EXPIRED_G3',       '2021-01-01', '2023-12-31'),
(9,  '610649', 'NAV_OLD',    'EXPIRED_G4',       '2020-06-01', '2022-06-30'),
(11, '015581', 'HUM_OLD',    'EXPIRED_G5',       '2019-01-01', '2020-12-31');

PRINT CONCAT('BINPCN rows inserted total: ', (SELECT COUNT(*) FROM dbo.BINPCN));
GO

-- =============================================================================
--  STEP 4 — Verify: run the EXACT query from the Talend job
-- =============================================================================

PRINT '=== QUERY RESULTS (active rows only, BP_END >= GETDATE()) ===';

SELECT DISTINCT
    BP_BIN,
    BP_PCN,
    BP_CHGRP,
    PB_NAME,
    BP_PLANTYPE
FROM dbo.BINPCN  a
INNER JOIN dbo.PBM b ON a.BP_PBID = b.PB_PBID
WHERE a.BP_END >= GETDATE()
ORDER BY PB_NAME, BP_BIN, BP_PCN, BP_CHGRP;

GO

-- =============================================================================
--  STEP 5 — Row counts summary
-- =============================================================================

SELECT
    'dbo.PBM'           AS TableName,
    COUNT(*)            AS TotalRows  FROM dbo.PBM
UNION ALL
SELECT
    'dbo.BINPCN Total'  AS TableName,
    COUNT(*)            AS TotalRows  FROM dbo.BINPCN
UNION ALL
SELECT
    'Active (BP_END >= today)' AS TableName,
    COUNT(*)            AS TotalRows
FROM dbo.BINPCN WHERE BP_END >= GETDATE();
GO

-- =============================================================================
--  CLEANUP HELPER — run this ONLY if you want to remove test data and tables
--  (commented out by default)
-- =============================================================================
/*
DROP TABLE IF EXISTS dbo.BINPCN;
DROP TABLE IF EXISTS dbo.PBM;
PRINT 'Tables dropped.';
*/
