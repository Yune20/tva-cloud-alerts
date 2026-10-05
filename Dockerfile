FROM python:3.11-slim

WORKDIR /app

# Install only requests
RUN pip install --no-cache-dir requests

# Copy script
COPY cloud_alerts.py .

# Create non-root user
RUN useradd -m -r appuser && chown -R appuser:appuser /app
USER appuser

# Run
CMD ["python", "-u", "cloud_alerts.py"]
