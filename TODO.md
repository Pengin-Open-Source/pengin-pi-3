# Pengin Pi 3 - Alpha Build TODO

This document outlines the core development tasks required to reach the alpha build milestone for Pengin Pi 3.

## Core Issues

- [ ] **Standardize History Models:**
    - [ ] Create inheritable mixins or abstract base classes for history tracking.
    - [ ] Develop and document history standards for all models that require an audit trail.
    - [ ] Refactor existing history models (e.g., in `forums`, `blogs`) to use the new standardized system.

- [ ] **Slug Editor:**
    - [ ] Debug and resolve errors related to rendering and creating sub-pages.
    - [ ] Ensure full CRUD (Create, Read, Update, Delete) functionality for parent/root slugs.
    - [ ] Implement stable functionality for creating, editing, and navigating nested child slugs.

- [ ] **Theme Overhaul:**
    - [ ] Port the designated UI/UX template from the Penpot server.
    - [ ] Integrate the new theme as the base template for the entire Django project.
    - [ ] Ensure all existing pages are responsive and function correctly with the new theme.

- [ ] **MongoDB Integration:**
    - [ ] Add MongoDB support to the Django project, likely using a library like `djongo`.
    - [ ] Configure the project to use MongoDB as the primary database for content-heavy models (like slugs/dynamic pages).
    - [ ] Keep SQL (SQLite/MySQL/PostgreSQL) for user authentication, session management, and other relational data.

- [ ] **Dynamic SEO and Metadata Management:**
    - [ ] **Metadata:** Develop a system for pages/slugs to have comprehensive, default metadata. Create an editor in the admin panel or a standalone view to manage metadata for each slug.
    - [ ] **Sitemap:** Implement a dynamically generated `sitemap.xml` that updates automatically when pages/slugs are created, modified, or deleted, respecting `robots.txt` rules.
    - [ ] **Robots.txt:** Create a dynamic editor for `robots.txt` to allow administrators to easily toggle indexing for different URL paths or regions of the site.

- [ ] **Chat System Integration:**
    - [ ] **Rocket.Chat:** Replace the existing custom chat system with a full Rocket.Chat integration.
        - [ ] Remove the old chat UI and related JavaScript (`chat.js`).
        - [ ] Embed or integrate the Rocket.Chat UI seamlessly into the main theme.
    - [ ] **Mattermost:** Plan and implement support for Mattermost. This will likely be a separate, modular Django app to keep the integration clean and independent.