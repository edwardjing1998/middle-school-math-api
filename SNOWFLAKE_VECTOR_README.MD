# Recommended vector table

CREATE TABLE IF NOT EXISTS EDU_AI_APP.WEBAPP.RAG_STD_ITEM_VECTOR (
    DOC_ID          VARCHAR NOT NULL,
    SET_ID          VARCHAR NOT NULL,
    ITEM_ID         VARCHAR NOT NULL,
    COURSE_LEVEL    VARCHAR,
    STANDARD_TEXT   VARCHAR,
    DOCUMENT_TEXT   VARCHAR,
    SOURCE_TABLE    VARCHAR,
    EMBEDDING       VECTOR(FLOAT, 768),
    CREATED_AT      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    UPDATED_AT      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),

    CONSTRAINT PK_RAG_STD_ITEM_VECTOR
        PRIMARY KEY (DOC_ID)
);

# Generate the indexed document: Do not embed only STANDARD_TEXT. Include useful metadata:

Set ID: NE_MATH_9_12_2022
Item ID: HS.G.CO.1
Course Level: Geometry
Standard Text: Prove theorems about lines, angles, triangles, and circles.

This makes course-level and standard-text searches work better.

MERGE INTO EDU_AI_APP.WEBAPP.RAG_STD_ITEM_VECTOR AS target
USING (
    SELECT
        CONCAT(SET_ID, ':', ITEM_ID) AS DOC_ID,
        SET_ID,
        ITEM_ID,
        COURSE_LEVEL,
        STANDARD_TEXT,

        CONCAT(
            'Set ID: ', COALESCE(SET_ID, ''), '\n',
            'Item ID: ', COALESCE(ITEM_ID, ''), '\n',
            'Course Level: ', COALESCE(COURSE_LEVEL, ''), '\n',
            'Standard Text: ', COALESCE(STANDARD_TEXT, '')
        ) AS DOCUMENT_TEXT

    FROM EDU_AI_APP.WEBAPP.STD_ITEM
    WHERE STANDARD_TEXT IS NOT NULL
      AND TRIM(STANDARD_TEXT) <> ''
) AS source
ON target.DOC_ID = source.DOC_ID

WHEN MATCHED THEN UPDATE SET
    target.SET_ID = source.SET_ID,
    target.ITEM_ID = source.ITEM_ID,
    target.COURSE_LEVEL = source.COURSE_LEVEL,
    target.STANDARD_TEXT = source.STANDARD_TEXT,
    target.DOCUMENT_TEXT = source.DOCUMENT_TEXT,
    target.SOURCE_TABLE = 'EDU_AI_APP.WEBAPP.STD_ITEM',
    target.EMBEDDING = SNOWFLAKE.CORTEX.EMBED_TEXT_768(
        'snowflake-arctic-embed-m',
        source.DOCUMENT_TEXT
    ),
    target.UPDATED_AT = CURRENT_TIMESTAMP()

WHEN NOT MATCHED THEN INSERT (
    DOC_ID,
    SET_ID,
    ITEM_ID,
    COURSE_LEVEL,
    STANDARD_TEXT,
    DOCUMENT_TEXT,
    SOURCE_TABLE,
    EMBEDDING,
    CREATED_AT,
    UPDATED_AT
)
VALUES (
    source.DOC_ID,
    source.SET_ID,
    source.ITEM_ID,
    source.COURSE_LEVEL,
    source.STANDARD_TEXT,
    source.DOCUMENT_TEXT,
    'EDU_AI_APP.WEBAPP.STD_ITEM',
    SNOWFLAKE.CORTEX.EMBED_TEXT_768(
        'snowflake-arctic-embed-m',
        source.DOCUMENT_TEXT
    ),
    CURRENT_TIMESTAMP(),
    CURRENT_TIMESTAMP()
);

# Verify the index

SELECT COUNT(*) AS SOURCE_COUNT
FROM EDU_AI_APP.WEBAPP.STD_ITEM
WHERE STANDARD_TEXT IS NOT NULL
  AND TRIM(STANDARD_TEXT) <> '';

# Inspect indexed content:

SELECT
    DOC_ID,
    SET_ID,
    ITEM_ID,
    COURSE_LEVEL,
    STANDARD_TEXT,
    DOCUMENT_TEXT,
    SOURCE_TABLE
FROM EDU_AI_APP.WEBAPP.RAG_STD_ITEM_VECTOR
ORDER BY SET_ID, ITEM_ID
LIMIT 20;

# Check missing records:

SELECT
    source.SET_ID,
    source.ITEM_ID
FROM EDU_AI_APP.WEBAPP.STD_ITEM AS source
LEFT JOIN EDU_AI_APP.WEBAPP.RAG_STD_ITEM_VECTOR AS vector
    ON vector.SET_ID = source.SET_ID
   AND vector.ITEM_ID = source.ITEM_ID
WHERE source.STANDARD_TEXT IS NOT NULL
  AND TRIM(source.STANDARD_TEXT) <> ''
  AND vector.DOC_ID IS NULL;

# Test vector search directly

WITH ranked_results AS (
    SELECT
        DOC_ID,
        SET_ID,
        ITEM_ID,
        COURSE_LEVEL,
        STANDARD_TEXT,
        VECTOR_COSINE_SIMILARITY(
            EMBEDDING,
            SNOWFLAKE.CORTEX.EMBED_TEXT_768(
                'snowflake-arctic-embed-m',
                'Which standards are related to arts?'
            )
        ) AS SCORE
    FROM EDU_AI_APP.WEBAPP.RAG_STD_ITEM_VECTOR
)
SELECT *
FROM ranked_results
ORDER BY SCORE DESC
LIMIT 10;

# Add a score threshold: Use the following query to remove weak matches:

WITH ranked_results AS (
    SELECT
        DOC_ID,
        SET_ID,
        ITEM_ID,
        COURSE_LEVEL,
        STANDARD_TEXT,
        VECTOR_COSINE_SIMILARITY(
            EMBEDDING,
            SNOWFLAKE.CORTEX.EMBED_TEXT_768(
                'snowflake-arctic-embed-m',
                'Which standards are related to arts?'
            )
        ) AS SCORE
    FROM EDU_AI_APP.WEBAPP.RAG_STD_ITEM_VECTOR
)
SELECT *
FROM ranked_results
WHERE SCORE >= 0.80
ORDER BY SCORE DESC
LIMIT 10;