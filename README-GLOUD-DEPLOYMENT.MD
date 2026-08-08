1) install libraries:

pip install -r requirements.txt


2) running app in the local

python main.py

3) run in the google cloud:

gcloud run deploy middleschool-maths-snowflake-api --source . --allow-unauthenticated

* `middleschool-maths-snowflake-api`: The name of your service.
* `--source .`: Tells it to build the container from the current directory.
* `--allow-unauthenticated`: Makes the API public so you can access it via the URL.

After the command finishes, Google Cloud will give you a URL: 
Service [middleschool-maths-snowflake-api] revision [middleschool-maths-snowflake-api-00001-2cb] has been deployed and is serving 100 percent of traffic.
Service URL: https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app

Opening that link will show `{"message": "Hello World"}`.

3.1) deployment response A:

Please enter numeric choice or text value (must exactly match list item):  34

To make this the default region, run `gcloud config set run/region us-central1`.

Deploying from source requires an Artifact Registry Docker repository to store built containers. A repository named [cloud-run-source-deploy] in region 
[us-central1] will be created.

Do you want to continue (Y/n)?  

3.2) deployement response B:

Do you want to continue (Y/n)?  Y

Building using Dockerfile and deploying container to Cloud Run service [hello-world-api] in project [movie-418203] region [us-central1]
✓ Building and deploying new service... Done.                                                                                                                    
  ✓ Creating Container Repository...                                                                                                                             
  ✓ Validating Service...                                                                                                                                        
  ✓ Uploading sources...                                                                                                                                         
  ✓ Building Container... Logs are available at [https://console.cloud.google.com/cloud-build/builds;region=us-central1/ae0f02a2-9308-41e3-8b0d-28edabf7e10d?proj
  ect=981729324811].                                                                                                                                             
  ✓ Creating Revision...                                                                                                                                         
  ✓ Routing traffic...                                                                                                                                           
  ✓ Setting IAM Policy...                                                                                                                                        
Done. 


3.3) check deployment logs:

gcloud logging read \
'resource.type="cloud_run_revision"
 resource.labels.service_name="middleschool-maths-snowflake-api"
 resource.labels.location="us-central1"
 severity>=ERROR' \
--project movie-418203 \
--limit 50

curl -i -G "http://localhost:8282/api/bible-task-paragraphs" \
  --data-urlencode "taskId=2026-01-09-活水团契-青年团契" \
  --data-urlencode "limit=1" \
  --data-urlencode "offset=0"




curl -X PUT "https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/math-questions/b15c9390c9f34c66b815a2bce7cc98a5/image-url-initial" \
  -H "Content-Type: application/json" \
  -d '{"image_url_initial":"https://example.com/out.svg"}'


curl -sS -X POST "https://middleschool-maths-snowflake-api-981729324811.us-central1.run.app/api/standards/items/subjectives/upsert" \
  -H "Content-Type: application/json" \
  --data '{
    "setId":"NE_MATH_9_12_2022",
    "itemId":"HS.A1.1",
    "subjectives":[
      {
        "subjectiveId":"OBJ-1",
        "title":"Identify linear functions",
        "difficulty":"medium",
        "description":"Recognize linear relationships from tables and graphs.",
        "prerequisites":["Slope","Intercept"],
        "question_types":["multiple_choice","short_answer"],
        "success_criteria":["Correctly classify 4/5 examples"],
        "tags":["linear","functions"]
      }
    ]
  }' | python -m json.tool


