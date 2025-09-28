# Cloud Run + Supabase Deployment Plan

This document records the plan to migrate the RAG backend from its local Chroma database to Supabase Postgres (pgvector) and to deploy the FastAPI chat service on Google Cloud Run.

## Overview
- Replace local `chroma_db` files with Supabase Postgres + pgvector for embeddings and metadata.
- Containerize the existing FastAPI streaming API and deploy it as a Cloud Run service.
- Manage secrets (Supabase keys, OpenAI key, etc.) via environment variables configured on Cloud Run.

## 1. Move RAG storage to Supabase

### 1.1. Prepare Supabase
1. Enable `pgvector` in the Supabase database: `create extension if not exists vector;`.
2. Create tables:
   - `documents` (id, source, title, metadata JSON).
   - `document_chunks` (id, document_id, content, embedding vector, token_count).
   - Optional: conversation history tables if transcripts need persistence.
3. Ensure the service role has insert/select/update/delete permissions on these tables.

### 1.2. Update the codebase
1. Add a Postgres helper (SQLAlchemy, `asyncpg`, or Supabase client) to read/write chunk data.
2. Update `rag_pipeline.py` (and any helpers) to:
   - Write new chunks + embeddings to Postgres instead of Chroma.
   - Query similar chunks via `embedding <-> query_embedding` ordering and limit K.
3. Modify configuration (`config.py`) to read the connection string from `SUPABASE_DB_URL`.
4. Provide a migration script that exports existing Chroma data and imports it into Supabase.

### 1.3. Testing
1. Point the local app at a Supabase dev database and verify ingestion + retrieval.
2. Run integration tests (e.g., `tmp_test_rag_pipeline.py`) to compare relevance vs. Chroma.

## 2. Deploy API to Cloud Run

### 2.1. Containerize
1. Create/refresh `Dockerfile`:
   - Base image `python:3.x-slim`.
   - Copy `requirements.txt` / install deps.
   - Copy source code.
   - Expose port `$PORT` and run `uvicorn main:app --host 0.0.0.0 --port ${PORT}`.
2. Add `.dockerignore` (exclude `chroma_db`, `uploads`, `.venv`, etc.).

### 2.2. Build + Push
1. `gcloud config set project <PROJECT_ID>`.
2. `gcloud builds submit --tag gcr.io/<PROJECT_ID>/houmy-api:latest` (or use Artifact Registry).

### 2.3. Deploy
1. `gcloud run deploy houmy-api --image gcr.io/<PROJECT_ID>/houmy-api:latest --region <REGION> --platform managed`.
2. Set environment variables:
   - `SUPABASE_DB_URL`
   - `SUPABASE_SERVICE_KEY`
   - `SUPABASE_URL`
   - `OPENAI_API_KEY`
   - other secrets (e.g., document storage bucket URL).
3. Configure concurrency (start with 10), min instances 0, max as needed.
4. Allow unauthenticated if the public frontend calls it directly; otherwise enforce IAM.

### 2.4. Post-deploy
1. Update frontend `.env` / config to call the Cloud Run URL.
2. Verify streaming works end-to-end.
3. Set up logging/monitoring with `gcloud run services logs read` and Cloud Monitoring dashboards.
4. Configure budget alerts in GCP Billing.

## 3. Rollout Checklist
- [ ] Supabase schema created + pgvector enabled.
- [ ] RAG pipeline reading/writing Supabase locally.
- [ ] Migration script seeded initial data.
- [ ] Docker image builds successfully in Cloud Build.
- [ ] Cloud Run deployment responding (health check + streaming test).
- [ ] Frontend updated to use new API endpoint.
- [ ] Alerts/monitoring configured.

