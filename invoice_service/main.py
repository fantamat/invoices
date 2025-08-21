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


from utils import replace_null_values



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

CALLBACK_URL = os.environ.get("CALLBACK_URL", "")

PROMPT_SYSTEM = """
You are a finance document parsing assistant. Use the provided **Invoice** response_schema as the only source of field names.
**Return exactly ONE valid JSON object. No explanations.**

Rules:
- **No invention**: if a value isn’t printed or is unreadable, return an **empty value by type** ("" for strings, 0 for numbers, [] for arrays).
- **Preserve original text** (names, item descriptions, addresses). Do not translate.
- **Dates** → YYYY-MM-DD. **Numbers** → '.' as decimal separator, no thousand separators. **Do not round** beyond what is printed, except as defined below.
- **Roles**: Supplier/Issuer vs Buyer/Customer — never swap. For receipts without printed buyer legal data (IČO/DIČ), leave our company empty and set the merchant as counterparty.

Meaning of line fields:
- `unit_price` = NET unit price (without VAT), **4–6 decimals** allowed.
- `ext_price`   = quantity × unit_price (NET), **must be 2 decimals**.
- `total_with_vat` = line gross total (with VAT), **must be 2 decimals**.

**Snapping rule (mandatory, no tolerances):**
- If the document prints a line NET total (base) or an invoice VAT base, set `ext_price` **exactly** to that printed value (2 decimals).
- Then set `unit_price = ext_price / quantity`, rounded to **4–6 decimals**, such that `round(quantity * unit_price, 2) == ext_price`.
- If only a GROSS unit/total is printed **and** a VAT rate is explicitly available, derive NET as `gross/(1+rate/100)` and then apply the snapping rule so the 2-decimal `ext_price` matches the printed base or the derived base.
- If no VAT rate is printed anywhere, **do not derive NET**; keep printed numbers and leave missing NET fields empty by type.

- **Totals**: copy printed totals (2 decimals). **Do NOT fix totals**. If something doesn’t reconcile and values aren’t explicitly available, keep what is printed and leave the rest empty by type.

- **Payment method**: POS cues (MASTERCARD/VISA/Contactless/PIN) → card; “Hotově/Hotovost/Cash” → cash; bank details present (account/IBAN/VS) → bank_transfer.

**Output only the JSON object.**
"""

PROMPT_TEMPLATE_DOCUMENT_TEXT = (
    "The following is text extracted from the document (markdown/plain). "
    "Treat it as authoritative for numbers and identifiers:\n\n{document_text}"
)

PROMPT_UNIFIED_POLICY = """
This document can be an image or PDF; you may receive **page images** and **converted text**.

- **Text-first, image-assisted**: use converted text as primary for numbers/IDs/dates; use images for columns, row alignment, and any OCR-missed text.
- **Line items**: extract exactly what is printed; keep original order. If a receipt aggregates items to one row, output one row. If a description wraps, merge into one description.
- **NET vs GROSS**:
  - Invoices: unit price columns are typically **NET** unless explicitly labeled gross.
  - Receipts: “Cena/j.” or “Cena” is typically **GROSS** unless explicitly “bez DPH/without VAT”.
  - To derive NET from GROSS you must see an explicit VAT rate (line rate or VAT summary). After derivation, apply the **snapping rule** so 2-decimal `ext_price` matches the printed/derived base exactly.
- **Conflicts (text vs image)**: prefer printed numeric values visible on the page; use layout only to align, never to invent numbers.

Follow the **Invoice** response_schema exactly. Missing fields → empty value by type.
"""




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
        model TEXT NOT NULL,
        token_count INTEGER,
        input_token_count INTEGER,
        output_token_count INTEGER,
        thoughts_token_count INTEGER,
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

def save_to_database(file_id: str, file_name: str, file_type: str, 
                    token_count: Optional[int] = None, 
                    input_token_count: Optional[int] = None,
                    output_token_count: Optional[int] = None,
                    thoughts_token_count: Optional[int] = None,
                    model: Optional[str] = None, 
                    response_data: Optional[Dict] = None, 
                    error_message: Optional[str] = None):
    """Save processing data to SQLite database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO invoice_processes 
        (file_id, file_name, file_type, timestamp, model, token_count, input_token_count, output_token_count, thoughts_token_count, response_json, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            file_id,
            file_name,
            file_type,
            datetime.now().isoformat(),
            model,
            token_count,
            input_token_count,
            output_token_count,
            thoughts_token_count,
            json.dumps(response_data) if response_data else None,
            error_message
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"Saved processing data for file {file_name} to database")
    except Exception as e:
        logger.error(f"Error saving to database: {str(e)}")


def generate_response(content, message, model_name):
    response = client.models.generate_content(
        model=model_name,
        contents=content,
        config={
            'response_mime_type': 'application/json',
            'response_schema': Invoice,
        },
    )
    
    invoice: Invoice = response.parsed
    token_count = response.usage_metadata.total_token_count
    input_token_count = response.usage_metadata.prompt_token_count
    output_token_count = response.usage_metadata.candidates_token_count
    thoughts_token_count = response.usage_metadata.thoughts_token_count
    logger.info(message)
    logger.info(f"Tokens: Input tokens: {input_token_count}, Output tokens: {output_token_count}, Thoughts tokens: {thoughts_token_count}, Total tokens: {token_count}")

    return {
        "invoice": replace_null_values(invoice.model_dump()),
        "total_token_count": token_count,
        "input_token_count": input_token_count,
        "output_token_count": output_token_count,
        "thoughts_token_count": thoughts_token_count,
        "model": model_name
    }


def process_image(model_name: str, image_path: str) -> Dict[str, Any]:
    """Process an image using Gemini and extract invoice data"""
    try:
        image = Image.open(image_path)
        
        logger.info(f"Processing image: {Path(image_path).name}")
        # global client
        if not client:
            raise RuntimeError("Gemini client not initialized")

        contents = [PROMPT_SYSTEM, PROMPT_UNIFIED_POLICY, image]

        return generate_response(contents, f"Processing image: {Path(image_path).name}", model_name)

    except Exception as e:
        logger.error(f"Error processing image {image_path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")


def process_pdf(model_name: str, pdf_path: str) -> Dict[str, Any]:
    """Process a PDF document using Gemini"""
    try:
        # Use MarkItDown to convert PDF to markdown text
        md = MarkItDown(enable_plugins=False)
        with open(pdf_path, 'rb') as f:
            result = md.convert_stream(f, mime_type='application/pdf')
        
        markdown_text = result.text_content or ""
        logger.info(f"PDF converted to markdown text using MarkItDown")
        
        # Also convert PDF to image for visual analysis
        pages = convert_from_path(pdf_path)
        if len(pages) > 5:
            pages = pages[:5]
            logger.info(f"PDF has more than 5 pages, limiting to first 5 pages")

        contents: List[Any] = [
            PROMPT_SYSTEM,
            PROMPT_UNIFIED_POLICY,
            PROMPT_TEMPLATE_DOCUMENT_TEXT.format(document_text=markdown_text[:8000]),
        ]
        contents.extend(pages)

        return generate_response(contents, f"Processing PDF: {Path(pdf_path).name}", model_name)

    except Exception as e:
        logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


def process_docx(model_name: str, docx_path: str) -> Dict[str, Any]:
    """Process a DOCX document using Gemini"""
    try:
        # Use MarkItDown to convert DOCX to markdown text
        md = MarkItDown(enable_plugins=False)
        with open(docx_path, 'rb') as f:
            result = md.convert_stream(f, mime_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        
        markdown_text = result.text_content or ""
        logger.info(f"DOCX converted to markdown text using MarkItDown")

        contents = [
            PROMPT_SYSTEM,
            PROMPT_UNIFIED_POLICY,
            PROMPT_TEMPLATE_DOCUMENT_TEXT.format(document_text=markdown_text[:8000]),
        ]

        return generate_response(contents, f"Processing DOCX: {Path(docx_path).name}", model_name)

    except Exception as e:
        logger.error(f"Error processing DOCX {docx_path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing DOCX: {str(e)}")


@app.post("/invoice", response_class=JSONResponse)
async def process_invoice(file: UploadFile = File(...), file_id: str = Form(...), model_name: str = Form(...)):
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
                result = process_image(model_name, temp_file_path)
                file_type = "image"
            elif file_extension == 'pdf':
                result = process_pdf(model_name, temp_file_path)
                file_type = "pdf"
            elif file_extension == 'docx':
                result = process_docx(model_name, temp_file_path)
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
                model=model_name,
                token_count=result.get("total_token_count"),
                input_token_count=result.get("input_token_count"),
                output_token_count=result.get("output_token_count"),
                thoughts_token_count=result.get("thoughts_token_count"),
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
async def process_invoice_async(file: UploadFile = File(...), file_id: str = Form(...), model_name: str = Form(...)):
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
                model_name,
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

async def _process_and_callback(model_name, temp_file_path, file_extension, file_id, filename, callback_url):
    file_type = None
    result = None
    error_message = None
    try:
        if file_extension in ['jpg', 'jpeg', 'png']:
            result = process_image(model_name, temp_file_path)
            file_type = "image"
        elif file_extension == 'pdf':
            result = process_pdf(model_name, temp_file_path)
            file_type = "pdf"
        elif file_extension == 'docx':
            result = process_docx(model_name, temp_file_path)
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
            model=model_name,
            token_count=result.get("total_token_count") if result else None,
            input_token_count=result.get("input_token_count") if result else None,
            output_token_count=result.get("output_token_count") if result else None,
            thoughts_token_count=result.get("thoughts_token_count") if result else None,
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
    uvicorn.run("main:app", host="0.0.0.0", port=8007, reload=True)
