-- Cain's Pantry items. Run supabase_profiles.sql first.
--
-- Demo-grade security. Any client using the anon key can read and write
-- every pantry row. Fine for a local demo, not for production.

create table if not exists public.pantry_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  name text not null check (char_length(btrim(name)) > 0),
  created_at timestamptz not null default now()
);

create unique index if not exists pantry_items_user_name_lower
  on public.pantry_items (user_id, lower(name));

alter table public.pantry_items enable row level security;

drop policy if exists "Demo anon can use pantry items" on public.pantry_items;
create policy "Demo anon can use pantry items"
  on public.pantry_items
  for all
  to anon, authenticated
  using (true)
  with check (true);

grant select, insert, update, delete on public.pantry_items to anon, authenticated;
