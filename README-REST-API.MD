# 查询团契成员列表:

https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/groups/G001/members

https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/groups?limit=10&offset=0 

https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/groups/G001

https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/members/M001


# save the records into BIBLE_TASKS

curl -X POST "https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/bible-tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "groupId": "G001",
    "memberId": "M1001",
    "bookName": "约书亚记",
    "bookCode": "JOS",
    "fromChapter": 1,
    "toChapter": 1,
    "title": "刚强壮胆进入应许之地",
    "description": "约书亚接续摩西的领导呼召与神的应许。",
    "passageText": "约书亚记 1:1-9 经文内容……",
    "passageTextDetail": "解经：神三次强调刚强壮胆，显明使命与同在。"
  }'

curl "http://localhost:8282/api/churches/Omaha Chinese Christine Church/full?limitTasks=200&offsetTasks=0"

curl -X POST \
  'http://localhost:8282/api/bible-task-paragraphs' \
  -H 'Content-Type: application/json' \
  -d '{
    "taskId": "T00000001",
    "paragraphId": 3,
    "paragraphContent": "This is paragraph 3",
    "paragraphImageUrl": "https://example.com/p3.png"
  }'

curl -i -G "https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/bible-task-paragraphs" \
  --data-urlencode "taskId=2026-01-09-活水团契-青年团契" \
  --data-urlencode "paragraphId=1" \
  --data-urlencode "limit=1" \
  --data-urlencode "offset=0"


gcloud run deploy https://middleschool-maths-snowflake-api --source . --allow-unauthenticated 


curl -G "https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/bible-tasks/passage-text-detail" \
  --data-urlencode "taskId=2026-01-09-活水团契-青年团契" \
  -H "accept: application/json"

curl -G "https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/bible-task-paragraphs/by-task-id" \
  --data-urlencode "taskId=2026-01-09-活水团契-青年团契" \
  -H "accept: application/json"

curl -G "https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/bible-tasks/passage-text-detail/youth" \
  --data-urlencode "limit=10" \
  --data-urlencode "offset=0" \
  -H "accept: application/json"


curl -X POST "http://localhost:8282/api/standards/sets/upsert" \
  -H "Content-Type: application/json" \
  -d '{
    "set": {
      "setId": "NE_MATH_9_12_2022",
      "state": "Nebraska",
      "subject": "Mathematics",
      "gradeRange": "9-12",
      "title": "Nebraska Mathematics (2022-)",
      "versionYear": "2022-",
      "source": "CSP",
      "description": "Grades 9-12 standards"
    },
    "items": [
      { "itemId": "2.1", "standardText": "Make sense of problems and persevere in solving them. MP.1" },
      { "itemId": "2.2", "standardText": "Reason quantitatively and abstractly and consider the reasoning of others. MP.2" }
    ],
    "replaceItems": true
  }'


curl -X GET \
  "https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/standards/items?state=Nebraska&subject=Maths&grade=9-12" \
  -H "Accept: application/json"


curl -X POST https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/math-questions \
  -H "Content-Type: application/json" \
  -d '{
    "state": "Nebraska",
    "subject": "Geometry",
    "grade": "Grade 10",
    "notation": "Circle Tangent Theorem",
    "question": "Prove that angle EHF equals angle EAF.",
    "hint": "Use harmonic division property.",
    "answer": "By projective transformation, angles are equal.",
    "has_diagram": true,
    "diagram_steps": {
      "steps": [
        {"step": 1, "action": "Draw circle O"},
        {"step": 2, "action": "Draw tangent at A"}
      ]
    }
  }'


curl -X POST https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/math-questions \
  -H "Content-Type: application/json" \
  -d '{
    "state": "Nebraska",
    "subject": "Geometry",
    "grade": "Grade 10",
    "notation": "Circle Tangent Theorem",
    "question": "Prove that angle EHF equals angle EAF.",
    "hint": "Use harmonic division property.",
    "answer": "By projective transformation, angles are equal.",
    "has_diagram": true,
    "diagram_steps": {
      "steps": [
        {"step": 1, "action": "Draw circle O"},
        {"step": 2, "action": "Draw tangent at A"}
      ]
    }
  }'


curl -sS -X POST "https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/enrollments" \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": 1001,
    "school_id": "310264001234",
    "math_course_id": "a1b2c3d4_request_id",
    "enroll_status": "ACTIVE",
    "start_date": "2026-02-01",
    "term": "2026-Spring",
    "grade_at_enroll": "2",
    "teacher_note": "First enrollment test"
  }' | jq .


curl -sS "https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/standards/items/subjectives?limit=5" | jq .

curl -i "http://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/standards/sets/options?limit=200"


## context search index 
curl -X POST \
  "http://localhost:8282/api/rag/index-standards" \
  -H "Content-Type: application/json" \
  -d '{"limit":100}'

curl -G \
  "http://localhost:8282/api/rag/search" \
  --data-urlencode "q=geometry standards" \
  --data-urlencode "limit=5"

## ask openAi:

curl -X POST \
  "http://localhost:8282/api/rag/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question":"Which standards relate to geometry?",
    "topK":5
  }'


## 

curl -G \
  "http://localhost:8282/api/rag/std-item-search" \
  --data-urlencode "q=angles triangles circles and geometric proofs" \
  --data-urlencode "educationLevel=High School" \
  --data-urlencode "subjectArea=Geometry" \
  --data-urlencode "limit=5"

##

curl -X POST \
  "http://localhost:8282/api/rag/std-item-search/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which high-school standards involve triangles and angles?",
    "educationLevel": "High School",
    "subjectArea": "Geometry",
    "topK": 5
  }'

## 

curl -X POST \
  "http://localhost:8282/api/rag/std-item-search/context" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which elementary standards involve shapes?",
    "educationLevel": "Elementary School",
    "subjectArea": "Geometry",
    "topK": 5
  }'

##

curl -X POST \
  "http://localhost:8282/api/rag/std-item-search/context" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which elementary standards involve shapes?",
    "educationLevel": "Elementary School",
    "subjectArea": "Geometry",
    "topK": 5
  }'

## 

curl -G \
  "http://localhost:8282/api/rag/std-item-search" \
  --data-urlencode "q=education standard" \
  --data-urlencode "itemId=HS.G.1.d" \
  --data-urlencode "limit=1"

## 

curl -X POST \
  "http://localhost:8282/api/rag/std-item-search/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which standards involve circles?",
    "educationLevel": "High School",
    "subjectArea": "Geometry",
    "topK": 5,
    "minCosine": 0.40
  }'

## Supported filters

setId
itemId
levelCode
educationLevel
subjectCode
subjectArea
courseLevel