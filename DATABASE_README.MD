-- ============================================================
-- Snowflake DDL for MVP Tables:
--   GROUPS, MEMBERS, BIBLE_TASKS, AI_STUDY_GUIDES, MEETINGS, MEETING_NOTES
-- Notes:
-- 1) Snowflake has no enforced PK/FK constraints; we declare them for clarity.
-- 2) Use TIMESTAMP_NTZ for app-managed timestamps (recommended for many apps).
-- 3) Store JSON outputs in VARIANT.
-- ============================================================

-- (Optional) Create schema
-- CREATE DATABASE IF NOT EXISTS FAMILY_FELLOWSHIP;
-- CREATE SCHEMA IF NOT EXISTS FAMILY_FELLOWSHIP.MVP;
-- USE SCHEMA FAMILY_FELLOWSHIP.MVP;

-- ============================================================
-- 1) GROUPS
-- ============================================================
CREATE OR REPLACE TABLE GROUPS (
  CHURCH_NAME.    STRING
  GROUP_ID        STRING         NOT NULL,
  NAME            STRING         NOT NULL,
  TIMEZONE        STRING         DEFAULT 'America/Chicago',
  BIBLE_VERSION   STRING         DEFAULT 'cmn-cu89s',
  CREATED_AT      TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP(),

  CONSTRAINT PK_GROUPS PRIMARY KEY (GROUP_ID)
);

-- ============================================================
-- 2) MEMBERS
-- ============================================================
CREATE OR REPLACE TABLE MEMBERS (
  MEMBER_ID       STRING         NOT NULL,
  GROUP_ID        STRING         NOT NULL,
  NAME            STRING         NOT NULL,
  ROLE            STRING         DEFAULT 'MEMBER', -- LEADER / MEMBER
  CREATED_AT      TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP(),

  CONSTRAINT PK_MEMBERS PRIMARY KEY (MEMBER_ID),
  CONSTRAINT FK_MEMBERS_GROUPS FOREIGN KEY (GROUP_ID) REFERENCES GROUPS(GROUP_ID)
);

-- ============================================================
-- 3) BIBLE_TASKS
--    You can map this to your existing "assignment" concept if you like.
-- ============================================================
CREATE OR REPLACE TABLE BIBLE_TASKS (
  TASK_ID         STRING         NOT NULL,  -- could be assignment_id
  GROUP_ID        STRING         NOT NULL,
  MEMBER_ID       STRING         NOT NULL,  -- or STUDENT_ID if you keep that naming
  BOOK_NAME       STRING         NOT NULL,  -- e.g., 约翰福音
  BOOK_CODE       STRING,                  -- e.g., JHN (optional)
  FROM_CHAPTER    NUMBER(10,0)   NOT NULL,
  TO_CHAPTER      NUMBER(10,0)   NOT NULL,
  TITLE           STRING         NOT NULL,
  DESCRIPTION     STRING,
  PASSAGE_TEXT    STRING,                 -- concatenated text (or keep per-verse elsewhere)
  PASSAGE_TEXT_DETAIL    STRING,          -- concatenated text (or keep per-verse elsewhere)
  CREATED_AT      TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP(),

  CONSTRAINT PK_BIBLE_TASKS PRIMARY KEY (TASK_ID),
  CONSTRAINT FK_BIBLE_TASKS_GROUPS FOREIGN KEY (GROUP_ID) REFERENCES GROUPS(GROUP_ID),
  CONSTRAINT FK_BIBLE_TASKS_MEMBERS FOREIGN KEY (MEMBER_ID) REFERENCES MEMBERS(MEMBER_ID)
);

-- ============================================================
-- 4) AI_STUDY_GUIDES
-- ============================================================
CREATE OR REPLACE TABLE AI_STUDY_GUIDES (
  GUIDE_ID        STRING         NOT NULL,
  TASK_ID         STRING         NOT NULL,
  MODEL           STRING,                 -- e.g., gpt-4.1 / gpt-5 etc.
  CONTENT_JSON    VARIANT        NOT NULL, -- structured guide JSON
  STATUS          STRING         DEFAULT 'DRAFT', -- DRAFT / APPROVED
  CREATED_AT      TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP(),

  CONSTRAINT PK_AI_STUDY_GUIDES PRIMARY KEY (GUIDE_ID),
  CONSTRAINT FK_AI_STUDY_GUIDES_TASKS FOREIGN KEY (TASK_ID) REFERENCES BIBLE_TASKS(TASK_ID)
);

-- Helpful query acceleration (optional)
-- CREATE OR REPLACE SEARCH OPTIMIZATION ON AI_STUDY_GUIDES(STATUS);

-- ============================================================
-- 5) MEETINGS
-- ============================================================
CREATE OR REPLACE TABLE MEETINGS (
  MEETING_ID      STRING         NOT NULL,
  TASK_ID         STRING         NOT NULL,
  MEETING_DATE    TIMESTAMP_NTZ  NOT NULL,
  DURATION_MIN    NUMBER(10,0)   DEFAULT 60,
  CREATED_AT      TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP(),

  CONSTRAINT PK_MEETINGS PRIMARY KEY (MEETING_ID),
  CONSTRAINT FK_MEETINGS_TASKS FOREIGN KEY (TASK_ID) REFERENCES BIBLE_TASKS(TASK_ID)
);

-- ============================================================
-- 6) MEETING_NOTES
-- ============================================================
CREATE OR REPLACE TABLE MEETING_NOTES (
  NOTES_ID        STRING         NOT NULL,
  MEETING_ID      STRING         NOT NULL,
  RAW_TEXT        STRING,
  CLEANED_TEXT    STRING,
  SUMMARY_JSON    VARIANT,               -- AI summarized notes / action items JSON
  CREATED_AT      TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP(),

  CONSTRAINT PK_MEETING_NOTES PRIMARY KEY (NOTES_ID),
  CONSTRAINT FK_MEETING_NOTES_MEETINGS FOREIGN KEY (MEETING_ID) REFERENCES MEETINGS(MEETING_ID)
);

-- ============================================================
-- Optional indexes / clustering (Snowflake uses micro-partitions)
-- If you expect large tables, consider clustering keys:
-- ============================================================
-- ALTER TABLE BIBLE_TASKS CLUSTER BY (GROUP_ID, BOOK_NAME, CREATED_AT);
-- ALTER TABLE MEETINGS CLUSTER BY (TASK_ID, MEETING_DATE);
-- ALTER TABLE MEETING_NOTES CLUSTER BY (MEETING_ID, CREATED_AT);

