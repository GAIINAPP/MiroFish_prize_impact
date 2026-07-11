# Build context: ./stock_seed  (see ../docker-compose.yml)
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./stock_seed

EXPOSE 8090
CMD ["uvicorn", "stock_seed.api:app", "--host", "0.0.0.0", "--port", "8090"]
