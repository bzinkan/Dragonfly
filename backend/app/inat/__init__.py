"""iNaturalist API integration.

Two surfaces:

- `client.py` -- shared async httpx client + auth.
- `cv.py` -- /v1/computervision/score_image (kid-photo species suggestions).
- `taxa.py` -- /v1/taxa/{id} (taxon lookup for the species cache).

The iNat OAuth token is optional. If `settings.inat_oauth_token` is empty
(dev / CI) the CV path returns a `cv_unavailable` shape rather than
raising; callers fall back to manual species selection per
`docs/architecture.md` external-dependency table.
"""
