# DR-TENNIS-FORECAST-LIT-001 findings — pre-off tennis forecasting against market prices

**Returned:** 2026-07-28, via founder's ChatGPT Deep Research (Cost-Aware Deep Research
Routing Amendment). **Assessed:** 2026-07-28 (assessment follows the verbatim report).
Citation markers (`citeturn...`) are artifacts of the source tool preserved verbatim; they
resolve only inside the founder's ChatGPT session, so every load-bearing claim below is
classified as a SOURCE CLAIM pending spot-check of the underlying papers — not as an
independently verified fact.

---

## Verbatim report

# Pre-off Tennis Forecasting Against Market Prices

## Executive assessment

The post-2018 tennis literature does **not** show a large, stable body of methods that beat closing bookmaker or exchange prices on broad, pre-match out-of-sample evaluation. The credible record is much thinner than the general ML-for-sports literature suggests. The strongest broad-sample finding I found is a **tiny** improvement in **classification accuracy** from a bookmaker-augmented gradient-boosting setup, while its **proper scores were not better than the bookmaker baseline**. The other positive results that survive scrutiny are mostly **selective** rather than broad: they identify subsets of matches where the market appears weaker, but they do not beat the market across all matches. citeturn9view2turn27view0turn13view0turn15view1

That matters for calibration. Relative to this literature, your measured **+0.001058 nats** against a de-vigged closing price looks **small in absolute terms**, but **not suspiciously large**. If anything, it sits toward the **high end of credible broad-market headroom** reported in published work, because most broad models either fail to beat the market at all or only do so by a hair on one metric while losing on proper scoring rules. The two most striking "market-beating" claims in this literature are a WTA buzz model that weakened materially after data correction and failed to extend past 2020, and a graph/intransitivity model that is profitable only on filtered subsets while still losing to Pinnacle on overall Brier score. citeturn9view2turn27view0turn18view1turn15view4turn12view1turn13view0

A practical reading of the literature is therefore: **broad pre-off headroom over the close is real but very narrow; claimed edges are often fragile; and most of the durable signal comes from either market anchoring itself or from carefully targeted residuals rather than from replacing the market with a more complex model.** citeturn8view3turn27view3turn20view3

## Candidate methods table

| Method and publication date | Market benchmark beaten | Out-of-sample effect size | Sample and test design | Data required | Free data status | Confidence note |
|---|---|---|---|---|---|---|
| **Bookmaker-augmented gradient boosting** in Wilkens, *Journal of Sports Analytics* (2021) citeturn5view1turn28view0 | **Bookmaker-implied probabilities** from normalized odds. Benchmark accuracy in prediction panel: **69.0%**; gradient boosting: **69.1%**. But benchmark **log-loss 0.579** vs gradient boosting **0.581**, benchmark **Brier 0.198** vs gradient boosting **0.199**. citeturn9view2 | **+0.10 percentage points in accuracy**, but **worse proper scores**. Penn et al. later classify this as only a "small improvement" over the bookmaker benchmark. citeturn27view0turn27view3 | About **39,000** matches total from **2010–2019**; seven rolling annual forecasts with about **4,000 prediction matches per year**. The paper reports annual forecast averages, not clustered CIs. citeturn7view0turn8view0 | Match, player, ranking, and multi-book odds features including average odds and max-to-average spreads. citeturn7view3turn6view2 | **Mostly obtainable**, but the multi-book odds history is not a clean universally free feed. citeturn7view3 | **Low-to-moderate** for "beats the market," because the win is only on accuracy, not on proper scoring rules. |
| **Wikipedia Relative Buzz factor** in Ramirez, Reade, and Singleton, *International Journal of Forecasting* (2023), as corrected by Clegg and Cartlidge (2025) citeturn16search1turn16search2 | **Bet365 closing odds** and related bookmaker prices in WTA singles. Original reported ROIs: **17.3%** and **28.8%** on two Bet365 strategies. After correction of the "Hercog" data error, those two strategies fall to **-7.36%** and **-6.31%**. A narrower "competitive matches" strategy remains at **+12.44% ROI** over **262** bets in the original 2019–2020 window. citeturn18view3turn18view1turn18view2 | Broad positive claims largely **disappear after correction**; only the narrow competitive-match filter remains positive in the original window. On an extended clean out-of-sample sample through **August 2023**, **no further profits** are generated and the new WikiBuzz and rank-distance coefficients are no longer significant. citeturn15view1turn15view4 | Original RRS data: WTA, training **2015–2018**, testing **2019–2020**. Correction extends clean out-of-sample to **2019–2023** with **17,751 matches / 35,274 player-match rows** and **13,913 player-match rows** in the post-2020 re-estimation window. citeturn14view2turn15view4 | Bookmaker odds, rankings, and pre-match Wikipedia page views. citeturn15view2 | **Yes**, or close enough: tennis-data-style odds plus Wikipedia page views are publicly accessible. citeturn14view2turn16search4 | **Low** as a durable research lead. Valuable mainly as a cautionary tale about fragile profit claims and data cleaning. |
| **Intransitivity / graph-neural filtering** in Clegg and Cartlidge, arXiv (2025) citeturn19search11 | **Pinnacle implied probabilities** with Shin margin adjustment. Overall the model is **worse than Pinnacle** on the full out-of-sample set: model **0.215 Brier** vs Pinnacle **0.196**. But after filtering to matches with \(I^*(A_{uv}) \ge 2.55\), the betting simulation reports **+3.26% Kelly ROI** over **1,903** bets and **+1.14% unit ROI** over **2,063** bets, with random-bet p-values **0.005** and **0.022** after Bonferroni correction. citeturn12view1turn13view0 | **Subset-only positive edge**. Not a broad market-beating forecast; rather, a claim that the market is weaker in a specific relational segment. citeturn35view3turn35view4 | **8,375** out-of-sample matches from **2023-01-01 to 2025-06-08** across men and women. The authors also report a reduced earlier test set and an extended comparison for an unoptimized earlier version. citeturn12view1turn12view2 | Historical match graph, surface information, and Pinnacle odds for evaluation. citeturn12view1turn13view4 | **Mixed**. Match histories are free; Pinnacle closing odds are not always cleanly free in reusable form. | **Moderate-low**. Methodology is explicit and the multiplicity correction is better than most papers, but it is still a preprint and the advantage is filtered, not broad. |
| **Best-odds shopping using the corrected buzz model** from the Clegg–Cartlidge replication of Ramirez (2025 correction paper) citeturn16search2 | **Best available odds across bookmakers**, not a single closing bookmaker or exchange. Strict replication gives **+3.05% ROI** over **2,350** bets on the out-of-sample 2019–2020 WTA window. citeturn14view1turn18view0 | Positive, but depends on **shopping best prices** rather than beating a single close. citeturn14view1 | **5,188–5,189 player-match odds observations**, **2019–2020**. citeturn14view1 | Multi-book odds aggregation plus buzz/rank features. | **Not cleanly free/executable** in a production sense without robust multi-book odds capture. | **Low** for your use case, because your benchmark is the close itself and execution costs/availability will dominate. |

The short version is that I found only **three genuinely relevant post-2018 candidate families** for "market-beating" pre-off work: **market-augmented ML**, **attention/crowd residuals**, and **relational/intransitivity filtering**. Of those, only the first is even close to a broad all-match comparison, and it wins only on **accuracy**, not on **proper scoring**. citeturn27view0turn13view0turn15view1

## What published effect sizes say about your result

The broad literature's reference class is narrow. In the most directly comparable broad study, Wilkens's bookmaker-augmented models are essentially at parity with bookmaker-implied probabilities out of sample, with the best machine-learning variant improving **accuracy by only 0.1 percentage points** while **not** improving log-loss or Brier. Penn et al. explicitly summarize that literature as showing only a **small improvement** over the bookmaker benchmark for that best-performing model. citeturn9view2turn27view0turn27view3

The published results that look larger are mostly **not** comparable to your all-match residual setup. Ramirez et al.'s original WTA buzz profits of **17%–29% ROI** were materially weakened by replication and cleaning; after removing one erroneous odds observation, the headline strategies turned negative, and only a narrow "competitive-match" slice remained positive. Moreover, when that slice was carried forward to a longer clean out-of-sample period through **August 2023**, it stopped generating new profits and its explanatory variables stopped being significant. citeturn18view3turn18view1turn15view1turn15view4

Likewise, Clegg and Cartlidge's intransitivity model is only positive **after filtering** to a specific subset. On the full sample it is plainly inferior to Pinnacle by Brier score, and even in the high-intransitivity subset the paper still says bookmaker implied probabilities remain more accurate, with profitability arising from **selective mispricing**, not broad probability superiority. citeturn12view1turn35view3turn35view4

So, against that reference class, your **+0.001058 nats** over the close reads as follows. It is **small**, because broad-market headroom over the close in tennis appears to be genuinely tiny. It is **plausible**, because the literature repeatedly finds that the market is hard to beat but not perfectly immune to narrow residual information. And it is **not obviously suspiciously large**, because I did not find a credible post-2018 broad pre-match paper reporting materially larger robust proper-score gains against the closing market on a comparably large sample. The bigger published "wins" are either non-comparable subset ROI stories or claims that fall apart under replication. citeturn27view0turn9view2turn15view1turn13view0

## Feature families with incremental signal beyond your current baseline

The literature gives only a short list of feature families that look meaningfully incremental once you already have **Elo/rating structure, serve-return information, and a market anchor**.

The first is **crowd-attention or sentiment residuals**. Ramirez et al. use a Wikipedia Relative Buzz Factor and show that it predicts bookmaker mispricing in WTA matches when added alongside odds-implied probability and ranking distance. That is genuine incremental evidence over an odds-plus-ranking setup. But the replication record is poor: after correction and extension, the coefficients are no longer significant in the later sample. I would therefore classify this family as **interesting but fragile**, and only worth touching if the data are essentially free and you can test it under a very hard multiplicity budget. citeturn16search1turn15view2turn15view1

The second is **relational or intransitivity structure**: not head-to-head as a raw count, but local cyclic matchup structure in the player network. Clegg and Cartlidge argue that bookmakers are weakest when matchups sit in highly intransitive local neighborhoods, and they show subset profitability there. This is the best current published case I found for a feature family that is not already in the standard Elo-plus-serve-stat toolkit and that might plausibly survive after market anchoring. It is also comparatively cheap in data terms, because it uses historical match results rather than paid point-by-point feeds. citeturn35view4turn35view3turn35view0

The third is **cross-book disagreement / odds-dispersion features**. Wilkens finds that the **spread between average and maximum odds** is among the high-importance variables in bookmaker-augmented models, alongside the average odds levels themselves. This is not the same thing as using the close; it is using the **shape of the market around the close**. Your current description mentions only a de-vigged closing price, not dispersion across books, so this is one of the few literature-backed residual families that may still be open to you. The catch is operational: you need multi-book snapshots or a clean odds-history panel. citeturn6view0turn6view2

After that, the literature gets much weaker.

**Opponent-adjusted serve/return histories** do help relative to cruder point-based models. Gollub shows that opponent-adjusted Barnett–Clarke variants and Efron–Morris shrinkage improve over the raw Barnett–Clarke approach; and Ingram's Bayesian hierarchical point model beats the opponent-adjusted baseline on point-level quantities. But neither result is evidence of incremental value over a strong Elo-plus-serve baseline, much less over a market-anchored residual. In fact, Ingram's best proposed model is still slightly **worse than Elo** on match accuracy and log loss. Because you already use a Barnett–Clarke point model and decomposed serve statistics, I would treat this family as **already substantially covered** by your current stack. citeturn21view2turn22view0turn22view1

For **point-by-point / point-specific / tracking data**, the literature is even more cautionary. Wang and Drekic show that point-specific modifications and ensembles can improve traditional Markovian models, but they also say those methods are dampened by requirements for **higher-volume, denser point-by-point data**, and some attempted modifications such as **decaying service-point win probabilities** did not yield notable gains. The paper positions these as promising in a methodological sense, not as a proven route to beating bookmaker closes. In addition, the higher-resolution tracking literature tends to rely on tournament-specific tracking datasets or rich serve-location/velocity features, which are not an obvious fit for a no-new-data-purchase constraint. citeturn25view0turn25view0

I did **not** find convincing post-2018 published evidence that pre-match **travel**, **time zone**, **altitude**, **ball type**, **time of day**, or **injury proxies** add robust incremental value over an Elo-plus-serve-plus-market baseline in broad out-of-sample evaluation. There are plausible anecdotes and some domain arguments, and Penn's Wimbledon case study notes that bookmaker/model divergences can reveal injury information missing from the model, but I did not find a good tennis paper that shows these features adding durable out-of-sample lift over the market anchor you already use. citeturn26view0

For your purposes, the short list is therefore:

- **Intransitivity / graph-relational residuals**: strongest genuinely new family with some positive subset evidence. citeturn35view4turn35view3
- **Cross-book dispersion / disagreement around the close**: cheap, plausible, and explicitly important in bookmaker-augmented work. citeturn6view0turn6view2
- **Crowd-attention residuals**: free enough to test, but fragile and empirically unstable after replication. citeturn15view1turn16search1

## Negative results and what they imply about model classes

The cleanest negative result is that **most machine-learning classes do not reliably beat bookmaker prices in pre-match tennis forecasting**. Wilkens runs logistic regression, neural nets, random forests, gradient boosting, SVMs, and ensembles on about **39,000** men's and women's matches. The conclusion is blunt: rankings plus bookmaker odds already contain most of the information; historical player and match variables add little; and longer-run betting returns are mainly negative. The models improve on rankings alone, but not meaningfully on bookmaker-implied probabilities. citeturn8view3turn9view2

A second negative result is that **point-based complexity does not automatically buy better match-win forecasts**. Gollub shows that point-model refinements improve over basic Barnett–Clarke constructions, but the strongest performer remains the Elo-calibrated variant. Ingram's Bayesian hierarchical point model improves on the opponent-adjusted point baseline but remains slightly worse than Elo on 2014 out-of-sample match accuracy and log loss. Wang and Drekic's 2026 paper then shows that the gains from point-specific refinements are modest and often depend on ensembles; the individual point-specific and H2H-only variants are not strong standalone winners, and decaying service-point probabilities were one of the attempted modifications that produced no notable results. citeturn21view2turn22view0turn25view0

A third negative result is that **graph/neural sophistication does not, by itself, crack the closing market**. Penn et al.'s dynamic graph-based odds forecaster gets close to bookmaker performance in major tournaments but is still **below** the bookmakers, and their own literature comparison suggests that only one prior model—again, the bookmaker-augmented Wilkens setup—managed even a tiny reported improvement over bookmaker accuracy. Clegg and Cartlidge's GNN also loses to Pinnacle overall. So the evidence does **not** support the claim that neural or graph models reliably outperform a well-specified market-anchored linear residual at your scale. citeturn27view0turn27view1turn12view1

A fourth negative result is methodological rather than architectural: **profit claims can evaporate under data cleaning and longer horizons**. The Ramirez buzz paper is the clearest example. The correction shows that a single extreme odds error explains much of the headline profitability, and the remaining positive subset does not grow when extended through 2023. This is exactly the kind of result your advisory memo is trying to avoid re-deriving the hard way. citeturn18view1turn15view1turn15view4

One more lesson comes from the recent Grand Slam regression and ML work around Dortmund. In the Grand Slam-only setting, the variable derived from bookmaker probabilities is **always selected**, and the strongest Brier results often come from **simple linear or spline regressions** with odds and a small number of structured covariates, not from the fanciest machine-learning models. The broader 2026 benchmark preprint makes the same point from another angle: once Elo is tuned, the extra headroom available to classical ML and deep nets is very narrow. citeturn31view1turn31view2turn20view3

The advisory answer to your model-class question is therefore: **there is no published evidence that gradient boosting, Bayesian hierarchical models, GNNs, or neural nets reliably beat a strong market-anchored linear residual on broad pre-off tennis forecasting.** What exists is evidence of **niche or subset** gains, and evidence that complex models can match or slightly exceed weaker baselines. That is a much weaker proposition. citeturn12view1turn27view0turn22view0turn20view3

## Where the market seems weakest

The strongest broad structural result is **favorite–longshot bias**, especially in softer fixed-odds bookmaker markets rather than sharper books. Hegarty and Whelan show on **111,976 tennis bets** that normalized-probability tests reject strong-form efficiency for tennis and that average payouts decline materially as odds get longer; even the lowest one percent of odds still produce an average payout below one. In a related 2025 market-structure paper, Hegarty and Whelan show the pattern is **much weaker for Pinnacle** than for average bookmaker odds, which is exactly the caveat your own execution-cost note calls for: apparent inefficiency can be a property of **market structure and margins**, not exploitable value at sharp prices. citeturn33view1turn33view4turn36view0

The clearest segment-specific modern result is **high-intransitivity matchups**. Clegg and Cartlidge argue that the market is weakest where relational matchup structure is cyclic rather than hierarchical. They also find women's tennis to exhibit **11.5% more intransitivity overall** than men's, especially on hard and grass, and their filtered ROI results are built on exactly these high-intransitivity neighborhoods. That does **not** mean WTA is generally easier to beat; it means one plausible weak segment is the subset of matches where player interactions are structurally awkward for rating models and maybe for markets. citeturn35view0turn35view1turn35view3

There is also stronger evidence for **gender-related pricing differences** than for directly exploitable WTA-vs-ATP inefficiency. Barrutiabengoa, Corredor, and Muga analyze **51,881** matches and find that bookmakers quote **higher prices for women's matches than for men's**, even after accounting for uncertainty and media attention. That suggests a different pricing regime or information asymmetry around women's tennis, but it is a margin/pricing result, not by itself a proof of forecast edge after costs. citeturn34view0

What I did **not** find, in credible post-2018 work, is a strong tennis-specific published hierarchy saying "Challenger/ITF is definitively easier than ATP/WTA main tour," or "qualifying is systematically weakest," or "early rounds survive costs at the close." There are practitioner claims on this point, but they generally do not disclose methodology well enough to clear your evidence bar. The peer-reviewed literature is stronger on **women vs men**, **soft books vs sharp books**, and **structural uncertainty / intransitivity** than on **tour tier** or **round**. citeturn34view0turn35view3turn36view0

So the usable segment conclusion is narrow. If you want literature-backed weak segments with your execution caveat respected, the priority order is:

- **Soft fixed-odds books rather than sharp books/exchanges**. The observed favorite–longshot bias is materially weaker at sharper prices. citeturn36view0
- **High-intransitivity matchups**, especially in women's hard/grass contexts. citeturn35view0turn35view1turn35view3
- **Women's tennis as a different pricing regime**, but not yet as a clean standalone exploitable segment. citeturn34view0

## Evaluation practice against a market

The best practice in this corner of the literature is to evaluate at the **match level** with **proper scoring rules** first, then to treat profitability and CLV-style notions as separate diagnostics. Kovalchik argued earlier for multiple performance measures, and Wilkens reports log loss, Brier, calibration, discrimination, AUC, and accuracy. But Wilkens also optimizes for **accuracy**, which is exactly why the small "beat the bookmaker" result survives in accuracy but not in proper scores. For your use case, that is a warning: if the claim is "better than the close," the primary yardsticks should be **log score / Brier** rather than accuracy. citeturn9view2turn8view0

When the unit of analysis is expanded beyond one binary forecast per match—say, to all possible bets on both sides or multiple odds bins—**clustering becomes necessary**. Hegarty and Whelan cluster standard errors at the **match level** because each match generates multiple related betting observations. Ramirez/Reade/Singleton's replication paper reports standard errors robust to **both match and tournament clusters** for its market-mispricing regressions. Your current day-clustering rule is therefore not out of family; if anything, it is stricter than much of the literature. The key is simply not to pretend that all bet-level observations are independent. citeturn33view2turn5view3

For **multiplicity control**, most papers are weak, but there are good examples. Clegg and Cartlidge explicitly apply a **Bonferroni correction** when assessing two profitability tests for their filtered strategy. That is the right direction of travel for selective-bet or segment-mining work, especially if you are screening many feature families or many market subsets. citeturn13view0

For **retirements and walkovers**, the literature is inconsistent, so pre-specification matters. Ingram discards retirements, walkovers, and matches without serving statistics. Wilkens, by contrast, treats retirement/non-completion as a binary completed outcome for winner prediction because "the other player automatically wins." For a pre-off market comparison, the correct choice should follow the market's settlement convention and your forecast target. Walkovers should usually be excluded because no true pre-off match is played. Retirements should either be included consistently if the market settles them as wins, or excluded consistently if your target is "won a completed match." The worst practice is switching definitions midstream. citeturn22view4turn6view0

On **CLV**, I did not find a tennis-specific paper making it the main training target. The literature instead does one of two things: it either treats the odds-implied probability as the benchmark to beat in forecast evaluation, or it tries to forecast the odds themselves. That aligns with your current view that CLV belongs in a **diagnostic family**, not as the optimization target. citeturn26view0turn9view3

## Advisory takeaways for this request

The literature does not suggest an abandoned gold mine of broad pre-match feature families waiting beyond your current stack. Most of the obvious families have already been tested in some form, and the recurring result is that once you include the market—or even a strong Elo—the incremental headroom is tiny. citeturn8view3turn20view3turn22view0

If the goal is to avoid spending weeks on dead ends, the most defensible priorities are:

**First, test cross-book dispersion features** if you can source them cleanly. The literature gives them more support than many sexier ideas, and they are exactly the kind of information that a single de-vigged close omits. citeturn6view0turn6view2

**Second, test intransitivity / relational-network residuals** rather than bigger black-box model classes. The strongest positive recent evidence is not "deep nets beat the market," but "a specific relational feature family identifies matchups where the market is weaker." citeturn35view4turn35view3

**Third, treat crowd-attention signals as low-cost probes, not as a strategic pillar.** They have some published signal, but the best known tennis example is fragile under replication and extension. citeturn15view1turn16search1

Conversely, the literature argues **against** betting development time on the hope that a generic gradient-boosting, Bayesian, neural, or point-by-point model class will reliably outrun a well-specified market-anchored linear residual on a 96k-match problem. The published evidence just is not there. citeturn9view2turn12view1turn22view0turn20view3

On your final calibration question: **your measured effect looks plausible and small, not suspiciously large**. Its main implication is not "the result is too good to be true," but rather "the literature says this is about the scale where real residual gains live, and extreme claims above this scale often die under replication or after costs." citeturn15view1turn27view0turn13view0

---

## Assessment (2026-07-28)

**Facts established in our own repository, confirmed relevant by the report:** our primary
metric is already the log score (never accuracy); our day-clustering is at or above the
literature's standard; CLV is already a diagnostic family and never a training target;
retirement/walkover handling is already pre-specified in the corpus loader.

**Source claims (unverified pending spot-check), load-bearing ones:** Wilkens 2021 —
bookmaker-augmented GBM beats the market on accuracy only, loses on log-loss/Brier; Clegg &
Cartlidge 2025 — intransitivity subset ROI +1.14–3.26% with Bonferroni control, model loses
to Pinnacle on full-sample Brier; Ramirez et al. buzz result collapses under a single-row
data correction; Wilkens — max-vs-average odds spread among the highest-importance features.

**Inferences we accept:** (1) Our +0.001058 nats is plausible and small — the reference
class says this is the scale at which real residual gains live. This RAISES confidence in
our measurement. (2) There is no published support for expecting a GBM/Bayesian/GNN
combiner to beat the market-anchored linear residual at our scale.

**Recommendations adopted:**
1. **Cross-book dispersion feature — test immediately.** We already parse Max and Avg
   (2010→, 73.9% of corpus); the feature is computable from cached rows with no new data
   and no cache rebuild. Note: `tennis_edge/features.py` bans odds-derived names from
   features as a leakage guard; adding a deliberate market-shape feature is a governed
   exception requiring explicit documentation, not a workaround — the ban exists to stop
   *accidental* market leakage, and the offset is already market information at the same
   knowledge time. Deployment caveat recorded: dispersion is not observable live without a
   multi-book feed, so even a positive result is measurement-only until that is solved.
2. **Intransitivity residual — queue behind dispersion.** Computable from the Sackmann
   match graph we hold. Subset-only evidence; any test must carry multiplicity control
   (Bonferroni across the feature families screened) per the report's own standard.
3. **Crowd-attention (Wikipedia buzz) — parked.** Fragile under replication; only worth a
   probe under a hard multiplicity budget after the above two are decided.

**Retired by this finding:** the gradient-boosted combiner ambition (old Layer 6 /
`residual_gbm.py` direction) as a *priority* — the literature offers no support that the
class beats a well-specified market-anchored linear residual at our scale. The experiment
file stays for reference; effort goes to the two feature families above.

**Impact on claims:** none of our published numbers change. The finding strengthens the
credibility of the forecast result and sharpens the roadmap.
