# Grid Dispatch Agent - Docker镜像
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY grid_agent/ ./grid_agent/
COPY api/ ./api/
COPY setup.py pyproject.toml .

# Install package
RUN pip install --no-cache-dir -e .

EXPOSE 8000

# Use shell form to see any startup errors
CMD ["python", "-c", "import api.server; print('Server module loaded:', api.server)"]
