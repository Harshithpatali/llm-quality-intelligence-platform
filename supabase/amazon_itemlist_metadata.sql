-- Catalog grounding dataset supplied for the portfolio project.
-- This is product/item-list metadata, not Amazon internal customer or support data.

create table if not exists public.amazon_itemlist_metadata (
    item_id text not null,
    domain_name text not null,
    item_name text,
    brand text,
    color text,
    product_type text,
    style text,
    material text,
    model_number text,
    bullet_points text[],
    bullet_points_text text,
    country text,
    num_bullets integer,
    source_dataset text not null default 'final_clean_amazon.jsonl',
    created_at timestamptz not null default now(),
    primary key (item_id, domain_name)
);

alter table public.amazon_itemlist_metadata enable row level security;

create index if not exists amazon_itemlist_metadata_brand_idx
    on public.amazon_itemlist_metadata (brand);
create index if not exists amazon_itemlist_metadata_product_type_idx
    on public.amazon_itemlist_metadata (product_type);
create index if not exists amazon_itemlist_metadata_domain_idx
    on public.amazon_itemlist_metadata (domain_name);
create index if not exists amazon_itemlist_metadata_item_name_idx
    on public.amazon_itemlist_metadata using gin (
        to_tsvector('simple', coalesce(item_name, ''))
    );

comment on table public.amazon_itemlist_metadata is
    'Amazon item-list product metadata supplied for the portfolio project; not Amazon internal customer or support data.';
