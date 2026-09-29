-- Cain's Pantry shopping list. Run supabase_profiles.sql, then supabase_pantry.sql, first.
--
-- Demo-grade security. Any client using the anon key can read and write
-- every shopping row. Fine for a local demo, not for production.

create table if not exists public.shopping_list_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  name text not null check (char_length(btrim(name)) > 0),
  created_at timestamptz not null default now()
);

create unique index if not exists shopping_list_items_user_name_lower
  on public.shopping_list_items (user_id, lower(name));

alter table public.shopping_list_items enable row level security;

drop policy if exists "Demo anon can use shopping list items" on public.shopping_list_items;
create policy "Demo anon can use shopping list items"
  on public.shopping_list_items
  for all
  to anon, authenticated
  using (true)
  with check (true);

grant select, insert, update, delete on public.shopping_list_items to anon, authenticated;
