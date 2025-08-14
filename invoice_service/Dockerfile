FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBUG=False 

WORKDIR /app

# Install system dependencies for PDF processing
RUN apt-get update && apt-get install -y \
    poppler-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .

# Install Python dependencies with uv
RUN pip install uv && \
    uv venv --python=python3.11 && \
    uv pip install -r requirements.txt && \
    pip uninstall -y uv


# activate the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Create a directory for logs
RUN mkdir -p logs

COPY main.py .
COPY invoice_types.py .


# Expose port for the FastAPI application
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
