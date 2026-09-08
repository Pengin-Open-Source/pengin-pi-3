# Pengin Pi Project Structure

This document provides an overview of the directory structure for the Pengin Pi Django project. Understanding this structure is key to navigating the codebase and contributing effectively.

## High-Level Overview

The project follows a standard Django layout, with a central project directory and multiple "apps" for different functionalities.

```
pengin-pi-3/
├── main/               # Core Django project configuration + the User/Slug system
├── static/             # Project-wide static files (CSS, JS, images) - add your own
├── templates/          # Project-wide Django templates
├── util/               # Shared utility modules and helper functions
├── <your-app>/         # Add each new Django app at the repo root, alongside main/
├── manage.py           # Django's command-line utility
└── README.md           # Project README
```

## Main Directories Explained

### `main/`
This is the heart of the Django project. It contains the configuration files that apply to the entire web application, plus the core `User` model and the `Slug` dynamic-page system.
- `settings.py`: The main settings file for the Django project. It defines installed apps, database configuration, middleware, and other global settings.
- `urls.py`: The root URLconf. It's the entry point for Django's URL dispatcher, routing incoming web requests to the correct app and view.
- `wsgi.py` / `asgi.py`: Configuration files for deploying the application on WSGI/ASGI compatible web servers.

### App Directories
This skeleton ships with no business apps - `main` is the only entry in `INSTALLED_APPS` beyond the framework/third-party ones. As you add features, each one becomes its own self-contained Django app directory at the repo root (models/views/templates/urls for that feature), added to `INSTALLED_APPS` in `main/settings.py` and wired into `main/urls.py`. This modular approach keeps the code organized and makes it easier to maintain and develop features independently.

### `static/`
This directory holds static assets that are used across the entire project and are not specific to one app. This includes global CSS stylesheets, JavaScript files, and images. Django's `collectstatic` command gathers files from here (and from the `static` subdirectories of each app) for deployment.

### `templates/`
This directory contains Django templates that are shared across multiple apps or define the base layout of the site. For example, `base.html`, which other templates extend, would typically live here.

### `util/`
This is a non-Django directory for custom Python utility modules and helper functions that can be used by any of the Django apps. For example, the `util/mail/` directory contains logic for sending emails.