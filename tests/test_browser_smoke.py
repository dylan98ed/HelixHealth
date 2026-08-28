from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_home_page_loads_in_a_real_browser(live_server, browser_page):
    external_requests = []
    application_origin = urlparse(live_server.url).netloc

    def record_external_request(request):
        request_url = urlparse(request.url)
        if request_url.netloc and request_url.netloc != application_origin:
            external_requests.append(request.url)

    browser_page.on("request", record_external_request)
    response = browser_page.goto(live_server.url, wait_until="networkidle")

    assert response is not None
    assert response.ok
    expect(browser_page).to_have_title("Home | HelixHealth")
    expect(browser_page.get_by_role("heading", name="HelixHealth")).to_be_visible()
    expect(browser_page.get_by_text("Foundation smoke page")).to_be_visible()
    assert (
        browser_page.locator(".navbar").evaluate(
            "element => getComputedStyle(element).backgroundColor"
        )
        == "rgb(13, 110, 253)"
    )
    assert browser_page.evaluate("typeof window.htmx !== 'undefined'")
    assert external_requests == []
