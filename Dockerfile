FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
# Render injects $PORT. BASE_PATH/ROOT_PATH set via dashboard env vars.
CMD ["sh","-c","uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
