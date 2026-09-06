"""Visible professional-registration actions shared by both browser environments."""

from playwright.sync_api import Page


def fill_professional_registration(
    page: Page, *, dni: str, first_name: str = "Ada", last_name: str = "Lovelace"
) -> None:
    page.get_by_label("DNI", exact=True).fill(dni)
    page.get_by_label("First name", exact=True).fill(first_name)
    page.get_by_label("Last name", exact=True).fill(last_name)
    page.get_by_label("Date of birth", exact=True).fill("1990-01-01")
    page.get_by_label("Specialty", exact=True).select_option("general-medicine")
    page.get_by_label("Hospital service", exact=True).select_option("inpatient-ward")
