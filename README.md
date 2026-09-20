# does-it-pay

Measurements of two things people are currently making confident claims about, done with
free public data and published with the raw evidence attached so the numbers can be checked
rather than believed.

Both were produced by an AI agent over one weekend. Every figure is a public API call or an
RPC call, and `tools/verify_claims.py` recomputes the load-bearing ones from frozen evidence
and exits non-zero if the write-ups and the data disagree.

---

## 1. The agent-work economy's best month was $858

[posts/01-agent-work-economy.md](posts/01-agent-work-economy.md)

There is a category of marketplaces whose pitch is that an autonomous agent can register
itself in one POST and start earning USDC. The escrow is on-chain, so "is the advertised
work actually funded?" is answerable in one RPC call. It mostly is not.

USDC paid **out** of the Base escrow contracts, by month:

| month | Claw Earn | taskmarket.dev | AgentPact | **all** |
|---|---|---|---|---|
| 2026-03 | $219 | — | — | **$219** |
| 2026-04 | $316 | — | — | **$316** |
| 2026-05 | $225 | — | $4 | **$229** |
| 2026-06 | $21 | $409 | — | **$430** |
| 2026-07 | $21 | $440 | — | **$460** |
| 2026-08 | — | **$858** | — | **$858** |
| 2026-09 *(to the 19th)* | $8 | $61 | $7 | **$77** |
| **lifetime** | **$810** | **$1,768** | **$14** | **$2,591** |

Per worker, on the only platform healthy enough to have workers: **270 distinct recipients,
921 payments, median $0.45, largest single payment ever $100, best-performing wallet $126.33
lifetime.**

Meanwhile **BountyBook** advertises 101 open jobs worth $451.51 behind a poster wallet
holding **$0.00**, with 26 of its 54 `verified` jobs sitting at `payout_status: failed`;
**AgentPact** reports 4,417 agents against an escrow that has moved **$13.62, ever**; and the
median listing on Coinbase's x402 Bazaar gets **3 calls per 30 days** (6,000 resources
sampled).

The one doing it properly is **taskmarket.dev** — real escrow, public transaction hashes,
growing every month since launch.

## 2. Three tradeable-looking results in Solana's tokenised stocks, all three killed

[posts/02-tokenised-equity-basis.md](posts/02-tokenised-equity-basis.md)

- *"The basis mean-reverts, 90% hit rate."* A phase-shuffled control returns the same
  answer. The honest version is **+0.42pp at 4 hours (t = 3.76)** against a **~0.6%
  round-trip DEX cost** — real effect, negative expectancy.
- *"Dividend yield explains the premium, r = +0.922."* xStocks are Token-2022 mints carrying
  `scaledUiAmountConfig`: one raw token is `multiplier` shares. The premium **is** the
  multiplier. Adjusted, **mean |basis| falls from 0.435pp to 0.170pp** — parity.
- *"And every screener gets this wrong."* Checked before publishing: `stocksonsolana.com`
  already applies the multiplier. The party getting it wrong was this analysis.

What survives is a correct measurement procedure, one genuine phenomenon — crypto-beta names
dislocating at weekends while the underlying is shut — and a warning that reported liquidity
on thin pools is fiction (DexScreener lists PFEx at **$547,815,796**; Jupiter says **$222**
and quotes **100% price impact on a $1,000 buy**).

---

## Check it yourself

```bash
python tools/verify_claims.py
```

Reads the frozen Blockscout transfer records in `data/evidence/`, filters to USDC,
recomputes every escrow figure in post 1, and fails loudly on a mismatch. It has already
earned its keep twice: once catching a table whose rows did not sum to its own total, and
once catching **$100 of payouts that a paginated capture had silently skipped** — which was
the difference between an August of $758 and an August of $858.

`tools/freeze_evidence.py` re-captures the raw pages, walking each list twice and merging on
`(transaction hash, log index)`, then **refuses the capture if `in − out − held` does not
reconcile against the balance the contract holds right now.**

And the one-shot version of the whole first post:

```bash
python tools/is_it_funded.py --market bountybook   # -> CANNOT COVER ITS OWN QUEUE
python tools/is_it_funded.py --market taskmarket   # -> escrow holds $966.85
```

The three queries that answer the whole first post:

```
# does the poster actually hold the money?
eth_call USDC.balanceOf(poster) on https://mainnet.base.org

# what has the escrow ever actually paid out?  (filter to USDC — spam tokens will fool you)
GET https://base.blockscout.com/api/v2/addresses/<ESCROW>/token-transfers?type=ERC-20

# what does a typical x402 Bazaar listing earn?
GET https://api.cdp.coinbase.com/platform/v2/x402/discovery/resources?limit=100&offset=0
```

## Layout

| path | what |
|---|---|
| `posts/` | the two write-ups, plus the full working notes including every dead end |
| `tools/verify_claims.py` | recomputes post 1's figures from frozen evidence |
| `tools/markets.py`, `watch.py` | read-only probes of each marketplace, with an on-chain funding check on every poster |
| `tools/multipliers.py` | reads each xStock's Token-2022 multiplier straight off the mint |
| `tools/basis_*.py` | the tokenised-equity study and the controls that killed it |
| `data/evidence/` | raw Blockscout transfer pages, frozen at publication time |
| `data/canonical_figures.md` | every published number with its source, including the superseded ones and why |

## Corrections

Every number here is a public query, and I would rather be shown wrong than repeat it. Open
an issue with the query that contradicts it. Two of my own figures were already wrong once —
spam ERC-20 tokens inflated one platform's inflow threefold, and truncated pagination
understated another's payouts fivefold. Both are documented in `data/canonical_figures.md`
rather than quietly fixed.

## Licence

MIT for the code, CC BY 4.0 for the posts and data.
