# Pengin Pi 3

A Django starter skeleton: the core project scaffolding, dynamic-page (Slug) system, and account/auth flow, with the Docker/nginx deployment shape already wired up. This is a bones-only skeleton - no business apps are included yet.

## What's included

- **`main`**: the whole project - the custom `User` model, the `Slug` dynamic-page system (`/slug/create/`, `/slug/edit/<id>/`, and a catch-all page renderer), login/signup/logout, password reset, profile editing, sitemap and robots.txt generation, and `main/auth/` - the central RBAC framework (departments/titles, permission checks, view guards, an ACL toolkit).
- **`util/`**: generic, non-Django infrastructure - email sending (SES), S3/local file storage, rate limiting, reCAPTCHA v3, pagination, and hardening middleware. No auth/permissions/user-framework logic lives here - that's all in `main/auth/`.
- **`templates/`**: the base page shell (`layout.html`), nav/footer/copyright components, generic Bootstrap macros (pagination, forms, cards, a carousel), and the auth page templates.
- Docker/nginx/docker-compose deployment shape matching how this project actually runs in production.

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
