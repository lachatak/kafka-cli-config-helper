#!/bin/sh

# Exit if any of the intermediate steps fail
set -e

rm -f "$3"/trustStore.jks
echo "$1" | keytool -keystore "$3"/trustStore.jks -alias CARoot -import -storepass "$2" -noprompt
echo "TrustStore generated to $3/trustStore.jks"
