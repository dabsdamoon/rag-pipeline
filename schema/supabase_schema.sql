-- Enable pgvector extension once per database
create extension if not exists vector;

-- Canonical source metadata (replaces assets/dict_source_id.json)
create table if not exists public.source_metadata (
  source_id     text primary key,
  name          text not null,
  display_name  text not null,
  source_type   text not null check (source_type in ('book', 'insurance')),
  purchase_link text default '',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index if not exists source_metadata_type_idx
  on public.source_metadata (source_type);

-- Optional registry for document ingestion versions
create table if not exists public.documents (
  id             uuid primary key default gen_random_uuid(),
  source_id      text not null references public.source_metadata(source_id) on delete cascade,
  title          text,
  version        text,
  file_checksum  text,
  created_at     timestamptz not null default now()
);

create index if not exists documents_source_idx
  on public.documents (source_id);

-- Chunk store backed by pgvector embeddings
create table if not exists public.document_chunks (
  id             uuid primary key default gen_random_uuid(),
  document_id    uuid references public.documents(id) on delete cascade,
  source_id      text not null references public.source_metadata(source_id) on delete cascade,
  chunk_index    integer not null,
  content        text not null,
  embedding      vector(1536) not null,
  token_count    integer,
  created_at     timestamptz not null default now()
);

create index if not exists document_chunks_source_idx
  on public.document_chunks (source_id);

-- IVFFlat index for cosine similarity; tune lists based on corpus size
create index if not exists document_chunks_embedding_cosine_idx
  on public.document_chunks
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- Conversation history summaries for personalised chat context
create table if not exists public.history (
  id             uuid primary key default gen_random_uuid(),
  user_id        text not null,
  session_id     text,
  summary        text not null,
  embedding      vector(1536) not null,
  turn_timestamp timestamptz not null default now(),
  created_at     timestamptz not null default now()
);

create index if not exists history_user_idx
  on public.history (user_id);

create index if not exists history_embedding_cosine_idx
  on public.history
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 50);
