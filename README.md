# Pengin Pi 3

A Django starter skeleton built around three things every project on it inherits for free: a role-based security posture, a database-backed page/content system (the Slug CMS), and a self-generating editor for that content. It's bones-only otherwise - no business apps ship with it, so every project starts from the same hardened, content-manageable foundation instead of re-solving auth, bot defense, and page editing from scratch each time.

## Security

- **Custom `User` model + RBAC** (`main/auth/`) - departments (`Group`) and titles within them (`TeamRole`/`TeamUserRole`), the actual permission-check functions (`is_root`, `is_manager_of_group`, `can_access_group`, ...), view-guard mixins/decorators built on them, and a small Need/RoleNeed/ItemNeed ACL toolkit (`principals.py`) for permission composition finer-grained than department/title alone. `User.is_superuser` (not a stored role) means "Administrator." Nothing outside `main/auth/` should implement its own permission logic - see `PROJECT_STRUCTURE.md`.
- **Rate limiting on every POST that matters** - `util.security.ratelimit.RateLimitedPostMixin`/`RateLimitedGetMixin` wrap any view with a per-IP rate limit and are applied by default to login/signup/password-reset/profile edits and Slug create/edit/delete - staff-only forms included, on the assumption that "logged in" and "staff-only" don't by themselves rule out scripted abuse.
- **reCAPTCHA v3 wherever a form has real consequences** - `util.security.recaptcha.verify_recaptcha_token`/`RecaptchaRequiredMixin` gate anonymous-facing forms. `Slug.requires_recaptcha` extends the same protection into the CMS itself: `SlugView.dispatch()` already checks it on every POST a Slug's own embedded content ever sends back to itself, so the protection exists before any form-embedding feature is built on top of it, not bolted on after the first bot incident.
- **`HardenedBlocklistMiddleware`** (`util/middleware/blocklist.py`) - a Django-layer IP blocklist read from the same `nginx_blocklist.conf` an edge fail2ban setup writes to, so a banned IP is rejected even if a request reaches the app layer.
- **A hardened Docker/nginx/Traefik deployment shape** (`install_readme.md`) - real-IP extraction behind a reverse proxy, per-path rate/connection limits, and nginx-level blocking of hidden-file/vuln-scanner/CMS-probe requests with access logging deliberately left *on* for that traffic (an easy mistake to make - blocking a request and not logging it means fail2ban can never see or ban the IP making it), plus Let's Encrypt via Traefik.

## The Slug CMS

Every page in a project built on this - marketing pages, one-offs, whatever - is a `Slug` (`main/models/slug.py`): a `name`/`parent` pair forming a path hierarchy, resolved by a single catch-all `SlugView`. A Slug renders through one shared trio (also used by other content types, like `Event`, via `util/dynamic_render.py`):
- `template_name` - a named template to extend or render as-is, and/or
- `render_template` - raw markup stored directly on the Slug itself, and
- `json` - the data plugged into whichever of the above is used.

Set `is_dynamic` on a Slug and it stops being a page and becomes a **content type**: its `json` holds a JSON Schema, and its children get a generated create/edit form (`main/views/slug_dynamic.py`, `util/dynamic_forms.py`) whose submitted data is stored in FerretDB (`util/slug_dynamic_data.py`) instead of as a one-off Django model - a way to add a structured, admin-editable collection (a blog, a job board, a product catalog) without writing a model and a migration for it.

## The dynamic page editor

Editing a Slug's content doesn't mean hand-editing JSON in a textarea. `util/slug_content_form.py` builds a real, per-field HTML form from a Slug's *current* content every time its edit page loads - there's no stored schema to drift out of sync with the content itself:
- `_field_kind()` sniffs each JSON value's likely widget - boolean, number, image, video, HTML, plain text, or a list of strings - straight from the value.
- `extract_referenced_keys()` scans the *actual rendering surface* - the named template's source **and** any raw `render_template` markup - for `{{ }}`/`{% %}` variable references, so a key the template references but that's missing from `json` still gets a field instead of silently staying unreachable.
- Image/video fields get a real upload widget (backed by `util/file`, S3 or local storage) alongside a path field, with a live preview.
- An "Advanced" section keeps the raw `template_name`/`render_template`/`json` reachable for reshaping the page itself (new keys, a different template) - save from there and the per-field form regenerates from the new shape on next load, with no separate migration step.

## Adding features

This project deliberately does not use separate Django apps per feature - everything lives inside `main` (organized into submodules, e.g. `main/models/`, `main/views/`), with only generic non-auth infrastructure in `util/`. See `PROJECT_STRUCTURE.md` for the full convention, and `main/auth/` for the RBAC framework every feature's permission checks should go through.

## Local development

```
python -m venv env
source env/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real values
python manage.py migrate
python manage.py runserver
```

By default `main/settings.py` falls back to a local SQLite database if no `DB_*` environment variables are set, so you can get started without Postgres running.

## Docker deployment

See `install_readme.md` for the full Docker Compose deployment guide.

## License

GPLv3 - see `LICENSE`.
