FROM python:3.9-slim

# nonroot
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/instance && \
    chown -R appuser:appuser /app

USER appuser

ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app
ENV FLASK_DEBUG=0

EXPOSE 5000

CMD ["python", "-u", "app.py"]
