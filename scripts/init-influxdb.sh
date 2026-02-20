#!/bin/bash
set -e

# Wait for InfluxDB to be ready
echo "Waiting for InfluxDB to start..."
until influx ping &> /dev/null; do
  sleep 1
done

echo "InfluxDB is ready. Creating API token..."

# Create API token with all access
TOKEN=$(influx auth create \
  --org iot-org \
  --all-access \
  --description "PLC Logger Token" \
  --json | jq -r '.token')

echo "Generated token: ${TOKEN}"

# Save token to file for other containers to read
echo "${TOKEN}" > /var/lib/influxdb2/token.txt

echo "Token saved to /var/lib/influxdb2/token.txt"
