# Use the official Python base image
FROM python:3.9-slim

# Set environment variables to avoid writing .pyc files and to ensure proper buffering
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Install required system dependencies
RUN apt-get update && \
    apt-get install -y \
    wget \
    curl \
    unzip \
    sudo \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    firefox-esr \
    && rm -rf /var/lib/apt/lists/*

# Install geckodriver (for Selenium Firefox)
RUN wget https://github.com/mozilla/geckodriver/releases/download/v0.35.0/geckodriver-v0.35.0-linux64.tar.gz -O /tmp/geckodriver.tar.gz && \
    tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin && \
    chmod +x /usr/local/bin/geckodriver && \
    rm /tmp/geckodriver.tar.gz

# Create and set the working directory
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . /app/

# Expose the port that the Flask app will run on
EXPOSE 5000

# Start the Flask app when the container is run
CMD ["flask", "run", "--host", "0.0.0.0", "--port", "5000"]
