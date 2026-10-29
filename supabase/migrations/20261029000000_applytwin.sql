-- ApplyTwin lives in the Twinly Supabase project but keeps its own space:
-- tables prefixed applytwin_, one private storage bucket "applytwin". Same auth.users (Sign in with Google),
-- nothing in Twinly's tables is read or written. Every row is owned by the signed-in user (RLS).

create table if not exists public.applytwin_accounts (
  user_id uuid primary key references auth.users(id) on delete cascade,
  profile jsonb not null default '{}'::jsonb,       -- contact, school, search prefs, apply policy
  vault jsonb not null default '{}'::jsonb,         -- the Career Vault
  answers jsonb not null default '[]'::jsonb,       -- application answer bank
  learnings jsonb not null default '{}'::jsonb,     -- preferences + outcome learning
  updated_at timestamptz not null default now()
);

create table if not exists public.applytwin_applications (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade default auth.uid(),
  job_key text not null,
  company text, title text, url text, ats text,
  status text not null,
  resume_path text,                                 -- object path in the applytwin bucket
  notes text,
  created_at timestamptz not null default now()
);
create index if not exists applytwin_applications_user on public.applytwin_applications(user_id, created_at desc);

alter table public.applytwin_accounts enable row level security;
alter table public.applytwin_applications enable row level security;

drop policy if exists "own account" on public.applytwin_accounts;
create policy "own account" on public.applytwin_accounts for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "own applications" on public.applytwin_applications;
create policy "own applications" on public.applytwin_applications for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- private bucket; objects live under <user_id>/...
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('applytwin', 'applytwin', false, 10485760, array['application/pdf', 'application/x-tex', 'text/plain', 'application/json'])
on conflict (id) do nothing;

drop policy if exists "applytwin own files read" on storage.objects;
create policy "applytwin own files read" on storage.objects for select to authenticated
  using (bucket_id = 'applytwin' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "applytwin own files write" on storage.objects;
create policy "applytwin own files write" on storage.objects for insert to authenticated
  with check (bucket_id = 'applytwin' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "applytwin own files update" on storage.objects;
create policy "applytwin own files update" on storage.objects for update to authenticated
  using (bucket_id = 'applytwin' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "applytwin own files delete" on storage.objects;
create policy "applytwin own files delete" on storage.objects for delete to authenticated
  using (bucket_id = 'applytwin' and (storage.foldername(name))[1] = auth.uid()::text);

-- This project grants nothing to API roles by default: signed-in users need table access (RLS above still limits
-- every row to its owner). Anonymous visitors get none.
grant select, insert, update, delete on public.applytwin_accounts to authenticated;
grant select, insert, update, delete on public.applytwin_applications to authenticated;
grant usage, select on sequence public.applytwin_applications_id_seq to authenticated;
