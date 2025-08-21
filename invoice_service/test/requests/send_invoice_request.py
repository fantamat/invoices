#!/usr/bin/env python
"""
Example script to send a request to the invoice processing service.
This script demonstrates how to send an image, PDF or DOCX file for processing.

Usage: 
    python send_invoice_request.py <file_path> <file_id>

Example:
    python send_invoice_request.py "../../data/invoices/faktura.png" "invoice-123"
"""

import os
import sys
import json
import requests
import mimetypes
from pathlib import Path

# Service URL - change this to match your deployment
SERVICE_URL = "http://localhost:8007"


def get_mimetype(file_path):
    """Get mimetype of a file based on its extension"""
    mime, _ = mimetypes.guess_type(file_path)
    if mime is None:
        # Default to application/octet-stream if mimetype can't be determined
        mime = "application/octet-stream"
    return mime


def send_invoice_request(model_name, file_path, file_id):
    """Send an invoice file to the processing service"""
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    # Prepare the files and data for the request
    with open(file_path, "rb") as f:
        file_content = f.read()
        
    file_name = os.path.basename(file_path)
    mime_type = get_mimetype(file_path)
    
    files = {
        "file": (file_name, file_content, mime_type)
    }
    
    data = {
        "file_id": file_id,
        "model_name": model_name,
    }
    
    # Send the request
    url = f"{SERVICE_URL}/invoice"
    print(f"Sending {file_path} to {url} with file_id {file_id}")
    
    try:
        response = requests.post(url, files=files, data=data)
        response.raise_for_status()  # Raise an exception for non-2xx responses
        
        # Pretty print the response JSON
        result = response.json()
        print("\nResponse:")
        print(json.dumps(result, indent=2))
        
        # Save the response to a file
        output_file = Path(f"{file_id}_response.json")
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
            
        print(f"\nResponse saved to {output_file.absolute()}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        if hasattr(e, "response") and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"Server response: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Server response: {e.response.text}")


def query_history(file_id=None, limit=10, offset=0):
    """Query the processing history from the service"""
    url = f"{SERVICE_URL}/history"
    params = {
        "limit": limit,
        "offset": offset
    }
    
    if file_id:
        params["file_id"] = file_id
        
    print(f"Querying history from {url}")
    if file_id:
        print(f"Filtering by file_id: {file_id}")
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        # Pretty print the response JSON
        result = response.json()
        print("\nHistory Results:")
        print(f"Total records: {result['total']}")
        print(f"Showing {len(result['results'])} records (offset: {result['offset']}, limit: {result['limit']})")
        
        for i, record in enumerate(result['results']):
            print(f"\nRecord #{i+1}:")
            print(f"  ID: {record['id']}")
            print(f"  File: {record['file_name']} (type: {record['file_type']})")
            print(f"  File ID: {record['file_id']}")
            print(f"  Timestamp: {record['timestamp']}")
            print(f"  Token count: {record['token_count']}")
            if record['error_message']:
                print(f"  Error: {record['error_message']}")
                
        # Save the response to a file
        output_file = Path("history_response.json")
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
            
        print(f"\nHistory results saved to {output_file.absolute()}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error querying history: {e}")
        if hasattr(e, "response") and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"Server response: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Server response: {e.response.text}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Process invoice: python send_invoice_request.py <file_path> <file_id>")
        print("  Query history: python send_invoice_request.py --history [file_id] [limit] [offset]")
        sys.exit(1)
        
    # Check if querying history
    if sys.argv[1] == "--history":
        file_id = sys.argv[2] if len(sys.argv) > 2 else None
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        offset = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        query_history(file_id, limit, offset)
    else:
        # Process invoice
        file_path = sys.argv[1]
        file_id = sys.argv[2] if len(sys.argv) > 2 else f"invoice-{os.path.basename(file_path)}"
        model_name = sys.argv[3] if len(sys.argv) > 3 else "gemini-2.5-pro-preview-03-25"

        send_invoice_request(model_name, file_path, file_id)
