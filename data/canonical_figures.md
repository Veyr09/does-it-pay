# Canonical figures (re-derive before publishing anything that quotes them)

All measured 2026-09-19 between 18:00 and 20:40 CEST.

## BountyBook (api.bountybook.ai)
- `GET /jobs?status=open` → **101 unique open jobs, $451.51 advertised** (their own
  `/stats` says `openCount 123`, `totalAvailable 638.01`).
- `/stats`: total 206, totalBudget $947.15, **totalPaidOut $174.71**, completed 54,
  activeAgents 20, workingAgents 6.
- Poster behind 99 of 100 first-page jobs: `0xcef19483e5fb8385d7a785c071f640a290cd1143`
  → **0.00 USDC, 0 ETH on Base**.
- Platform payer wallet seen settling a real payout: `0x1bc6c2268260c391c7871cf9f2dfa43207f72f2b`
  → **0.40 USDC**. Example settled payout tx `0xe6f5e8ae…` = 0.416667 USDC.
- Of 54 verified jobs: **28 confirmed ($58.21), 26 failed ($116.50)**.
- One poster is `0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266`, the standard Hardhat/Anvil
  test account.

## taskmarket.dev (Daydreams Systems)
- 4 open tasks, **$210.91 advertised, all four carrying an on-chain `escrowTxHash`**.
- Escrow holder for the $199 task: `0xddc6cc3e4d11c1f3527b867c7dad4ed9869c33f7`
  → **966.85 USDC on Base**. Funding is real.
- Submission economics: **first 5 submissions per bounty are free**, later ones need an
  x402 payment. Live $9.90 task had **76 submissions**; $2.00 task had 60.

## AgentPact
- Claims 4,417 agents / 4,212 offers / 475 open needs (`/api/public/overview`).
- Immutable escrow `0x588168712bF758aFD747bF46471afa53f9599A64`:
  **$13.62 lifetime**, last USDC transfer **2026-09-01T22:57:29Z**.

## AgentHansa
- 171 quests, **all `settled`**, $10,988 lifetime rewards, **zero open**.

## x402 / Bazaar
- CDP discovery API, **6,000 resources sampled** (the larger sample supersedes an earlier
  1,500-resource one): calls in last 30 days **median 3, p75 7, p90 23, p99 664,
  max 121,144**; price per call **median $0.01, p90 $0.05**; estimated 30-day revenue per
  resource **median $0.12, p75 $0.48, p90 $1.99, p99 $9.00**.
- Networks advertised across those resources: Base 6,385, Solana 1,874, Polygon 798,
  Arbitrum 746.
- **No agent task-marketplace endpoint appears in the Bazaar at all** (searched 3,000
  resources for agenthire / clustly / taskmarket / bountybook / agentpact / clawearn /
  aiagentstore / agenthansa: zero matches). AgentHire's self-reported "$50K volume on
  Solana" is therefore unverified here and must be quoted as self-reported.
- Ecosystem (`api.agentic.market/v1/ecosystem/*`): **$1,360,645 settled over 30,471,182
  payments in 30 days**, ~2,600 unique buyers/day, 700–1,500 unique sellers/day.

## Salad / consumer GPU
- RTX 5070 Ti **$0.079/hr** median, $0.165 top decile, 96% of hours earning.
- Marginal electricity 0.28 kW × ~$0.25/kWh = **$0.070/hr**.

## Headline
Across the two marketplaces with an open queue, **$658.42 of work is advertised and
$210.92 of it is backed by money that exists on-chain — 32%**, all of it on one platform.

## Liquidity that is not liquidity (added 2026-09-19 21:00 CEST)
`PFEx` is listed on DexScreener with **$547,815,796 of reported pool liquidity** and a
−5.65% discount to spot. Jupiter quotes **100.00% price impact on a $1,000 buy**. The
reserve figure is meaningless and the "discount" is untradeable. It has been removed from
the verified universe.

Same class of problem, smaller: `ORCLx` quotes a +0.02% premium with **4.12% impact on
$1,000 and 17.23% on $10,000**; `AVGOx` 2.19% / 3.92%; `INTCx` 0.30% / 3.39%.

Verified universe after pruning: **20 tickers** — SPY QQQ NVDA TSLA AAPL MSFT META GLD CRCL
MSTR COIN HOOD AMZN GOOGL INTC PLTR ORCL AVGO KO MCD.

## The escrow-level size of the agent-work economy (2026-09-19 ~21:15 CEST)
Every one of these is an ERC-20 transfer history on Base, read from
`base.blockscout.com/api/v2/addresses/<addr>/token-transfers?type=ERC-20`.

| platform | escrow address(es) | lifetime USDC in | out | latest transfer | by month |
|---|---|---|---|---|---|
| **taskmarket.dev** | `0xddc6cc3e…` (escrow) | **$928.35** | $310.67 | **2026-09-19** | Aug $606.25, Sep $632.77 |
| taskmarket.dev | `0x8884f95b…` (contract) | $2,629.63 | $0.00 | 2026-09-18 | Jul $1,586.13, Aug $884.21, Sep $159.28 |
| **Claw Earn** | 4 contracts (`0xa2808f8b…`, `0xd59439e3…`, `0x33654112…`, `0x1845e2dc…`) | **$2,891.25** | $809.76 | 2026-09-01 | Mar $556, Apr $621, **May $2,268**, Jun $195, Jul $44, **Sep $17** |
| **AgentPact** | `0x58816871…` | **$13.62** | $13.62 | 2026-09-01 | Feb $7, May $6, Sep $14 |
| BountyBook | no escrow contract; pays from a hot wallet holding **$0.40** | — | $174.71 claimed | — | — |

**Total ever settled through the escrows of the agent task-marketplace category: roughly
$6,400.** [SUPERSEDED — see CORRECTED CATEGORY FIGURES below.] The only one currently alive is taskmarket.dev, and
Claw Earn — which peaked at $2,268 in May 2026 — did **$17 in September**.

Note the distinction that the narrative collapses: **x402 API payments** are genuinely
large ($1,360,645 over 30 days, 30.5M payments averaging $0.045 — agents buying search,
inference and data). **Agent task marketplaces**, where an agent is paid to do a piece of
work, are a few thousand dollars in total, ever. These are not the same economy.

Caveat to state when publishing: this covers the escrow contracts I could identify on Base
for the platforms in the gigs.sh directory. Solana-settled platforms (AgentHire, Clustly)
and any off-chain settlement are not included, and gigs.sh's own snapshot is dated
2026-05-18 — which, on this evidence, was close to the category's peak.

## Correction made during research
`clawearn.com` is a **parked GoDaddy domain and is not the platform**. Claw Earn lives at
`aiagentstore.ai/claw-earn`; it is real, in beta, and currently shows
**0 available tasks, 1 occupied, 83 completed**. Nearly published the wrong claim.

## The directory itself is stale
`github.com/gigs-sh/gigs-sh` — 47 listing files, **last commit 2026-05-20**. Its published
snapshot date is 2026-05-18. Four months without an update, over exactly the period in
which Claw Earn's escrow went from $2,268/month to $17/month.

## Clustly, from its own browse page (2026-09-19)
`clustly.ai/browse` publishes its own counters: **646 on the network, 435 services live
(147 agents, +20 this week), 110 agents active in the past 24h, and USDC SETTLED $1,952
across 436 confirmed mainnet transfers** (page notes clustly.ai figures as of 2026-07-21).
Average confirmed transfer: **$4.48**.

The number that matters for anyone thinking of listing: of 435 live services, the "has
completed hires" filter counts **10**. Supply exceeds demand by roughly 40 to 1.

## Revised category total
| platform | lifetime USDC settled | source |
|---|---|---|
| Claw Earn | $2,891.25 | 4 Base escrow contracts, ERC-20 transfer history |
| Clustly | $1,952 | platform's own published counter (Solana mainnet) |
| taskmarket.dev | $928.35 | Base escrow wallet `0xddc6cc3e…` |
| BountyBook | $174.71 | platform's own `/stats` `totalPaidOut` |
| AgentPact | $13.62 | immutable escrow `0x58816871…` |
| **total** | **≈ $5,960** | |

So "about $6,000" was the headline at this point. [SUPERSEDED below: spam tokens and truncated pagination. The verified figure is $2,492 paid out of Base escrows, ~$4,600 across the category.] It included the largest Solana-settled
platform rather than only the Base slice.

## AgentHire (2026-09-19 ~22:40 CEST)
Homepage counters: **"500+ Active Agents · 10K+ Jobs Completed · $50K+ Volume Processed"**,
settlement described as x402/USDC on Solana.

Checked against the platform's own surfaces the same minute:
- `www.agenthire.app/agents` (its public Agent Directory) renders
  **"No agents found matching your criteria."**
- `GET /api/v1/agents?limit=5` returns **HTTP 500 `{"error":"TypeError: fetch failed"}`**.
- `/jobs` and `/analytics` both require registering an agent, so neither is publicly checkable.
- Zero AgentHire endpoints appear in the x402 Bazaar (3,000 resources searched).

Write it up neutrally: the backend is erroring, so the honest statement is that the claimed
figures are **self-reported and not verifiable from any public surface**, not that they are
false. Excluded from the category total for that reason.

## NEAR / agent.market (2026-09-19)
`market.near.ai` redirects to `agent.market`. `api.agent.market/jobs` has returned
**HTTP 502 Server Error** on every attempt across several hours. Not measurable; excluded.

## Numbers I did NOT measure and must attribute, not assert
- "$684M tokenised equity supply on Solana, +47% in three weeks" — Solana Compass,
  2026-09-11. Second-hand; attribute it or drop it.
- "xStocks ~$800M AUM, ~two-thirds on Solana" — xStocks' own post, 2026-09-11. Second-hand.
- Clustly's $1,952 settled and BountyBook's $174.71 paid out are **platform self-reports**,
  not independent reads. Base escrow figures (Claw Earn, taskmarket, AgentPact) are direct
  ERC-20 transfer reads and can be stated as measured.

## Address identities verified on Blockscout (2026-09-20 ~00:55 CEST)
Before publishing anything that names a platform, each address was checked to be what the
platform's own API said it was:
- Claw Earn's four: `0xa2808f8b…` **ClawEscrow**, `0xd59439e3…` **ClawEscrowAgentFast**,
  `0x33654112…` **ClawEscrow**, `0x1845e2dc…` **ClawEscrowAgentFast** — all verified
  contracts. Caveat to state: these are the four their API lists as *active*; deprecated
  contracts, if any, are not in the $2,891.25 total.
- AgentPact `0x58816871…` → verified contract **AgentPactEscrow**.
- taskmarket.dev `0xddc6cc3e…` → verified contract named **Diamond** (an EIP-2535 diamond
  proxy, i.e. the protocol's own escrow, not somebody's wallet). `0x8884f95b…` → verified
  **TaskMarketForwarder**.
- BountyBook `0xcef19483…` (poster of 99/100 open jobs) and `0x1bc6c226…` (the wallet that
  settled the one payout traced) are **both externally owned accounts, not contracts** —
  consistent with BountyBook paying from a hot wallet rather than an escrow.

---

# CORRECTED CATEGORY FIGURES (2026-09-20 ~00:35 CEST) — supersede everything above

Two bugs in the earlier escrow numbers, both found by reconciling against current balances:

1. **Spam tokens were counted.** The first pass summed *all* ERC-20 transfers. Claw Earn's
   escrows have received tokens named "nokycswap.vip to noKYC swap", "zkSwap.vip…" and
   similar. Filtering strictly to USDC `0x833589fc…` changes Claw Earn's lifetime **in**
   from **$2,891.25 to $882.25**.
2. **Pagination was truncated.** taskmarket.dev's escrow has **1,428 transfers**, not the
   ~400 the first pass read.

## Verified, USDC only, complete pagination

| platform | escrow | USDC in | USDC out | held now |
|---|---|---|---|---|
| taskmarket.dev | `0xddc6cc3e…` (Diamond) | **$2,732.89** | **$1,667.98** | $966.85 |
| Claw Earn | 4 × ClawEscrow* | **$882.25** | **$809.76** | $97.44 |
| AgentPact | `0x58816871…` | **$13.62** | **$13.62** | ~0 |
| **Base total** | | **$3,628.76** | **$2,491.36** | **$1,064.29** |

(taskmarket in − out − held leaves ~$98 unexplained; treat the reconciliation as
approximate to within about 4%.)

## USDC paid OUT of escrow, by month — the number that matters

| month | Claw Earn | taskmarket | AgentPact | **all** |
|---|---|---|---|---|
| 2026-02 | 0 | 0 | 2 | **2** |
| 2026-03 | 219 | 0 | 0 | **219** |
| 2026-04 | 316 | 0 | 0 | **316** |
| 2026-05 | 225 | 0 | 4 | **229** |
| 2026-06 | 21 | 409 | 0 | **430** |
| 2026-07 | 21 | 440 | 0 | **461** |
| 2026-08 | 0 | **758** | 0 | **758** |
| 2026-09 (to 19th) | 8 | 61 | 7 | **76** |
| **lifetime** | **810** | **1,668** | **14** | **2,492** |

**So the whole Base-settled agent task-marketplace category has paid out about $2,500 in its
life, and its best month ever was August 2026 at roughly $758.** Adding Clustly's
self-reported $1,952 on Solana and BountyBook's self-reported $174.71 gives **~$4,600
across the category**, of which **$2,492 is independently verifiable on-chain**.

## Claims that must be retracted from earlier drafts
- ~~"about $6,000 has ever settled"~~ → **~$4,600 across the category, $2,492 verifiable.**
- ~~"Claw Earn $2,891.25 lifetime"~~ → **$882.25 in, $809.76 out.**
- ~~"the category peaked in May"~~ → **Claw Earn peaked in April; taskmarket.dev grew through
  August ($409 → $440 → $758). The category's best month is August 2026.** September is
  running at $76 so far, with $966.85 still sitting in taskmarket's escrow against open tasks.
