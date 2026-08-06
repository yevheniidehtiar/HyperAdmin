# Community Donation Options

## Overview

HyperAdmin relies on an autonomous agentic workflow powered by Claude Max (~$100/month). To make this infrastructure sustainable as the project grows, we are researching community funding models. This document summarizes the available platforms, evaluates their suitability for our use case, and recommends a minimum viable setup.

## Platform Comparison

| Feature | GitHub Sponsors | Open Collective | Polar.sh | Buy Me a Coffee | Ko-fi |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Platform Fees** | **0%** (GitHub covers fees for individuals) | 10% (Platform + Fiscal Host) | 4% + 40¢ per transaction | 5% | **0%** (optional gold tier) |
| **Payment Processing** | Stripe (standard credit card fees ~2.9% + 30¢) | Stripe/PayPal | Stripe built-in | Stripe | Stripe/PayPal |
| **Payout Schedule** | Monthly (via Stripe Connect) | On demand / Monthly | Monthly / Manual | Instant | Instant |
| **Tax/Legal (MoR)** | No (You handle taxes) | **Yes** (Acts as Fiscal Host) | **Yes** (Merchant of Record) | No | No |
| **Repo Integration** | Native (`FUNDING.yml` / GitHub UI) | Badges only | Deep (Issues, PRs, Badges) | Links/Badges | Links/Badges |
| **Best For** | Standard OSS sponsorship | Shared treasury/teams | Direct issue bounties & MoR | Casual tips | Casual tips |

## Platform Analysis

### 1. GitHub Sponsors
**Pros:** Native integration is unbeatable. Users don't leave GitHub. 0% platform fees for individuals means maximum money goes to API costs. Highly trusted by the developer community.
**Cons:** You act as your own Merchant of Record (MoR). You are responsible for local tax compliance. Payouts require a Stripe Connect account.
**Verdict:** **Strongest candidate** for general recurring sponsorship.

### 2. Polar.sh
**Pros:** Deeply integrated into the GitHub ecosystem. Acts as the Merchant of Record (MoR), which means they handle all VAT/sales tax compliance automatically. Built specifically for OSS. Allows users to pledge money directly to specific issues.
**Cons:** 4% platform fee is higher than GitHub Sponsors.
**Verdict:** **Excellent alternative**, especially if we want to combine recurring sponsorships with issue-specific bounties while offloading tax liability.

### 3. Open Collective
**Pros:** Extreme transparency. Acts as a fiscal host (they hold the money, handle taxes, and you submit expenses). Great for teams where multiple maintainers need to be paid out.
**Cons:** 10% total fee is the highest of the bunch. Heavyweight setup for a single $100/mo API bill.
**Verdict:** Overkill for our current needs.

### 4. Ko-fi / Buy Me a Coffee
**Pros:** Easy to set up. Good for one-off tips.
**Cons:** Not native to the developer/OSS workflow. Lacks the professional integration of GitHub Sponsors or Polar.sh.
**Verdict:** Not recommended for this specific OSS use case.

## Recommended Approach

We recommend starting with **GitHub Sponsors** as the primary platform, supplemented by **Polar.sh** if issue-level bounties or tax offloading (MoR) become a priority.

1. **Why GitHub Sponsors?** Zero fees for individual maintainers means a single $100 sponsor completely covers the Claude Max bill. The native `FUNDING.yml` integration places the Sponsor button directly on the repo homepage, maximizing visibility.
2. **License Implications:** Accepting donations does not affect the MIT License. The MIT license grants broad usage rights without warranty. Sponsorships are strictly voluntary financial support, not a purchase of software rights or a change in the licensing terms.
3. **Comparable Projects:** Projects like *FastAPI*, *Pydantic*, and *Auto-GPT* successfully use GitHub Sponsors to fund API costs, CI/CD infrastructure, and maintainer time. They universally leverage the native `FUNDING.yml` integration.

## Proposed Sponsor Tiers

| Tier | Amount | Perks |
| :--- | :--- | :--- |
| **Supporter** | $5/month | Name listed in `CONTRIBUTORS.md` under a special "Backers" section. |
| **Backer** | $20/month | Name and link in the `README.md` Sponsors section. |
| **Sponsor** | $100/month | Covers exactly one month of Claude Max. Prominent logo placement in `README.md`. |
| **Patron** | $200/month | All previous perks + Direct input on roadmap priorities and feature requests. |

## Next Steps: Minimum Viable Setup

To activate this, we only need to commit a `FUNDING.yml` file to the repository.

Create `.github/FUNDING.yml`:
```yaml
# These are supported funding model platforms

github: [yevheniidehtiar] # Replace with actual GitHub Sponsors username
# polar: yevheniidehtiar # Uncomment if setting up Polar.sh
```

Once the GitHub Sponsors profile is approved and the file is merged, the native "Sponsor" button will appear on the repository.
