-- Versioned, human-governed rubrics. Generated content is a draft, never active by default.
create table if not exists public.llm_rubrics (
  rubric_id uuid primary key,
  rubric_name text not null,
  version integer not null check (version > 0),
  status text not null default 'draft' check (status in ('draft','approved','active','retired')),
  rubric_json jsonb not null,
  source_document text,
  generation_notes text not null default '',
  created_by text not null default 'system',
  reviewed_by text,
  review_notes text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  approved_at timestamptz,
  activated_at timestamptz,
  unique (rubric_name, version)
);
create index if not exists idx_llm_rubrics_name_version on public.llm_rubrics(rubric_name, version desc);
create unique index if not exists idx_llm_rubrics_one_active on public.llm_rubrics(rubric_name) where status = 'active';
alter table public.llm_rubrics enable row level security;
