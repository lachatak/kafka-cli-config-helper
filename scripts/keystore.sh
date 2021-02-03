#!/bin/bash

# Exit if any of the intermediate steps fail
set -e

echo "$1" > /tmp/compositefile.txt
echo "$2" >> /tmp/compositefile.txt

rm -f "$4"/keyStore.p12
openssl pkcs12 -export -in /tmp/compositefile.txt -out "$4"/keyStore.p12 -password pass:"$3"
echo "KeyStore generated to $4/keyStore.p12"
