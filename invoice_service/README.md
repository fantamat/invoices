# Invoice Processing Service

A FastAPI service that processes invoice documents (images, PDFs, or DOCX files) and extracts structured data using Google's Gemini AI model.

## Features

- Process invoice images (JPG, PNG)
- Process PDF documents using Microsoft's markitdown library for text extraction and rendering
- Process DOCX documents using Microsoft's markitdown library for text extraction
- Extract structured invoice data in JSON format
- Log token usage to files
- SQLite database storage for all processing inputs and outputs
- REST API endpoints for querying processing history

## Requirements

- Python 3.12+
- Google Gemini API key
- Google Gemini model name

## Installation

1. Clone the repository
2. Install the dependencies:

```bash
pip install -r requirements.txt
```

Or use uv for faster package installation:

```bash
pip install uv
uv pip install -r requirements.txt
```

3. Set up your environment variables:

```bash
# On Windows PowerShell
$env:GEMINI_API_KEY="your-api-key-here"
$env:GEMINI_MODEL="gemini-2.5-pro-preview-03-25" # Or your preferred Gemini model
$env:DB_LOCATION="db"

# On Linux/macOS
export GEMINI_API_KEY="your-api-key-here"
export GEMINI_MODEL="gemini-2.5-pro-preview-03-25" # Or your preferred Gemini model
export DB_LOCATION="db"
```

## Usage

Start the service in development mode:

```bash
uvicorn main:app --reload --port 8080
```

The service will be available at http://localhost:8080

In production mode with Docker, the service runs on port 8000.

### API Endpoints

#### POST /invoice

Upload an invoice file to be processed:

```bash
# For development mode
curl -X POST -F "file=@/path/to/invoice.pdf" -F "file_id=your-file-id" http://localhost:8080/invoice

# For Docker/Podman container
curl -X POST -F "file=@/path/to/invoice.pdf" -F "file_id=your-file-id" http://localhost:8000/invoice
```

#### GET /healthcheck

Check if the service is running correctly:

```bash
# For development mode
curl http://localhost:8080/healthcheck

# For Docker/Podman container
curl http://localhost:8000/healthcheck
```

#### GET /history

Retrieve processing history:

```bash
# Get the latest 50 records (development mode)
curl http://localhost:8080/history
# Get the latest 50 records (Docker/Podman)
curl http://localhost:8000/history

# Pagination with limit and offset (development mode)
curl http://localhost:8080/history?limit=10&offset=20
# Pagination with limit and offset (Docker/Podman)
curl http://localhost:8000/history?limit=10&offset=20

# Filter by file_id (development mode)
curl http://localhost:8080/history?file_id=your-file-id
# Filter by file_id (Docker/Podman)
curl http://localhost:8000/history?file_id=your-file-id
```

#### DELETE /history/{record_id}

Delete a specific record from the history:

```bash
# Development mode
curl -X DELETE http://localhost:8080/history/123

# Docker/Podman
curl -X DELETE http://localhost:8000/history/123
```

## API Documentation

Interactive API documentation is available at:

### Development Mode
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

### Docker/Podman
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Docker and Podman

You can also run this service using Docker or Podman:

### Docker

```bash
# Build the Docker image
docker build -t invoice-service .

# Run the Docker container
docker run -p 8000:8000 -e GEMINI_API_KEY="your-api-key-here" -e GEMINI_MODEL="gemini-2.5-pro-preview-03-25" invoice-service
```

### Podman

```bash
# Build the image using Podman
podman build -t invoice-service .

# Run the container with Podman
podman run -p 8000:8000 --env-file .env invoice-service
```

When using Podman with an environment file, make sure to create a `.env` file with the following content:

```
GEMINI_API_KEY=your-api-key-here
GEMINI_MODEL=gemini-2.5-pro-preview-03-25
```

### Volumes

To persist database files and logs outside the container, use Docker or Podman volumes:

```bash
# Docker example with named volumes
docker run -p 8000:8000 \
    -e GEMINI_API_KEY="your-api-key-here" \
    -e GEMINI_MODEL="gemini-2.5-pro-preview-03-25" \
    -v invoice_db:/app/db \
    -v invoice_logs:/app/logs \
    invoice-service

# Podman example with host directories
podman run -p 8000:8000 \
    --env-file .env \
    -v /host/path/to/db:/app/db \
    -v /host/path/to/logs:/app/logs \
    invoice-service
```

Replace `/host/path/to/db` and `/host/path/to/logs` with your preferred host directories.