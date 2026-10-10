
# Python runtime matching our reference trained model
FROM python:3.13-slim

# Configure Python for containers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set the application directory
WORKDIR /app

# Install Python dependencies
COPY requirements-inference.txt ./requirements-inference.txt

RUN python -m pip install --no-cache-dir \
    -r requirements-inference.txt

# Copy only files needed for inference
COPY src/api.py src/preprocess.py ./src/
COPY models/incident_model.joblib ./models/incident_model.joblib

# Run the application as a non-root user
RUN useradd --create-home --uid 10001 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Document the API port
EXPOSE 8000

# Container health check
HEALTHCHECK --interval=30s --timeout=5s \
    --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

# Start FastAPI through Uvicorn
CMD ["python", "-m", "uvicorn", "src.api:app", \
     "--host", "0.0.0.0", "--port", "8000"]
