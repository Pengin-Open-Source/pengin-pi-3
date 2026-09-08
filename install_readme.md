# Pengin Pi 3 - Docker Deployment Guide

This guide provides instructions for deploying the Pengin Pi 3 application using Docker and Traefik.

## Prerequisites

1.  **Docker and Docker Compose:** Ensure you have Docker and Docker Compose installed on your server.
2.  **Git:** To clone the repository.
3.  **Domain Name:** A domain name pointing to your server's public IP address.
4.  **Open Ports:** Ensure ports 80 and 443 are open on your server's firewall.

## 1. Directory Structure Setup

We will set up the project in the `/opt/pengin-pi-3` directory on your server, with the code cloned directly there (`docker-compose.yml`, `.env`, and the rest of the project all live together in this one directory).

```bash
sudo git clone <your-repo-url> /opt/pengin-pi-3
cd /opt/pengin-pi-3
```

Your final structure should look like this:
```
/opt/pengin-pi-3/
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
├── manage.py
├── .env                # For storing secret variables (copy from .env.example) - never commit this
└── ...
```

## 2. Configuration

`docker-compose.yml` defines five services: `postgres`, `web` (this Django app, via uwsgi), `nginx` (serves static/media and fronts `web`), `ferretdb` (Mongo-compatible store used by the dynamic CMS pieces), and `redis`. There's no separate `traefik` service in this compose file - the `nginx` service attaches to an already-running, externally-managed Traefik instance via Docker labels and the shared `root_proxy` external network, so Traefik itself (and its SSL cert storage) is assumed to already be running on the host, outside this project.

### `.env`
Copy `.env.example` to `.env` in `/opt/pengin-pi-3/` and fill in real values. **Do not commit this file to Git.**

```bash
cp .env.example .env
```

## 3. Running the Application

Once `.env` is in place, from `/opt/pengin-pi-3`:

```bash
sudo docker-compose up --build -d
```

This command will:
- Build the Django application image from the `Dockerfile`.
- Create and start the `postgres`, `web`, `nginx`, `ferretdb`, and `redis` services.
- The `-d` flag runs the containers in detached mode (in the background).

Your application should now be running and accessible at your domain, secured with an SSL certificate from Let's Encrypt, courtesy of the host's existing Traefik instance.

## Managing the Application

*   **To stop the containers:**
    ```bash
    sudo docker-compose down
    ```
*   **To view logs:**
    ```bash
    sudo docker-compose logs -f web
    sudo docker-compose logs -f postgres
    ```
*   **To update the application:**
    1.  Pull the latest code: `cd /opt/pengin-pi-3 && sudo git pull`
    2.  Rebuild and restart the services: `sudo docker-compose up --build -d`