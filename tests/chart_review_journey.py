"""Chart and audit acceptance steps shared by the isolated and Compose browsers."""

import json
import re
from pathlib import Path

from playwright.sync_api import expect

from access_control.acceptance_personas import (
    CARE_COORDINATOR,
    CHART_REASON,
    PAGED_ACTIVE_USERNAME_PREFIX,
)

EXCHANGE_SOURCE = "https://chart-exchange.example.test"


def chart_exchange_file():
    path = Path(
        "docs/interoperability/fhir-r4/json-v2/fixtures/independent-valid-bundle.json"
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    patient, doctor, procedure, _ = [entry["resource"] for entry in document["entry"]]
    patient["identifier"][0]["value"] = "20000016"
    patient["birthDate"] = "1990-01-01"
    doctor["identifier"][0]["value"] = "49989123"
    doctor["qualification"][0]["identifier"][0]["value"] = "MN 49989123"
    doctor["name"] = [{"family": "Exchange", "given": ["Pat"]}]
    procedure["authoredOn"] = "2025-12-16"
    return json.dumps(document).encode()


def grant_audit(accounts, username):
    workspace = accounts.get_by_role("link", name="Account administration")
    if workspace.count():
        workspace.click()
        accounts.get_by_role("link", name="Users", exact=True).click()
    accounts.locator("#searchbar").fill(username)
    accounts.get_by_role("button", name="Search", exact=True).click()
    accounts.get_by_role("link", name=username, exact=True).click()
    accounts.locator("#id_user_permissions_from").get_by_role(
        "option", name=re.compile("Can review clinical chart audit$")
    ).dblclick()
    accounts.get_by_role("button", name="Save", exact=True).click()


def review_chart(signed_in, accounts, colleague, reception, populated):
    first_doctor = f"{PAGED_ACTIVE_USERNAME_PREFIX}-00"
    importer = signed_in(first_doctor)
    importer.get_by_label("DNI", exact=True).fill("20000016")
    importer.get_by_role("button", name="Find patient").click()
    importer.get_by_role(
        "link", name="Record admission for Patient 16 Zpagination"
    ).click()
    importer.get_by_role("link", name="Interoperability", exact=True).click()
    importer.get_by_role("link", name="Import FHIR XML", exact=True).click()
    importer.get_by_label("Source organization system").fill(
        "https://external.example/identifiers/institution"
    )
    importer.get_by_label("FHIR XML file").set_input_files(
        {
            "name": "chart-medication.xml",
            "mimeType": "application/fhir+xml",
            "buffer": Path(__file__).with_name("chart-medication.xml").read_bytes(),
        }
    )
    importer.get_by_role("button", name="Import FHIR XML", exact=True).click()
    expect(
        importer.get_by_role("heading", name="External clinical import")
    ).to_be_visible()
    importer.get_by_role("link", name="Clinical workspace", exact=True).click()
    importer.get_by_role("link", name="Assigned patient charts").click()
    importer.get_by_role("link", name=populated).click()
    importer.get_by_role("link", name="External tablet", exact=True).click()
    expect(importer.get_by_text("Take with food", exact=True)).to_be_visible()
    expect(
        importer.get_by_text("1 tablet · oral · daily · 5 days", exact=True)
    ).to_be_visible()

    # Reimport through the same visible flow, then find the order in the chart.
    for _ in range(2):
        importer.get_by_role("link", name="Import FHIR JSON", exact=True).click()
        importer.get_by_label("Source organization system").fill(EXCHANGE_SOURCE)
        importer.get_by_label("FHIR JSON file").set_input_files(
            {
                "name": "exchange.json",
                "mimeType": "application/fhir+json",
                "buffer": chart_exchange_file(),
            }
        )
        importer.get_by_role("button", name="Import FHIR JSON", exact=True).click()
        expect(importer.get_by_role("heading", name="FHIR JSON import")).to_be_visible()
    colleague.get_by_role("link", name="Back to patient chart").click()
    timeline = colleague.get_by_role("list", name="Clinical timeline")
    order = timeline.get_by_role("listitem").filter(has_text="Requested procedure")
    expect(order).to_have_count(1)
    expect(order).to_contain_text("2025-12-16")
    expect(order).to_contain_text("Requester: Exchange, Pat")
    expect(timeline.get_by_role("listitem").last).to_contain_text("Requested procedure")
    expect(
        timeline.get_by_role("listitem").filter(has_text=CHART_REASON)
    ).to_contain_text(f"Professional: Not recorded · Recorded by {CARE_COORDINATOR}")
    order.get_by_role("link").click()
    expect(colleague.get_by_text("http://loinc.org", exact=False)).to_contain_text(
        "24627-2"
    )
    receipt = colleague.get_by_text("Received ", exact=False)
    expect(receipt).to_be_visible()
    external_id = receipt.inner_text().split("External identifier ")[1].strip()
    colleague.get_by_role("link", name="Back to patient chart").click()
    colleague.get_by_role("link", name="Review chart audit").click()
    chart_audit_url = colleague.url
    assert reception.goto(chart_audit_url).status == 403
    assert importer.goto(chart_audit_url).status == 403

    def open_correction(tab):
        tab.get_by_label("Record type").select_option(
            label="Personal or family history"
        )
        tab.get_by_role("button", name="Filter events").click()
        row = tab.get_by_role("row").filter(has_text="revise")
        day = row.get_by_role("cell").first.inner_text().split()[0]
        tab.get_by_label("Event date").fill(day)
        tab.get_by_role("button", name="Filter events").click()
        row.get_by_role("link", name="Personal or family history").click()
        expect(
            tab.get_by_role("heading", name="Personal or family history · revise")
        ).to_be_visible()
        expect(
            tab.locator("section").filter(has=tab.get_by_role("heading", name="Before"))
        ).to_contain_text("Mother")
        expect(
            tab.locator("section").filter(has=tab.get_by_role("heading", name="After"))
        ).to_contain_text("Sister")

    colleague.get_by_label("Record type").select_option(label="Requested procedure")
    colleague.get_by_role("button", name="Filter events").click()
    imported_event = colleague.get_by_role(
        "link", name="Requested procedure", exact=True
    )
    expect(imported_event).to_have_count(1)
    imported_event.click()
    expect(
        colleague.get_by_role("heading", name="Requested procedure · import")
    ).to_be_visible()
    expect(colleague.locator("dl")).to_contain_text(EXCHANGE_SOURCE)
    expect(colleague.locator("dl")).to_contain_text(first_doctor)
    assert (
        json.loads(
            colleague.locator("section")
            .filter(has=colleague.get_by_role("heading", name="After"))
            .locator("pre")
            .inner_text()
        )["external_identifier"]
        == external_id
    )
    colleague.get_by_role("link", name="Back to clinical audit").click()
    open_correction(colleague)
    grant_audit(accounts, CARE_COORDINATOR)
    administrative = signed_in(CARE_COORDINATOR)
    administrative.get_by_role("link", name="Clinical audit", exact=True).click()
    administrative.get_by_label("Patient DNI").fill("20000016")
    open_correction(administrative)
    assert colleague.goto(administrative.url).status == 403

    grant_audit(accounts, first_doctor)
    reviewer = signed_in(first_doctor)
    reviewer.get_by_role("link", name="Assigned patient charts").click()
    reviewer.get_by_role("link", name=populated).click()
    reviewer.get_by_role("link", name="Review chart audit").click()
    open_correction(reviewer)
    return reviewer
