import os
import tempfile
import logging
import sqlite3
import json
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Optional, List, Any, Union
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse, Response
import uvicorn
from PIL import Image
from google import genai
from markitdown import MarkItDown  # Microsoft's library for converting documents to markdown
from pdf2image import convert_from_path

from invoice_types import Invoice

from contextlib import asynccontextmanager
import httpx
import asyncio


# Configure logging
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / "invoice_service.log"

# Create logger
logger = logging.getLogger("invoice_service")
logger.setLevel(logging.INFO)

# Setup SQLite database
DB_DIR = Path(os.environ.get("DB_LOCATION", "db"))
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "invoices.db"

MODEL_NAME = os.environ.get("GEMINI_MODEL", "")

CALLBACK_URL = os.environ.get("GEMINI_CALLBACK_URL", "")

def setup_database():
    """Initialize the SQLite database with required tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
      # Create table for storing invoice processing data
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS invoice_processes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT NOT NULL,
        file_name TEXT NOT NULL,
        file_type TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        token_count INTEGER,
        response_json TEXT,
        error_message TEXT
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")

# Initialize database on module load
setup_database()

# Create handlers
file_handler = RotatingFileHandler(
    log_file, 
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5
)
console_handler = logging.StreamHandler()

# Create formatters and add it to handlers
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(log_format)
console_handler.setFormatter(log_format)

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)



# Initialize Google Gemini client
client = None  # Will be initialized on startup




@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Google Gemini client
    global client
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable not set")
        raise RuntimeError("GEMINI_API_KEY environment variable not set")

    if not MODEL_NAME:
        logger.error("GEMINI_MODEL environment variable not set")
        raise RuntimeError("GEMINI_MODEL environment variable not set")

    client = genai.Client(api_key=api_key)
    logger.info("Google Gemini client initialized")
    
    yield  # This is where the app runs
    
    # Shutdown: Clean up resources if needed
    # No cleanup needed for the Gemini client

app = FastAPI(
    title="Invoice Processing Service",
    description="Service for extracting structured data from invoice images or documents",
    version="1.0.0",
    lifespan=lifespan
)

def save_to_database(file_id: str, file_name: str, file_type: str, token_count: Optional[int] = None, 
                    request_data: Optional[Dict] = None, response_data: Optional[Dict] = None, 
                    error_message: Optional[str] = None):
    """Save processing data to SQLite database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO invoice_processes 
        (file_id, file_name, file_type, timestamp, token_count, response_json, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            file_id,
            file_name,
            file_type,
            datetime.now().isoformat(),
            token_count,
            json.dumps(response_data) if response_data else None,
            error_message
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"Saved processing data for file {file_name} to database")
    except Exception as e:
        logger.error(f"Error saving to database: {str(e)}")


def process_image(image_path: str) -> Dict[str, Any]:
    """Process an image using Gemini and extract invoice data"""
    try:
        image = Image.open(image_path)
        
        logger.info(f"Processing image: {Path(image_path).name}")
        # global client
        if not client:
            raise RuntimeError("Gemini client not initialized")
        
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[image, "Extract the structured data from the image in the given JSON format."],
            config={
                'response_mime_type': 'application/json',
                'response_schema': Invoice,
            },
        )
        
        invoice: Invoice = response.parsed
        token_count = response.usage_metadata.total_token_count
        
        # Log token usage
        logger.info(f"File processed: {Path(image_path).name}, tokens used: {token_count}")
        
        return {
            "invoice": invoice.model_dump(),
            "total_token_count": token_count,
        }
    except Exception as e:
        logger.error(f"Error processing image {image_path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")


def process_pdf(pdf_path: str) -> Dict[str, Any]:
    """Process a PDF document using Gemini"""
    try:
        # Use MarkItDown to convert PDF to markdown text
        md = MarkItDown(enable_plugins=False)
        with open(pdf_path, 'rb') as f:
            result = md.convert_stream(f, mime_type='application/pdf')
        
        markdown_text = result.text_content
        logger.info(f"PDF converted to markdown text using MarkItDown")
        
        # Also convert PDF to image for visual analysis
        contents = convert_from_path(pdf_path)
        if len(contents) > 5:
            contents = contents[:5]  # Limit to first 5 pages
            logger.info(f"PDF has more than 5 pages, limiting to first 5 pages")
        
        contents.append(
            f"Extract the structured invoice data from this document. The document contains the following text:\n\n{markdown_text[:4000]}"
        )
        contents.append("Extract the structured data in the given JSON format.")
        
        # Process with Gemini using both the markdown text and image
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config={
                'response_mime_type': 'application/json',
                'response_schema': Invoice,
            },
        )
        
        invoice: Invoice = response.parsed
        token_count = response.usage_metadata.total_token_count
        
        # Log token usage
        logger.info(f"PDF processed: {Path(pdf_path).name}, tokens used: {token_count}")
        
        return {
            "invoice": invoice.model_dump(),
            "total_token_count": token_count,
        }
    except Exception as e:
        logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


def process_docx(docx_path: str) -> Dict[str, Any]:
    """Process a DOCX document using Gemini"""
    try:
        # Use MarkItDown to convert DOCX to markdown text
        md = MarkItDown(enable_plugins=False)
        with open(docx_path, 'rb') as f:
            result = md.convert_stream(f, mime_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        
        markdown_text = result.text_content
        logger.info(f"DOCX converted to markdown text using MarkItDown")
        
        # Process with Gemini
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                f"Extract the structured invoice data from this document. The document contains the following text:\n\n{markdown_text[:4000]}",  # Limit text length
                "Extract the structured data in the given JSON format."
            ],
            config={
                'response_mime_type': 'application/json',
                'response_schema': Invoice,
            },
        )
        
        invoice: Invoice = response.parsed
        token_count = response.usage_metadata.total_token_count
        
        # Log token usage
        logger.info(f"DOCX processed: {Path(docx_path).name}, tokens used: {token_count}")
        
        return {
            "invoice": invoice.model_dump(),
            "total_token_count": token_count,
        }
    except Exception as e:
        logger.error(f"Error processing DOCX {docx_path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing DOCX: {str(e)}")


@app.post("/invoice", response_class=JSONResponse)
async def process_invoice(file: UploadFile = File(...), file_id: str = Form(...)):
    """
    Process an invoice document (image, PDF, or DOCX) and extract structured data
    """
    # Check file type
    file_extension = file.filename.lower().split('.')[-1]
    
    # Save uploaded file temporarily
    temp_file_path = tempfile.mktemp(suffix=f'.{file_extension}')    
    try:
        # Read the uploaded file content
        content = await file.read()
        
        # Save to temporary file for processing
        with open(temp_file_path, 'wb') as temp_file:
            temp_file.write(content)
        
        # Process file based on type
        try:
            if file_extension in ['jpg', 'jpeg', 'png']:
                result = process_image(temp_file_path)
                file_type = "image"
            elif file_extension == 'pdf':
                result = process_pdf(temp_file_path)
                file_type = "pdf"
            elif file_extension == 'docx':
                result = process_docx(temp_file_path)
                file_type = "docx"
            else:
                error_msg = f"Unsupported file format: {file_extension}"                # Log the error to database
                raise HTTPException(status_code=400, detail=error_msg)
              # Add file_id to the result
            result["file_id"] = file_id
              # Store processing data in database
            save_to_database(
                file_id=file_id,
                file_name=file.filename,
                file_type=file_type,
                token_count=result.get("total_token_count"),
                request_data={"filename": file.filename, "file_id": file_id},
                response_data=result
            )
            
            return result
        except HTTPException as e:  # Handle HTTP exceptions raised during processing
            logger.error(f"HTTP error processing file {file.filename}: {str(e)}")
            raise e
        except Exception as e:            # Log any other exceptions
            error_msg = f"Error processing file: {str(e)}"
            raise HTTPException(status_code=500, detail=error_msg)
    
    finally:
        # Clean up the temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@app.post("/invoice/async", response_class=JSONResponse)
async def process_invoice_async(file: UploadFile = File(...), file_id: str = Form(...)):
    """
    Asynchronously process an invoice document and immediately respond.
    The result will be sent to the configured CALLBACK_URL.
    """
    file_extension = file.filename.lower().split('.')[-1]
    temp_file_path = tempfile.mktemp(suffix=f'.{file_extension}')
    try:
        content = await file.read()
        with open(temp_file_path, 'wb') as temp_file:
            temp_file.write(content)

        # Respond immediately
        response_data = {"status": "processing", "file_id": file_id, "filename": file.filename}
        asyncio.create_task(
            _process_and_callback(
                temp_file_path,
                file_extension,
                file_id,
                file.filename,
                CALLBACK_URL
            )
        )
        return response_data
    finally:
        # Do not remove temp file here; cleanup is handled in the background task
        pass

async def _process_and_callback(temp_file_path, file_extension, file_id, filename, callback_url):
    file_type = None
    result = None
    error_message = None
    try:
        if file_extension in ['jpg', 'jpeg', 'png']:
            result = process_image(temp_file_path)
            file_type = "image"
        elif file_extension == 'pdf':
            result = process_pdf(temp_file_path)
            file_type = "pdf"
        elif file_extension == 'docx':
            result = process_docx(temp_file_path)
            file_type = "docx"
        else:
            error_message = f"Unsupported file format: {file_extension}"
            result = {"error": error_message}
            file_type = "unsupported"

        if result and "invoice" in result:
            result["file_id"] = file_id

        # Save to database
        save_to_database(
            file_id=file_id,
            file_name=filename,
            file_type=file_type,
            token_count=result.get("total_token_count") if result else None,
            request_data={"filename": filename, "file_id": file_id},
            response_data=result,
            error_message=error_message
        )

        # Send callback if URL is set
        if callback_url:
            async with httpx.AsyncClient(timeout=30) as client:
                await client.post(callback_url, json=result if result else {"error": error_message, "file_id": file_id})
        else:
            logger.warning("No CALLBACK_URL configured; skipping callback.")
    except Exception as e:
        logger.error(f"Async processing error for file {filename}: {str(e)}")
        # Attempt to send error callback
        if callback_url:
            async with httpx.AsyncClient(timeout=30) as client:
                await client.post(callback_url, json={"error": str(e), "file_id": file_id})
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@app.get("/healthcheck")
async def healthcheck():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/history")
async def get_processing_history(limit: int = 50, offset: int = 0, file_id: Optional[str] = None):
    """
    Retrieve processing history from the database
    
    Parameters:
    - limit: Maximum number of records to return (default: 50)
    - offset: Offset for pagination (default: 0)
    - file_id: Optional filter by file ID
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        cursor = conn.cursor()
        
        # Build query based on parameters
        query = "SELECT * FROM invoice_processes"
        params = []
        
        if file_id:
            query += " WHERE file_id = ?"
            params.append(file_id)
            
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Count total records for pagination info
        count_query = "SELECT COUNT(*) as count FROM invoice_processes"
        if file_id:
            count_query += " WHERE file_id = ?"
            cursor.execute(count_query, [file_id])
        else:
            cursor.execute(count_query)
            
        total_count = cursor.fetchone()["count"]
          # Convert rows to list of dicts
        results = []
        for row in rows:
            item = dict(row)            # Parse JSON strings back to objects
            if item["response_json"]:
                item["response_json"] = json.loads(item["response_json"])
                
            results.append(item)
            
        conn.close()
        
        return {
            "total": total_count,
            "offset": offset,
            "limit": limit,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error retrieving history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving processing history: {str(e)}")


@app.delete("/history/{record_id}")
async def delete_history_record(record_id: int):
    """Delete a specific history record from the database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if record exists
        cursor.execute("SELECT id FROM invoice_processes WHERE id = ?", [record_id])
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Record with ID {record_id} not found")
        
        cursor.execute("DELETE FROM invoice_processes WHERE id = ?", [record_id])
        conn.commit()
        conn.close()
        
        return {"message": f"Record {record_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting record: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting record: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
