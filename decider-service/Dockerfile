FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY model ./model

EXPOSE 6009

# Switch to ML-only decider (no rule-based logic)
CMD ["uvicorn", "app.main_ml_only:app", "--host", "0.0.0.0", "--port", "6009"]
