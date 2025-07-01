# Use Python 3.13 slim image as base
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies in a single layer with cache cleanup
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    wget \
    git \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xvfb \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy only requirements first to leverage Docker layer caching
COPY requirements.txt ./

# Install Python dependencies with caching optimizations
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium --with-deps

# Install MCP servers globally
RUN npm install -g @playwright/mcp@latest @modelcontextprotocol/server-filesystem \
    && npm cache clean --force

# Install Playwright browsers
RUN playwright install chromium --with-deps

# Create output directory
RUN mkdir -p ./output

# Copy source code last to maximize cache hits
COPY src/ ./

# Expose port 8000
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set Playwright environment variables for proper browser discovery
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Start the application with headless mode for cloud deployment
CMD ["python", "-m", "bedrock_agent.web", "--headless"]