-- Structural snapshot of schema `tennis`. Regenerate with the query in README.md.
-- Constraints, indexes, RLS policies, functions and cron live in objects.md with the
-- reasoning behind each. Snapshot taken 2026-07-30.

create table tennis.book_snapshots (
  id bigint not null, market_id text not null, event_name text,
  market_start timestamptz, market_status text, inplay boolean,
  total_matched numeric, book jsonb not null, captured_at timestamptz not null
);
create table tennis.config (
  key text not null, value text not null, updated_at timestamptz not null
);
create table tennis.fixtures (
  id bigint not null, match_key text not null, match_date date not null,
  tour text not null, player_a text not null, player_b text not null,
  surface text not null, best_of smallint not null,
  odds_a numeric(10,3) not null, odds_b numeric(10,3) not null,
  source text not null, quoted_at timestamptz not null, updated_at timestamptz not null
);
create table tennis.forecasts (
  match_date date not null, tour text not null, player_a text not null,
  player_b text not null, surface text, p_model double precision not null,
  p_market double precision not null, won_a boolean not null,
  completion text not null, state_as_of date not null, model_digest text not null,
  pulled_at timestamptz not null
);
create table tennis.head_to_head (
  tour text not null, player_a text not null, player_b text not null,
  wins_a integer not null, wins_b integer not null, as_of date not null
);
create table tennis.ledger (
  match_key text not null, prediction_id bigint not null, match_date date not null,
  winner text not null, a_won boolean not null, settled_at timestamptz not null,
  notes text, tour text, completion text,
  model_log_loss double precision, market_log_loss double precision
);
create table tennis.market_complex (
  match_key text not null, match_date date not null, solved_at timestamptz not null,
  solver_status text not null, serve_a double precision, serve_b double precision,
  implied_prob_a double precision, quotes jsonb not null, residual double precision
);
create table tennis.model (
  digest text not null, coefficients jsonb not null, feature_names text[] not null,
  feature_set_version text not null, l2 double precision not null,
  trained_from date not null, trained_through date not null,
  trained_rows integer not null, is_current boolean not null,
  created_at timestamptz not null
);
create table tennis.placed_bets (
  id bigint not null, match_key text not null, match_date date not null,
  tour text not null, player_a text not null, player_b text not null,
  side text not null, stake numeric not null, matched_odds numeric not null,
  commission numeric not null, placed_at timestamptz not null, status text not null,
  pnl numeric, graded_at timestamptz
);
create table tennis.player_aliases (
  feed_name text not null, tour text not null, player text not null,
  note text, created_at timestamptz not null
);
create table tennis.player_state (
  tour text not null, player text not null, as_of date not null,
  elo double precision not null, surface_elo jsonb not null,
  weighted_elo double precision, matches integer not null, last_played date,
  serve_rate double precision, return_rate double precision,
  serve_points double precision, serve_matches integer not null,
  pyramid_elo double precision, pyramid_surface_elo jsonb not null,
  pyramid_matches integer not null, pyramid_last_played date,
  pyramid_recent_14d integer not null, pyramid_tour_share double precision,
  serve_detail jsonb not null, retirement_rate double precision not null,
  workload_minutes_14d double precision not null, workload_long_28d integer not null,
  last_surface text not null, rank integer, rank_date date
);
create table tennis.predictions (
  id bigint not null, match_key text not null, match_date date not null,
  tour text not null, player_a text not null, player_b text not null,
  surface text not null, best_of smallint not null,
  odds_a numeric(10,3) not null, odds_b numeric(10,3) not null,
  market_probability_a double precision not null, probability_a double precision not null,
  fair_odds_a numeric(10,3) not null, fair_odds_b numeric(10,3) not null,
  break_even_a double precision not null, break_even_b double precision not null,
  edge_a double precision not null, edge_b double precision not null,
  commission numeric(6,4) not null, features jsonb not null, contributions jsonb not null,
  reasons text[] not null, status text not null, recommendation text not null,
  model_digest text not null, state_as_of date not null, created_at timestamptz not null
);
create table tennis.price_observations (
  match_key text not null, tour text not null, venue text not null,
  odds_a numeric not null, odds_b numeric not null,
  commence_time timestamptz, captured_at timestamptz not null
);
create table tennis.result_aliases (alias text not null, key text not null);
create table tennis.results (
  match_date date not null, tour text not null, key_a text not null,
  key_b text not null, winner_key text, completion text not null,
  pulled_at timestamptz not null
);
create table tennis.state_pull_log (
  id bigint not null, ran_at timestamptz not null, ok boolean not null,
  players integer, as_of date, detail text
);
create table tennis.unmapped_names (
  feed_name text not null, tour text not null, seen_count integer not null,
  first_seen timestamptz not null, last_seen timestamptz not null
);
