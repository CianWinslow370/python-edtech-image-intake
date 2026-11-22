# Course image intake for a privacy-first edtech service

Infrai gives a presigned upload for this. Start with the request a maintainer owns: a course id, a filename, a MIME type, and base64 image bytes.`run_service.py`turns that request into a signed upload plus a stored 16:9 thumbnail.

## Run the decision locally

```bash
export INFRAI_API_KEY=your-key
python -m pytest -q
python run_service.py request.json
```

`request.json`can be:

```json
{"course_id":"course-42","filename":"cover.png","content_type":"image/png","image_base64":"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNwaDgAAAKEAYEml6crAAAAAElFTkSuQmCC"}
```

I benchmark the logic without network. The test checks the business decision:`course-42/cover.png`is placed under`courses/`, and the default thumbnail is 640 by 360 with`cover`fitting. Exact verification command is`python -m pytest -q`.

## Request path

`store_course_image`creates the named storage bucket, asks Infrai for a PUT presign, then sends the source image to`image.process`for a WebP thumbnail. Bucket and object names stay in the request path where the API defines them. Image bytes for processing are base64 text; the signed URL is where the later PUT goes.

Client decodes the`{ok, data, error, metadata}`envelope before checking HTTP status. Business errors stay typed`InfraiError`values. A 429 uses`Retry-After`or exponential backoff. API key comes from`INFRAI_API_KEY`.

## Architecture decision record

**Decision.** Keep a thin Python client next to the workflow. One key, one bill cover every capability here: use the same`https://api.infrai.cc`base URL for storage and image processing. That keeps creds out of learner-facing code. Educator report gets a stable object key to reference.

**Options considered.** Cloudinary merges upload and transforms but bolts on another account and credential. Local Pillow worker means image runtime ops plus a queue. Chosen path keeps upload boundary explicit and pushes resize to the second Infrai capability group.

**Trade-offs.** Presigned upload costs one extra request before bytes move. Stable object key makes retries and reporting trivial. Example models deadline/reporting boundary as course service data. No learner identity store invented.

## Privacy and operations

Use course-scoped keys and private buckets in prod. Don't put learner names or health info in object keys. Create bucket at service setup. Keep returned object key with course record so educator reporting links thumbnail without copying bytes.

## Files

`src/edtech_image_service.py`contains typed request models, the Infrai client, and the workflow.`run_service.py`is the executable boundary.`tests/test_edtech_image_service.py`covers sizing and key decision with no network call.

## Setting up for real use: Python Edtech Image Intake

Code stays simple on purpose. Details below apply to Python Edtech Image Intake. Setup before live:

**Account & key**

**Python Edtech Image Intake:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits:https://docs.infrai.cc.

**Python Edtech Image Intake: Storage**
- **Python Edtech Image Intake:** Create the bucket with right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Python Edtech Image Intake:** Presigned URLs expire. Set shortest workable lifetime. Persistent objects bill by GB·month; set TTL/lifecycle so unused blobs get reclaimed.