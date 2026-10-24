FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN mkdir -p /docs/design /evals/datasets /evals/corpora/milestone_3 /evals/runners /evals/scorers && \
    touch /docs/design/m3-improvement-claim-rule-v1.policy.json \
          /evals/datasets/milestone_3.py \
          /evals/datasets/milestone_3.jsonl \
          /evals/datasets/milestone_3.manifest.json \
          /evals/corpora/milestone_3/manifest.json \
          /evals/corpora/milestone_3/refund-policy.txt \
          /evals/corpora/milestone_3/shipping-policy.txt \
          /evals/corpora/milestone_3/account-security.txt \
          /evals/corpora/milestone_3/billing-policy.txt \
          /evals/runners/milestone_3.py \
          /evals/runners/milestone_3_comparison.py \
          /evals/runners/m3_claim_authority.py \
          /evals/runners/evaluation_ownership.py \
          /evals/runners/ragas_review.py \
          /evals/runners/evaluation.py \
          /evals/scorers/deepeval_cloudflare.py
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "knora.main:app", "--host", "0.0.0.0", "--port", "8000"]
