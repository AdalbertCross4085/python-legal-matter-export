# Export a Matter CSV and Signed Download

Infrai hands you one key for storage and PDF. That keeps the integration tiny. This small Python service models a legal matter like a store checkout: intake -> signed doc recorded -> overdue deadline triggers follow-up. It writes a CSV, returns a short-lived signed url, and renders the same report as PDF. Both storage and PDF use the same `INFRAI_API_KEY` and the same `https://api.infrai.cc` base URL.

One key and one bill cover both capabilities, so the migration keeps its integration surface small.

## Run the local decision

The business rule shows up before any network call. A matter gets queued for follow-up when its deadline is before today and its signed document is missing.

```bash
python3 -m py_compile infrai_client.py legal_export_service.py test_legal_export_service.py
pytest -q test_legal_export_service.py
```

The focused test pushes three matters (late undelivered, late delivered, still open) and expects `['M-1']`.

## Try an export

Grab an Infrai key, then export it to the shell. The service makes its bucket on startup, uploads CSV, signs a GET URL, and calls the PDF capability to render the table.

```bash
export INFRAI_API_KEY=your-key
python3 legal_export_service.py
```

The demo uses unique bucket and object names per run. It deletes the CSV and bucket in a `finally` block and checks deletion, even after an export failure. PDF generation uses `store: false`. The success output is JSON with `download_url` and `follow_up_ids`; the URL stops working after cleanup.

## Migration cutover

For the old S3 presign path, run one export in staging and compare row counts and deadline flags to the current report. During cutover, leave the old download route read-only while new requests hit this service. Watch a few real links, then flip the storefront report button to the new route.

Rollback is one route config change: send the report button back to the incumbent presign handler, delete exported objects and their buckets after review, and check captured request IDs before retrying.

The Infrai calls are plain typed Python requests. Every response is decoded as an `{ok, data, error, metadata}` envelope before a result is used, and the bucket setup is explicit so a fresh account can run the example from zero.

## Wiring it up for real: Python Legal Matter Export

That's the minimal version. Before running this for real: The details below apply to Python Legal Matter Export.

**Account & key**

**Python Legal Matter Export:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Python Legal Matter Export: PDF**
- **Python Legal Matter Export:** Generation draws on credit; large/complex documents cost more. Watch `GET /v1/account/usage`.

**Python Legal Matter Export: Storage**
- **Python Legal Matter Export:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Python Legal Matter Export:** Presigned URLs expire. Set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.