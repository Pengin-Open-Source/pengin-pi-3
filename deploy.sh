#!/bin/bash

# Define the absolute path to your .env file
ENV_FILE="./.env"

# Array of all required environment keys needed by the modular docker-compose file
REQUIRED_VARS=(
  "DB_CONTAINER"
  "REDIS_CONTAINER"
  "WEB_CONTAINER"
  "DB_NAME"
  "DB_USER"
  "DB_PASSWORD"
  "SES_SENDER"
  "SES_SENDER_NAME"
  "SES_USERNAME_SMTP"
  "SES_PASSWORD_SMTP"
  "SES_HOST"
  "URL"
  "URL2"
  "SECRET_KEY"
)

# 1. Check if the physical .env file exists
if [ ! -f "$ENV_FILE" ]; then
  echo "❌ Error: Configuration file '$ENV_FILE' not found."
  echo "Please create a valid .env file before running this script."
  exit 1
fi

# 2. Extract values and validate each environment key
MISSING_COUNT=0
echo "🔍 Validating project environment parameters..."

for VAR in "${REQUIRED_VARS[@]}"; do
  # Search for the key and extract its assigned value, cleaning up spaces and quotes
  VALUE=$(grep -E "^${VAR}[[:space:]]*=" "$ENV_FILE" | cut -d'=' -f2- | xargs)
  
  if [ -z "$VALUE" ] || [ "$VALUE" == "SECRET" ]; then
    echo "⚠️  Missing or invalid parameter: $VAR"
    MISSING_COUNT=$((MISSING_COUNT + 1))
  fi
done

# 3. Halt orchestration if any validations fail
if [ $MISSING_COUNT -gt 0 ]; then
  echo "❌ Initialization Halted: $MISSING_COUNT configuration errors found in .env."
  exit 1
else
  echo "✅ Configuration validation passed successfully."
fi

# 4. Initialize the Docker infrastructure stack
echo "🚀 Building and bringing up services..."
docker compose down
docker compose up --build -d

echo "🎉 Deployment successfully initialized."