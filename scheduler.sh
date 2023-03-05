#!/bin/bash

# This post helped a lot with this script
# https://levelup.gitconnected.com/cron-docker-the-easiest-job-scheduler-youll-ever-create-e1753eb5ea44

if [ -z "$CRON_FILE" ]; then
   CRON_FILE="schedule"
fi

echo "Loading crontab file: $CRON_FILE"

# Load the crontab file
crontab $CRON_FILE
(echo "PATH=$PATH" ; crontab -l) | crontab -

# Start cron
echo "Starting cron..."
cron -f
