FROM python:3.11-slim
WORKDIR /app
COPY . .
EXPOSE 8787
CMD ["python", "backend/app.py"]

