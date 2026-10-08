-- Accounts, jobs, pronunciations and daily usage (Stage 1 plan §10).
--
-- The API and workers connect as the database owner and bypass row-level security.
-- RLS protects the tables if a browser ever talks to Supabase directly with a user's
-- token: each signed-in user can read only their own rows, and nobody else can read
-- anything.
--
-- The input text of a job is never stored (Stage 1 plan §14).

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  tier text not null default 'free' check (tier in ('free')),
  created_at timestamptz not null default now()
);

create table public.jobs (
  id text primary key,
  user_id uuid references auth.users (id) on delete cascade,
  anon_id text,
  status text not null check (status in ('queued', 'running', 'done', 'error', 'cancelled')),
  lang text not null,
  voice text not null,
  blend_voice text,
  blend_ratio real,
  speed real not null,
  pitch real not null,
  chars integer not null check (chars >= 0),
  audio_seconds real,
  storage_key text,
  wav_key text,
  error text,
  cached boolean not null default false,
  created_at timestamptz not null default now(),
  finished_at timestamptz,
  constraint jobs_have_one_owner check ((user_id is null) <> (anon_id is null))
);

create index jobs_user_recent on public.jobs (user_id, created_at desc) where user_id is not null;

create table public.pronunciations (
  user_id uuid not null references auth.users (id) on delete cascade,
  word text not null check (char_length(word) between 1 and 100),
  say text not null check (char_length(say) between 1 and 200),
  primary key (user_id, word)
);

create table public.usage_daily (
  subject text not null, -- 'users:<uuid>' or 'anon:<id>'
  day date not null,
  chars integer not null default 0,
  jobs integer not null default 0,
  primary key (subject, day)
);

-- Row-level security: owners read their own rows; no policy = no access.
alter table public.profiles enable row level security;
alter table public.jobs enable row level security;
alter table public.pronunciations enable row level security;
alter table public.usage_daily enable row level security;

create policy "read own profile" on public.profiles
  for select to authenticated using (id = (select auth.uid()));

create policy "read own jobs" on public.jobs
  for select to authenticated using (user_id = (select auth.uid()));

create policy "read own pronunciations" on public.pronunciations
  for select to authenticated using (user_id = (select auth.uid()));

-- usage_daily has no policies: only the API (database owner) reads it.

-- A profile for every new account
create function public.create_profile() returns trigger
  language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.profiles (id) values (new.id);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.create_profile();
