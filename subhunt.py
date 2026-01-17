#!/bin/bash

# Enhanced Subdomain Enumeration Tool
# Usage: ./subdomain_hunter.sh target.com

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# Color codes for better output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOMAIN="${1:-}"
OUTPUT_DIR="results_${DOMAIN}"
GITHUB_TOKEN=""  # Use environment variable instead of hardcoded token

# Function to print colored output
log_info() { echo -e "${BLUE}[*]${NC} $1"; }
log_success() { echo -e "${GREEN}[+]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[-]${NC} $1"; }

# Check dependencies
check_dependencies() {
    local deps=("subfinder" "assetfinder" "findomain" "jq" "curl")
    local missing=()
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            missing+=("$dep")
        fi
    done
    
    if [ ${#missing[@]} -ne 0 ]; then
        log_error "Missing dependencies: ${missing[*]}"
        log_info "Please install the missing tools before running this script"
        exit 1
    fi
}

# Validate domain format
validate_domain() {
    local domain_regex="^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$"
    if [[ ! "$DOMAIN" =~ $domain_regex ]]; then
        log_error "Invalid domain format: $DOMAIN"
        exit 1
    fi
}

# Usage information
show_usage() {
    cat << EOF
Usage: $0 domain.com

Required Tools:
  - subfinder, assetfinder, findomain, jq, curl

Optional Environment Variables:
  - GITHUB_TOKEN: GitHub token for github-subdomains (recommended)

Examples:
  $0 example.com
  GITHUB_TOKEN=ghp_xxx $0 example.com
EOF
}

# Main execution
main() {
    # Check if domain is provided
    if [ -z "$DOMAIN" ]; then
        log_error "No domain specified"
        show_usage
        exit 1
    fi

    # Validate domain format
    validate_domain

    # Check dependencies
    log_info "Checking dependencies..."
    check_dependencies

    # Create output directory
    if [ -d "$OUTPUT_DIR" ]; then
        log_warning "Output directory $OUTPUT_DIR already exists. Previous results may be overwritten."
    else
        mkdir -p "$OUTPUT_DIR"
    fi

    cd "$OUTPUT_DIR" || exit 1

    log_info "Starting subdomain enumeration for: $DOMAIN"
    log_info "Results will be saved in: $OUTPUT_DIR"

    # Run subfinder with timeout
    log_info "Running Subfinder..."
    timeout 300 subfinder -d "$DOMAIN" -all -recursive -silent -o subfinder.txt

    # Run assetfinder with timeout
    log_info "Running Assetfinder..."
    timeout 180 assetfinder --subs-only "$DOMAIN" | sort -u > assetfinder.txt

    # Run findomain with timeout
    log_info "Running Findomain..."
    timeout 240 findomain -t "$DOMAIN" --quiet | sort -u > findomain.txt

    # Fetch from crt.sh with timeout
    log_info "Fetching from crt.sh..."
    timeout 60 curl -s --retry 3 "https://crt.sh/?q=%25.${DOMAIN}&output=json" | \
        jq -r '.[].name_value // empty' 2>/dev/null | \
        sed 's/\*\.//g' | sort -u > crtsh.txt || {
        log_warning "crt.sh query failed or returned no results"
        touch crtsh.txt
    }

    # Fetch from Wayback Machine with timeout
    log_info "Fetching from Wayback Machine..."
    timeout 90 curl -s --retry 3 "http://web.archive.org/cdx/search/cdx?url=*.${DOMAIN}/*&output=text&fl=original&collapse=urlkey" | \
        sed -e 's_https*://__' -e "s/\/.*//" -e 's/:.*//' -e 's/^www\.//' | \
        sort -u > wayback.txt || {
        log_warning "Wayback Machine query failed or returned no results"
        touch wayback.txt
    }

    # Run GitHub subdomain scraper if token is available with timeout
    if [ -n "$GITHUB_TOKEN" ]; then
        if command -v github-subdomains &> /dev/null; then
            log_info "Running GitHub Subdomain Scraper..."
            timeout 120 github-subdomains -d "$DOMAIN" -t "$GITHUB_TOKEN" -o github.txt 2>/dev/null || {
                log_warning "GitHub subdomains scan failed"
                touch github.txt
            }
        else
            log_warning "github-subdomains not found, skipping GitHub enumeration"
            touch github.txt
        fi
    else
        log_warning "GITHUB_TOKEN not set, skipping GitHub enumeration"
        touch github.txt
    fi

    # Merge all results and remove invalid entries
    log_info "Merging and processing results..."
    cat *.txt 2>/dev/null | \
        grep -E "^[a-zA-Z0-9.-]*\.${DOMAIN//./\\.}$" | \
        sed 's/^\.//; s/\.$//' | \
        sort -u > final.txt

    # Generate statistics
    local total_count=$(wc -l < final.txt 2>/dev/null || echo 0)
    
    log_success "Enumeration completed!"
    log_info "Total unique subdomains found: $total_count"
    log_success "Final subdomains saved to: $OUTPUT_DIR/final.txt"

    # Show file sizes for each tool
    log_info "Results by tool:"
    for file in subfinder.txt assetfinder.txt findomain.txt crtsh.txt wayback.txt github.txt; do
        if [ -f "$file" ]; then
            local count=$(wc -l < "$file" 2>/dev/null || echo 0)
            log_info "  ${file%.txt}: $count subdomains"
        fi
    done
}

# Handle script interruption
trap 'log_error "Script interrupted by user"; exit 1' INT TERM

# Run main function
main "$@"
