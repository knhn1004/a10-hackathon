# Dockerfile for sandbox container
FROM python:3.11-slim

WORKDIR /app

# Install dependencies for code execution
RUN pip install --no-cache-dir \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    matplotlib==3.8.2 \
    numpy==1.26.3 \
    pandas==2.2.0 \
    requests==2.31.0 \
    pillow==10.2.0

# Copy sandbox server
COPY sandbox_server.py .

# Expose port
EXPOSE 8000

# Run server
CMD ["python", "sandbox_server.py"]

