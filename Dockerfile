# Telegram Trading Signals Bot - Docker image
# Python 3.11 slim for small image size
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY config.py main.py webhook_server.py signal_processor.py telegram_notifier.py coinglass_poller.py ./

# Default port 80 for TradingView HTTP webhooks
EXPOSE 80

# Run the bot (FastAPI + Uvicorn)
CMD ["python", "main.py"]
