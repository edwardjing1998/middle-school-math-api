-- Use your DB/Schema (optional if you always fully qualify)
USE DATABASE EDU_AI_APP;
USE SCHEMA WEBAPP;

-- 1) Create table
CREATE TABLE IF NOT EXISTS STD_ITEM_SUBJECTIVES (
  SET_ID            VARCHAR(16777216) NOT NULL,
  ITEM_ID           VARCHAR(16777216) NOT NULL,

  SUBJECTIVE_ID     VARCHAR(16777216) NOT NULL,   -- e.g. "OBJ-1" or UUID
  TITLE             VARCHAR(16777216),
  DIFFICULTY        VARCHAR(16777216),            -- you wrote "difficult"; better: DIFFICULTY
  DESCRIPTION       VARCHAR(16777216),

  PREREQUISITES     VARIANT,                      -- store array as JSON
  QUESTION_TYPES    VARIANT,                      -- store array as JSON
  SUCCESS_CRITERIA  VARIANT,                      -- store array as JSON
  TAGS              VARIANT,                      -- store array as JSON

  CREATED_AT        TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP(),
  UPDATED_AT        TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP(),

  CONSTRAINT PK_STD_ITEM_SUBJECTIVES
    PRIMARY KEY (SET_ID, ITEM_ID, SUBJECTIVE_ID),

  CONSTRAINT FK_SUBJECTIVES_TO_ITEM
    FOREIGN KEY (SET_ID, ITEM_ID)
    REFERENCES STD_ITEM (SET_ID, ITEM_ID)
);

-- 2) Optional: helpful clustering for query performance
-- (adjust if your queries filter by SET_ID/ITEM_ID frequently)
ALTER TABLE STD_ITEM_SUBJECTIVES CLUSTER BY (SET_ID, ITEM_ID);

-- 3) Optional: indexes don't exist in Snowflake; use clustering + pruning