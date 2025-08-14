#!/bin/bash
# Script to process all files in ../data/test_invoices using send_invoice_request.py
# and store the results in ./test/data/results

INVOICE_DIR="../data/test_invoices"
RESULTS_DIR="./test/data/results"
SCRIPT_PATH="./test/requests/send_invoice_request.py"

mkdir -p "$RESULTS_DIR"

for file in "$INVOICE_DIR"/*; do
    [ -f "$file" ] || continue
    filename=$(basename "$file")
    file_id="test-$filename"
    echo "Processing $file with file_id $file_id"
    python "$SCRIPT_PATH" "$file" "$file_id"
    # Move the response file to the results directory
    response_file="${file_id}_response.json"
    if [ -f "$response_file" ]; then
        mv "$response_file" "$RESULTS_DIR/"
    fi
done

echo "All files processed. Results are in $RESULTS_DIR"