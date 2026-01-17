#!/bin/bash

# Subdomain Enumeration Tool by Krrish
# Usage: ./subdomain_hunter.sh target.com

DOMAIN=$1
OUTPUT_DIR="results_$DOMAIN"
GITHUB_TOKEN=""

# Check if domain is passed
if [ -z "$DOMAIN" ]; then
    echo "[!] Usage: $0 domain.com"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"
cd "$OUTPUT_DIR" || exit

echo "[*] Running Subfinder..."
subfinder -d "$DOMAIN" -all -recursive -o subfinder.txt

echo "[*] Running Assetfinder..."
assetfinder --subs-only "$DOMAIN" > assetfinder.txt

echo "[*] Running Findomain..."
findomain -t "$DOMAIN" | tee findomain.txt

echo "[*] Fetching from crt.sh..."
curl -s "https://crt.sh/?q=${DOMAIN}&output=json" | jq -r '.[].name_value' | sed 's/\*\.//g' | sort -u > crtsh.txt

echo "[*] Fetching from Wayback Machine..."
curl -s "http://web.archive.org/cdx/search/cdx?url=*.$DOMAIN/*&output=text&fl=original&collapse=urlkey" \
| sort | sed -e 's_https*://__' -e "s/\/.*//" -e 's/:.*//' -e 's/^www\.//' | sort -u > wayback.txt

echo "[*] Running GitHub Subdomain Scraper..."
github-subdomains -d "$DOMAIN" -t "$GITHUB_TOKEN"

echo "[*] Merging all results..."
cat *.txt | sort -u > final.txt

echo "[+] Done! Final subdomains saved to: $OUTPUT_DIR/final.txt"
