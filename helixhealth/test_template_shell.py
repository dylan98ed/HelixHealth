from html.parser import HTMLParser
from pathlib import Path

from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse


class AssetURLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag not in {"link", "script"}:
            return
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.urls.append(value)


def test_smoke_page_uses_pinned_local_frontend_assets(client):
    response = client.get(reverse("home"))

    assert response.status_code == 200
    html = response.content.decode()
    assert "Foundation smoke page" in html

    parser = AssetURLParser()
    parser.feed(html)

    expected_assets = {
        "vendor/bootstrap/5.3.8/bootstrap.min.css": "Bootstrap  v5.3.8",
        "vendor/bootstrap/5.3.8/bootstrap.bundle.min.js": "Bootstrap v5.3.8",
    }
    assert {static(path) for path in expected_assets} <= set(parser.urls)
    assert not any(url.startswith(("http://", "https://", "//")) for url in parser.urls)

    for asset_path, version_marker in expected_assets.items():
        resolved_path = finders.find(asset_path)
        assert resolved_path is not None
        assert version_marker in Path(resolved_path).read_text(encoding="utf-8")

    static_url = static("")
    htmx_urls = [
        url
        for url in parser.urls
        if url.startswith(f"{static_url}django_htmx/") and url.endswith(".js")
    ]
    assert len(htmx_urls) == 1

    htmx_asset_path = htmx_urls[0].removeprefix(static_url)
    resolved_htmx_path = finders.find(htmx_asset_path)
    assert resolved_htmx_path is not None
    assert 'version:"2.0.10"' in Path(resolved_htmx_path).read_text(encoding="utf-8")
