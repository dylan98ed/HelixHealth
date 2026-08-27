# Vendored frontend assets

The application serves these assets locally so pages do not depend on a CDN at
runtime.

- Bootstrap 5.3.8 CSS and bundled JavaScript are copied from the versioned
  `bootstrap@5.3.8` distribution on jsDelivr. Their SHA-384 integrity values are
  recorded in `templates/base.html`.
- HTMX 2.0.10 is supplied by the locked `django-htmx==1.29.0` dependency and is
  rendered with its `{% htmx_script %}` template tag.

Keep version directories, dependency pins, integrity values, and template paths
in sync when upgrading an asset.
