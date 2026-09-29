-- Cain's Pantry profiles. Run this before supabase_pantry.sql.
--
-- Demo-grade security. The policies below let the anon key read and write
-- every row, including password hashes. That is enough for a class demo
-- and it is not safe for real accounts. Do not put personal passwords here.
-- For a real app, use Supabase Auth and row policies scoped to auth.uid().

create table if not exists public.profiles (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  password_hash text not null,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

drop policy if exists "Demo anon can use profiles" on public.profiles;
create policy "Demo anon can use profiles"
  on public.profiles
  for all
  to anon, authenticated
  using (true)
  with check (true);

grant select, insert, update, delete on public.profiles to anon, authenticated;
