-- Cain's Pantry imported recipes. Run supabase_profiles.sql first.
--
-- Personal imports only. A shared TheMealDB catalog, if one is added later,
-- belongs in a different table so sample rows and user imports do not collide.
--
-- Login in this app is the profiles table, not Supabase Auth, so auth.uid()
-- is null on these requests and cannot scope rows. Every imported-recipe
-- request sends the signed-in profile id in the x-profile-id header. Policies
-- allow a row only when user_id matches that header. A request with no header,
-- or a different id, cannot read or write the row.
--
-- The anon key can still set that header. That is the same demo trust model
-- as pantry_items and shopping_list_items. Do not use it for real accounts.

create schema if not exists private;

create or replace function private.request_profile_id()
returns uuid
language plpgsql
stable
set search_path = ''
as $$
declare
  raw text;
begin
  raw := nullif(
    current_setting('request.headers', true)::json->>'x-profile-id',
    ''
  );
  if raw is null then
    return null;
  end if;
  begin
    return raw::uuid;
  exception
    when invalid_text_representation then
      return null;
  end;
end;
$$;

revoke all on function private.request_profile_id() from public;
grant usage on schema private to anon, authenticated;
grant execute on function private.request_profile_id() to anon, authenticated;

create table if not exists public.imported_recipes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  external_id text not null check (char_length(btrim(external_id)) > 0),
  title text not null check (char_length(btrim(title)) > 0),
  ingredients jsonb not null default '[]'::jsonb,
  optional_ingredients jsonb not null default '[]'::jsonb,
  tags text[] not null default '{}',
  source_url text,
  source_kind text not null check (source_kind in ('mealdb', 'url', 'manual')),
  instructions text,
  created_at timestamptz not null default now(),
  constraint imported_recipes_user_external unique (user_id, external_id),
  constraint imported_recipes_ingredients_array check (
    jsonb_typeof(ingredients) = 'array'
    and jsonb_array_length(ingredients) > 0
  ),
  constraint imported_recipes_optional_array check (
    jsonb_typeof(optional_ingredients) = 'array'
  )
);

comment on table public.imported_recipes is
  'Recipes one person imported. Not a shared catalog.';

create index if not exists imported_recipes_user_created
  on public.imported_recipes (user_id, created_at);

alter table public.imported_recipes enable row level security;

drop policy if exists "Users can use their own imported recipes"
  on public.imported_recipes;
create policy "Users can use their own imported recipes"
  on public.imported_recipes
  for all
  to anon, authenticated
  using ((select private.request_profile_id()) = user_id)
  with check ((select private.request_profile_id()) = user_id);

grant select, insert, update, delete on public.imported_recipes to anon, authenticated;
