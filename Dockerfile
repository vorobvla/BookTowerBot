FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
#Create assets directory for static files
RUN mkdir -p /app/assets  \
    /app/assets/db  \
    /app/assets/map  \
    /app/assets/participants  \
    /app/assets/recs  \
    /app/assets/timetables \
    /app/.auth_db


# Install dependencies first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY bot/ bot/
COPY admin/ admin/
COPY doc/ doc/
COPY auth_approval/ auth_approval/

# Set permissions and create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expose admin console port
EXPOSE 8080

# Entry command to run root main.py with the proper arguments
ENTRYPOINT ["python", "main.py"]
CMD ["--host", "0.0.0.0", "--port", "8080", "--assets-path", "/app/assets"]
