# Use the official lightweight Python image.
FROM python:3.11-slim

# Allow statements and log messages to show in Cloud Run logs immediately
ENV PYTHONUNBUFFERED=1 \
    # Cloud Run expects the service to listen on 0.0.0.0:8080
    PORT=8080

# Install system dependencies (if any libraries need them)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create and set the working directory
WORKDIR /app

# Copy only requirements first for caching
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# The command to run your Streamlit app. Cloud Run forwards traffic to port 8080 by default.
CMD ["streamlit", "run", "generate_infographic.py", "--server.port", "8080", "--server.address", "0.0.0.0"] 