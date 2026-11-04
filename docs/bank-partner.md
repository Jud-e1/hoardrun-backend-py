# Choosing a bank partner

*Prepared November 2026. Not legal advice. A fintech lawyer should confirm the approach (item #19), and every provider fact below needs checking with the provider before you sign.*

## Why Hoardrun needs one before launch

Today Hoardrun keeps customers' cash on its own books. Card and bank deposits land in Hoardrun's own Stripe and bank accounts, mixed with company money. In the US, a company that holds and moves other people's money needs either:

- **a money transmitter licence in almost every state** it operates in (typically years and seven figures), or
- **a bank partner**, which holds customer money in a pooled account "for the benefit of" (FBO) the customers.

With an FBO account, balances can be eligible for FDIC *pass-through* insurance, but only when the records are right. The bank stays responsible to its regulators for what Hoardrun does.

Three things in the product depend on this:

| In the app | Why it needs the partner |
|---|---|
| Hoardrun cash (balances, sends between members, card spending) | Holding and moving customer money |
| Savings goals, fixed deposits at 4–5.5% APY | Paying interest on balances is deposit-like. It has to come from the bank (or be removed). |
| Sending to other people's banks (switched off today) | Paying out to third parties needs a bank to originate it |

Investments are already set up the right way: they're held at Alpaca, a licensed broker-dealer, in each customer's own account (#15). They don't go through the bank partner.

## The realistic routes

| | A. Stripe Financial Accounts (Treasury) | B. A BaaS platform plus its partner bank | C. A sponsor bank directly |
|---|---|---|---|
| Examples | Stripe; balances held at its partner banks (Stripe names Fifth Third, among others) | Unit, Synctera, Treasury Prime | Column, Lead Bank, Cross River, Coastal Community, Grasshopper |
| Fit with Hoardrun today | **Closest.** Card payments (#9) and Hoardrun cards (#14) already run on Stripe, so balances, cards and ACH could all sit in one place. | Good. A new integration for accounts, ACH and cards. | Most control, most work. You build more and run your own compliance with the bank. |
| Typical time to launch (industry estimates) | Weeks to a couple of months, after Stripe approves the use case | 2–4 months | 6–12 months |
| Main risks | Stripe's product limits and approval; the platform carries losses on connected accounts | The middleware layer. When Synapse failed in 2024, customers lost access to money because records didn't match the banks'. | Bank appetite: several sponsor banks have been under regulatory orders, so check status first |

**Recommendation: start with Stripe (route A).** It reuses what's built, keeps card issuing and balances under one provider, and is the shortest path to holding money properly.

Ask Stripe early:
1. Can Hoardrun's consumer use case (individuals, peer-to-peer sends) run on Financial Accounts?
2. Can balances earn interest? If not, fixed deposits need to become goals without interest, or move to a partner bank's CD product.
3. Can Issuing cards spend straight from the financial account?

If Stripe says no to the use case, route B with a platform that shows you its daily reconciliation is next. Route C makes sense once you have a compliance team.

## What every partner will ask for, and where Hoardrun stands

| Requirement | Status |
|---|---|
| Customer identity checks (CIP/KYC) | ✅ Persona ID + selfie (#13); money movement blocked until verified |
| **Daily reconciliation, owner-level records** | ✅ New: `python -m app.services.reconciliation` (below) |
| Account closure and data export | ✅ (#7) |
| Secure hosting, migrations, no secrets in code | ✅ (#16, #17), once the leaked passwords are rotated |
| Accurate marketing (no "bank", no invented figures) | ✅ English pages fixed (below); the 9 other languages still need the same change |
| **Sanctions screening (OFAC)** at sign-up and on payments | ❌ Missing |
| **Transaction monitoring** and suspicious activity reporting (BSA/AML) | ❌ Missing; needs a named BSA officer |
| **Disputes and error resolution** (Regulation E) for unauthorized transfers and card charges | ❌ Missing: no way to report a problem with a payment |
| Monthly statements | ❌ Missing (transactions and CSV export exist) |
| Complaints process | ⚠️ A help page, but no logged, tracked complaints |
| Customer agreements, privacy notice (GLBA), fee schedule, e-sign consent | ⚠️ Generic Terms and Privacy pages; need real ones from counsel (#19) |
| SOC 2 report | Usually asked for within the first year |

The ❌ rows are the engineering work a partner will expect before going live. They're good candidates for right after #19.

## The reconciliation tool

A partner compares, every day, the balance of the FBO account with what Hoardrun says it owes each customer. Run from `fintech_backend`:

```bash
python -m app.services.reconciliation                       # totals and checks
python -m app.services.reconciliation --fbo-balance 1234.56 # compare with the bank's figure
python -m app.services.reconciliation --csv owners.csv      # one row per customer
```

It splits what each customer is owed into:
- **cash** (with card holds shown)
- **savings**
- **pooled investments** (venture funds, circles)
- **held at the broker**, which isn't in the FBO account

It also checks every cash account: the balance has to be explained by its transactions, and available cash has to equal the balance less card holds. It exits with an error if anything doesn't match.

A test moves money through every feature and requires zero differences to the cent:
- card deposit
- savings in and out, fixed deposit opened and broken
- a send between members
- a bank withdrawal that's returned, and a bank deposit
- a card hold, charge and refund
- investing, and the sweep back

Run the tool daily, after Plaid and Stripe events have synced, and keep the CSVs.

## Wording changed now

On the landing page, the site description and the fixed-deposit sheet (English):

| Before | After |
|---|---|
| "Banking Reimagined", "Experience the future of banking", "Individual Banking", "comprehensive universal banking services" | "Money Reimagined", "Saving, spending, sending and investing in one app", "Personal Accounts", "Hoardrun is a financial technology company, not a bank…" |
| "1M+ active users", "$50B+ assets under management", "99.9% uptime guarantee", "150+ countries" (not real figures) | "$1 to start investing", "$0 to send to Hoardrun members", "24/7 freeze your card", "2 min to check your identity" |
| "AI-powered investment strategies… grow your wealth securely" | "Buy ETFs and crypto from $1, held at a licensed broker. Investments can lose value." |
| "…with full regulatory compliance", "…to external bank accounts globally", "Military-grade encryption" | Plain descriptions of what the app does |
| "guaranteed returns" (fixed deposits) | "Lock in a fixed rate for a set term" |

A footer disclosure is now on the landing page: *Hoardrun is a financial technology company, not a bank. Investments are offered through a licensed broker-dealer, are not FDIC insured, and may lose value.* Once the partner is signed, it gains the line the partner requires, typically "Banking services provided by [Bank], Member FDIC."

## Steps

1. **Rotate the leaked credentials** (docs/hosting.md, step 0). A partner's security review will ask.
2. **Talk to Stripe** (route A) with the three questions above. In parallel, get a fintech lawyer to confirm the structure (#19).
3. **Name a BSA/AML officer** and draft the compliance programme. The partner reviews it.
4. **Build the ❌ items**: OFAC screening, monitoring, disputes, statements, complaints.
5. **Integrate**: customer cash moves into the partner's accounts. The Hoardrun ledger stays as it is, and the reconciliation report proves both sides match.
6. **Launch in a limited beta** with the partner's sign-off on marketing and disclosures.

## Sources

- Sponsor bank directory and status notes: [rupturelabs.io/companies/sponsor-banks](https://rupturelabs.io/companies/sponsor-banks)
- How the BaaS model is changing: [American Banker](https://www.americanbanker.com/payments/news/how-the-banking-as-a-service-model-is-changing)
- Sponsor banks overview: [AAR Advisory](https://aaradvisory.substack.com/p/sponsor-banks-the-banking-infrastructure)
- Stripe: [Treasury / Financial Accounts for platforms](https://stripe.com/us/treasury/platforms), [How Treasury works](https://docs.stripe.com/treasury/how-treasury-works)
- FDIC proposed custodial account recordkeeping rule: [Federal Register, 2 Oct 2024](https://www.federalregister.gov/documents/2024/10/02/2024-22565/recordkeeping-for-custodial-accounts), [status (reginfo.gov)](https://www.reginfo.gov/public/do/eAgendaViewRule?pubId=202510&RIN=3064-AG07)
