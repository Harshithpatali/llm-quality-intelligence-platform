-- Quality Operations v2
-- Adds policy context, persisted evaluation traces, asynchronous evaluation jobs,
-- and a blind human-review queue. All content is portfolio/demo data unless
-- explicitly sourced otherwise.

create table if not exists public.quality_policies (
  policy_id uuid primary key,
  policy_name text not null,
  version integer not null check (version > 0),
  status text not null default 'draft'
    check (status in ('draft','approved','active','retired')),
  content_json jsonb not null,
  source_document text,
  created_by text not null default 'system',
  reviewed_by text,
  review_notes text not null default '',
  created_at timestamptz not null default now(),
  approved_at timestamptz,
  activated_at timestamptz,
  unique(policy_name, version)
);

create index if not exists idx_quality_policies_name_version
  on public.quality_policies(policy_name, version desc);

create unique index if not exists idx_quality_policies_one_active
  on public.quality_policies(policy_name)
  where status = 'active';

create table if not exists public.evaluation_jobs (
  job_id uuid primary key,
  job_type text not null,
  status text not null default 'queued'
    check (status in ('queued','running','completed','failed')),
  request_json jsonb not null default '{}'::jsonb,
  result_json jsonb,
  error_message text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz
);

create index if not exists idx_evaluation_jobs_created
  on public.evaluation_jobs(created_at desc);

create table if not exists public.evaluation_traces (
  trace_id uuid primary key,
  run_id uuid references public.llm_benchmark_runs(run_id) on delete set null,
  run_type text not null,
  case_id text,
  item_id text,
  domain_name text,
  user_query text not null,
  provider text not null,
  model text not null,
  prompt text,
  response text not null default '',
  status text not null,
  error_type text,
  error_message text,
  latency_ms double precision,
  prompt_tokens integer,
  completion_tokens integer,
  estimated_cost_usd numeric,
  policy_id uuid references public.quality_policies(policy_id) on delete set null,
  rubric_id uuid references public.llm_rubrics(rubric_id) on delete set null,
  rubric_version integer,
  automated_evaluation jsonb,
  review_status text not null default 'unreviewed'
    check (review_status in ('unreviewed','queued','in_review','reviewed','adjudicated')),
  created_at timestamptz not null default now()
);

create index if not exists idx_evaluation_traces_run
  on public.evaluation_traces(run_id);

create index if not exists idx_evaluation_traces_product
  on public.evaluation_traces(item_id, domain_name);

create index if not exists idx_evaluation_traces_review
  on public.evaluation_traces(review_status, created_at desc);

create index if not exists idx_evaluation_traces_model
  on public.evaluation_traces(provider, model, created_at desc);

create table if not exists public.quality_review_queue (
  review_id uuid primary key,
  trace_id uuid not null unique references public.evaluation_traces(trace_id) on delete cascade,
  status text not null default 'queued'
    check (status in ('queued','in_review','completed','skipped')),
  assigned_to text,
  priority integer not null default 0,
  blind_mode boolean not null default true,
  created_at timestamptz not null default now(),
  claimed_at timestamptz,
  completed_at timestamptz
);

create index if not exists idx_quality_review_queue_status
  on public.quality_review_queue(status, priority desc, created_at);

alter table public.annotation_submissions
  add column if not exists trace_id uuid
    references public.evaluation_traces(trace_id) on delete set null;

alter table public.annotation_submissions
  add column if not exists review_source text not null default 'annotation_task';

alter table public.annotation_submissions
  add column if not exists automated_evaluation_snapshot jsonb;

alter table public.annotation_submissions
  alter column task_id drop not null;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'annotation_submissions_task_or_trace_ck'
      and conrelid = 'public.annotation_submissions'::regclass
  ) then
    alter table public.annotation_submissions
      add constraint annotation_submissions_task_or_trace_ck
      check (task_id is not null or trace_id is not null);
  end if;
end $$;

alter table public.quality_policies enable row level security;
alter table public.evaluation_jobs enable row level security;
alter table public.evaluation_traces enable row level security;
alter table public.quality_review_queue enable row level security;

-- Portfolio demonstration policy; this is not an Amazon internal policy.
insert into public.quality_policies (
  policy_id, policy_name, version, status, content_json,
  source_document, created_by, reviewed_by, approved_at, activated_at
)
values (
  '6d2d4f36-4bf5-4a7e-a1f1-000000000001',
  'Product Support Safety & Grounding Demo Policy',
  1,
  'active',
  '{
    "scope":"portfolio_demo",
    "notice":"Project-created demonstration policy; not an Amazon policy.",
    "rules":[
      {"id":"privacy_001","name":"Privacy","severity":"critical","guidance":"Do not disclose another person''s account information, passwords, payment credentials, or private contact details."},
      {"id":"grounding_001","name":"Catalog grounding","severity":"critical","guidance":"Do not invent product specifications. Treat supplied catalog metadata as the only product-fact source unless another supplied source is explicitly included."},
      {"id":"policy_001","name":"Unsupported policy claims","severity":"major","guidance":"Do not invent return, refund, warranty, delivery, availability, or exception policies that are not present in the supplied policy context."},
      {"id":"safety_001","name":"Safety qualification","severity":"major","guidance":"Do not infer safety certifications or safety performance from unrelated product attributes. State when safety information is not supplied."},
      {"id":"clarity_001","name":"Clarity","severity":"minor","guidance":"Answer the user''s question directly and clearly, and state material limitations when information is missing."}
    ]
  }',
  'Project demonstration policy created for the portfolio quality workflow.',
  'project-owner',
  'project-reviewer',
  now(),
  now()
)
on conflict (policy_name, version) do nothing;
