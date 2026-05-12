# Pengin Pi Project Structure

This document provides an overview of the directory structure for the Pengin Pi Django project. Understanding this structure is key to navigating the codebase and contributing effectively.

## High-Level Overview

The project follows a standard Django layout, with a central project directory and multiple "apps" for different functionalities.

```
pengin-pi-3/
├── .github/            # GitHub specific files (issue templates, workflows)
├── main/               # Core Django project configuration
├── static/             # Project-wide static files (CSS, JS, images)
├── templates/          # Project-wide Django templates
├── util/               # Shared utility modules and helper functions
├── about/              # Django app for the "About" section
├── blogs/              # Django app for the blog feature
├── events/             # Django app for the events/calendar system
├── forums/             # Django app for the BBS/Forum
├── home/               # Django app for the main landing pages
├── tickets/            # Django app for the ticketing system
├── manage.py           # Django's command-line utility
├── db.sqlite3          # Development database file
└── README.md           # Project README
```

## Main Directories Explained

### `main/`
This is the heart of the Django project. It contains the configuration files that apply to the entire web application.
- `settings.py`: The main settings file for the Django project. It defines installed apps, database configuration, middleware, and other global settings.
- `urls.py`: The root URLconf. It's the entry point for Django's URL dispatcher, routing incoming web requests to the correct app and view.
- `wsgi.py` / `asgi.py`: Configuration files for deploying the application on WSGI/ASGI compatible web servers.

### App Directories (`blogs/`, `forums/`, `tickets/`, etc.)
Each of these directories is a self-contained Django "app" that encapsulates a specific feature of the website. For example:
- The `blogs` app contains the models, views, and templates related to blog posts.
- The `tickets` app handles the logic for the support ticket system.
This modular approach keeps the code organized and makes it easier to maintain and develop features independently.

### `static/`
This directory holds static assets that are used across the entire project and are not specific to one app. This includes global CSS stylesheets, JavaScript files, and images. Django's `collectstatic` command gathers files from here (and from the `static` subdirectories of each app) for deployment.

### `templates/`
This directory contains Django templates that are shared across multiple apps or define the base layout of the site. For example, `base.html`, which other templates extend, would typically live here.

### `util/`
This is a non-Django directory for custom Python utility modules and helper functions that can be used by any of the Django apps. For example, the `util/mail/` directory contains logic for sending emails.