# Vendored frontend assets

The application serves these assets locally so pages do not depend on a CDN at
runtime.

- Bootstrap 5.3.8 CSS and bundled JavaScript are copied from the versioned
  `bootstrap@5.3.8` distribution on jsDelivr. They are served from the same
  origin without Subresource Integrity because Git line-ending normalization
  can change tracked text bytes across operating systems.
- HTMX 2.0.10 is supplied by the locked `django-htmx==1.29.0` dependency and is
  rendered with its `{% htmx_script %}` template tag.

Keep version directories, dependency pins, and template paths in sync when
upgrading an asset.
