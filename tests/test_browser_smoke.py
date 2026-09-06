from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_home_page_loads_in_a_real_browser(live_server, browser_page, tmp_path):
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
    expect(browser_page).to_have_title("HelixHealth · A clearer path to patient care")
    expect(browser_page.get_by_role("heading", name="HelixHealth")).to_be_visible()
    expect(browser_page.get_by_role("link", name="Open your workspace")).to_be_visible()
    expect(browser_page.get_by_text("Foundation smoke page")).to_have_count(0)
    assert (
        browser_page.locator(".site-header").evaluate(
            "element => getComputedStyle(element).backgroundColor"
        )
        == "rgb(255, 255, 255)"
    )
    browser_page.screenshot(path=str(tmp_path / "landing-desktop.png"), full_page=True)
    browser_page.set_viewport_size({"width": 390, "height": 844})
    assert browser_page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth"
    )
    browser_page.screenshot(path=str(tmp_path / "landing-mobile.png"), full_page=True)
    print(f"UI screenshots: {tmp_path}")
    browser_page.get_by_role("link", name="Open your workspace").click()
    expect(browser_page.get_by_label("Username")).to_be_visible()
    expect(browser_page.get_by_label("Password")).to_be_visible()
    assert browser_page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth"
    )
    assert browser_page.evaluate("typeof window.htmx !== 'undefined'")
    assert external_requests == []
