-- ============================================================================
-- MMIT MASTER JOB SUPPORT SCRIPT
-- MMIT_MHA_Data_Ingestion_Final - 11 table sample data + ingestion procedures
-- ============================================================================
USE Formulary_Data;
GO

-- ============================================================================
-- SECTION 1 - CREATE ALL 11 TABLES
-- ============================================================================

IF OBJECT_ID('dbo.MMIT_Drugs', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MMIT_Drugs
    (
        DrugID            INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_MMIT_Drugs PRIMARY KEY,
        NDCCode           VARCHAR(11) NOT NULL,
        DrugName          VARCHAR(200) NOT NULL,
        BrandName         VARCHAR(200) NULL,
        GenericName       VARCHAR(200) NULL,
        ManufacturerName  VARCHAR(200) NULL,
        DrugClass         VARCHAR(100) NULL,
        TherapeuticClass  VARCHAR(100) NULL,
        FormularyStatus   VARCHAR(50) NULL,
        IsActive          BIT NOT NULL CONSTRAINT DF_MMIT_Drugs_IsActive DEFAULT (1),
        LoadDate          DATETIME NOT NULL CONSTRAINT DF_MMIT_Drugs_LoadDate DEFAULT (GETDATE()),
        IsNew             BIT NOT NULL CONSTRAINT DF_MMIT_Drugs_IsNew DEFAULT (1)
    );
END
GO

IF OBJECT_ID('dbo.MMIT_PansController', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MMIT_PansController
    (
        PanID                    INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_MMIT_PansController PRIMARY KEY,
        PlanID                   VARCHAR(50) NOT NULL,
        DrugID                   INT NOT NULL,
        PARequired               BIT NOT NULL,
        StepTherapyRequired      BIT NOT NULL,
        QuantityLimitRequired    BIT NOT NULL,
        PAType                   VARCHAR(50) NULL,
        EffectiveDate            DATE NOT NULL,
        TermDate                 DATE NULL,
        LoadDate                 DATETIME NOT NULL CONSTRAINT DF_MMIT_PansController_LoadDate DEFAULT (GETDATE()),
        IsNew                    BIT NOT NULL CONSTRAINT DF_MMIT_PansController_IsNew DEFAULT (1)
    );
END
GO

IF OBJECT_ID('dbo.MMIT_Medopen_Bridge', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MMIT_Medopen_Bridge
    (
        BridgeID           INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_MMIT_Medopen_Bridge PRIMARY KEY,
        MMITDrugID         INT NOT NULL,
        MedOpenDrugID      VARCHAR(50) NOT NULL,
        MedOpenDrugName    VARCHAR(200) NULL,
        CrosswalkType      VARCHAR(50) NULL,
        MatchConfidence    DECIMAL(5,2) NULL,
        LoadDate           DATETIME NOT NULL CONSTRAINT DF_MMIT_Medopen_Bridge_LoadDate DEFAULT (GETDATE()),
        IsNew              BIT NOT NULL CONSTRAINT DF_MMIT_Medopen_Bridge_IsNew DEFAULT (1)
    );
END
GO

IF OBJECT_ID('dbo.MMIT_NDC_Bridge', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MMIT_NDC_Bridge
    (
        NDCBridgeID        INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_MMIT_NDC_Bridge PRIMARY KEY,
        NDC11              VARCHAR(11) NOT NULL,
        NDC10              VARCHAR(10) NULL,
        LabelerCode        VARCHAR(6) NULL,
        ProductCode        VARCHAR(4) NULL,
        PackageCode        VARCHAR(2) NULL,
        DrugID             INT NOT NULL,
        ProductName        VARCHAR(200) NULL,
        LoadDate           DATETIME NOT NULL CONSTRAINT DF_MMIT_NDC_Bridge_LoadDate DEFAULT (GETDATE()),
        IsNew              BIT NOT NULL CONSTRAINT DF_MMIT_NDC_Bridge_IsNew DEFAULT (1)
    );
END
GO

IF OBJECT_ID('dbo.MMIT_Restrictions', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MMIT_Restrictions
    (
        RestrictionID         INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_MMIT_Restrictions PRIMARY KEY,
        DrugID                INT NOT NULL,
        PlanID                VARCHAR(50) NOT NULL,
        PlanName              VARCHAR(200) NULL,
        RestrictionType       VARCHAR(50) NULL,
        RestrictionDetails    VARCHAR(500) NULL,
        CoverageStatus        VARCHAR(50) NULL,
        TierLevel             INT NULL,
        EffectiveDate         DATE NOT NULL,
        LoadDate              DATETIME NOT NULL CONSTRAINT DF_MMIT_Restrictions_LoadDate DEFAULT (GETDATE()),
        IsNew                 BIT NOT NULL CONSTRAINT DF_MMIT_Restrictions_IsNew DEFAULT (1)
    );
END
GO

IF OBJECT_ID('dbo.MMIT_Statuses', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MMIT_Statuses
    (
        StatusID             INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_MMIT_Statuses PRIMARY KEY,
        StatusCode           VARCHAR(20) NOT NULL,
        StatusDescription    VARCHAR(200) NULL,
        StatusType           VARCHAR(50) NULL,
        StatusCategory       VARCHAR(50) NULL,
        IsActive             BIT NOT NULL,
        LoadDate             DATETIME NOT NULL CONSTRAINT DF_MMIT_Statuses_LoadDate DEFAULT (GETDATE()),
        IsNew                BIT NOT NULL CONSTRAINT DF_MMIT_Statuses_IsNew DEFAULT (1)
    );
END
GO

IF OBJECT_ID('dbo.MMIT_IDSAs', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MMIT_IDSAs
    (
        IDSARecordID         INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_MMIT_IDSAs PRIMARY KEY,
        DrugID               INT NOT NULL,
        PlanID               VARCHAR(50) NOT NULL,
        StatusCode           VARCHAR(20) NOT NULL,
        CoverageType         VARCHAR(50) NULL,
        FormularyTier        INT NULL,
        CoverageNotes        VARCHAR(500) NULL,
        EffectiveDate        DATE NOT NULL,
        LoadDate             DATETIME NOT NULL CONSTRAINT DF_MMIT_IDSAs_LoadDate DEFAULT (GETDATE()),
        IsNew                BIT NOT NULL CONSTRAINT DF_MMIT_IDSAs_IsNew DEFAULT (1)
    );
END
GO

IF OBJECT_ID('dbo.MMIT_PanDetails', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MMIT_PanDetails
    (
        PanDetailID              INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_MMIT_PanDetails PRIMARY KEY,
        PanID                    INT NOT NULL,
        CriterionType            VARCHAR(100) NULL,
        CriterionText            VARCHAR(1000) NULL,
        RequiredDocumentation    VARCHAR(500) NULL,
        CriterionOrder           INT NOT NULL,
        LoadDate                 DATETIME NOT NULL CONSTRAINT DF_MMIT_PanDetails_LoadDate DEFAULT (GETDATE()),
        IsNew                    BIT NOT NULL CONSTRAINT DF_MMIT_PanDetails_IsNew DEFAULT (1)
    );
END
GO

IF OBJECT_ID('dbo.MMIT_States', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MMIT_States
    (
        StateID              INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_MMIT_States PRIMARY KEY,
        StateCode            CHAR(2) NOT NULL,
        StateName            VARCHAR(50) NOT NULL,
        Region               VARCHAR(50) NULL,
        Division             VARCHAR(50) NULL,
        IsActive             BIT NOT NULL CONSTRAINT DF_MMIT_States_IsActive DEFAULT (1),
        LoadDate             DATETIME NOT NULL CONSTRAINT DF_MMIT_States_LoadDate DEFAULT (GETDATE())
    );
END
GO

IF OBJECT_ID('dbo.MMIT_ZipCodes', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MMIT_ZipCodes
    (
        ZipCodeID            INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_MMIT_ZipCodes PRIMARY KEY,
        ZipCode              VARCHAR(5) NOT NULL,
        City                 VARCHAR(100) NULL,
        StateCode            CHAR(2) NOT NULL,
        County               VARCHAR(100) NULL,
        ZipType              VARCHAR(20) NULL,
        LoadDate             DATETIME NOT NULL CONSTRAINT DF_MMIT_ZipCodes_LoadDate DEFAULT (GETDATE())
    );
END
GO

IF OBJECT_ID('dbo.MMIT_PansControllerNCD', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MMIT_PansControllerNCD
    (
        NCDPanID             INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_MMIT_PansControllerNCD PRIMARY KEY,
        PlanID               VARCHAR(50) NOT NULL,
        DrugID               INT NOT NULL,
        NCDReason            VARCHAR(200) NULL,
        AlternativeDrug      VARCHAR(200) NULL,
        EffectiveDate        DATE NOT NULL,
        TermDate             DATE NULL,
        LoadDate             DATETIME NOT NULL CONSTRAINT DF_MMIT_PansControllerNCD_LoadDate DEFAULT (GETDATE()),
        IsNew                BIT NOT NULL CONSTRAINT DF_MMIT_PansControllerNCD_IsNew DEFAULT (1)
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE [name] = 'UQ_MMIT_Drugs_NDCCode')
BEGIN
    ALTER TABLE dbo.MMIT_Drugs ADD CONSTRAINT UQ_MMIT_Drugs_NDCCode UNIQUE (NDCCode);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE [name] = 'UQ_MMIT_Statuses_StatusCode')
BEGIN
    ALTER TABLE dbo.MMIT_Statuses ADD CONSTRAINT UQ_MMIT_Statuses_StatusCode UNIQUE (StatusCode);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE [name] = 'UQ_MMIT_States_StateCode')
BEGIN
    ALTER TABLE dbo.MMIT_States ADD CONSTRAINT UQ_MMIT_States_StateCode UNIQUE (StateCode);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE [name] = 'UQ_MMIT_ZipCodes_ZipCode')
BEGIN
    ALTER TABLE dbo.MMIT_ZipCodes ADD CONSTRAINT UQ_MMIT_ZipCodes_ZipCode UNIQUE (ZipCode);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = 'UX_MMIT_PansController_BusinessKey' AND object_id = OBJECT_ID('dbo.MMIT_PansController'))
BEGIN
    CREATE UNIQUE INDEX UX_MMIT_PansController_BusinessKey
        ON dbo.MMIT_PansController (PlanID, DrugID, EffectiveDate);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = 'UX_MMIT_Medopen_Bridge_BusinessKey' AND object_id = OBJECT_ID('dbo.MMIT_Medopen_Bridge'))
BEGIN
    CREATE UNIQUE INDEX UX_MMIT_Medopen_Bridge_BusinessKey
        ON dbo.MMIT_Medopen_Bridge (MMITDrugID, MedOpenDrugID);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = 'UX_MMIT_NDC_Bridge_NDC11' AND object_id = OBJECT_ID('dbo.MMIT_NDC_Bridge'))
BEGIN
    CREATE UNIQUE INDEX UX_MMIT_NDC_Bridge_NDC11
        ON dbo.MMIT_NDC_Bridge (NDC11);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = 'UX_MMIT_Restrictions_BusinessKey' AND object_id = OBJECT_ID('dbo.MMIT_Restrictions'))
BEGIN
    CREATE UNIQUE INDEX UX_MMIT_Restrictions_BusinessKey
        ON dbo.MMIT_Restrictions (DrugID, PlanID, RestrictionType, EffectiveDate);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = 'UX_MMIT_IDSAs_BusinessKey' AND object_id = OBJECT_ID('dbo.MMIT_IDSAs'))
BEGIN
    CREATE UNIQUE INDEX UX_MMIT_IDSAs_BusinessKey
        ON dbo.MMIT_IDSAs (DrugID, PlanID);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = 'UX_MMIT_PanDetails_BusinessKey' AND object_id = OBJECT_ID('dbo.MMIT_PanDetails'))
BEGIN
    CREATE UNIQUE INDEX UX_MMIT_PanDetails_BusinessKey
        ON dbo.MMIT_PanDetails (PanID, CriterionOrder);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = 'UX_MMIT_PansControllerNCD_BusinessKey' AND object_id = OBJECT_ID('dbo.MMIT_PansControllerNCD'))
BEGIN
    CREATE UNIQUE INDEX UX_MMIT_PansControllerNCD_BusinessKey
        ON dbo.MMIT_PansControllerNCD (PlanID, DrugID, EffectiveDate);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE [name] = 'FK_MMIT_PansController_Drugs')
BEGIN
    ALTER TABLE dbo.MMIT_PansController
        ADD CONSTRAINT FK_MMIT_PansController_Drugs
            FOREIGN KEY (DrugID) REFERENCES dbo.MMIT_Drugs (DrugID);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE [name] = 'FK_MMIT_Medopen_Bridge_Drugs')
BEGIN
    ALTER TABLE dbo.MMIT_Medopen_Bridge
        ADD CONSTRAINT FK_MMIT_Medopen_Bridge_Drugs
            FOREIGN KEY (MMITDrugID) REFERENCES dbo.MMIT_Drugs (DrugID);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE [name] = 'FK_MMIT_NDC_Bridge_Drugs')
BEGIN
    ALTER TABLE dbo.MMIT_NDC_Bridge
        ADD CONSTRAINT FK_MMIT_NDC_Bridge_Drugs
            FOREIGN KEY (DrugID) REFERENCES dbo.MMIT_Drugs (DrugID);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE [name] = 'FK_MMIT_Restrictions_Drugs')
BEGIN
    ALTER TABLE dbo.MMIT_Restrictions
        ADD CONSTRAINT FK_MMIT_Restrictions_Drugs
            FOREIGN KEY (DrugID) REFERENCES dbo.MMIT_Drugs (DrugID);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE [name] = 'FK_MMIT_IDSAs_Drugs')
BEGIN
    ALTER TABLE dbo.MMIT_IDSAs
        ADD CONSTRAINT FK_MMIT_IDSAs_Drugs
            FOREIGN KEY (DrugID) REFERENCES dbo.MMIT_Drugs (DrugID);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE [name] = 'FK_MMIT_IDSAs_Statuses')
BEGIN
    ALTER TABLE dbo.MMIT_IDSAs
        ADD CONSTRAINT FK_MMIT_IDSAs_Statuses
            FOREIGN KEY (StatusCode) REFERENCES dbo.MMIT_Statuses (StatusCode);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE [name] = 'FK_MMIT_PanDetails_PansController')
BEGIN
    ALTER TABLE dbo.MMIT_PanDetails
        ADD CONSTRAINT FK_MMIT_PanDetails_PansController
            FOREIGN KEY (PanID) REFERENCES dbo.MMIT_PansController (PanID);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE [name] = 'FK_MMIT_ZipCodes_States')
BEGIN
    ALTER TABLE dbo.MMIT_ZipCodes
        ADD CONSTRAINT FK_MMIT_ZipCodes_States
            FOREIGN KEY (StateCode) REFERENCES dbo.MMIT_States (StateCode);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE [name] = 'FK_MMIT_PansControllerNCD_Drugs')
BEGIN
    ALTER TABLE dbo.MMIT_PansControllerNCD
        ADD CONSTRAINT FK_MMIT_PansControllerNCD_Drugs
            FOREIGN KEY (DrugID) REFERENCES dbo.MMIT_Drugs (DrugID);
END
GO
-- ============================================================================
-- SECTION 2 - INSERT SAMPLE DATA
-- ============================================================================
MERGE dbo.MMIT_Statuses AS tgt
USING
(
    VALUES
        ('COVERED', 'Covered', 'Coverage', 'Positive', 1, '2026-06-05T08:00:00'),
        ('TIER1', 'Tier 1 Preferred Generic', 'Tier', 'Preferred', 1, '2026-06-05T08:00:00'),
        ('TIER2', 'Tier 2 Preferred Brand', 'Tier', 'Preferred', 1, '2026-06-05T08:00:00'),
        ('TIER3', 'Tier 3 Non-Preferred Brand', 'Tier', 'Standard', 1, '2026-06-05T08:00:00'),
        ('TIER4', 'Tier 4 Specialty', 'Tier', 'Specialty', 1, '2026-06-05T08:00:00'),
        ('PA_REQUIRED', 'Prior Authorization Required', 'Restriction', 'Utilization Management', 1, '2026-06-05T08:00:00'),
        ('NOT_COVERED', 'Not Covered', 'Coverage', 'Negative', 1, '2026-06-05T08:00:00'),
        ('STEP_THERAPY', 'Step Therapy Required', 'Restriction', 'Utilization Management', 1, '2026-06-05T08:00:00'),
        ('QUANTITY_LIMIT', 'Quantity Limit Applies', 'Restriction', 'Utilization Management', 1, '2026-06-05T08:00:00'),
        ('PREFERRED', 'Preferred Formulary Product', 'Preference', 'Positive', 1, '2026-06-05T08:00:00'),
        ('NON_PREFERRED', 'Non-Preferred Formulary Product', 'Preference', 'Negative', 1, '2026-06-05T08:00:00'),
        ('FORMULARY_EXCEPTION', 'Formulary Exception Allowed', 'Exception', 'Case Management', 1, '2026-06-05T08:00:00'),
        ('COVERED_RESTRICTED', 'Covered with Restrictions', 'Coverage', 'Conditional', 1, '2026-06-05T08:00:00'),
        ('NOT_ON_FORMULARY', 'Not on Formulary', 'Coverage', 'Negative', 1, '2026-06-05T08:00:00'),
        ('COVERED_NF', 'Covered Non-Formulary', 'Coverage', 'Conditional', 1, '2026-06-05T08:00:00')
) AS src (StatusCode, StatusDescription, StatusType, StatusCategory, IsActive, LoadDate)
ON tgt.StatusCode = src.StatusCode
WHEN MATCHED THEN
    UPDATE SET
        tgt.StatusDescription = src.StatusDescription,
        tgt.StatusType = src.StatusType,
        tgt.StatusCategory = src.StatusCategory,
        tgt.IsActive = src.IsActive,
        tgt.LoadDate = src.LoadDate,
        tgt.IsNew = 1
WHEN NOT MATCHED BY TARGET THEN
    INSERT (StatusCode, StatusDescription, StatusType, StatusCategory, IsActive, LoadDate, IsNew)
    VALUES (src.StatusCode, src.StatusDescription, src.StatusType, src.StatusCategory, src.IsActive, src.LoadDate, 1);
GO
MERGE dbo.MMIT_States AS tgt
USING
(
    VALUES
        ('AL', 'Alabama', 'South', 'East South Central', 1, '2026-06-05T08:00:00'),
        ('AK', 'Alaska', 'West', 'Pacific', 1, '2026-06-05T08:00:00'),
        ('AZ', 'Arizona', 'West', 'Mountain', 1, '2026-06-05T08:00:00'),
        ('AR', 'Arkansas', 'South', 'West South Central', 1, '2026-06-05T08:00:00'),
        ('CA', 'California', 'West', 'Pacific', 1, '2026-06-05T08:00:00'),
        ('CO', 'Colorado', 'West', 'Mountain', 1, '2026-06-05T08:00:00'),
        ('CT', 'Connecticut', 'Northeast', 'New England', 1, '2026-06-05T08:00:00'),
        ('DE', 'Delaware', 'South', 'South Atlantic', 1, '2026-06-05T08:00:00'),
        ('DC', 'District of Columbia', 'South', 'South Atlantic', 1, '2026-06-05T08:00:00'),
        ('FL', 'Florida', 'South', 'South Atlantic', 1, '2026-06-05T08:00:00'),
        ('GA', 'Georgia', 'South', 'South Atlantic', 1, '2026-06-05T08:00:00'),
        ('HI', 'Hawaii', 'West', 'Pacific', 1, '2026-06-05T08:00:00'),
        ('ID', 'Idaho', 'West', 'Mountain', 1, '2026-06-05T08:00:00'),
        ('IL', 'Illinois', 'Midwest', 'East North Central', 1, '2026-06-05T08:00:00'),
        ('IN', 'Indiana', 'Midwest', 'East North Central', 1, '2026-06-05T08:00:00'),
        ('IA', 'Iowa', 'Midwest', 'West North Central', 1, '2026-06-05T08:00:00'),
        ('KS', 'Kansas', 'Midwest', 'West North Central', 1, '2026-06-05T08:00:00'),
        ('KY', 'Kentucky', 'South', 'East South Central', 1, '2026-06-05T08:00:00'),
        ('LA', 'Louisiana', 'South', 'West South Central', 1, '2026-06-05T08:00:00'),
        ('ME', 'Maine', 'Northeast', 'New England', 1, '2026-06-05T08:00:00'),
        ('MD', 'Maryland', 'South', 'South Atlantic', 1, '2026-06-05T08:00:00'),
        ('MA', 'Massachusetts', 'Northeast', 'New England', 1, '2026-06-05T08:00:00'),
        ('MI', 'Michigan', 'Midwest', 'East North Central', 1, '2026-06-05T08:00:00'),
        ('MN', 'Minnesota', 'Midwest', 'West North Central', 1, '2026-06-05T08:00:00'),
        ('MS', 'Mississippi', 'South', 'East South Central', 1, '2026-06-05T08:00:00'),
        ('MO', 'Missouri', 'Midwest', 'West North Central', 1, '2026-06-05T08:00:00'),
        ('MT', 'Montana', 'West', 'Mountain', 1, '2026-06-05T08:00:00'),
        ('NE', 'Nebraska', 'Midwest', 'West North Central', 1, '2026-06-05T08:00:00'),
        ('NV', 'Nevada', 'West', 'Mountain', 1, '2026-06-05T08:00:00'),
        ('NH', 'New Hampshire', 'Northeast', 'New England', 1, '2026-06-05T08:00:00'),
        ('NJ', 'New Jersey', 'Northeast', 'Middle Atlantic', 1, '2026-06-05T08:00:00'),
        ('NM', 'New Mexico', 'West', 'Mountain', 1, '2026-06-05T08:00:00'),
        ('NY', 'New York', 'Northeast', 'Middle Atlantic', 1, '2026-06-05T08:00:00'),
        ('NC', 'North Carolina', 'South', 'South Atlantic', 1, '2026-06-05T08:00:00'),
        ('ND', 'North Dakota', 'Midwest', 'West North Central', 1, '2026-06-05T08:00:00'),
        ('OH', 'Ohio', 'Midwest', 'East North Central', 1, '2026-06-05T08:00:00'),
        ('OK', 'Oklahoma', 'South', 'West South Central', 1, '2026-06-05T08:00:00'),
        ('OR', 'Oregon', 'West', 'Pacific', 1, '2026-06-05T08:00:00'),
        ('PA', 'Pennsylvania', 'Northeast', 'Middle Atlantic', 1, '2026-06-05T08:00:00'),
        ('RI', 'Rhode Island', 'Northeast', 'New England', 1, '2026-06-05T08:00:00'),
        ('SC', 'South Carolina', 'South', 'South Atlantic', 1, '2026-06-05T08:00:00'),
        ('SD', 'South Dakota', 'Midwest', 'West North Central', 1, '2026-06-05T08:00:00'),
        ('TN', 'Tennessee', 'South', 'East South Central', 1, '2026-06-05T08:00:00'),
        ('TX', 'Texas', 'South', 'West South Central', 1, '2026-06-05T08:00:00'),
        ('UT', 'Utah', 'West', 'Mountain', 1, '2026-06-05T08:00:00'),
        ('VT', 'Vermont', 'Northeast', 'New England', 1, '2026-06-05T08:00:00'),
        ('VA', 'Virginia', 'South', 'South Atlantic', 1, '2026-06-05T08:00:00'),
        ('WA', 'Washington', 'West', 'Pacific', 1, '2026-06-05T08:00:00'),
        ('WV', 'West Virginia', 'South', 'South Atlantic', 1, '2026-06-05T08:00:00'),
        ('WI', 'Wisconsin', 'Midwest', 'East North Central', 1, '2026-06-05T08:00:00'),
        ('WY', 'Wyoming', 'West', 'Mountain', 1, '2026-06-05T08:00:00')
) AS src (StateCode, StateName, Region, Division, IsActive, LoadDate)
ON tgt.StateCode = src.StateCode
WHEN MATCHED THEN
    UPDATE SET
        tgt.StateName = src.StateName,
        tgt.Region = src.Region,
        tgt.Division = src.Division,
        tgt.IsActive = src.IsActive,
        tgt.LoadDate = src.LoadDate
WHEN NOT MATCHED BY TARGET THEN
    INSERT (StateCode, StateName, Region, Division, IsActive, LoadDate)
    VALUES (src.StateCode, src.StateName, src.Region, src.Division, src.IsActive, src.LoadDate);
GO
MERGE dbo.MMIT_ZipCodes AS tgt
USING
(
    VALUES
        ('10001', 'New York', 'NY', 'New York', 'Standard', '2026-06-05T08:00:00'),
        ('90001', 'Los Angeles', 'CA', 'Los Angeles', 'Standard', '2026-06-05T08:00:00'),
        ('60601', 'Chicago', 'IL', 'Cook', 'Standard', '2026-06-05T08:00:00'),
        ('77001', 'Houston', 'TX', 'Harris', 'PO Box', '2026-06-05T08:00:00'),
        ('85001', 'Phoenix', 'AZ', 'Maricopa', 'PO Box', '2026-06-05T08:00:00'),
        ('19103', 'Philadelphia', 'PA', 'Philadelphia', 'Standard', '2026-06-05T08:00:00'),
        ('78205', 'San Antonio', 'TX', 'Bexar', 'Standard', '2026-06-05T08:00:00'),
        ('92101', 'San Diego', 'CA', 'San Diego', 'Standard', '2026-06-05T08:00:00'),
        ('75201', 'Dallas', 'TX', 'Dallas', 'Standard', '2026-06-05T08:00:00'),
        ('95113', 'San Jose', 'CA', 'Santa Clara', 'Standard', '2026-06-05T08:00:00'),
        ('78701', 'Austin', 'TX', 'Travis', 'Standard', '2026-06-05T08:00:00'),
        ('32202', 'Jacksonville', 'FL', 'Duval', 'Standard', '2026-06-05T08:00:00'),
        ('76102', 'Fort Worth', 'TX', 'Tarrant', 'Standard', '2026-06-05T08:00:00'),
        ('43215', 'Columbus', 'OH', 'Franklin', 'Standard', '2026-06-05T08:00:00'),
        ('28202', 'Charlotte', 'NC', 'Mecklenburg', 'Standard', '2026-06-05T08:00:00'),
        ('46204', 'Indianapolis', 'IN', 'Marion', 'Standard', '2026-06-05T08:00:00'),
        ('98101', 'Seattle', 'WA', 'King', 'Standard', '2026-06-05T08:00:00'),
        ('80202', 'Denver', 'CO', 'Denver', 'Standard', '2026-06-05T08:00:00'),
        ('02108', 'Boston', 'MA', 'Suffolk', 'Standard', '2026-06-05T08:00:00'),
        ('20001', 'Washington', 'DC', 'District of Columbia', 'Standard', '2026-06-05T08:00:00')
) AS src (ZipCode, City, StateCode, County, ZipType, LoadDate)
ON tgt.ZipCode = src.ZipCode
WHEN MATCHED THEN
    UPDATE SET
        tgt.City = src.City,
        tgt.StateCode = src.StateCode,
        tgt.County = src.County,
        tgt.ZipType = src.ZipType,
        tgt.LoadDate = src.LoadDate
WHEN NOT MATCHED BY TARGET THEN
    INSERT (ZipCode, City, StateCode, County, ZipType, LoadDate)
    VALUES (src.ZipCode, src.City, src.StateCode, src.County, src.ZipType, src.LoadDate);
GO
MERGE dbo.MMIT_Drugs AS tgt
USING
(
    VALUES
        ('00074009901', 'Humira', 'Humira', 'Adalimumab', 'AbbVie', 'TNF Inhibitor', 'Immunology', 'Preferred', 1, '2026-06-05T08:00:00'),
        ('00006010001', 'Keytruda', 'Keytruda', 'Pembrolizumab', 'Merck', 'PD-1 Inhibitor', 'Oncology', 'Covered with Restrictions', 1, '2026-06-05T08:00:00'),
        ('00169413201', 'Ozempic', 'Ozempic', 'Semaglutide', 'Novo Nordisk', 'GLP-1 Receptor Agonist', 'Diabetes', 'Tier 2', 1, '2026-06-05T08:00:00'),
        ('00003089421', 'Eliquis', 'Eliquis', 'Apixaban', 'Bristol Myers Squibb', 'Anticoagulant', 'Cardiovascular', 'Tier 2', 1, '2026-06-05T08:00:00'),
        ('50458057990', 'Xarelto', 'Xarelto', 'Rivaroxaban', 'Janssen', 'Anticoagulant', 'Cardiovascular', 'Tier 3', 1, '2026-06-05T08:00:00'),
        ('00597015290', 'Jardiance', 'Jardiance', 'Empagliflozin', 'Boehringer Ingelheim', 'SGLT2 Inhibitor', 'Diabetes', 'Preferred', 1, '2026-06-05T08:00:00'),
        ('00078077767', 'Entresto', 'Entresto', 'Sacubitril/Valsartan', 'Novartis', 'ARNI', 'Heart Failure', 'Tier 2', 1, '2026-06-05T08:00:00'),
        ('00247075790', 'Dupixent', 'Dupixent', 'Dupilumab', 'Sanofi / Regeneron', 'IL-4/13 Inhibitor', 'Immunology', 'Covered with Restrictions', 1, '2026-06-05T08:00:00'),
        ('00781730191', 'Skyrizi', 'Skyrizi', 'Risankizumab', 'AbbVie', 'IL-23 Inhibitor', 'Immunology', 'Tier 4', 1, '2026-06-05T08:00:00'),
        ('57894006001', 'Stelara', 'Stelara', 'Ustekinumab', 'Janssen', 'IL-12/23 Inhibitor', 'Immunology', 'Tier 4', 1, '2026-06-05T08:00:00'),
        ('57894015001', 'Imbruvica', 'Imbruvica', 'Ibrutinib', 'Pharmacyclics', 'BTK Inhibitor', 'Oncology', 'Covered with Restrictions', 1, '2026-06-05T08:00:00'),
        ('59572050121', 'Revlimid', 'Revlimid', 'Lenalidomide', 'Celgene', 'Immunomodulator', 'Oncology', 'Covered NF', 1, '2026-06-05T08:00:00'),
        ('58406043504', 'Enbrel', 'Enbrel', 'Etanercept', 'Amgen', 'TNF Inhibitor', 'Immunology', 'Tier 4', 1, '2026-06-05T08:00:00'),
        ('57894016001', 'Remicade', 'Remicade', 'Infliximab', 'Janssen', 'TNF Inhibitor', 'Immunology', 'Covered with Restrictions', 1, '2026-06-05T08:00:00'),
        ('00078063998', 'Cosentyx', 'Cosentyx', 'Secukinumab', 'Novartis', 'IL-17 Inhibitor', 'Immunology', 'Tier 4', 1, '2026-06-05T08:00:00'),
        ('00002128180', 'Taltz', 'Taltz', 'Ixekizumab', 'Eli Lilly', 'IL-17 Inhibitor', 'Immunology', 'Tier 4', 1, '2026-06-05T08:00:00'),
        ('57894064011', 'Tremfya', 'Tremfya', 'Guselkumab', 'Janssen', 'IL-23 Inhibitor', 'Immunology', 'Tier 4', 1, '2026-06-05T08:00:00'),
        ('00781756061', 'Rinvoq', 'Rinvoq', 'Upadacitinib', 'AbbVie', 'JAK Inhibitor', 'Immunology', 'Covered with Restrictions', 1, '2026-06-05T08:00:00'),
        ('55513084101', 'Aimovig', 'Aimovig', 'Erenumab', 'Amgen', 'CGRP Inhibitor', 'Neurology', 'Tier 3', 1, '2026-06-05T08:00:00'),
        ('50474070062', 'Cimzia', 'Cimzia', 'Certolizumab Pegol', 'UCB', 'TNF Inhibitor', 'Immunology', 'Tier 4', 1, '2026-06-05T08:00:00')
) AS src (NDCCode, DrugName, BrandName, GenericName, ManufacturerName, DrugClass, TherapeuticClass, FormularyStatus, IsActive, LoadDate)
ON tgt.NDCCode = src.NDCCode
WHEN MATCHED THEN
    UPDATE SET
        tgt.DrugName = src.DrugName,
        tgt.BrandName = src.BrandName,
        tgt.GenericName = src.GenericName,
        tgt.ManufacturerName = src.ManufacturerName,
        tgt.DrugClass = src.DrugClass,
        tgt.TherapeuticClass = src.TherapeuticClass,
        tgt.FormularyStatus = src.FormularyStatus,
        tgt.IsActive = src.IsActive,
        tgt.LoadDate = src.LoadDate,
        tgt.IsNew = 1
WHEN NOT MATCHED BY TARGET THEN
    INSERT (NDCCode, DrugName, BrandName, GenericName, ManufacturerName, DrugClass, TherapeuticClass, FormularyStatus, IsActive, LoadDate, IsNew)
    VALUES (src.NDCCode, src.DrugName, src.BrandName, src.GenericName, src.ManufacturerName, src.DrugClass, src.TherapeuticClass, src.FormularyStatus, src.IsActive, src.LoadDate, 1);
GO
MERGE dbo.MMIT_NDC_Bridge AS tgt
USING
(
    SELECT
        src.NDC11,
        src.NDC10,
        src.LabelerCode,
        src.ProductCode,
        src.PackageCode,
        d.DrugID,
        src.ProductName,
        CAST('2026-06-05T08:00:00' AS DATETIME) AS LoadDate
    FROM
    (
        VALUES
            ('00074009901', '0074009901', '00074', '0099', '01', 'Humira', 'Humira'),
        ('00006010001', '0006010001', '00006', '0100', '01', 'Keytruda', 'Keytruda'),
        ('00169413201', '0169413201', '00169', '4132', '01', 'Ozempic', 'Ozempic'),
        ('00003089421', '0003089421', '00003', '0894', '21', 'Eliquis', 'Eliquis'),
        ('50458057990', '0458057990', '50458', '0579', '90', 'Xarelto', 'Xarelto'),
        ('00597015290', '0597015290', '00597', '0152', '90', 'Jardiance', 'Jardiance'),
        ('00078077767', '0078077767', '00078', '0777', '67', 'Entresto', 'Entresto'),
        ('00247075790', '0247075790', '00247', '0757', '90', 'Dupixent', 'Dupixent'),
        ('00781730191', '0781730191', '00781', '7301', '91', 'Skyrizi', 'Skyrizi'),
        ('57894006001', '7894006001', '57894', '0060', '01', 'Stelara', 'Stelara'),
        ('57894015001', '7894015001', '57894', '0150', '01', 'Imbruvica', 'Imbruvica'),
        ('59572050121', '9572050121', '59572', '0501', '21', 'Revlimid', 'Revlimid'),
        ('58406043504', '8406043504', '58406', '0435', '04', 'Enbrel', 'Enbrel'),
        ('57894016001', '7894016001', '57894', '0160', '01', 'Remicade', 'Remicade'),
        ('00078063998', '0078063998', '00078', '0639', '98', 'Cosentyx', 'Cosentyx'),
        ('00002128180', '0002128180', '00002', '1281', '80', 'Taltz', 'Taltz'),
        ('57894064011', '7894064011', '57894', '0640', '11', 'Tremfya', 'Tremfya'),
        ('00781756061', '0781756061', '00781', '7560', '61', 'Rinvoq', 'Rinvoq'),
        ('55513084101', '5513084101', '55513', '0841', '01', 'Aimovig', 'Aimovig'),
        ('50474070062', '0474070062', '50474', '0700', '62', 'Cimzia', 'Cimzia')
    ) AS src (NDC11, NDC10, LabelerCode, ProductCode, PackageCode, DrugName, ProductName)
    INNER JOIN dbo.MMIT_Drugs AS d
        ON d.DrugName = src.DrugName
) AS src
ON tgt.NDC11 = src.NDC11
WHEN MATCHED THEN
    UPDATE SET
        tgt.NDC10 = src.NDC10,
        tgt.LabelerCode = src.LabelerCode,
        tgt.ProductCode = src.ProductCode,
        tgt.PackageCode = src.PackageCode,
        tgt.DrugID = src.DrugID,
        tgt.ProductName = src.ProductName,
        tgt.LoadDate = src.LoadDate,
        tgt.IsNew = 1
WHEN NOT MATCHED BY TARGET THEN
    INSERT (NDC11, NDC10, LabelerCode, ProductCode, PackageCode, DrugID, ProductName, LoadDate, IsNew)
    VALUES (src.NDC11, src.NDC10, src.LabelerCode, src.ProductCode, src.PackageCode, src.DrugID, src.ProductName, src.LoadDate, 1);
GO
MERGE dbo.MMIT_PansController AS tgt
USING
(
    SELECT
        src.PlanID,
        d.DrugID,
        src.PARequired,
        src.StepTherapyRequired,
        src.QuantityLimitRequired,
        src.PAType,
        CAST(src.EffectiveDate AS DATE) AS EffectiveDate,
        CAST(src.TermDate AS DATE) AS TermDate,
        CAST(src.LoadDate AS DATETIME) AS LoadDate
    FROM
    (
        VALUES
            ('CVS_COMM_100', 'Humira', 1, 1, 1, 'Specialty Prior Authorization', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('CVS_MEDD_200', 'Keytruda', 1, 0, 0, 'Oncology Prior Authorization', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('ESI_COMM_100', 'Ozempic', 0, 1, 1, 'GLP-1 Clinical Review', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('ESI_MEDD_200', 'Eliquis', 0, 0, 1, 'Quantity Monitoring', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('OPT_COMM_100', 'Xarelto', 1, 0, 1, 'Anticoagulant Review', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('OPT_EXCH_200', 'Jardiance', 0, 1, 0, 'Step Therapy Review', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('PRIME_COMM_100', 'Entresto', 0, 0, 0, 'None', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('PRIME_MEDD_200', 'Dupixent', 1, 1, 0, 'Specialty Dermatology PA', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('HUMANA_MAPD_100', 'Skyrizi', 1, 1, 1, 'Specialty Gastroenterology PA', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('HUMANA_COMM_200', 'Stelara', 1, 1, 0, 'Biologic Prior Authorization', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('CVS_EXCH_300', 'Imbruvica', 1, 0, 0, 'Oncology Prior Authorization', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('ESI_COMM_400', 'Revlimid', 1, 0, 1, 'Specialty Oncology PA', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('OPT_MEDD_300', 'Enbrel', 1, 1, 0, 'Rheumatology PA', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('PRIME_EXCH_400', 'Remicade', 1, 0, 1, 'Infusion Prior Authorization', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('HUMANA_COMM_500', 'Cosentyx', 1, 1, 0, 'Psoriasis Prior Authorization', '2026-01-01', NULL, '2026-06-05T08:00:00')
    ) AS src (PlanID, DrugName, PARequired, StepTherapyRequired, QuantityLimitRequired, PAType, EffectiveDate, TermDate, LoadDate)
    INNER JOIN dbo.MMIT_Drugs AS d
        ON d.DrugName = src.DrugName
) AS src
ON tgt.PlanID = src.PlanID AND tgt.DrugID = src.DrugID AND tgt.EffectiveDate = src.EffectiveDate
WHEN MATCHED THEN
    UPDATE SET
        tgt.PARequired = src.PARequired,
        tgt.StepTherapyRequired = src.StepTherapyRequired,
        tgt.QuantityLimitRequired = src.QuantityLimitRequired,
        tgt.PAType = src.PAType,
        tgt.TermDate = src.TermDate,
        tgt.LoadDate = src.LoadDate,
        tgt.IsNew = 1
WHEN NOT MATCHED BY TARGET THEN
    INSERT (PlanID, DrugID, PARequired, StepTherapyRequired, QuantityLimitRequired, PAType, EffectiveDate, TermDate, LoadDate, IsNew)
    VALUES (src.PlanID, src.DrugID, src.PARequired, src.StepTherapyRequired, src.QuantityLimitRequired, src.PAType, src.EffectiveDate, src.TermDate, src.LoadDate, 1);
GO
MERGE dbo.MMIT_PanDetails AS tgt
USING
(
    SELECT
        pc.PanID,
        src.CriterionType,
        src.CriterionText,
        src.RequiredDocumentation,
        src.CriterionOrder,
        CAST(src.LoadDate AS DATETIME) AS LoadDate
    FROM
    (
        VALUES
            ('CVS_COMM_100', 'Humira', 'Diagnosis', 'Moderate to severe rheumatoid arthritis confirmed by specialist', 'Provider attestation and chart notes', 1, '2026-06-05T08:00:00'),
        ('CVS_COMM_100', 'Humira', 'Lab Requirement', 'Negative TB screening documented within 12 months', 'TB test result', 2, '2026-06-05T08:00:00'),
        ('CVS_MEDD_200', 'Keytruda', 'Diagnosis', 'FDA-approved oncology diagnosis required', 'Pathology report', 1, '2026-06-05T08:00:00'),
        ('ESI_COMM_100', 'Ozempic', 'Step Therapy', 'Trial of metformin unless contraindicated', 'Medication history', 1, '2026-06-05T08:00:00'),
        ('ESI_COMM_100', 'Ozempic', 'Clinical Threshold', 'A1C remains uncontrolled after first-line therapy', 'Recent A1C lab', 2, '2026-06-05T08:00:00'),
        ('ESI_MEDD_200', 'Eliquis', 'Quantity Limit', 'Maximum 2 tablets per day', 'Prescription details', 1, '2026-06-05T08:00:00'),
        ('OPT_COMM_100', 'Xarelto', 'Diagnosis', 'Approved diagnosis of DVT, PE, or AFib', 'Problem list or discharge summary', 1, '2026-06-05T08:00:00'),
        ('OPT_EXCH_200', 'Jardiance', 'Step Therapy', 'Failure or intolerance to metformin documented', 'Medication history', 1, '2026-06-05T08:00:00'),
        ('PRIME_COMM_100', 'Entresto', 'Clinical Threshold', 'NYHA class II-IV heart failure documented', 'Ejection fraction results', 1, '2026-06-05T08:00:00'),
        ('PRIME_MEDD_200', 'Dupixent', 'Diagnosis', 'Moderate to severe atopic dermatitis or asthma diagnosis', 'Clinical notes', 1, '2026-06-05T08:00:00'),
        ('PRIME_MEDD_200', 'Dupixent', 'Documentation', 'Body surface area or eosinophil history required', 'Lab results or assessment', 2, '2026-06-05T08:00:00'),
        ('HUMANA_MAPD_100', 'Skyrizi', 'Specialist', 'Prescription written by dermatologist or gastroenterologist', 'Specialist note', 1, '2026-06-05T08:00:00'),
        ('HUMANA_MAPD_100', 'Skyrizi', 'Step Therapy', 'Failure of at least one preferred biologic', 'Claims history', 2, '2026-06-05T08:00:00'),
        ('HUMANA_COMM_200', 'Stelara', 'Diagnosis', 'Psoriasis, psoriatic arthritis, or Crohn''s disease diagnosis', 'Problem list', 1, '2026-06-05T08:00:00'),
        ('CVS_EXCH_300', 'Imbruvica', 'Diagnosis', 'B-cell malignancy confirmed', 'Pathology and oncology note', 1, '2026-06-05T08:00:00'),
        ('ESI_COMM_400', 'Revlimid', 'REMS', 'Active REMS enrollment required', 'REMS enrollment confirmation', 1, '2026-06-05T08:00:00'),
        ('OPT_MEDD_300', 'Enbrel', 'Step Therapy', 'History of methotrexate trial required', 'Medication fill history', 1, '2026-06-05T08:00:00'),
        ('PRIME_EXCH_400', 'Remicade', 'Site of Care', 'Infusion site of care review completed', 'Infusion center request', 1, '2026-06-05T08:00:00'),
        ('HUMANA_COMM_500', 'Cosentyx', 'Diagnosis', 'Plaque psoriasis or ankylosing spondylitis diagnosis', 'Specialist note', 1, '2026-06-05T08:00:00'),
        ('HUMANA_COMM_500', 'Cosentyx', 'Lab Requirement', 'Negative TB screening before initiation', 'TB test result', 2, '2026-06-05T08:00:00')
    ) AS src (PlanID, DrugName, CriterionType, CriterionText, RequiredDocumentation, CriterionOrder, LoadDate)
    INNER JOIN dbo.MMIT_Drugs AS d
        ON d.DrugName = src.DrugName
    INNER JOIN dbo.MMIT_PansController AS pc
        ON pc.PlanID = src.PlanID
       AND pc.DrugID = d.DrugID
) AS src
ON tgt.PanID = src.PanID AND tgt.CriterionOrder = src.CriterionOrder
WHEN MATCHED THEN
    UPDATE SET
        tgt.CriterionType = src.CriterionType,
        tgt.CriterionText = src.CriterionText,
        tgt.RequiredDocumentation = src.RequiredDocumentation,
        tgt.LoadDate = src.LoadDate,
        tgt.IsNew = 1
WHEN NOT MATCHED BY TARGET THEN
    INSERT (PanID, CriterionType, CriterionText, RequiredDocumentation, CriterionOrder, LoadDate, IsNew)
    VALUES (src.PanID, src.CriterionType, src.CriterionText, src.RequiredDocumentation, src.CriterionOrder, src.LoadDate, 1);
GO
MERGE dbo.MMIT_Restrictions AS tgt
USING
(
    SELECT
        d.DrugID,
        src.PlanID,
        src.PlanName,
        src.RestrictionType,
        src.RestrictionDetails,
        src.CoverageStatus,
        src.TierLevel,
        CAST(src.EffectiveDate AS DATE) AS EffectiveDate,
        CAST(src.LoadDate AS DATETIME) AS LoadDate
    FROM
    (
        VALUES
            ('Humira', 'PBM_CVS_001', 'CVS Caremark National Commercial', 'Prior Authorization', 'Specialty review and TB screening required', 'Covered with Restrictions', 4, '2026-01-01', '2026-06-05T08:00:00'),
        ('Humira', 'PBM_ESI_001', 'Express Scripts National Commercial', 'Step Therapy', 'Trial of methotrexate required before Humira', 'Covered with Restrictions', 4, '2026-01-01', '2026-06-05T08:00:00'),
        ('Keytruda', 'PBM_CVS_002', 'CVS Caremark Oncology', 'Prior Authorization', 'Oncology diagnosis and biomarker confirmation required', 'Covered with Restrictions', 4, '2026-01-01', '2026-06-05T08:00:00'),
        ('Ozempic', 'PBM_OPT_001', 'OptumRx Commercial Essential', 'Step Therapy', 'Step through metformin and preferred GLP-1 alternatives', 'Tier 2', 2, '2026-01-01', '2026-06-05T08:00:00'),
        ('Ozempic', 'PBM_PRIME_001', 'Prime Therapeutics Exchange', 'Quantity Limit', '1 pen per 28 days without exception approval', 'Covered with Restrictions', 2, '2026-01-01', '2026-06-05T08:00:00'),
        ('Eliquis', 'PBM_HUM_001', 'Humana Pharmacy Solutions MAPD', 'Quantity Limit', 'Maximum of 60 tablets per 30 days', 'Tier 2', 2, '2026-01-01', '2026-06-05T08:00:00'),
        ('Xarelto', 'PBM_CVS_003', 'CVS Caremark National Commercial', 'Non-Preferred', 'Preferred anticoagulant is Eliquis', 'Tier 3', 3, '2026-01-01', '2026-06-05T08:00:00'),
        ('Jardiance', 'PBM_ESI_002', 'Express Scripts Diabetes Plus', 'Preferred', 'Preferred SGLT2 agent on plan formulary', 'Preferred', 2, '2026-01-01', '2026-06-05T08:00:00'),
        ('Entresto', 'PBM_OPT_002', 'OptumRx Cardiology', 'Covered', 'Covered for guideline-directed therapy', 'Covered', 2, '2026-01-01', '2026-06-05T08:00:00'),
        ('Dupixent', 'PBM_PRIME_002', 'Prime Therapeutics Specialty', 'Prior Authorization', 'Specialist attestation and disease severity required', 'Covered with Restrictions', 4, '2026-01-01', '2026-06-05T08:00:00'),
        ('Skyrizi', 'PBM_HUM_002', 'Humana Pharmacy Solutions Commercial', 'Step Therapy', 'Preferred biologic failure required first', 'Tier 4', 4, '2026-01-01', '2026-06-05T08:00:00'),
        ('Stelara', 'PBM_CVS_004', 'CVS Caremark Specialty', 'Formulary Exception', 'Medical exception review required for non-preferred biologic', 'Formulary Exception', 4, '2026-01-01', '2026-06-05T08:00:00'),
        ('Imbruvica', 'PBM_ESI_003', 'Express Scripts Oncology', 'Prior Authorization', 'B-cell malignancy diagnosis and oncology note required', 'Covered with Restrictions', 4, '2026-01-01', '2026-06-05T08:00:00'),
        ('Revlimid', 'PBM_OPT_003', 'OptumRx Oncology', 'Quantity Limit', '28 capsules per fill under REMS oversight', 'Covered NF', 4, '2026-01-01', '2026-06-05T08:00:00'),
        ('Enbrel', 'PBM_PRIME_003', 'Prime Therapeutics Rheumatology', 'Step Therapy', 'Must fail methotrexate or leflunomide first', 'Tier 4', 4, '2026-01-01', '2026-06-05T08:00:00'),
        ('Remicade', 'PBM_HUM_003', 'Humana Infusion Management', 'Prior Authorization', 'Site-of-care and diagnosis review required', 'Covered with Restrictions', 4, '2026-01-01', '2026-06-05T08:00:00'),
        ('Cosentyx', 'PBM_CVS_005', 'CVS Caremark Dermatology', 'Prior Authorization', 'Plaque psoriasis diagnosis and TB screening required', 'Covered with Restrictions', 4, '2026-01-01', '2026-06-05T08:00:00'),
        ('Taltz', 'PBM_ESI_004', 'Express Scripts Dermatology', 'Tier Override', 'Non-preferred IL-17 agent; override allowed with exception', 'Non-Preferred', 4, '2026-01-01', '2026-06-05T08:00:00'),
        ('Rinvoq', 'PBM_OPT_004', 'OptumRx Specialty Essential', 'Prior Authorization', 'Specialty review for RA or UC diagnosis', 'Covered with Restrictions', 4, '2026-01-01', '2026-06-05T08:00:00'),
        ('Aimovig', 'PBM_PRIME_004', 'Prime Therapeutics Neurology', 'Quantity Limit', 'One autoinjector pack per 30 days', 'Tier 3', 3, '2026-01-01', '2026-06-05T08:00:00')
    ) AS src (DrugName, PlanID, PlanName, RestrictionType, RestrictionDetails, CoverageStatus, TierLevel, EffectiveDate, LoadDate)
    INNER JOIN dbo.MMIT_Drugs AS d
        ON d.DrugName = src.DrugName
) AS src
ON tgt.DrugID = src.DrugID AND tgt.PlanID = src.PlanID AND tgt.RestrictionType = src.RestrictionType AND tgt.EffectiveDate = src.EffectiveDate
WHEN MATCHED THEN
    UPDATE SET
        tgt.PlanName = src.PlanName,
        tgt.RestrictionDetails = src.RestrictionDetails,
        tgt.CoverageStatus = src.CoverageStatus,
        tgt.TierLevel = src.TierLevel,
        tgt.LoadDate = src.LoadDate,
        tgt.IsNew = 1
WHEN NOT MATCHED BY TARGET THEN
    INSERT (DrugID, PlanID, PlanName, RestrictionType, RestrictionDetails, CoverageStatus, TierLevel, EffectiveDate, LoadDate, IsNew)
    VALUES (src.DrugID, src.PlanID, src.PlanName, src.RestrictionType, src.RestrictionDetails, src.CoverageStatus, src.TierLevel, src.EffectiveDate, src.LoadDate, 1);
GO
MERGE dbo.MMIT_IDSAs AS tgt
USING
(
    SELECT
        d.DrugID,
        src.PlanID,
        src.StatusCode,
        src.CoverageType,
        src.FormularyTier,
        src.CoverageNotes,
        CAST(src.EffectiveDate AS DATE) AS EffectiveDate,
        CAST(src.LoadDate AS DATETIME) AS LoadDate
    FROM
    (
        VALUES
            ('Humira', 'PBM_CVS_001', 'COVERED_RESTRICTED', 'Commercial', 4, 'Covered after specialty PA approval', '2026-01-01', '2026-06-05T08:00:00'),
        ('Keytruda', 'PBM_CVS_002', 'PA_REQUIRED', 'Commercial', 4, 'Oncology diagnosis validation required', '2026-01-01', '2026-06-05T08:00:00'),
        ('Ozempic', 'PBM_OPT_001', 'STEP_THERAPY', 'Commercial', 2, 'Step through metformin first', '2026-01-01', '2026-06-05T08:00:00'),
        ('Ozempic', 'PBM_PRIME_001', 'QUANTITY_LIMIT', 'Exchange', 2, '1 pen per 28 days', '2026-01-01', '2026-06-05T08:00:00'),
        ('Eliquis', 'PBM_HUM_001', 'TIER2', 'Medicare', 2, 'Preferred oral anticoagulant', '2026-01-01', '2026-06-05T08:00:00'),
        ('Xarelto', 'PBM_CVS_003', 'NON_PREFERRED', 'Commercial', 3, 'Use Eliquis when clinically appropriate', '2026-01-01', '2026-06-05T08:00:00'),
        ('Jardiance', 'PBM_ESI_002', 'PREFERRED', 'Commercial', 2, 'Preferred SGLT2 agent', '2026-01-01', '2026-06-05T08:00:00'),
        ('Entresto', 'PBM_OPT_002', 'COVERED', 'Commercial', 2, 'Covered for HFrEF', '2026-01-01', '2026-06-05T08:00:00'),
        ('Dupixent', 'PBM_PRIME_002', 'PA_REQUIRED', 'Medicare', 4, 'Disease severity documentation required', '2026-01-01', '2026-06-05T08:00:00'),
        ('Skyrizi', 'PBM_HUM_002', 'STEP_THERAPY', 'Commercial', 4, 'Preferred biologic trial required', '2026-01-01', '2026-06-05T08:00:00'),
        ('Stelara', 'PBM_CVS_004', 'FORMULARY_EXCEPTION', 'Commercial', 4, 'Exception review available', '2026-01-01', '2026-06-05T08:00:00'),
        ('Imbruvica', 'PBM_ESI_003', 'COVERED_RESTRICTED', 'Commercial', 4, 'Restricted oncology specialty product', '2026-01-01', '2026-06-05T08:00:00'),
        ('Revlimid', 'PBM_OPT_003', 'COVERED_NF', 'Commercial', 4, 'Non-formulary approval with REMS', '2026-01-01', '2026-06-05T08:00:00'),
        ('Enbrel', 'PBM_PRIME_003', 'TIER4', 'Commercial', 4, 'Specialty biologic tier', '2026-01-01', '2026-06-05T08:00:00'),
        ('Remicade', 'PBM_HUM_003', 'PA_REQUIRED', 'Commercial', 4, 'Infusion site review required', '2026-01-01', '2026-06-05T08:00:00'),
        ('Cosentyx', 'PBM_CVS_005', 'COVERED_RESTRICTED', 'Commercial', 4, 'Dermatology PA required', '2026-01-01', '2026-06-05T08:00:00'),
        ('Taltz', 'PBM_ESI_004', 'NON_PREFERRED', 'Commercial', 4, 'Non-preferred IL-17 option', '2026-01-01', '2026-06-05T08:00:00'),
        ('Rinvoq', 'PBM_OPT_004', 'PA_REQUIRED', 'Commercial', 4, 'RA or UC diagnosis confirmation needed', '2026-01-01', '2026-06-05T08:00:00'),
        ('Aimovig', 'PBM_PRIME_004', 'QUANTITY_LIMIT', 'Commercial', 3, 'One carton every 30 days', '2026-01-01', '2026-06-05T08:00:00'),
        ('Cimzia', 'PBM_HUM_004', 'TIER4', 'Commercial', 4, 'Specialty rheumatology biologic', '2026-01-01', '2026-06-05T08:00:00')
    ) AS src (DrugName, PlanID, StatusCode, CoverageType, FormularyTier, CoverageNotes, EffectiveDate, LoadDate)
    INNER JOIN dbo.MMIT_Drugs AS d
        ON d.DrugName = src.DrugName
    INNER JOIN dbo.MMIT_Statuses AS s
        ON s.StatusCode = src.StatusCode
) AS src
ON tgt.DrugID = src.DrugID AND tgt.PlanID = src.PlanID
WHEN MATCHED THEN
    UPDATE SET
        tgt.StatusCode = src.StatusCode,
        tgt.CoverageType = src.CoverageType,
        tgt.FormularyTier = src.FormularyTier,
        tgt.CoverageNotes = src.CoverageNotes,
        tgt.EffectiveDate = src.EffectiveDate,
        tgt.LoadDate = src.LoadDate,
        tgt.IsNew = 1
WHEN NOT MATCHED BY TARGET THEN
    INSERT (DrugID, PlanID, StatusCode, CoverageType, FormularyTier, CoverageNotes, EffectiveDate, LoadDate, IsNew)
    VALUES (src.DrugID, src.PlanID, src.StatusCode, src.CoverageType, src.FormularyTier, src.CoverageNotes, src.EffectiveDate, src.LoadDate, 1);
GO
MERGE dbo.MMIT_Medopen_Bridge AS tgt
USING
(
    SELECT
        d.DrugID AS MMITDrugID,
        src.MedOpenDrugID,
        src.MedOpenDrugName,
        src.CrosswalkType,
        CAST(src.MatchConfidence AS DECIMAL(5,2)) AS MatchConfidence,
        CAST(src.LoadDate AS DATETIME) AS LoadDate
    FROM
    (
        VALUES
            ('Humira', 'MO-1001', 'Humira Pen 40 MG/0.4 ML', 'Exact', 99.80, '2026-06-05T08:00:00'),
        ('Keytruda', 'MO-1002', 'Keytruda IV Solution', 'Exact', 99.60, '2026-06-05T08:00:00'),
        ('Ozempic', 'MO-1003', 'Ozempic Pen Injector', 'Exact', 99.40, '2026-06-05T08:00:00'),
        ('Eliquis', 'MO-1004', 'Eliquis Oral Tablet', 'Exact', 99.90, '2026-06-05T08:00:00'),
        ('Xarelto', 'MO-1005', 'Xarelto Oral Tablet', 'Exact', 99.70, '2026-06-05T08:00:00'),
        ('Jardiance', 'MO-1006', 'Jardiance Oral Tablet', 'Exact', 99.50, '2026-06-05T08:00:00'),
        ('Entresto', 'MO-1007', 'Entresto Oral Tablet', 'Exact', 99.45, '2026-06-05T08:00:00'),
        ('Dupixent', 'MO-1008', 'Dupixent Prefilled Pen', 'Exact', 99.10, '2026-06-05T08:00:00'),
        ('Skyrizi', 'MO-1009', 'Skyrizi Prefilled Pen', 'Exact', 98.95, '2026-06-05T08:00:00'),
        ('Stelara', 'MO-1010', 'Stelara Injection', 'Exact', 99.20, '2026-06-05T08:00:00'),
        ('Imbruvica', 'MO-1011', 'Imbruvica Oral Capsule', 'Exact', 99.55, '2026-06-05T08:00:00'),
        ('Revlimid', 'MO-1012', 'Revlimid Oral Capsule', 'Exact', 99.35, '2026-06-05T08:00:00'),
        ('Enbrel', 'MO-1013', 'Enbrel SureClick Autoinjector', 'Exact', 99.25, '2026-06-05T08:00:00'),
        ('Remicade', 'MO-1014', 'Remicade IV Infusion', 'Semantic', 98.50, '2026-06-05T08:00:00'),
        ('Cosentyx', 'MO-1015', 'Cosentyx Sensoready Pen', 'Exact', 99.15, '2026-06-05T08:00:00')
    ) AS src (DrugName, MedOpenDrugID, MedOpenDrugName, CrosswalkType, MatchConfidence, LoadDate)
    INNER JOIN dbo.MMIT_Drugs AS d
        ON d.DrugName = src.DrugName
) AS src
ON tgt.MMITDrugID = src.MMITDrugID AND tgt.MedOpenDrugID = src.MedOpenDrugID
WHEN MATCHED THEN
    UPDATE SET
        tgt.MedOpenDrugName = src.MedOpenDrugName,
        tgt.CrosswalkType = src.CrosswalkType,
        tgt.MatchConfidence = src.MatchConfidence,
        tgt.LoadDate = src.LoadDate,
        tgt.IsNew = 1
WHEN NOT MATCHED BY TARGET THEN
    INSERT (MMITDrugID, MedOpenDrugID, MedOpenDrugName, CrosswalkType, MatchConfidence, LoadDate, IsNew)
    VALUES (src.MMITDrugID, src.MedOpenDrugID, src.MedOpenDrugName, src.CrosswalkType, src.MatchConfidence, src.LoadDate, 1);
GO
MERGE dbo.MMIT_PansControllerNCD AS tgt
USING
(
    SELECT
        src.PlanID,
        d.DrugID,
        src.NCDReason,
        src.AlternativeDrug,
        CAST(src.EffectiveDate AS DATE) AS EffectiveDate,
        CAST(src.TermDate AS DATE) AS TermDate,
        CAST(src.LoadDate AS DATETIME) AS LoadDate
    FROM
    (
        VALUES
            ('PBM_CVS_901', 'Humira', 'Lower-net-cost biosimilar preferred', 'Amjevita', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('PBM_CVS_902', 'Skyrizi', 'Plan prefers alternate IL-23 product for selected lines', 'Tremfya', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('PBM_ESI_901', 'Xarelto', 'Preferred anticoagulant contract favors Eliquis', 'Eliquis', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('PBM_ESI_902', 'Taltz', 'Lower cost IL-17 alternative available', 'Cosentyx', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('PBM_OPT_901', 'Revlimid', 'Generic strategy and specialty optimization review', 'Lenalidomide generic', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('PBM_OPT_902', 'Aimovig', 'Competing CGRP agent preferred on select formularies', 'Ajovy', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('PBM_PRIME_901', 'Dupixent', 'Contracted alternative required before approval', 'Adbry', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('PBM_PRIME_902', 'Cimzia', 'Preferred TNF inhibitor alignment', 'Enbrel', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('PBM_HUM_901', 'Keytruda', 'Medical benefit pathway preferred over pharmacy benefit', 'Hospital outpatient billing', '2026-01-01', NULL, '2026-06-05T08:00:00'),
        ('PBM_HUM_902', 'Rinvoq', 'Lower cost JAK alternative preferred', 'Xeljanz', '2026-01-01', NULL, '2026-06-05T08:00:00')
    ) AS src (PlanID, DrugName, NCDReason, AlternativeDrug, EffectiveDate, TermDate, LoadDate)
    INNER JOIN dbo.MMIT_Drugs AS d
        ON d.DrugName = src.DrugName
) AS src
ON tgt.PlanID = src.PlanID AND tgt.DrugID = src.DrugID AND tgt.EffectiveDate = src.EffectiveDate
WHEN MATCHED THEN
    UPDATE SET
        tgt.NCDReason = src.NCDReason,
        tgt.AlternativeDrug = src.AlternativeDrug,
        tgt.TermDate = src.TermDate,
        tgt.LoadDate = src.LoadDate,
        tgt.IsNew = 1
WHEN NOT MATCHED BY TARGET THEN
    INSERT (PlanID, DrugID, NCDReason, AlternativeDrug, EffectiveDate, TermDate, LoadDate, IsNew)
    VALUES (src.PlanID, src.DrugID, src.NCDReason, src.AlternativeDrug, src.EffectiveDate, src.TermDate, src.LoadDate, 1);
GO

-- ============================================================================
-- SECTION 3 - CREATE INGESTION SPs
-- Each SP creates its corresponding _Holding table if missing, merges data,
-- and reports inserted / updated / deleted counts back to Talend.
-- ============================================================================

IF OBJECT_ID('dbo.sp_MMIT_Load_Drugs', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_MMIT_Load_Drugs;
GO

CREATE PROCEDURE dbo.sp_MMIT_Load_Drugs
AS
BEGIN
    DECLARE @InsertedCnt INT = 0;
    DECLARE @UpdatedCnt  INT = 0;
    DECLARE @DeletedCnt  INT = 0;
    DECLARE @HoldingCnt  INT = 0;
    DECLARE @MergeActions TABLE (ActionName NVARCHAR(10) NOT NULL);

    SET NOCOUNT ON;

    BEGIN TRY
        IF OBJECT_ID('dbo.MMIT_Drugs_Holding', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.MMIT_Drugs_Holding
            (
                NDCCode VARCHAR(11) NOT NULL,
            DrugName VARCHAR(200) NOT NULL,
            BrandName VARCHAR(200) NULL,
            GenericName VARCHAR(200) NULL,
            ManufacturerName VARCHAR(200) NULL,
            DrugClass VARCHAR(100) NULL,
            TherapeuticClass VARCHAR(100) NULL,
            FormularyStatus VARCHAR(50) NULL,
            IsActive BIT NOT NULL,
            LoadDate DATETIME NULL
            );
        END
        SELECT @HoldingCnt = COUNT(1)
        FROM dbo.MMIT_Drugs_Holding;

        IF @HoldingCnt = 0
        BEGIN
            SELECT 'MMIT_Drugs' AS EntityName, 0 AS InsertedCnt, 0 AS UpdatedCnt, 0 AS DeletedCnt;
            RETURN;
        END

        MERGE dbo.MMIT_Drugs AS tgt
        USING dbo.MMIT_Drugs_Holding AS src
            ON tgt.NDCCode = src.NDCCode
        WHEN MATCHED AND
            (
                ISNULL(tgt.DrugName, '') <> ISNULL(src.DrugName, '') OR
                ISNULL(tgt.BrandName, '') <> ISNULL(src.BrandName, '') OR
                ISNULL(tgt.GenericName, '') <> ISNULL(src.GenericName, '') OR
                ISNULL(tgt.ManufacturerName, '') <> ISNULL(src.ManufacturerName, '') OR
                ISNULL(tgt.DrugClass, '') <> ISNULL(src.DrugClass, '') OR
                ISNULL(tgt.TherapeuticClass, '') <> ISNULL(src.TherapeuticClass, '') OR
                ISNULL(tgt.FormularyStatus, '') <> ISNULL(src.FormularyStatus, '') OR
                ISNULL(tgt.IsActive, 0) <> ISNULL(src.IsActive, 0)
            ) THEN
            UPDATE SET
                tgt.DrugName = src.DrugName,
                tgt.BrandName = src.BrandName,
                tgt.GenericName = src.GenericName,
                tgt.ManufacturerName = src.ManufacturerName,
                tgt.DrugClass = src.DrugClass,
                tgt.TherapeuticClass = src.TherapeuticClass,
                tgt.FormularyStatus = src.FormularyStatus,
                tgt.IsActive = src.IsActive,
                tgt.LoadDate = ISNULL(src.LoadDate, GETDATE()),
                tgt.IsNew = 1
        WHEN NOT MATCHED BY TARGET THEN
            INSERT (NDCCode, DrugName, BrandName, GenericName, ManufacturerName, DrugClass, TherapeuticClass, FormularyStatus, IsActive, LoadDate, IsNew)
            VALUES (src.NDCCode, src.DrugName, src.BrandName, src.GenericName, src.ManufacturerName, src.DrugClass, src.TherapeuticClass, src.FormularyStatus, src.IsActive, ISNULL(src.LoadDate, GETDATE()), 1)
        OUTPUT $action INTO @MergeActions (ActionName);

        SELECT
            @InsertedCnt = SUM(CASE WHEN ActionName = 'INSERT' THEN 1 ELSE 0 END),
            @UpdatedCnt = SUM(CASE WHEN ActionName = 'UPDATE' THEN 1 ELSE 0 END)
        FROM @MergeActions;

        SET @InsertedCnt = ISNULL(@InsertedCnt, 0);
        SET @UpdatedCnt = ISNULL(@UpdatedCnt, 0);

        UPDATE tgt
        SET tgt.IsNew = 0, tgt.IsActive = 0, tgt.LoadDate = GETDATE()
        FROM dbo.MMIT_Drugs AS tgt
        WHERE NOT EXISTS
        (
            SELECT 1
            FROM dbo.MMIT_Drugs_Holding AS src
            WHERE src.NDCCode = tgt.NDCCode
        )
          AND (ISNULL(tgt.IsNew, 1) <> 0 OR ISNULL(tgt.IsActive, 1) <> 0)
;

        SET @DeletedCnt = @@ROWCOUNT;
        SELECT 'MMIT_Drugs' AS EntityName, @InsertedCnt AS InsertedCnt, @UpdatedCnt AS UpdatedCnt, @DeletedCnt AS DeletedCnt;
    END TRY
    BEGIN CATCH
        RAISERROR(ERROR_MESSAGE(), 16, 1);
    END CATCH
END;
GO
IF OBJECT_ID('dbo.sp_MMIT_Load_PansController', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_MMIT_Load_PansController;
GO

CREATE PROCEDURE dbo.sp_MMIT_Load_PansController
AS
BEGIN
    DECLARE @InsertedCnt INT = 0;
    DECLARE @UpdatedCnt  INT = 0;
    DECLARE @DeletedCnt  INT = 0;
    DECLARE @HoldingCnt  INT = 0;
    DECLARE @MergeActions TABLE (ActionName NVARCHAR(10) NOT NULL);

    SET NOCOUNT ON;

    BEGIN TRY
        IF OBJECT_ID('dbo.MMIT_PansController_Holding', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.MMIT_PansController_Holding
            (
                PlanID VARCHAR(50) NOT NULL,
            DrugID INT NOT NULL,
            PARequired BIT NOT NULL,
            StepTherapyRequired BIT NOT NULL,
            QuantityLimitRequired BIT NOT NULL,
            PAType VARCHAR(50) NULL,
            EffectiveDate DATE NOT NULL,
            TermDate DATE NULL,
            LoadDate DATETIME NULL
            );
        END
        SELECT @HoldingCnt = COUNT(1)
        FROM dbo.MMIT_PansController_Holding;

        IF @HoldingCnt = 0
        BEGIN
            SELECT 'MMIT_PansController' AS EntityName, 0 AS InsertedCnt, 0 AS UpdatedCnt, 0 AS DeletedCnt;
            RETURN;
        END

        MERGE dbo.MMIT_PansController AS tgt
        USING dbo.MMIT_PansController_Holding AS src
            ON tgt.PlanID = src.PlanID AND tgt.DrugID = src.DrugID AND tgt.EffectiveDate = src.EffectiveDate
        WHEN MATCHED AND
            (
                ISNULL(tgt.PARequired, -2147483648) <> ISNULL(src.PARequired, -2147483648) OR
                ISNULL(tgt.StepTherapyRequired, -2147483648) <> ISNULL(src.StepTherapyRequired, -2147483648) OR
                ISNULL(tgt.QuantityLimitRequired, -2147483648) <> ISNULL(src.QuantityLimitRequired, -2147483648) OR
                ISNULL(tgt.PAType, '') <> ISNULL(src.PAType, '') OR
                ISNULL(CONVERT(VARCHAR(10), tgt.TermDate, 120), '') <> ISNULL(CONVERT(VARCHAR(10), src.TermDate, 120), '')
            ) THEN
            UPDATE SET
                tgt.PARequired = src.PARequired,
                tgt.StepTherapyRequired = src.StepTherapyRequired,
                tgt.QuantityLimitRequired = src.QuantityLimitRequired,
                tgt.PAType = src.PAType,
                tgt.TermDate = src.TermDate,
                tgt.LoadDate = ISNULL(src.LoadDate, GETDATE()),
                tgt.IsNew = 1
        WHEN NOT MATCHED BY TARGET THEN
            INSERT (PlanID, DrugID, PARequired, StepTherapyRequired, QuantityLimitRequired, PAType, EffectiveDate, TermDate, LoadDate, IsNew)
            VALUES (src.PlanID, src.DrugID, src.PARequired, src.StepTherapyRequired, src.QuantityLimitRequired, src.PAType, src.EffectiveDate, src.TermDate, ISNULL(src.LoadDate, GETDATE()), 1)
        OUTPUT $action INTO @MergeActions (ActionName);

        SELECT
            @InsertedCnt = SUM(CASE WHEN ActionName = 'INSERT' THEN 1 ELSE 0 END),
            @UpdatedCnt = SUM(CASE WHEN ActionName = 'UPDATE' THEN 1 ELSE 0 END)
        FROM @MergeActions;

        SET @InsertedCnt = ISNULL(@InsertedCnt, 0);
        SET @UpdatedCnt = ISNULL(@UpdatedCnt, 0);

        UPDATE tgt
        SET tgt.IsNew = 0, tgt.LoadDate = GETDATE()
        FROM dbo.MMIT_PansController AS tgt
        WHERE NOT EXISTS
        (
            SELECT 1
            FROM dbo.MMIT_PansController_Holding AS src
            WHERE src.PlanID = tgt.PlanID AND src.DrugID = tgt.DrugID AND src.EffectiveDate = tgt.EffectiveDate
        )
          AND (ISNULL(tgt.IsNew, 1) <> 0)
;

        SET @DeletedCnt = @@ROWCOUNT;
        SELECT 'MMIT_PansController' AS EntityName, @InsertedCnt AS InsertedCnt, @UpdatedCnt AS UpdatedCnt, @DeletedCnt AS DeletedCnt;
    END TRY
    BEGIN CATCH
        RAISERROR(ERROR_MESSAGE(), 16, 1);
    END CATCH
END;
GO
IF OBJECT_ID('dbo.sp_MMIT_Load_MedopenBridge', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_MMIT_Load_MedopenBridge;
GO

CREATE PROCEDURE dbo.sp_MMIT_Load_MedopenBridge
AS
BEGIN
    DECLARE @InsertedCnt INT = 0;
    DECLARE @UpdatedCnt  INT = 0;
    DECLARE @DeletedCnt  INT = 0;
    DECLARE @HoldingCnt  INT = 0;
    DECLARE @MergeActions TABLE (ActionName NVARCHAR(10) NOT NULL);

    SET NOCOUNT ON;

    BEGIN TRY
        IF OBJECT_ID('dbo.MMIT_Medopen_Bridge_Holding', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.MMIT_Medopen_Bridge_Holding
            (
                MMITDrugID INT NOT NULL,
            MedOpenDrugID VARCHAR(50) NOT NULL,
            MedOpenDrugName VARCHAR(200) NULL,
            CrosswalkType VARCHAR(50) NULL,
            MatchConfidence DECIMAL(5,2) NULL,
            LoadDate DATETIME NULL
            );
        END
        SELECT @HoldingCnt = COUNT(1)
        FROM dbo.MMIT_Medopen_Bridge_Holding;

        IF @HoldingCnt = 0
        BEGIN
            SELECT 'MMIT_Medopen_Bridge' AS EntityName, 0 AS InsertedCnt, 0 AS UpdatedCnt, 0 AS DeletedCnt;
            RETURN;
        END

        MERGE dbo.MMIT_Medopen_Bridge AS tgt
        USING dbo.MMIT_Medopen_Bridge_Holding AS src
            ON tgt.MMITDrugID = src.MMITDrugID AND tgt.MedOpenDrugID = src.MedOpenDrugID
        WHEN MATCHED AND
            (
                ISNULL(tgt.MedOpenDrugName, '') <> ISNULL(src.MedOpenDrugName, '') OR
                ISNULL(tgt.CrosswalkType, '') <> ISNULL(src.CrosswalkType, '') OR
                ISNULL(tgt.MatchConfidence, -1.00) <> ISNULL(src.MatchConfidence, -1.00)
            ) THEN
            UPDATE SET
                tgt.MedOpenDrugName = src.MedOpenDrugName,
                tgt.CrosswalkType = src.CrosswalkType,
                tgt.MatchConfidence = src.MatchConfidence,
                tgt.LoadDate = ISNULL(src.LoadDate, GETDATE()),
                tgt.IsNew = 1
        WHEN NOT MATCHED BY TARGET THEN
            INSERT (MMITDrugID, MedOpenDrugID, MedOpenDrugName, CrosswalkType, MatchConfidence, LoadDate, IsNew)
            VALUES (src.MMITDrugID, src.MedOpenDrugID, src.MedOpenDrugName, src.CrosswalkType, src.MatchConfidence, ISNULL(src.LoadDate, GETDATE()), 1)
        OUTPUT $action INTO @MergeActions (ActionName);

        SELECT
            @InsertedCnt = SUM(CASE WHEN ActionName = 'INSERT' THEN 1 ELSE 0 END),
            @UpdatedCnt = SUM(CASE WHEN ActionName = 'UPDATE' THEN 1 ELSE 0 END)
        FROM @MergeActions;

        SET @InsertedCnt = ISNULL(@InsertedCnt, 0);
        SET @UpdatedCnt = ISNULL(@UpdatedCnt, 0);

        UPDATE tgt
        SET tgt.IsNew = 0, tgt.LoadDate = GETDATE()
        FROM dbo.MMIT_Medopen_Bridge AS tgt
        WHERE NOT EXISTS
        (
            SELECT 1
            FROM dbo.MMIT_Medopen_Bridge_Holding AS src
            WHERE src.MMITDrugID = tgt.MMITDrugID AND src.MedOpenDrugID = tgt.MedOpenDrugID
        )
          AND (ISNULL(tgt.IsNew, 1) <> 0)
;

        SET @DeletedCnt = @@ROWCOUNT;
        SELECT 'MMIT_Medopen_Bridge' AS EntityName, @InsertedCnt AS InsertedCnt, @UpdatedCnt AS UpdatedCnt, @DeletedCnt AS DeletedCnt;
    END TRY
    BEGIN CATCH
        RAISERROR(ERROR_MESSAGE(), 16, 1);
    END CATCH
END;
GO
IF OBJECT_ID('dbo.sp_MMIT_Load_NDCBridge', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_MMIT_Load_NDCBridge;
GO

CREATE PROCEDURE dbo.sp_MMIT_Load_NDCBridge
AS
BEGIN
    DECLARE @InsertedCnt INT = 0;
    DECLARE @UpdatedCnt  INT = 0;
    DECLARE @DeletedCnt  INT = 0;
    DECLARE @HoldingCnt  INT = 0;
    DECLARE @MergeActions TABLE (ActionName NVARCHAR(10) NOT NULL);

    SET NOCOUNT ON;

    BEGIN TRY
        IF OBJECT_ID('dbo.MMIT_NDC_Bridge_Holding', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.MMIT_NDC_Bridge_Holding
            (
                NDC11 VARCHAR(11) NOT NULL,
            NDC10 VARCHAR(10) NULL,
            LabelerCode VARCHAR(6) NULL,
            ProductCode VARCHAR(4) NULL,
            PackageCode VARCHAR(2) NULL,
            DrugID INT NOT NULL,
            ProductName VARCHAR(200) NULL,
            LoadDate DATETIME NULL
            );
        END
        SELECT @HoldingCnt = COUNT(1)
        FROM dbo.MMIT_NDC_Bridge_Holding;

        IF @HoldingCnt = 0
        BEGIN
            SELECT 'MMIT_NDC_Bridge' AS EntityName, 0 AS InsertedCnt, 0 AS UpdatedCnt, 0 AS DeletedCnt;
            RETURN;
        END

        MERGE dbo.MMIT_NDC_Bridge AS tgt
        USING dbo.MMIT_NDC_Bridge_Holding AS src
            ON tgt.NDC11 = src.NDC11
        WHEN MATCHED AND
            (
                ISNULL(tgt.NDC10, '') <> ISNULL(src.NDC10, '') OR
                ISNULL(tgt.LabelerCode, '') <> ISNULL(src.LabelerCode, '') OR
                ISNULL(tgt.ProductCode, '') <> ISNULL(src.ProductCode, '') OR
                ISNULL(tgt.PackageCode, '') <> ISNULL(src.PackageCode, '') OR
                ISNULL(tgt.DrugID, -2147483648) <> ISNULL(src.DrugID, -2147483648) OR
                ISNULL(tgt.ProductName, '') <> ISNULL(src.ProductName, '')
            ) THEN
            UPDATE SET
                tgt.NDC10 = src.NDC10,
                tgt.LabelerCode = src.LabelerCode,
                tgt.ProductCode = src.ProductCode,
                tgt.PackageCode = src.PackageCode,
                tgt.DrugID = src.DrugID,
                tgt.ProductName = src.ProductName,
                tgt.LoadDate = ISNULL(src.LoadDate, GETDATE()),
                tgt.IsNew = 1
        WHEN NOT MATCHED BY TARGET THEN
            INSERT (NDC11, NDC10, LabelerCode, ProductCode, PackageCode, DrugID, ProductName, LoadDate, IsNew)
            VALUES (src.NDC11, src.NDC10, src.LabelerCode, src.ProductCode, src.PackageCode, src.DrugID, src.ProductName, ISNULL(src.LoadDate, GETDATE()), 1)
        OUTPUT $action INTO @MergeActions (ActionName);

        SELECT
            @InsertedCnt = SUM(CASE WHEN ActionName = 'INSERT' THEN 1 ELSE 0 END),
            @UpdatedCnt = SUM(CASE WHEN ActionName = 'UPDATE' THEN 1 ELSE 0 END)
        FROM @MergeActions;

        SET @InsertedCnt = ISNULL(@InsertedCnt, 0);
        SET @UpdatedCnt = ISNULL(@UpdatedCnt, 0);

        UPDATE tgt
        SET tgt.IsNew = 0, tgt.LoadDate = GETDATE()
        FROM dbo.MMIT_NDC_Bridge AS tgt
        WHERE NOT EXISTS
        (
            SELECT 1
            FROM dbo.MMIT_NDC_Bridge_Holding AS src
            WHERE src.NDC11 = tgt.NDC11
        )
          AND (ISNULL(tgt.IsNew, 1) <> 0)
;

        SET @DeletedCnt = @@ROWCOUNT;
        SELECT 'MMIT_NDC_Bridge' AS EntityName, @InsertedCnt AS InsertedCnt, @UpdatedCnt AS UpdatedCnt, @DeletedCnt AS DeletedCnt;
    END TRY
    BEGIN CATCH
        RAISERROR(ERROR_MESSAGE(), 16, 1);
    END CATCH
END;
GO
IF OBJECT_ID('dbo.sp_MMIT_Load_Restrictions', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_MMIT_Load_Restrictions;
GO

CREATE PROCEDURE dbo.sp_MMIT_Load_Restrictions
AS
BEGIN
    DECLARE @InsertedCnt INT = 0;
    DECLARE @UpdatedCnt  INT = 0;
    DECLARE @DeletedCnt  INT = 0;
    DECLARE @HoldingCnt  INT = 0;
    DECLARE @MergeActions TABLE (ActionName NVARCHAR(10) NOT NULL);

    SET NOCOUNT ON;

    BEGIN TRY
        IF OBJECT_ID('dbo.MMIT_Restrictions_Holding', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.MMIT_Restrictions_Holding
            (
                DrugID INT NOT NULL,
            PlanID VARCHAR(50) NOT NULL,
            PlanName VARCHAR(200) NULL,
            RestrictionType VARCHAR(50) NULL,
            RestrictionDetails VARCHAR(500) NULL,
            CoverageStatus VARCHAR(50) NULL,
            TierLevel INT NULL,
            EffectiveDate DATE NOT NULL,
            LoadDate DATETIME NULL
            );
        END
        SELECT @HoldingCnt = COUNT(1)
        FROM dbo.MMIT_Restrictions_Holding;

        IF @HoldingCnt = 0
        BEGIN
            SELECT 'MMIT_Restrictions' AS EntityName, 0 AS InsertedCnt, 0 AS UpdatedCnt, 0 AS DeletedCnt;
            RETURN;
        END

        MERGE dbo.MMIT_Restrictions AS tgt
        USING dbo.MMIT_Restrictions_Holding AS src
            ON tgt.DrugID = src.DrugID AND tgt.PlanID = src.PlanID AND tgt.RestrictionType = src.RestrictionType AND tgt.EffectiveDate = src.EffectiveDate
        WHEN MATCHED AND
            (
                ISNULL(tgt.PlanName, '') <> ISNULL(src.PlanName, '') OR
                ISNULL(tgt.RestrictionDetails, '') <> ISNULL(src.RestrictionDetails, '') OR
                ISNULL(tgt.CoverageStatus, '') <> ISNULL(src.CoverageStatus, '') OR
                ISNULL(tgt.TierLevel, -2147483648) <> ISNULL(src.TierLevel, -2147483648)
            ) THEN
            UPDATE SET
                tgt.PlanName = src.PlanName,
                tgt.RestrictionDetails = src.RestrictionDetails,
                tgt.CoverageStatus = src.CoverageStatus,
                tgt.TierLevel = src.TierLevel,
                tgt.LoadDate = ISNULL(src.LoadDate, GETDATE()),
                tgt.IsNew = 1
        WHEN NOT MATCHED BY TARGET THEN
            INSERT (DrugID, PlanID, PlanName, RestrictionType, RestrictionDetails, CoverageStatus, TierLevel, EffectiveDate, LoadDate, IsNew)
            VALUES (src.DrugID, src.PlanID, src.PlanName, src.RestrictionType, src.RestrictionDetails, src.CoverageStatus, src.TierLevel, src.EffectiveDate, ISNULL(src.LoadDate, GETDATE()), 1)
        OUTPUT $action INTO @MergeActions (ActionName);

        SELECT
            @InsertedCnt = SUM(CASE WHEN ActionName = 'INSERT' THEN 1 ELSE 0 END),
            @UpdatedCnt = SUM(CASE WHEN ActionName = 'UPDATE' THEN 1 ELSE 0 END)
        FROM @MergeActions;

        SET @InsertedCnt = ISNULL(@InsertedCnt, 0);
        SET @UpdatedCnt = ISNULL(@UpdatedCnt, 0);

        UPDATE tgt
        SET tgt.IsNew = 0, tgt.LoadDate = GETDATE()
        FROM dbo.MMIT_Restrictions AS tgt
        WHERE NOT EXISTS
        (
            SELECT 1
            FROM dbo.MMIT_Restrictions_Holding AS src
            WHERE src.DrugID = tgt.DrugID AND src.PlanID = tgt.PlanID AND src.RestrictionType = tgt.RestrictionType AND src.EffectiveDate = tgt.EffectiveDate
        )
          AND (ISNULL(tgt.IsNew, 1) <> 0)
;

        SET @DeletedCnt = @@ROWCOUNT;
        SELECT 'MMIT_Restrictions' AS EntityName, @InsertedCnt AS InsertedCnt, @UpdatedCnt AS UpdatedCnt, @DeletedCnt AS DeletedCnt;
    END TRY
    BEGIN CATCH
        RAISERROR(ERROR_MESSAGE(), 16, 1);
    END CATCH
END;
GO
IF OBJECT_ID('dbo.sp_MMIT_Load_Statuses', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_MMIT_Load_Statuses;
GO

CREATE PROCEDURE dbo.sp_MMIT_Load_Statuses
AS
BEGIN
    DECLARE @InsertedCnt INT = 0;
    DECLARE @UpdatedCnt  INT = 0;
    DECLARE @DeletedCnt  INT = 0;
    DECLARE @HoldingCnt  INT = 0;
    DECLARE @MergeActions TABLE (ActionName NVARCHAR(10) NOT NULL);

    SET NOCOUNT ON;

    BEGIN TRY
        IF OBJECT_ID('dbo.MMIT_Statuses_Holding', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.MMIT_Statuses_Holding
            (
                StatusCode VARCHAR(20) NOT NULL,
            StatusDescription VARCHAR(200) NULL,
            StatusType VARCHAR(50) NULL,
            StatusCategory VARCHAR(50) NULL,
            IsActive BIT NOT NULL,
            LoadDate DATETIME NULL
            );
        END
        SELECT @HoldingCnt = COUNT(1)
        FROM dbo.MMIT_Statuses_Holding;

        IF @HoldingCnt = 0
        BEGIN
            SELECT 'MMIT_Statuses' AS EntityName, 0 AS InsertedCnt, 0 AS UpdatedCnt, 0 AS DeletedCnt;
            RETURN;
        END

        MERGE dbo.MMIT_Statuses AS tgt
        USING dbo.MMIT_Statuses_Holding AS src
            ON tgt.StatusCode = src.StatusCode
        WHEN MATCHED AND
            (
                ISNULL(tgt.StatusDescription, '') <> ISNULL(src.StatusDescription, '') OR
                ISNULL(tgt.StatusType, '') <> ISNULL(src.StatusType, '') OR
                ISNULL(tgt.StatusCategory, '') <> ISNULL(src.StatusCategory, '') OR
                ISNULL(tgt.IsActive, 0) <> ISNULL(src.IsActive, 0)
            ) THEN
            UPDATE SET
                tgt.StatusDescription = src.StatusDescription,
                tgt.StatusType = src.StatusType,
                tgt.StatusCategory = src.StatusCategory,
                tgt.IsActive = src.IsActive,
                tgt.LoadDate = ISNULL(src.LoadDate, GETDATE()),
                tgt.IsNew = 1
        WHEN NOT MATCHED BY TARGET THEN
            INSERT (StatusCode, StatusDescription, StatusType, StatusCategory, IsActive, LoadDate, IsNew)
            VALUES (src.StatusCode, src.StatusDescription, src.StatusType, src.StatusCategory, src.IsActive, ISNULL(src.LoadDate, GETDATE()), 1)
        OUTPUT $action INTO @MergeActions (ActionName);

        SELECT
            @InsertedCnt = SUM(CASE WHEN ActionName = 'INSERT' THEN 1 ELSE 0 END),
            @UpdatedCnt = SUM(CASE WHEN ActionName = 'UPDATE' THEN 1 ELSE 0 END)
        FROM @MergeActions;

        SET @InsertedCnt = ISNULL(@InsertedCnt, 0);
        SET @UpdatedCnt = ISNULL(@UpdatedCnt, 0);

        UPDATE tgt
        SET tgt.IsNew = 0, tgt.IsActive = 0, tgt.LoadDate = GETDATE()
        FROM dbo.MMIT_Statuses AS tgt
        WHERE NOT EXISTS
        (
            SELECT 1
            FROM dbo.MMIT_Statuses_Holding AS src
            WHERE src.StatusCode = tgt.StatusCode
        )
          AND (ISNULL(tgt.IsNew, 1) <> 0 OR ISNULL(tgt.IsActive, 1) <> 0)
;

        SET @DeletedCnt = @@ROWCOUNT;
        SELECT 'MMIT_Statuses' AS EntityName, @InsertedCnt AS InsertedCnt, @UpdatedCnt AS UpdatedCnt, @DeletedCnt AS DeletedCnt;
    END TRY
    BEGIN CATCH
        RAISERROR(ERROR_MESSAGE(), 16, 1);
    END CATCH
END;
GO
IF OBJECT_ID('dbo.sp_MMIT_Load_IDSAs', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_MMIT_Load_IDSAs;
GO

CREATE PROCEDURE dbo.sp_MMIT_Load_IDSAs
AS
BEGIN
    DECLARE @InsertedCnt INT = 0;
    DECLARE @UpdatedCnt  INT = 0;
    DECLARE @DeletedCnt  INT = 0;
    DECLARE @HoldingCnt  INT = 0;
    DECLARE @MergeActions TABLE (ActionName NVARCHAR(10) NOT NULL);

    SET NOCOUNT ON;

    BEGIN TRY
        IF OBJECT_ID('dbo.MMIT_IDSAs_Holding', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.MMIT_IDSAs_Holding
            (
                DrugID INT NOT NULL,
            PlanID VARCHAR(50) NOT NULL,
            StatusCode VARCHAR(20) NOT NULL,
            CoverageType VARCHAR(50) NULL,
            FormularyTier INT NULL,
            CoverageNotes VARCHAR(500) NULL,
            EffectiveDate DATE NOT NULL,
            LoadDate DATETIME NULL
            );
        END
        SELECT @HoldingCnt = COUNT(1)
        FROM dbo.MMIT_IDSAs_Holding;

        IF @HoldingCnt = 0
        BEGIN
            SELECT 'MMIT_IDSAs' AS EntityName, 0 AS InsertedCnt, 0 AS UpdatedCnt, 0 AS DeletedCnt;
            RETURN;
        END

        MERGE dbo.MMIT_IDSAs AS tgt
        USING dbo.MMIT_IDSAs_Holding AS src
            ON tgt.DrugID = src.DrugID AND tgt.PlanID = src.PlanID
        WHEN MATCHED AND
            (
                ISNULL(tgt.StatusCode, '') <> ISNULL(src.StatusCode, '') OR
                ISNULL(tgt.CoverageType, '') <> ISNULL(src.CoverageType, '') OR
                ISNULL(tgt.FormularyTier, -2147483648) <> ISNULL(src.FormularyTier, -2147483648) OR
                ISNULL(tgt.CoverageNotes, '') <> ISNULL(src.CoverageNotes, '') OR
                ISNULL(CONVERT(VARCHAR(10), tgt.EffectiveDate, 120), '') <> ISNULL(CONVERT(VARCHAR(10), src.EffectiveDate, 120), '')
            ) THEN
            UPDATE SET
                tgt.StatusCode = src.StatusCode,
                tgt.CoverageType = src.CoverageType,
                tgt.FormularyTier = src.FormularyTier,
                tgt.CoverageNotes = src.CoverageNotes,
                tgt.EffectiveDate = src.EffectiveDate,
                tgt.LoadDate = ISNULL(src.LoadDate, GETDATE()),
                tgt.IsNew = 1
        WHEN NOT MATCHED BY TARGET THEN
            INSERT (DrugID, PlanID, StatusCode, CoverageType, FormularyTier, CoverageNotes, EffectiveDate, LoadDate, IsNew)
            VALUES (src.DrugID, src.PlanID, src.StatusCode, src.CoverageType, src.FormularyTier, src.CoverageNotes, src.EffectiveDate, ISNULL(src.LoadDate, GETDATE()), 1)
        OUTPUT $action INTO @MergeActions (ActionName);

        SELECT
            @InsertedCnt = SUM(CASE WHEN ActionName = 'INSERT' THEN 1 ELSE 0 END),
            @UpdatedCnt = SUM(CASE WHEN ActionName = 'UPDATE' THEN 1 ELSE 0 END)
        FROM @MergeActions;

        SET @InsertedCnt = ISNULL(@InsertedCnt, 0);
        SET @UpdatedCnt = ISNULL(@UpdatedCnt, 0);

        UPDATE tgt
        SET tgt.IsNew = 0, tgt.LoadDate = GETDATE()
        FROM dbo.MMIT_IDSAs AS tgt
        WHERE NOT EXISTS
        (
            SELECT 1
            FROM dbo.MMIT_IDSAs_Holding AS src
            WHERE src.DrugID = tgt.DrugID AND src.PlanID = tgt.PlanID
        )
          AND (ISNULL(tgt.IsNew, 1) <> 0)
;

        SET @DeletedCnt = @@ROWCOUNT;
        SELECT 'MMIT_IDSAs' AS EntityName, @InsertedCnt AS InsertedCnt, @UpdatedCnt AS UpdatedCnt, @DeletedCnt AS DeletedCnt;
    END TRY
    BEGIN CATCH
        RAISERROR(ERROR_MESSAGE(), 16, 1);
    END CATCH
END;
GO
IF OBJECT_ID('dbo.sp_MMIT_Load_PanDetails', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_MMIT_Load_PanDetails;
GO

CREATE PROCEDURE dbo.sp_MMIT_Load_PanDetails
AS
BEGIN
    DECLARE @InsertedCnt INT = 0;
    DECLARE @UpdatedCnt  INT = 0;
    DECLARE @DeletedCnt  INT = 0;
    DECLARE @HoldingCnt  INT = 0;
    DECLARE @MergeActions TABLE (ActionName NVARCHAR(10) NOT NULL);

    SET NOCOUNT ON;

    BEGIN TRY
        IF OBJECT_ID('dbo.MMIT_PanDetails_Holding', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.MMIT_PanDetails_Holding
            (
                PanID INT NOT NULL,
            CriterionType VARCHAR(100) NULL,
            CriterionText VARCHAR(1000) NULL,
            RequiredDocumentation VARCHAR(500) NULL,
            CriterionOrder INT NOT NULL,
            LoadDate DATETIME NULL
            );
        END
        SELECT @HoldingCnt = COUNT(1)
        FROM dbo.MMIT_PanDetails_Holding;

        IF @HoldingCnt = 0
        BEGIN
            SELECT 'MMIT_PanDetails' AS EntityName, 0 AS InsertedCnt, 0 AS UpdatedCnt, 0 AS DeletedCnt;
            RETURN;
        END

        MERGE dbo.MMIT_PanDetails AS tgt
        USING dbo.MMIT_PanDetails_Holding AS src
            ON tgt.PanID = src.PanID AND tgt.CriterionOrder = src.CriterionOrder
        WHEN MATCHED AND
            (
                ISNULL(tgt.CriterionType, '') <> ISNULL(src.CriterionType, '') OR
                ISNULL(tgt.CriterionText, '') <> ISNULL(src.CriterionText, '') OR
                ISNULL(tgt.RequiredDocumentation, '') <> ISNULL(src.RequiredDocumentation, '')
            ) THEN
            UPDATE SET
                tgt.CriterionType = src.CriterionType,
                tgt.CriterionText = src.CriterionText,
                tgt.RequiredDocumentation = src.RequiredDocumentation,
                tgt.LoadDate = ISNULL(src.LoadDate, GETDATE()),
                tgt.IsNew = 1
        WHEN NOT MATCHED BY TARGET THEN
            INSERT (PanID, CriterionType, CriterionText, RequiredDocumentation, CriterionOrder, LoadDate, IsNew)
            VALUES (src.PanID, src.CriterionType, src.CriterionText, src.RequiredDocumentation, src.CriterionOrder, ISNULL(src.LoadDate, GETDATE()), 1)
        OUTPUT $action INTO @MergeActions (ActionName);

        SELECT
            @InsertedCnt = SUM(CASE WHEN ActionName = 'INSERT' THEN 1 ELSE 0 END),
            @UpdatedCnt = SUM(CASE WHEN ActionName = 'UPDATE' THEN 1 ELSE 0 END)
        FROM @MergeActions;

        SET @InsertedCnt = ISNULL(@InsertedCnt, 0);
        SET @UpdatedCnt = ISNULL(@UpdatedCnt, 0);

        UPDATE tgt
        SET tgt.IsNew = 0, tgt.LoadDate = GETDATE()
        FROM dbo.MMIT_PanDetails AS tgt
        WHERE NOT EXISTS
        (
            SELECT 1
            FROM dbo.MMIT_PanDetails_Holding AS src
            WHERE src.PanID = tgt.PanID AND src.CriterionOrder = tgt.CriterionOrder
        )
          AND (ISNULL(tgt.IsNew, 1) <> 0)
;

        SET @DeletedCnt = @@ROWCOUNT;
        SELECT 'MMIT_PanDetails' AS EntityName, @InsertedCnt AS InsertedCnt, @UpdatedCnt AS UpdatedCnt, @DeletedCnt AS DeletedCnt;
    END TRY
    BEGIN CATCH
        RAISERROR(ERROR_MESSAGE(), 16, 1);
    END CATCH
END;
GO
IF OBJECT_ID('dbo.sp_MMIT_Load_States', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_MMIT_Load_States;
GO

CREATE PROCEDURE dbo.sp_MMIT_Load_States
AS
BEGIN
    DECLARE @InsertedCnt INT = 0;
    DECLARE @UpdatedCnt  INT = 0;
    DECLARE @DeletedCnt  INT = 0;
    DECLARE @HoldingCnt  INT = 0;
    DECLARE @MergeActions TABLE (ActionName NVARCHAR(10) NOT NULL);

    SET NOCOUNT ON;

    BEGIN TRY
        IF OBJECT_ID('dbo.MMIT_States_Holding', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.MMIT_States_Holding
            (
                StateCode CHAR(2) NOT NULL,
            StateName VARCHAR(50) NOT NULL,
            Region VARCHAR(50) NULL,
            Division VARCHAR(50) NULL,
            IsActive BIT NOT NULL,
            LoadDate DATETIME NULL
            );
        END
        SELECT @HoldingCnt = COUNT(1)
        FROM dbo.MMIT_States_Holding;

        IF @HoldingCnt = 0
        BEGIN
            SELECT 'MMIT_States' AS EntityName, 0 AS InsertedCnt, 0 AS UpdatedCnt, 0 AS DeletedCnt;
            RETURN;
        END

        MERGE dbo.MMIT_States AS tgt
        USING dbo.MMIT_States_Holding AS src
            ON tgt.StateCode = src.StateCode
        WHEN MATCHED AND
            (
                ISNULL(tgt.StateName, '') <> ISNULL(src.StateName, '') OR
                ISNULL(tgt.Region, '') <> ISNULL(src.Region, '') OR
                ISNULL(tgt.Division, '') <> ISNULL(src.Division, '') OR
                ISNULL(tgt.IsActive, 0) <> ISNULL(src.IsActive, 0)
            ) THEN
            UPDATE SET
                tgt.StateName = src.StateName,
                tgt.Region = src.Region,
                tgt.Division = src.Division,
                tgt.IsActive = src.IsActive,
                tgt.LoadDate = ISNULL(src.LoadDate, GETDATE())
        WHEN NOT MATCHED BY TARGET THEN
            INSERT (StateCode, StateName, Region, Division, IsActive, LoadDate)
            VALUES (src.StateCode, src.StateName, src.Region, src.Division, src.IsActive, ISNULL(src.LoadDate, GETDATE()))
        OUTPUT $action INTO @MergeActions (ActionName);

        SELECT
            @InsertedCnt = SUM(CASE WHEN ActionName = 'INSERT' THEN 1 ELSE 0 END),
            @UpdatedCnt = SUM(CASE WHEN ActionName = 'UPDATE' THEN 1 ELSE 0 END)
        FROM @MergeActions;

        SET @InsertedCnt = ISNULL(@InsertedCnt, 0);
        SET @UpdatedCnt = ISNULL(@UpdatedCnt, 0);

        UPDATE tgt
        SET tgt.IsActive = 0, tgt.LoadDate = GETDATE()
        FROM dbo.MMIT_States AS tgt
        WHERE NOT EXISTS
        (
            SELECT 1
            FROM dbo.MMIT_States_Holding AS src
            WHERE src.StateCode = tgt.StateCode
        )
          AND (ISNULL(tgt.IsActive, 1) <> 0)
;

        SET @DeletedCnt = @@ROWCOUNT;
        SELECT 'MMIT_States' AS EntityName, @InsertedCnt AS InsertedCnt, @UpdatedCnt AS UpdatedCnt, @DeletedCnt AS DeletedCnt;
    END TRY
    BEGIN CATCH
        RAISERROR(ERROR_MESSAGE(), 16, 1);
    END CATCH
END;
GO
IF OBJECT_ID('dbo.sp_MMIT_Load_ZipCodes', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_MMIT_Load_ZipCodes;
GO

CREATE PROCEDURE dbo.sp_MMIT_Load_ZipCodes
AS
BEGIN
    DECLARE @InsertedCnt INT = 0;
    DECLARE @UpdatedCnt  INT = 0;
    DECLARE @DeletedCnt  INT = 0;
    DECLARE @HoldingCnt  INT = 0;
    DECLARE @MergeActions TABLE (ActionName NVARCHAR(10) NOT NULL);

    SET NOCOUNT ON;

    BEGIN TRY
        IF OBJECT_ID('dbo.MMIT_ZipCodes_Holding', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.MMIT_ZipCodes_Holding
            (
                ZipCode VARCHAR(5) NOT NULL,
            City VARCHAR(100) NULL,
            StateCode CHAR(2) NOT NULL,
            County VARCHAR(100) NULL,
            ZipType VARCHAR(20) NULL,
            LoadDate DATETIME NULL
            );
        END
        SELECT @HoldingCnt = COUNT(1)
        FROM dbo.MMIT_ZipCodes_Holding;

        IF @HoldingCnt = 0
        BEGIN
            SELECT 'MMIT_ZipCodes' AS EntityName, 0 AS InsertedCnt, 0 AS UpdatedCnt, 0 AS DeletedCnt;
            RETURN;
        END

        MERGE dbo.MMIT_ZipCodes AS tgt
        USING dbo.MMIT_ZipCodes_Holding AS src
            ON tgt.ZipCode = src.ZipCode
        WHEN MATCHED AND
            (
                ISNULL(tgt.City, '') <> ISNULL(src.City, '') OR
                ISNULL(tgt.StateCode, '') <> ISNULL(src.StateCode, '') OR
                ISNULL(tgt.County, '') <> ISNULL(src.County, '') OR
                ISNULL(tgt.ZipType, '') <> ISNULL(src.ZipType, '')
            ) THEN
            UPDATE SET
                tgt.City = src.City,
                tgt.StateCode = src.StateCode,
                tgt.County = src.County,
                tgt.ZipType = src.ZipType,
                tgt.LoadDate = ISNULL(src.LoadDate, GETDATE())
        WHEN NOT MATCHED BY TARGET THEN
            INSERT (ZipCode, City, StateCode, County, ZipType, LoadDate)
            VALUES (src.ZipCode, src.City, src.StateCode, src.County, src.ZipType, ISNULL(src.LoadDate, GETDATE()))
        OUTPUT $action INTO @MergeActions (ActionName);

        SELECT
            @InsertedCnt = SUM(CASE WHEN ActionName = 'INSERT' THEN 1 ELSE 0 END),
            @UpdatedCnt = SUM(CASE WHEN ActionName = 'UPDATE' THEN 1 ELSE 0 END)
        FROM @MergeActions;

        SET @InsertedCnt = ISNULL(@InsertedCnt, 0);
        SET @UpdatedCnt = ISNULL(@UpdatedCnt, 0);

        DELETE tgt
        FROM dbo.MMIT_ZipCodes AS tgt
        WHERE NOT EXISTS
        (
            SELECT 1
            FROM dbo.MMIT_ZipCodes_Holding AS src
            WHERE src.ZipCode = tgt.ZipCode
        );

        SET @DeletedCnt = @@ROWCOUNT;
        SELECT 'MMIT_ZipCodes' AS EntityName, @InsertedCnt AS InsertedCnt, @UpdatedCnt AS UpdatedCnt, @DeletedCnt AS DeletedCnt;
    END TRY
    BEGIN CATCH
        RAISERROR(ERROR_MESSAGE(), 16, 1);
    END CATCH
END;
GO
IF OBJECT_ID('dbo.sp_MMIT_Load_PansControllerNCD', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_MMIT_Load_PansControllerNCD;
GO

CREATE PROCEDURE dbo.sp_MMIT_Load_PansControllerNCD
AS
BEGIN
    DECLARE @InsertedCnt INT = 0;
    DECLARE @UpdatedCnt  INT = 0;
    DECLARE @DeletedCnt  INT = 0;
    DECLARE @HoldingCnt  INT = 0;
    DECLARE @MergeActions TABLE (ActionName NVARCHAR(10) NOT NULL);

    SET NOCOUNT ON;

    BEGIN TRY
        IF OBJECT_ID('dbo.MMIT_PansControllerNCD_Holding', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.MMIT_PansControllerNCD_Holding
            (
                PlanID VARCHAR(50) NOT NULL,
            DrugID INT NOT NULL,
            NCDReason VARCHAR(200) NULL,
            AlternativeDrug VARCHAR(200) NULL,
            EffectiveDate DATE NOT NULL,
            TermDate DATE NULL,
            LoadDate DATETIME NULL
            );
        END
        SELECT @HoldingCnt = COUNT(1)
        FROM dbo.MMIT_PansControllerNCD_Holding;

        IF @HoldingCnt = 0
        BEGIN
            SELECT 'MMIT_PansControllerNCD' AS EntityName, 0 AS InsertedCnt, 0 AS UpdatedCnt, 0 AS DeletedCnt;
            RETURN;
        END

        MERGE dbo.MMIT_PansControllerNCD AS tgt
        USING dbo.MMIT_PansControllerNCD_Holding AS src
            ON tgt.PlanID = src.PlanID AND tgt.DrugID = src.DrugID AND tgt.EffectiveDate = src.EffectiveDate
        WHEN MATCHED AND
            (
                ISNULL(tgt.NCDReason, '') <> ISNULL(src.NCDReason, '') OR
                ISNULL(tgt.AlternativeDrug, '') <> ISNULL(src.AlternativeDrug, '') OR
                ISNULL(CONVERT(VARCHAR(10), tgt.TermDate, 120), '') <> ISNULL(CONVERT(VARCHAR(10), src.TermDate, 120), '')
            ) THEN
            UPDATE SET
                tgt.NCDReason = src.NCDReason,
                tgt.AlternativeDrug = src.AlternativeDrug,
                tgt.TermDate = src.TermDate,
                tgt.LoadDate = ISNULL(src.LoadDate, GETDATE()),
                tgt.IsNew = 1
        WHEN NOT MATCHED BY TARGET THEN
            INSERT (PlanID, DrugID, NCDReason, AlternativeDrug, EffectiveDate, TermDate, LoadDate, IsNew)
            VALUES (src.PlanID, src.DrugID, src.NCDReason, src.AlternativeDrug, src.EffectiveDate, src.TermDate, ISNULL(src.LoadDate, GETDATE()), 1)
        OUTPUT $action INTO @MergeActions (ActionName);

        SELECT
            @InsertedCnt = SUM(CASE WHEN ActionName = 'INSERT' THEN 1 ELSE 0 END),
            @UpdatedCnt = SUM(CASE WHEN ActionName = 'UPDATE' THEN 1 ELSE 0 END)
        FROM @MergeActions;

        SET @InsertedCnt = ISNULL(@InsertedCnt, 0);
        SET @UpdatedCnt = ISNULL(@UpdatedCnt, 0);

        UPDATE tgt
        SET tgt.IsNew = 0, tgt.LoadDate = GETDATE()
        FROM dbo.MMIT_PansControllerNCD AS tgt
        WHERE NOT EXISTS
        (
            SELECT 1
            FROM dbo.MMIT_PansControllerNCD_Holding AS src
            WHERE src.PlanID = tgt.PlanID AND src.DrugID = tgt.DrugID AND src.EffectiveDate = tgt.EffectiveDate
        )
          AND (ISNULL(tgt.IsNew, 1) <> 0)
;

        SET @DeletedCnt = @@ROWCOUNT;
        SELECT 'MMIT_PansControllerNCD' AS EntityName, @InsertedCnt AS InsertedCnt, @UpdatedCnt AS UpdatedCnt, @DeletedCnt AS DeletedCnt;
    END TRY
    BEGIN CATCH
        RAISERROR(ERROR_MESSAGE(), 16, 1);
    END CATCH
END;
GO

-- ============================================================================
-- SECTION 4 - MASTER JOB FLOW DOCUMENTATION
-- ============================================================================
-- PREJOB
--   tPrejob_1 -> tDBConnection_1 -> tDBRow_1 -> tDBRow_2
--   tDBRow_1  : EXEC dbo.sp_MMIT_Prep;
--   tDBRow_2  : Optional post-prep checkpoint / audit SQL before Wave 1 starts.
--   tDBRow_16 : OnSubjobError handler for PREJOB; recommended call:
--               EXEC dbo.sp_MMIT_Recover @JobName = 'MMIT_MHA_Data_Ingestion_Final',
--                    @ErrorStep = 'PREJOB', @ErrorMessage = 'sp_MMIT_Prep or prejob SQL failed';
--
-- WAVE 1 - PARALLEL (tParallelize_1)
--   Drugs_Data_Ingestion_Job           -> EXEC dbo.sp_MMIT_Load_Drugs
--       OnSubjobError -> tDBRow_5      -> EXEC dbo.sp_MMIT_Recover @ErrorStep = 'Drugs_Data_Ingestion_Job'
--   PansController_Data_Ingestion_Job  -> EXEC dbo.sp_MMIT_Load_PansController
--       OnSubjobError -> tDBRow_6      -> EXEC dbo.sp_MMIT_Recover @ErrorStep = 'PansController_Data_Ingestion_Job'
--   Synchronize                        -> Wait for both Wave 1 branches to finish
--
-- SEQUENTIAL AFTER WAVE 1
--   Medopen_Bridge_Data_Ingestion_Job  -> EXEC dbo.sp_MMIT_Load_MedopenBridge
--       OnSubjobError -> tDBRow_4      -> EXEC dbo.sp_MMIT_Recover @ErrorStep = 'Medopen_Bridge_Data_Ingestion_Job'
--
-- WAVE 2 - PARALLEL (tParallelize_2)
--   NDC_Bridge_Data_Ingestion_Job          -> EXEC dbo.sp_MMIT_Load_NDCBridge
--       OnSubjobError -> tDBRow_7          -> EXEC dbo.sp_MMIT_Recover @ErrorStep = 'NDC_Bridge_Data_Ingestion_Job'
--   Restrictions_Data_Ingestion_Job        -> EXEC dbo.sp_MMIT_Load_Restrictions
--       OnSubjobError -> tDBRow_8          -> EXEC dbo.sp_MMIT_Recover @ErrorStep = 'Restrictions_Data_Ingestion_Job'
--   Statuses_Data_Ingestion_Job            -> EXEC dbo.sp_MMIT_Load_Statuses
--       OnSubjobError -> tDBRow_9          -> EXEC dbo.sp_MMIT_Recover @ErrorStep = 'Statuses_Data_Ingestion_Job'
--   IDSAs_Data_Ingestion_Job               -> EXEC dbo.sp_MMIT_Load_IDSAs
--       OnSubjobError -> tDBRow_10         -> EXEC dbo.sp_MMIT_Recover @ErrorStep = 'IDSAs_Data_Ingestion_Job'
--   PanDetails_Data_Ingestion_Job          -> EXEC dbo.sp_MMIT_Load_PanDetails
--       OnSubjobError -> tDBRow_11         -> EXEC dbo.sp_MMIT_Recover @ErrorStep = 'PanDetails_Data_Ingestion_Job'
--   States_Data_Ingestion_Job              -> EXEC dbo.sp_MMIT_Load_States
--       OnSubjobError -> tDBRow_12         -> EXEC dbo.sp_MMIT_Recover @ErrorStep = 'States_Data_Ingestion_Job'
--   Zip_Code_Data_Ingestion_Job            -> EXEC dbo.sp_MMIT_Load_ZipCodes
--       OnSubjobError -> tDBRow_13         -> EXEC dbo.sp_MMIT_Recover @ErrorStep = 'Zip_Code_Data_Ingestion_Job'
--   PansControllerNCD_Data_Ingestion_Job   -> EXEC dbo.sp_MMIT_Load_PansControllerNCD
--       OnSubjobError -> tDBRow_14         -> EXEC dbo.sp_MMIT_Recover @ErrorStep = 'PansControllerNCD_Data_Ingestion_Job'
--   Synchronize                            -> Wait for all Wave 2 branches to finish
--
-- POSTJOB
--   tDBRow_15 : EXEC dbo.sp_MMIT_Finalize;
--   tDBRow_3  : OnSubjobError handler for POSTJOB; recommended call:
--               EXEC dbo.sp_MMIT_Recover @JobName = 'MMIT_MHA_Data_Ingestion_Final',
--                    @ErrorStep = 'POSTJOB', @ErrorMessage = 'sp_MMIT_Finalize failed';
-- ============================================================================
GO

-- ============================================================================
-- SECTION 5 - VERIFICATION QUERIES
-- ============================================================================
SELECT 'MMIT_Drugs' AS TableName, COUNT(1) AS RowCnt FROM dbo.MMIT_Drugs
UNION ALL
SELECT 'MMIT_PansController' AS TableName, COUNT(1) AS RowCnt FROM dbo.MMIT_PansController
UNION ALL
SELECT 'MMIT_Medopen_Bridge' AS TableName, COUNT(1) AS RowCnt FROM dbo.MMIT_Medopen_Bridge
UNION ALL
SELECT 'MMIT_NDC_Bridge' AS TableName, COUNT(1) AS RowCnt FROM dbo.MMIT_NDC_Bridge
UNION ALL
SELECT 'MMIT_Restrictions' AS TableName, COUNT(1) AS RowCnt FROM dbo.MMIT_Restrictions
UNION ALL
SELECT 'MMIT_Statuses' AS TableName, COUNT(1) AS RowCnt FROM dbo.MMIT_Statuses
UNION ALL
SELECT 'MMIT_IDSAs' AS TableName, COUNT(1) AS RowCnt FROM dbo.MMIT_IDSAs
UNION ALL
SELECT 'MMIT_PanDetails' AS TableName, COUNT(1) AS RowCnt FROM dbo.MMIT_PanDetails
UNION ALL
SELECT 'MMIT_States' AS TableName, COUNT(1) AS RowCnt FROM dbo.MMIT_States
UNION ALL
SELECT 'MMIT_ZipCodes' AS TableName, COUNT(1) AS RowCnt FROM dbo.MMIT_ZipCodes
UNION ALL
SELECT 'MMIT_PansControllerNCD' AS TableName, COUNT(1) AS RowCnt FROM dbo.MMIT_PansControllerNCD
ORDER BY TableName;
GO
