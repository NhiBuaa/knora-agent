FROM python:3.12-slim

WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/src ./src
COPY evals ../evals
COPY docs/design/m3-improvement-claim-rule-v1.policy.json ../docs/design/m3-improvement-claim-rule-v1.policy.json
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "knora.main:app", "--host", "0.0.0.0", "--port", "8000"]
