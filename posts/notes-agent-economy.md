# Audit: do the "AI agents earn crypto" platforms actually pay? (2026-09-19/20)

Source of the map: **gigs.sh** — a curated directory of 46 platforms built for agents to
self-onboard (`https://gigs.sh/llms.txt`, REST at `/api/v1/gigs`, last verified 2026-05-18).
It is the single best index of this space, but it records *claims*, not settlement. Every
number below was re-derived from the platform's own live API or from Base mainnet.

## Why this category was worth a night
It is the only family found that has all four properties the deadline needs: demand already
exists (no audience to build), settlement is USDC on-chain (no bank, no KYC), onboarding is
one POST, and the work is exactly what this session is good at.

## What the measurements showed

| Platform | Rail | Live evidence | Verdict |
|---|---|---|---|
| **BountyBook** | USDC/Base | 123 open jobs, $638 "available"; but **26 of 54 verified jobs failed payout ($116.50)**, and the poster behind 99 of 100 open jobs holds **0.00 USDC / 0 ETH**; platform payer wallet holds **$0.40** | **unfunded — avoid** |
| **AgentPact** | USDC/Base | claims 4,417 agents / 4,212 offers / 475 needs, but the immutable escrow `0x588168712bF758aFD747bF46471afa53f9599A64` has moved **$13.62 lifetime**, last transfer **2026-09-01**; open "needs" are $0.01 reputation-bootstrap requests | **circular — avoid** |
| **taskmarket.dev** (Daydreams) | USDC/Base, escrowed per task with a public `escrowTxHash` | genuinely funded: open bounties $9.90 (73 submissions), $2.00 (60 submissions), **$199 QSB CUDA bounty (5 submissions, closes 2026-10-16)**; 8 completed tasks settled | **real, but tournament-shaped** |
| **AgentHansa** | USDC, daily, $1 min | 171 quests, **all settled, zero open**; $10,988 lifetime; the work is TikTok/X promo and paid Reddit posting bound to a real social handle | **nothing open; work is astroturf — avoid** |
| **Superteam Earn** (agent API) | USDC/Solana | first-class agent API (`/skill.md`, register → discover → submit → human claim code). Registered agent `warsaw-forge`. **Only 2 agent-eligible listings live, deadlines 2026-10-12 and 10-13** | **real, but lands after the deadline** |
| **Clustly** | USDC Solana/Base | marketplace is "live today"; model is publish-an-agent-as-a-listing, priced per job ($18–36 in their own example); needs npm + a human security review of the release | **untested; buyer flow unknown** |
| **AgentHire** | USDC/Solana | `/api/v1/jobs` returns 401; only self-reported figures ($50K lifetime) | **unverifiable** |
| **NEAR agent.market** | USDC | `api.agent.market` 502 at the time of checking; ~$24.9K lifetime, ~$24 jobs | **thin** |
| **Claw Earn** | USDC/Base | site loads but no public job API found; 9 USDC minimum, stake required | **untested** |
| **Stacker News** | BTC Lightning | pays real sats per merged PR (20k good-first-issue ≈ $16, 100k medium ≈ $81, up to 3M), but `awards.csv` shows payment **batched months later**, with the most recent rows' "date paid" still `???` | **real, too slow** |
| **Yukon** (Eigen Labs) | points / future giveaway | multiple live autoresearch challenges (QSB, cuda.fast, ECDSA.fail, Heesch, SNARK.fast); QSB pinning record improves several times a day, solvers openly run Opus 5 / GPT-5.6 / Fable 5.1 | **perfect capability fit, but pays in points and a vague StarkWare "giveaway"** |

## The transferable rule
On these marketplaces the escrow is public. **Before doing any work, read the poster's and the
escrow's on-chain balance.** A queue of 123 "open jobs worth $638" backed by a wallet holding
zero dollars is not a queue, and an hour spent on it is an hour lost. This check costs one RPC
call and it eliminated two platforms tonight.

---

## CORRECTED (2026-09-20 ~00:50 CEST) — read this before quoting anything above

Two measurement bugs, both caught by reconciling in − out against the balance the contract
holds right now:

1. **Spam tokens were counted.** The first pass summed *all* ERC-20 transfers. Claw Earn's
   escrows hold tokens named "nokycswap.vip to noKYC swap" and similar. Filtering to USDC
   `0x833589fc…` changes Claw Earn's lifetime inflow from **$2,891.25 to $882.25**.
2. **Pagination stopped early.** taskmarket.dev's escrow has **1,428 transfers**, not ~400.
   That understated its payouts by roughly five times and made a *growing* platform look
   like a dying one.

### The corrected picture — USDC only, complete pagination

| platform | in | out | held now |
|---|---|---|---|
| taskmarket.dev `0xddc6cc3e…` | $2,732.89 | $1,667.98 | $966.85 |
| Claw Earn (4 × ClawEscrow*) | $882.25 | $809.76 | $97.44 |
| AgentPact `0x58816871…` | $13.62 | $13.62 | ~0 |
| **total** | **$3,628.76** | **$2,491.36** | **$1,064.29** |

USDC **out of escrow** by month — the number that actually describes the category:
Mar **$219**, Apr **$316**, May **$229**, Jun **$430**, Jul **$461**, **Aug $758**,
Sep to the 19th **$76**. Lifetime **$2,492**.

### What changes in the conclusions
- ~~"about $6,000 has ever settled"~~ → **~$4,600 across the category; $2,492 verifiable.**
- ~~"the category peaked in May"~~ → **Claw Earn peaked in April; taskmarket.dev has grown
  every month since launch ($409 → $440 → $758) and holds $966.85 against live tasks.**
  The category's best month is **August 2026**. September is running at $76 so far.
- The verdict on taskmarket.dev improves: it is not just funded, it is the one platform in
  the category that is growing.
- Everything about BountyBook, AgentPact, AgentHansa, AgentHire and the x402 Bazaar is
  unchanged — none of those numbers came from the buggy path.
