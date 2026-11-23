from __future__ import annotations

import base64
import csv
import io
import json
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import uuid4

from infrai_client import InfraiClient, InfraiError, StoragePaths


@dataclass(frozen=True)
class MatterIntake:
    matter_id: str
    client_name: str
    signed_document: str
    deadline: date
    delivered: bool


@dataclass(frozen=True)
class ExportResult:
    download_url: str
    pdf_data: Any
    follow_up_ids: list[str]


def follow_up_ids(matters: list[MatterIntake], today: date) -> list[str]:
    return [m.matter_id for m in matters if m.deadline < today and not m.delivered]


def _csv_bytes(matters: list[MatterIntake], today: date) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["matter_id", "client_name", "signed_document", "deadline", "delivered", "follow_up"])
    pending = set(follow_up_ids(matters, today))
    for matter in matters:
        writer.writerow([matter.matter_id, matter.client_name, matter.signed_document,
                         matter.deadline.isoformat(), str(matter.delivered).lower(),
                         str(matter.matter_id in pending).lower()])
    return output.getvalue().encode("utf-8")


def export_matters(client: InfraiClient, paths: StoragePaths, matters: list[MatterIntake], today: date) -> ExportResult:
    # Call shape mirrors storage.object.presign: bucket and key stay in the path.
    client.request("POST", "/v1/storage/bucket/create", {"name": paths.bucket})
    try:
        data = _csv_bytes(matters, today)
        client.request("PUT", f"/v1/storage/object/put/{paths.bucket}/{paths.key}", {
            "data_base64": base64.b64encode(data).decode("ascii"),
            "content_type": "text/csv",
        })
        signed = client.request("POST", f"/v1/storage/object/presign/{paths.bucket}/{paths.key}", {
            "op": "get", "expires_seconds": 900, "response_disposition": "attachment",
        })
        markdown = "\n".join([
            "# Matter export", "", "| Matter | Client | Deadline | Follow-up |", "|---|---|---|---|",
            *[f"| {m.matter_id} | {m.client_name} | {m.deadline.isoformat()} | {'yes' if m.matter_id in follow_up_ids(matters, today) else 'no'} |" for m in matters],
        ])
        pdf_data = client.request("POST", "/v1/pdf/generate", {
            "markdown": markdown, "page_size": "A4", "orientation": "portrait", "store": False,
        })
        return ExportResult(signed["url"], pdf_data, follow_up_ids(matters, today))
    finally:
        # The bucket belongs to this export; attempt bucket cleanup even if object deletion fails.
        try:
            try:
                client.request("DELETE", f"/v1/storage/object/delete/{paths.bucket}/{paths.key}")
            except InfraiError as exc:
                if exc.status != 404:
                    raise
            remaining = client.request("GET", f"/v1/storage/object/list/{paths.bucket}")
            if remaining:
                # Listing envelopes may include pagination alongside an empty object list.
                objects = remaining.get("objects", remaining.get("items", remaining)) if isinstance(remaining, dict) else remaining
                if objects:
                    raise RuntimeError(f"Object deletion not verified: {remaining}")
        finally:
            client.request("DELETE", f"/v1/storage/bucket/delete/{paths.bucket}")
            try:
                client.request("GET", f"/v1/storage/object/list/{paths.bucket}")
            except InfraiError as exc:
                if exc.status != 404:
                    raise
            else:
                raise RuntimeError(f"Bucket deletion not verified: {paths.bucket}")



def main() -> None:
    sample = [MatterIntake("M-104", "Northwind Retail", "settlement.pdf", date(2026, 9, 10), False)]
    result = export_matters(InfraiClient(), StoragePaths(f"legal-export-{uuid4().hex}", f"matter-export-{uuid4().hex}.csv"), sample, date.today())
    print(json.dumps({"download_url": result.download_url, "follow_up_ids": result.follow_up_ids}))


if __name__ == "__main__":
    main()
