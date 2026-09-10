# Pengin Pi Project Structure

This document provides an overview of the directory structure for the Pengin Pi Django project. Understanding this structure is key to navigating the codebase and contributing effectively.

## High-Level Overview

**This project does not use separate Django apps for features.** Everything lives inside the single `main` app (organized into submodules/subpackages), except generic, non-Django, non-auth infrastructure, which lives in `util/`. This is a deliberate departure from the "one app per feature" Django convention: it keeps permissions, models, and views for the whole project consolidated in one place instead of scattered and duplicated across many small apps.

```
pengin-pi-3/
├── main/               # The entire project - the only entry in INSTALLED_APPS besides framework/third-party
│   ├── auth/            # Central RBAC framework - see below
│   ├── models/           # All models (User, Slug, Address, ...) - one app_label, one migrations/ dir
│   ├── views/             # All views
│   ├── forms/              # All forms
│   ├── management/          # manage.py commands (main/management/commands/)
│   ├── migrations/            # The one migrations directory for the whole project
│   ├── settings.py, urls.py, wsgi.py, asgi.py
│   └── admin.py
├── static/             # Project-wide static files (CSS, JS, images) - add your own
├── templates/          # Project-wide Django templates
├── util/               # Shared, generic infrastructure - NOT for auth/permissions/user logic (see main/auth/)
├── manage.py           # Django's command-line utility
└── README.md           # Project README
```

## Main Directories Explained

### `main/`
This is the entire Django project - configuration, models, views, and the central auth framework all live here.
- `settings.py`: Installed apps, database configuration, middleware, and other global settings.
- `urls.py`: The root URLconf - routes every request in the project.
- `wsgi.py` / `asgi.py`: Configuration files for deploying on WSGI/ASGI compatible servers.
- `models/`, `views/`, `forms/`: Add new models/views/forms here as the project grows, organized into submodules by feature (e.g. `main/models/slug.py`, `main/views/slug.py`) rather than as separate Django apps. Every model shares the single `main` app_label, so there's exactly one `main/migrations/` directory for the whole project - no cross-app migration coordination to worry about.

### `main/auth/`
The central RBAC (role-based access control) framework - the one place all authorization, group, and user-permission logic lives, for the whole project. Nothing outside `main/auth/` should implement its own permission checks, group logic, or user-role framework - if a feature needs one, it extends or calls into `main/auth/`, not a private copy.
- `models.py`: `TeamRole`/`TeamUserRole` - `Group` = department, `TeamRole` = a title/position within a department, `TeamUserRole` = the user↔title join. `"Administrator"` is not a stored role - it means `User.is_superuser`.
- `permissions.py`: the actual "can this user do X" functions (`is_root`, `is_executive_manager`, `is_manager_of_group`, `can_access_group`, ...).
- `mixins.py` / `decorators.py`: class-based and function-based view guards built on `permissions.py`.
- `principals.py`: a small Need/RoleNeed/ItemNeed-style ACL toolkit, for finer-grained permission composition than the department/title model alone covers.
- `context_processors.py`: exposes the current user's roles to every template.
- `admin.py`: Django admin registrations for the models above (wired in via `main/admin.py`).

### `main/management/`
Django management command scaffolding (`main/management/commands/*.py`, run via `python manage.py <name>`). This is where test scripts and utility programs for exercising `main/auth/` (or anything else) belong - see `seed_departments.py` and `check_auth.py` for examples.

### `static/`
Project-wide static assets (CSS, JS, images). Django's `collectstatic` command gathers files from here for deployment.

### `templates/`
Django templates shared across the project - the base layout, nav/footer components, reusable widgets/macros, and per-feature page templates.

### `util/`
Generic, non-Django infrastructure with no auth/permissions/user-framework logic in it (that all belongs in `main/auth/` - see above). Examples: email sending, file storage (S3/local), rate limiting, reCAPTCHA, pagination.
