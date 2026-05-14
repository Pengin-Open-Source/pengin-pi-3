# Pengin Pi 3 - Docker Deployment Guide

This guide provides instructions for deploying the Pengin Pi 3 application using Docker and Traefik.

## Prerequisites

1.  **Docker and Docker Compose:** Ensure you have Docker and Docker Compose installed on your server.
2.  **Git:** To clone the repository.
3.  **Domain Name:** A domain name pointing to your server's public IP address.
4.  **Open Ports:** Ensure ports 80 and 443 are open on your server's firewall.

## 1. Directory Structure Setup

We will set up the project in the `/opt/pengin-pi-3` directory on your server.

First, create the main directory:
```bash
sudo mkdir -p /opt/pengin-pi-3
cd /opt/penjin-pi-3
```

Next, clone your project repository into a `source` subdirectory.

```bash
sudo git clone <your-repo-url> source
```

Your final structure should look like this:
```
/opt/pengin-pi-3/
├── source/             # Your Django project code
│   ├── Dockerfile
│   ├── manage.py
│   └── ...
├── docker-compose.yml  # The main compose file
├── traefik.yml         # Traefik configuration
├── acme.json           # For storing SSL certificates
└── .env                # For storing secret variables
```

## 2. Configuration

Navigate to the `source` directory and copy the `docker-compose.yml` from the repository to the parent directory `/opt/pengin-pi-3/`.

```bash
cd /opt/pengin-pi-3/source
sudo cp docker-compose.yml ../
```

Now, create the other required configuration files in `/opt/pengin-pi-3/`.

### `traefik.yml`
Create this file to configure Traefik.

### `.env`
Create a `.env` file in `/opt/pengin-pi-3/` to store your secrets. **Do not commit this file to Git.**

## 3. Running the Application

Once all the files are in place and configured, you can start the application.

From the `/opt/pengin-pi-3` directory, run the following command:

```bash
sudo docker-compose up --build -d
```

This command will:
- Build the Django application image from the `Dockerfile`.
- Create and start the `web`, `db`, and `traefik` services.
- The `-d` flag runs the containers in detached mode (in the background).

Your application should now be running and accessible at your domain, secured with an SSL certificate from Let's Encrypt, courtesy of Traefik.

## Managing the Application

*   **To stop the containers:**
    ```bash
    sudo docker-compose down
    ```
*   **To view logs:**
    ```bash
    sudo docker-compose logs -f web
    sudo docker-compose logs -f db
    ```
*   **To update the application:**
    1.  Pull the latest code: `cd /opt/pengin-pi-3/source && sudo git pull`
    2.  Rebuild and restart the services: `cd /opt/pengin-pi-3 && sudo docker-compose up --build -d`