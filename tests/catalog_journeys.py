"""Catalog acceptance steps shared by isolated and disposable HTTP journeys."""

import json

from playwright.sync_api import Page, expect


def import_catalog_and_verify_retries(page: Page) -> None:
    """Start on Medications; establish all pagination rows through ordinary POST."""
    entries = [
        {
            "system": "https://acceptance.example.test/upload",
            "version": "2026-09",
            "code": f"UPLOAD-{index:02d}",
            "name": f"Uploaded medication {index:02d}",
            "presentation": "10 mg tablet",
        }
        for index in range(21)
    ]

    def upload(rows: list[dict[str, str]], *, include_source: bool = True) -> None:
        document: dict[str, object] = {"entries": rows}
        if include_source:
            document["source_label"] = "Acceptance upload"
        page.get_by_role("link", name="Import JSON", exact=True).click()
        page.get_by_label("Normalized JSON file", exact=True).set_input_files(
            {
                "name": "catalog.json",
                "mimeType": "application/json",
                "buffer": json.dumps(document).encode(),
            }
        )
        page.get_by_role("button", name="Import JSON", exact=True).click()

    upload([])
    expect(page.get_by_role("alert")).to_contain_text("Provide at least one entry.")
    page.get_by_role("link", name="Back to catalog", exact=True).click()
    upload(entries, include_source=False)
    expect(page.get_by_role("alert")).to_contain_text("This field is required.")
    page.get_by_role("link", name="Back to catalog", exact=True).click()
    upload(entries)
    expect(page.get_by_role("status")).to_contain_text(
        "Imported 21 new entries; 0 unchanged."
    )
    page.get_by_role("link", name="Back to catalog", exact=True).click()
    upload(entries)
    expect(page.get_by_role("status")).to_contain_text(
        "Imported 0 new entries; 21 unchanged."
    )
    page.get_by_role("link", name="Back to catalog", exact=True).click()
    upload(
        [
            {**entries[0], "code": "REJECTED-UPLOAD", "name": "Must not persist"},
            {**entries[1], "name": "Conflicting replacement"},
        ]
    )
    expect(
        page.get_by_text(
            "An existing source identity has conflicting content.", exact=True
        )
    ).to_be_visible()
    page.get_by_role("link", name="Back to catalog", exact=True).click()
    upload(
        [
            {**entries[0], "code": "REJECTED-UPLOAD", "name": "Must not persist"},
            {**entries[1], "code": "INVALID-UPLOAD", "name": ""},
        ]
    )
    expect(page.get_by_role("heading", name="Rows needing correction")).to_be_visible()
    page.get_by_role("link", name="Back to catalog", exact=True).click()
    page.get_by_label("Code or name").fill("UPLOAD")
    page.get_by_role("button", name="Search", exact=True).click()
    records = page.get_by_role("region", name="Medications records")
    expect(records.locator("article")).to_have_count(20)
    page.get_by_role("navigation", name="Medications pagination").get_by_role(
        "link", name="Next", exact=True
    ).click()
    expect(records.locator("article")).to_have_count(1)
    expect(page.get_by_text("Uploaded medication 20", exact=True)).to_be_visible()
    page.get_by_label("Code or name").fill("REJECTED-UPLOAD")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(records.locator("article")).to_have_count(0)
