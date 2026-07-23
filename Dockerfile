FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install only the selected local MarkItDown converters. No OCR, cloud parser,
# or plugin dependency is included in this image.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ShieldAI handles raw enterprise context.  Keep the service process separate
# from the root user used while the image is built.
RUN addgroup --system shieldai && adduser --system --ingroup shieldai shieldai
COPY --chown=shieldai:shieldai . .

USER shieldai

# The dashboard and the MCP transport run in separate containers.  Each
# compose service overrides CMD with its respective entry point.
EXPOSE 8787 8765
CMD ["python", "backend/app.py"]
