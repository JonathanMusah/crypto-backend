-- Run this once in your Supabase project's SQL Editor.
-- (Project -> SQL Editor -> New query -> paste this -> Run)

-- 1. The table that holds every item in the shop
create table if not exists items (
  id uuid primary key default gen_random_uuid(),
  created_at timestamp with time zone default now(),
  name text not null,
  category text not null,
  price numeric,
  show_price boolean not null default true,
  image_url text not null,
  sold boolean not null default false
);

-- 2. Turn on Row Level Security
alter table items enable row level security;

-- 3. Anyone can VIEW items (this powers the public shop page)
create policy "Public can view items"
  on items for select
  using ( true );

-- 4. Only a logged-in user (the admin) can add/edit/delete
create policy "Authenticated can insert items"
  on items for insert
  to authenticated
  with check ( true );

create policy "Authenticated can update items"
  on items for update
  to authenticated
  using ( true );

create policy "Authenticated can delete items"
  on items for delete
  to authenticated
  using ( true );

-- 5. Storage bucket for photos
insert into storage.buckets (id, name, public)
values ('items', 'items', true)
on conflict (id) do nothing;

create policy "Public can view item photos"
  on storage.objects for select
  using ( bucket_id = 'items' );

create policy "Authenticated can upload item photos"
  on storage.objects for insert
  to authenticated
  with check ( bucket_id = 'items' );

create policy "Authenticated can delete item photos"
  on storage.objects for delete
  to authenticated
  using ( bucket_id = 'items' );
