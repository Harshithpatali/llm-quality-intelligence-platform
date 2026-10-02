-- Quality Operations v2 patch
-- Allow repeated blind reviews of the same evaluation trace for calibration
-- and inter-annotator agreement.

do $$
begin
  if exists (
    select 1
    from pg_constraint
    where conname = 'quality_review_queue_trace_id_key'
      and conrelid = 'public.quality_review_queue'::regclass
  ) then
    alter table public.quality_review_queue
      drop constraint quality_review_queue_trace_id_key;
  end if;
end $$;

create index if not exists idx_quality_review_queue_trace_status
  on public.quality_review_queue(trace_id, status, created_at desc);
