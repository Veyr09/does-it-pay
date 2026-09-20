# The basis on Solana tokenised equities — what it does, and what it is not worth

Measured 2026-09-19 from free public data: GeckoTerminal hourly OHLCV for the deepest
Solana pool per ticker (≈42 days, 900–1000 hourly points each) and Yahoo hourly bars with
pre/post for the underlying. 12 tickers with real liquidity: SPY, QQQ, NVDA, TSLA, META,
GLD, CRCL, MSTR, COIN, HOOD, AMZN, GOOGL. Code in `tools/basis_*.py`.

"Basis" here means `token_price / last_traded_spot − 1`, in percent, with spot
forward-filled so that hours when the US market is shut compare against the last print.

## Finding 1 — the premium is structural and ticker-specific
It is not noise around zero. Mean basis over the whole sample, by ticker:

| ticker | regular session | weekend |
|---|---|---|
| SPY | +0.53% | +0.57% |
| MSFT | +0.60% | +0.56% |
| QQQ | +0.26% | +0.23% |
| GOOGL | +0.20% | +0.24% |
| NVDA | +0.16% | +0.38% |
| TSLA | +0.03% | +0.30% |
| AMZN | 0.00% | −0.06% |
| GLD | 0.00% | −0.02% |
| CRCL | +0.01% | +0.60% |
| MSTR | −0.01% | +0.56% |
| COIN | −0.06% | −0.19% |
| HOOD | −0.05% | +0.19% |

So a screener that prints "MSFTx is +0.6% over spot" is telling you nothing: that is
MSFTx's normal state. The only number that carries information is the deviation from a
ticker's **own** baseline.

## Finding 2 — the basis widens when the US market is shut, most for crypto-beta names
Dispersion, not just level, changes. Standard deviation of the basis, regular → weekend:
MSTR 0.84 → 1.32, HOOD 0.96 → 1.82, CRCL 0.75 → 1.10, TSLA 0.41 → 0.55. The 90th
percentile of |basis| on weekends reaches **3.0% for HOOD, 2.5% for MSTR, 1.9% for CRCL**,
against roughly 1.5% during cash hours. Names with no crypto correlation (AMZN, GLD, SPY)
barely change. The pattern is what you would expect: with the underlying frozen, the token
keeps trading on crypto-market sentiment.

## Finding 3 — the deviation does revert, and it is still not a trade
This is the part worth being careful about, because the first version of the test looked
excellent and was wrong.

- Measuring the **change in basis** after an extreme z-score gives ~1.4pp of reversion at
  24h with a 90% hit rate. **A phase-shuffled control produced the same result** (−1.55 vs
  −1.36), so that test measures nothing but regression to the mean.
- The honest test is the **token's own forward USD return**. On overlapping windows,
  z < −1.5 gave +0.61pp excess at 4h (t = 10.1) while the shuffled control collapsed to
  +0.13 (t = 2.3). So there is a real effect.
- On **non-overlapping** samples, which is what the autocorrelation demands: 4h,
  z < −1.5 → mean +0.492%, baseline +0.069%, **edge +0.424pp, t = 3.76**. Statistically
  real. At 8h and 24h it is no longer significant (t = 1.47, 0.09).
- A plain 24-hour price-reversal control gives a weaker edge (t = 1.31 at 4h), so the basis
  does carry information beyond "it just dropped".
- **Round-trip cost on Solana DEXs is ~0.6%** (two legs at 0.25–0.30%, before slippage and
  priority fees). Net of that, the best bucket is **−0.108%**. The edge is smaller than the
  toll.

**Conclusion: real signal, negative net expectancy for a retail round trip.** Anything built
on this must say so. The usable version of the finding is not "here is a trade" — it is
"if you are buying on-chain equity exposure anyway, here is whether you are overpaying
relative to this ticker's own normal, and by how much."

---

## Extension: six months of daily data (added 2026-09-19 ~22:15 CEST)

Hourly OHLCV caps at 1,000 points, so the study above only sees ~42 days. Daily bars reach
back to each pool's start — roughly **2026-02-23 to 2026-09-18, 95–130 days per ticker**,
20 tickers. `tools/basis_long.py`, data in `data/basis_daily.json`.

### The premium is stable for the deep names and persistent for the thin ones
SPYx has run between **+0.34% and +0.65% every single month** since March. ORCLx has run
**+0.67% to +1.26%**, MCDx **+0.79% to +1.80%**, KOx **+1.12% to +6.34%**. Meanwhile the
crypto-beta names swing sign by month: MSTR +0.58 → −0.26, COIN +0.62 → −0.77,
HOOD +0.66 → −0.79.

### New listings open expensive and the premium decays — where liquidity arrives
First 14 days versus last 14 days of each pool's life:

| ticker | pool starts | first 14d | next 14d | last 14d |
|---|---|---|---|---|
| AVGO | 2026-03-16 | **+9.01%** | +0.37% | +0.26% |
| KO | 2026-02-23 | **+5.10%** | +2.29% | +2.12% |
| ORCL | 2026-03-20 | +1.16% | +1.18% | +0.81% |
| MCD | 2026-03-20 | +1.16% | +1.34% | **+1.78%** |

Four tickers opened above 1%. Two collapsed (AVGO by 8.7 points), two did not — and the two
that did not are the illiquid ones. **State the sample size when quoting this: n = 4.**

### Liquidity explains part of it, and only part
Across the 18 tickers with 30 days of data, the correlation between **log10 pool liquidity**
and **|mean 30-day basis|** is **−0.47**. Thinner pool, bigger gap — which is what you would
expect if the gap is closed by arbitrage that has to pay slippage: ORCLx carries the largest
persistent premium and quotes **17.23% price impact on a $10,000 buy**.

But it is not the whole story, and the counter-example is the biggest pool in the sample:
**SPYx, at $2.9M liquidity and 0.00% impact on $10,000, still sits at a stable +0.5%.**
Something other than trading friction is holding that one up — funding cost, creation
mechanics, or simply demand for on-chain S&P exposure that the redemption path does not
arbitrage away quickly. This study does not identify it and should not pretend to.

---

## The explanation, found late in the planning window (2026-09-19 ~23:05 CEST)

The structural premium is not a mispricing. It is **dividends**.

Trailing 12-month dividend yield against mean 60-day basis, 18 tickers:

| ticker | yield %/yr | mean basis % |
|---|---|---|
| MCD | 3.00 | +1.35 |
| KO | 2.38 | +2.03 |
| ORCL | 1.35 | +1.07 |
| SPY | 1.24 | +0.53 |
| AVGO | 0.71 | +0.67 |
| QQQ | 0.42 | +0.23 |
| META | 0.32 | +0.07 |
| GOOGL | 0.25 | +0.07 |
| NVDA | 0.23 | +0.15 |
| TSLA, GLD, CRCL, MSTR, COIN, HOOD, AMZN, INTC, PLTR | 0.00 | **−0.24 … +0.16** |

- **corr(dividend yield, basis) = +0.924**, n = 18.
- **Nine zero-yield tokens average −0.096%. Nine dividend payers average +0.687%.**
- It is not a liquidity artefact: **partial corr(yield, basis | log liquidity) = +0.929**.
  Liquidity has its own smaller, independent effect: partial corr = **−0.501**.
- Regression: **0.647 pp of basis per 1 pp of annual yield**, intercept −0.06%.

And the mechanism is documented by the issuer: Backed Finance's xStocks **reinvest dividends
into the token rather than paying cash** — the token's value rises to reflect distributions
the holder never receives separately.

**So comparing an xStock to its underlying's *price* quote and calling the gap a premium is
a category error.** The token is a total-return instrument; Yahoo's `regularMarketPrice` is
price-return. For a 3%-yield name that is more than a percentage point of phantom "premium",
and a naive screener would print it as if the buyer were being overcharged. **[SUPERSEDED —
see the CORRECTION at the end of this file: stocksonsolana.com already applies the
multiplier, and the party computing the basis wrongly was this analysis.]**

### What this does not establish
The time-series does not behave like simple continuous accrual: regressing each ticker's
basis on time gives noisy slopes (R² ≈ 0.00–0.15) and **corr(yield, annualised drift) =
−0.17**, dominated by AVGO and KO decaying from their listing-day premiums. So the
cross-section is explained; the accrual and reset dynamics are not. State it as a strong
association with a documented, plausible mechanism — not as a proven accounting identity.

### What it changes in the product
The board's baseline column is now interpretable rather than merely empirical: a ticker's
"normal" basis is approximately its accrued distribution. The number worth showing a trader
is the **deviation from that**, which is what the z-score already does — and, for dividend
payers, the honest label for the baseline is "accrued dividends", not "premium".

### Out-of-sample check (same session)
Four tickers held out and predicted from yield alone before measurement — XOM, PEP, UNH,
LLY, on pools of only $5k–19k: **corr = +0.885**, mean |error| **1.01pp**.
Pooled over all 22: **corr = +0.892**, slope **0.754**, intercept **−0.157%**.
Zero-yield group: n=9, mean **−0.096%**, **sd 0.137** — essentially exactly on spot.
Payers: n=13, mean **+0.954%**, sd 1.174.

### The event study that did NOT confirm it
If the premium is accrued dividends, the basis should step up around each ex-dividend date.
Comparing mean basis in the 7 days before and after each ex-div date inside the sample
window, 15 events across 9 payers:

- **11 of 15 steps are positive**, which is suggestive;
- but the mean step is **+0.036pp** against a mean dividend of **0.302%**, and the largest
  single move is AVGO's **−6.07pp** on 2026-03-23, which is its listing-premium decay rather
  than anything to do with the dividend;
- **corr(dividend size, basis step) = +0.271** — weak.

So the event study is too noisy to confirm the mechanism. The honest position is therefore:
**the cross-sectional association is strong, controlled and validated out of sample
(r = +0.892, n = 22; zero-yield group mean −0.096% with sd 0.137), the issuer documents
reinvesting dividends into the token, and that is the obvious explanation — but neither the
time-series drift nor the ex-dividend event study confirms the accrual dynamics directly.**

Publish it at exactly that strength. The cross-section is the finding; the mechanism is the
best available explanation for it, not a demonstrated one.

### The test that nearly overturned it, and what it actually showed
Pulling the **whole xStocks universe from Jupiter's token API (125 tokens)** and testing
yield against a *single live snapshot* of the basis gives **corr = +0.141 across 74 tickers**
— nothing like the +0.892 above. At a $2,000 liquidity floor it is even **−0.383**.

Run both tests on the **same 17 tickers** and the reason is obvious:

| basis measured as | corr with dividend yield |
|---|---|
| **60-day mean** | **+0.922** |
| **single live snapshot** | **+0.042** |

Mean absolute gap between a ticker's 60-day mean basis and its snapshot: **0.79pp**. Daily
noise is of the same order as the whole dividend signal, so one observation per ticker
cannot see it.

Two things follow. First, the finding survives — but it is a statement about **time-averaged**
basis, and must be written that way. Second, it explains why nobody has noticed: **the number
a screener shows you live cannot reveal this.** You have to average, per ticker, over weeks.
That is precisely what the board's baseline column is, and it is the reason the baseline is
worth showing at all.

### Data-quality note that came out of the same pull
Jupiter's liquidity figures and DexScreener's disagree wildly on thin tokenised-equity pools.
DexScreener reported **PFEx at $547,815,796**; Jupiter reports **$222**. Also DexScreener vs
Jupiter: MAx $154,234,007 vs $439; WMTx $386,594,314 vs $9,244; ORCLx $20,451 vs $4,224.
Jupiter's numbers are consistent with the Jupiter quote engine's own price impact (PFEx
quotes 100% impact on $1,000). **Use Jupiter for liquidity; DexScreener's reserve field is
not trustworthy on these pools.**

---

## The answer, and it is exact (2026-09-20 ~00:10 CEST)

The dividend correlation was a shadow of the real thing. xStocks on Solana are **Token-2022
mints carrying the `scaledUiAmountConfig` extension**: one raw token represents `multiplier`
shares, and the multiplier rises with every reinvested dividend and split. The issuer
documents this (`docs.xstocks.fi/docs/dividends-and-stock-splits`); what nobody seems to have
done is read the number off-chain and check it against the prices people are quoting.

One `getAccountInfo` call per mint returns it. For SPYx:
`scaledUiAmountConfig { multiplier 1.003909240, newMultiplier 1.005714560,
newMultiplierEffectiveTimestamp 1781755200 }` — effective now, so **+0.5715%**.

Implied premium `(multiplier − 1)` against the measured 60-day mean basis:

| ticker | multiplier − 1 | raw 60-day basis | **multiplier-adjusted** |
|---|---|---|---|
| KO | +2.256% | +2.03% | **−0.22%** |
| MCD | +2.118% | +1.35% | **−0.77%** |
| ORCL | +0.932% | +1.07% | **+0.14%** |
| AVGO | +0.616% | +0.67% | **+0.06%** |
| SPY | +0.571% | +0.53% | **−0.04%** |
| META | +0.285% | +0.07% | −0.22% |
| QQQ | +0.273% | +0.23% | **−0.05%** |
| GOOGL | +0.238% | +0.07% | −0.16% |
| NVDA | +0.170% | +0.15% | **−0.02%** |
| GLD · CRCL · MSTR · HOOD · COIN · PLTR · AMZN · INTC | **0.000%** | −0.24 … +0.16% | unchanged |

**Mean |basis| falls from 0.435pp to 0.170pp; the standard deviation falls from 0.612 to
0.209.** Every token with a multiplier collapses toward parity, and every token whose
multiplier is exactly 1.000 was already there.

So it is not a correlation with dividend yield. It is an identity: **the "premium" is the
multiplier.** The dividend-yield correlation was simply measuring the multiplier indirectly,
because the multiplier is what dividends do to these tokens.

### Why this matters to somebody
- Any Solana venue that does not apply `scaledUiAmountConfig` **misprices these tokens** — by
  up to **2.26% on KOx** today, and by more as multipliers grow.
- Screeners in this category print that error as "discount to real-world price".
- The correct comparison is `token_price / (multiplier × spot) − 1`, and the multiplier is
  one RPC call away.
- The multiplier steps at **00:30 UTC after each ex-date**, and xStocks explicitly advise
  venues to pause around that timestamp — a scheduled, published, repeating discontinuity in
  the quoted price of a live market.

### Consequence for this project's own board
The board must apply the multiplier, or it repeats the mistake it is pointing at. It shows
raw basis, the multiplier, and the adjusted basis side by side, so the reader can see which
part of the "premium" is an accounting artefact and which part is a market.

---

## CORRECTION (2026-09-20 ~00:30 CEST) — the accusation was wrong, check it before publishing

The draft written twenty minutes ago said Solana's tokenised-stock screeners print the
multiplier as a mispricing. **That is false for the leading one, and I checked before
publishing rather than after.**

Measured the same minute:

| | raw DEX price | multiplier | multiplier-adjusted | what stocksonsolana.com shows |
|---|---|---|---|---|
| SPYx | 768.84 | 1.005715 | **764.47** | **$763.50**, mark +0.24% vs spot $761.69 |
| MSTRx | 158.05 | 1.000000 | 158.05 | $157.49, mark +2.81% vs spot $153.19 |

`stocksonsolana.com` is already applying the multiplier — its displayed price matches the
adjusted figure, not the raw pool price. Its "MARK" column is therefore a *correct* premium,
not the artefact. Whatever other venues do, the obvious target of that accusation does it
right.

**So the party that had this wrong was this analysis.** Every basis number computed earlier
in this file came from raw DexScreener pool prices with no multiplier applied — which is why
dividend yield "explained" the premium so well: I was measuring the multiplier and calling
it a market.

### What actually survives, stated at the strength it deserves
1. **The correct measurement**: `token_price / (multiplier × spot) − 1`, with the multiplier
   read from the mint's `scaledUiAmountConfig`. This is documented by the issuer; it is not
   a discovery.
2. **What the corrected number says**: after adjustment these tokens trade essentially at
   parity — mean |basis| **0.170pp**, sd **0.209**, down from 0.435/0.612 raw.
3. **The residual is real and concentrated**: crypto-beta names at weekends, when the
   underlying is shut. MSTRx has no multiplier and still shows **+2.68%** right now.
4. **And it is not tradeable**: +0.42pp of 4-hour edge against ~0.6% of round-trip cost.
5. **The liquidity data-quality finding stands on its own** and is independent of all of
   this: DexScreener reports PFEx at $547,815,796 where Jupiter reports $222 and quotes 100%
   price impact on $1,000.

The publishable piece is therefore a measurement note, not an exposé. Rewrite it that way.
