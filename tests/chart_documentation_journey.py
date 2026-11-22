from playwright.sync_api import expect


def document_care(doctor, colleague):
    """Both clinicians start at the admission they opened from their assigned chart."""
    reason = "Follow-up after arrival"
    doctor.get_by_role("link", name="Back to patient chart").click()
    doctor.get_by_role("link", name="Record consultation").click()
    doctor.get_by_label("Visit time").fill("2026-01-15T09:45")
    doctor.get_by_label("Consultation reason").fill(reason)
    doctor.get_by_label("Initial evolution").fill("   ")
    doctor.get_by_role("button", name="Record consultation").click()
    expect(doctor.get_by_text("This field is required.")).to_be_visible()
    doctor.get_by_label("Initial evolution").fill("Reviewed symptoms at the visit.")
    doctor.get_by_role("button", name="Record consultation").click()
    expect(doctor.get_by_role("heading", name=reason)).to_be_visible()

    colleague.get_by_role("link", name="Back to patient chart").click()
    colleague.get_by_role("link", name=reason).click()
    colleague.get_by_label("Progress note").fill(
        "Follow-up completed by the second physician."
    )
    colleague.get_by_role("button", name="Add progress note").click()
    colleague.reload()
    expect(
        colleague.locator("section").filter(has_text="Initial evolution")
    ).to_contain_text(
        "2026-01-15 09:45 · America/Argentina/Buenos_Aires · Zpagination active, Paged 00"
    )
    note = colleague.locator("article").filter(
        has_text="Follow-up completed by the second physician."
    )
    expect(note).to_contain_text("Zpagination active, Paged 01")

    doctor.get_by_role("link", name="Back to patient chart").click()
    doctor.get_by_role("link", name="Add personal history").click()
    doctor.get_by_label("Description").fill("Previous outpatient follow-up.")
    doctor.get_by_role("button", name="Add personal history").click()
    doctor.get_by_role("link", name="Add family history").click()
    doctor.get_by_label("Family relationship").fill("Mother")
    doctor.get_by_label("Description").fill("Family history reported at intake.")
    doctor.get_by_role("button", name="Add family history").click()
    doctor.get_by_role("link", name="Edit family history").click()

    colleague.get_by_role("link", name="Back to patient chart").click()
    colleague.get_by_role("link", name="Edit family history").click()
    colleague.get_by_label("Family relationship").fill("Sister")
    colleague.get_by_label("Description").fill("Family history clarified at follow-up.")
    colleague.get_by_role("button", name="Edit family history").click()
    doctor.get_by_label("Description").fill("Concurrent correction")
    doctor.get_by_role("button", name="Edit family history").click()
    expect(doctor.get_by_text("This history has changed.", exact=False)).to_be_visible()
    doctor.get_by_role("link", name="Back to patient chart").click()
    doctor.reload()
    expect(
        doctor.get_by_role("heading", name="Family history · Sister")
    ).to_be_visible()
    expect(doctor.get_by_text("Family history clarified at follow-up.")).to_be_visible()
    expect(doctor.get_by_text("Previous outpatient follow-up.")).to_be_visible()
    expect(doctor.get_by_text("Family history reported at intake.")).to_have_count(0)
    doctor.get_by_role("link", name=reason).click()
    expect(
        doctor.locator("article").filter(has_text="Follow-up completed")
    ).to_have_count(1)
    doctor.get_by_label("Progress note").fill("Entry after revocation")
