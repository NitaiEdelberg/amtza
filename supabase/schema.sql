-- Anonymous game rounds, written by the backend (backend/gamelog.py).
-- Run once in the Supabase SQL editor.
--
-- No personal data: game_id is a random id the browser makes up per game, not
-- tied to a person or device. No IPs, no user agents.

create table if not exists public.rounds (
  id              bigint generated always as identity primary key,
  created_at      timestamptz not null default now(),
  game_id         uuid,
  lang            text not null check (lang in ('he', 'en')),
  round_num       int  not null,
  word1           text not null,
  word2           text not null,
  player_guess    text not null,
  computer_guess  text not null,
  similarity      real not null,
  is_won          boolean not null
);

create index if not exists rounds_game_id_idx on public.rounds (game_id);
create index if not exists rounds_created_at_idx on public.rounds (created_at);

-- Row-level security ON with no policies: the public anon key can neither read
-- nor write. Only the backend's secret key (which bypasses RLS) can insert.
alter table public.rounds enable row level security;
