create extension if not exists pgcrypto;

create table owners (
  id uuid primary key default gen_random_uuid(),
  channel text not null default 'whatsapp',
  external_id text not null,
  shop_name text,
  language text not null default 'id' check (language in ('id','en')),
  created_at timestamptz not null default now(),
  unique (channel, external_id)
);

create table transactions (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references owners(id) on delete cascade,
  type text not null check (type in ('sale','purchase','unknown')),
  tx_date date not null,
  total bigint,
  source text not null check (source in ('photo','voice','text')),
  original_extraction jsonb,
  edited boolean not null default false,
  total_mismatch_confirmed boolean not null default false,
  confirmed_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
create index on transactions (owner_id, tx_date);

create table transaction_items (
  id uuid primary key default gen_random_uuid(),
  transaction_id uuid not null references transactions(id) on delete cascade,
  name text not null,
  qty numeric,
  unit text,
  unit_price bigint,
  subtotal bigint,
  confidence numeric
);
create index on transaction_items (transaction_id);

create table stock_counts (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references owners(id) on delete cascade,
  product text not null,
  count integer not null,
  counted_at timestamptz not null default now(),
  image_path text
);

create table pending_confirmations (
  owner_id uuid primary key references owners(id) on delete cascade,
  kind text not null,
  source text not null check (source in ('photo','voice','text')),
  payload jsonb not null,
  updated_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '1 hour')
);

create table processed_messages (
  message_id text primary key,
  processed_at timestamptz not null default now()
);

create table model_calls (
  id bigserial primary key,
  owner_id uuid references owners(id) on delete set null,
  flow text not null,
  model text not null,
  latency_ms integer,
  tokens_in integer,
  tokens_out integer,
  ok boolean not null default true,
  created_at timestamptz not null default now()
);

alter table owners enable row level security;
alter table transactions enable row level security;
alter table transaction_items enable row level security;
alter table stock_counts enable row level security;
alter table pending_confirmations enable row level security;
alter table processed_messages enable row level security;
alter table model_calls enable row level security;
