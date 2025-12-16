FROM python:3.10-slim as base


ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .


RUN pip install --no-cache-dir Flask==3.1.2 && \
    pip install --no-cache-dir gunicorn==23.0.0 && \
    pip install --no-cache-dir pillow==12.0.0 && \
    pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir numpy==2.1.3 && \
    pip install --no-cache-dir scikit-learn==1.5.2 && \
    pip install --no-cache-dir streamlit==1.39.0 && \
    pip install --no-cache-dir pymongo==4.10.1 && \
    pip install --no-cache-dir requests==2.32.3

COPY flask_app.py .
COPY streamlit_app.py .
COPY model.pt .


ENV MODEL_PATH=/app/model.pt


EXPOSE 5000 8501


HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/')" || exit 1

RUN echo '#!/bin/bash\n\
# Start Flask in background with limited workers\n\
gunicorn --bind 0.0.0.0:5000 \
         --workers 1 \
         --threads 2 \
         --worker-class sync \
         --timeout 120 \
         --max-requests 1000 \
         --max-requests-jitter 100 \
         --preload \
         flask_app:app &\n\
\n\
# Wait for Flask to start\n\
sleep 5\n\
\n\
# Start Streamlit with memory-efficient settings\n\
streamlit run streamlit_app.py \
          --server.port=8501 \
          --server.address=0.0.0.0 \
          --server.headless=true \
          --server.maxUploadSize=10 \
          --server.enableCORS=false \
          --server.enableXsrfProtection=true \
          --browser.gatherUsageStats=false \
          --logger.level=warning\n\
' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]
