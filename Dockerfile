FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TRADING_LAB_DATA_DIR=/data \
    TRADING_LAB_ONLINE_MODE=1

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
RUN groupadd --gid 10001 tradinglab && \
    useradd --uid 10001 --gid 10001 --no-create-home tradinglab && \
    mkdir -p /data/reference_docs/shared /data/reference_docs/workspaces /app/reference_docs/shared /app/reference_docs/workspaces && \
    chown -R tradinglab:tradinglab /data /app/reference_docs
USER 10001:10001

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import os; from urllib.request import urlopen; urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8501') + '/_stcore/health', timeout=3)" || exit 1
CMD ["sh", "-c", "python -m streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.headless=true --server.enableXsrfProtection=true --server.enableCORS=true --browser.gatherUsageStats=false"]
