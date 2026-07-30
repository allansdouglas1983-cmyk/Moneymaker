-- TE-0041 #9: the two verifications the display-band change is GATED on.
-- The item's own risk note: "Do not remove the crossing term before the verification
-- returns." Neither can return yet — recorded here as repeatable queries so the gate
-- is a measurement waiting on data, not a promise waiting on memory.
--
-- Preconditions (checked 2026-07-30):
--   V1 needs tennis.book_snapshots rows  -> 0 today (delayed-key capture starts when
--      the founder registers the Betfair certificate; cron jobid 14 is armed).
--   V2 needs weeks of tennis.price_observations -> capture began 2026-07-30 (312 rows);
--      venue_last_update newly captured (TE-0041 #1), so staleness is measurable at all.

-- V1 — price definition: does the Odds API betfair_ex_uk h2h price equal the delayed
-- key's best availableToBack at the nearest timestamp? A systematic offset means the
-- feed is a mid/last-trade and the crossing term must STAY.
-- (Join key: match identity + nearest snapshot within 10 minutes.)
select
  o.match_key,
  o.captured_at,
  o.odds_a       as feed_back_a,
  s.best_back_a  as book_back_a,
  o.odds_a - s.best_back_a as gap_a,
  abs(extract(epoch from (o.captured_at - s.captured_at))) as clock_gap_s
from tennis.price_observations o
join lateral (
  select b.best_back_a, b.captured_at
  from tennis.book_snapshots b
  where b.match_key = o.match_key
    and abs(extract(epoch from (b.captured_at - o.captured_at))) < 600
  order by abs(extract(epoch from (b.captured_at - o.captured_at)))
  limit 1
) s on true
where o.venue = 'betfair_ex_uk'
order by o.captured_at desc
limit 500;

-- V2 — staleness cost: per (match, venue), the drift of the de-vigged home probability
-- between consecutive captures, against elapsed time — the live analogue of the S2
-- delay cost. Run only once the table spans weeks; a day of data measures noise.
with series as (
  select match_key, venue, captured_at, venue_last_update,
         (1.0/odds_a) / (1.0/odds_a + 1.0/odds_b) as p_home_raw,
         lag(captured_at) over w as prev_at,
         lag((1.0/odds_a) / (1.0/odds_a + 1.0/odds_b)) over w as prev_p
  from tennis.price_observations
  window w as (partition by match_key, venue order by captured_at)
)
select venue,
       count(*)                                              as steps,
       avg(extract(epoch from (captured_at - prev_at))/3600) as mean_gap_h,
       avg(abs(p_home_raw - prev_p))                         as mean_abs_drift,
       percentile_cont(0.9) within group (order by abs(p_home_raw - prev_p)) as p90_drift
from series
where prev_at is not null
group by venue
order by steps desc;

-- Capture health for #1 (per TE-0041's own verification query): provider-timestamp ages
-- should be small and NON-DEGENERATE per venue; identical ages everywhere means the
-- field is populated from the wrong source.
select venue, count(*) as rows,
       min(captured_at - venue_last_update)    as min_age,
       percentile_cont(0.5) within group (order by (captured_at - venue_last_update)) as median_age,
       max(captured_at - venue_last_update)    as max_age
from tennis.price_observations
where venue_last_update is not null
group by venue
order by rows desc
limit 40;
