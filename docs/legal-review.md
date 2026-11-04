# Legal review: brief for counsel

*Prepared November 2026 from a review of the code. It is not legal advice and drafts nothing final. Its purpose is to save a fintech lawyer time by showing exactly what Hoardrun does, where the gaps are, and which documents need writing. Read it with [bank-partner.md](bank-partner.md).*

## 1. What Hoardrun does (for scoping)

A US consumer app. People:
- sign up (email and password, or Google)
- verify identity (Persona)
- add money by card (Stripe Checkout) or bank (Plaid ACH)
- hold a cash balance, and send it to other members
- save into goals, fixed-term "deposits" and auto-save plans
- spend with a virtual Visa card (Stripe Issuing)
- buy ETFs and crypto through their own brokerage account (Alpaca)
- join investment "circles" and buy shares in venture funds
- ask an AI assistant (Anthropic) about their money

**Today there is no bank partner, and the company holds customer balances on its own books** (see bank-partner.md).

## 2. Issues ranked for counsel

| # | Issue | Why it matters | Where |
|---|---|---|---|
| 1 | **Holding and moving customer money** without a money transmitter licence or a bank partner | State money transmission laws; the structure must be settled before launch | Cash, sends, card spending |
| 2 | **Fixed deposits paying 4–5.5% APY from the company** | Looks like deposit-taking. If moved to a bank, Truth in Savings (Reg DD) disclosures apply. | Savings → Fixed deposits |
| 3 | **Venture funds and investment circles**: members pool money to buy fund shares or vote on investments | Likely securities and investment-adviser questions (offering exemptions, pooled vehicles) | `/venture-capital`, `/circles`, `/investment-opportunities`, `/startupregistration` |
| 4 | **Selfie and ID photos (biometrics)** through Persona | Illinois BIPA, Texas and Washington biometric laws need specific written consent and a retention policy. Persona can help; Hoardrun presents the consent. | Identity check |
| 5 | **Terms and Privacy pages are templates.** They contain "[Your Business Address]", and the privacy page only mentions Google sign-in. | Unenforceable terms; a privacy notice that doesn't match practice is deceptive | `/terms`, `/privacy` |
| 6 | **No record of what each person agreed to and when** (terms version, time, IP). Sign-up requires a "terms accepted" tick, but it isn't stored. Stripe, Alpaca and Persona consent times are sent to them, not kept by Hoardrun. | Proof of consent in disputes and for partners | Sign-up, card, investing |
| 7 | **No E-SIGN consent** for delivering disclosures electronically | Needed before electronic-only disclosures count | Sign-up |
| 8 | **No Regulation E error-resolution process** (report an unauthorized transfer or a card dispute; time limits; provisional credit) | Required for consumer electronic fund transfers and cards | Missing |
| 9 | **AI assistant**: sends balances and recent transactions to Anthropic. It says "general guidance, not financial advice". | Disclose in the privacy policy; check the assistant never gives personalised investment advice (adviser rules) | `/assistant` |
| 10 | **Marketing claims.** English fixed in #18 (no "bank", no invented figures, no "guaranteed returns"). The other 9 languages still carry the old claims. | UDAAP / FTC Act; partner banks review all marketing | `locales/*` |

## 3. Who receives personal data (for the privacy notice and vendor contracts)

| Company | What it receives | Why |
|---|---|---|
| **Persona** | Name, email, government ID images, selfie (biometric), ID details | Identity verification |
| **Alpaca Securities** | Name, date of birth, **SSN**, address, phone, employment, FINRA disclosures; orders and holdings | Brokerage account (SSN is passed through, not stored by Hoardrun) |
| **Stripe** | Card payments (card details go to Stripe directly); cardholder name, email, billing address, IP; card transactions | Card deposits, Hoardrun cards |
| **Plaid** | Bank login (directly in Plaid Link), bank accounts, balances, transactions; ACH transfers | Linking a bank, moving money |
| **Anthropic** | Balances, recent transactions, holdings and the person's questions | AI assistant |
| **Resend** | Email address, and email content (codes, alerts with amounts) | Emails |
| **Google** | Sign-in only (name, email, profile picture) | Sign in with Google |
| **Hosting** (Render, Vercel, the database provider) | Everything, as processors | Running the service |

Hoardrun stores encrypted where noted (bank tokens, account numbers) and keeps transaction records after an account closes.

## 4. Documents to write (with counsel)

| Document | Must cover (at least) | Shown |
|---|---|---|
| **User Agreement / Terms** | Company identity and address; eligibility (US, 18+); account, balances and who holds funds (the bank partner); sends, limits and fees; closing accounts; arbitration and class-action waiver if wanted; governing law | Sign-up (versioned acceptance stored) |
| **Privacy Policy + GLBA privacy notice** | The section 3 data and sharing; opt-outs; security; retention; state rights (CCPA/CPRA where not covered by GLBA) | Sign-up, then yearly if required |
| **E-SIGN consent** | Consent to electronic disclosures; hardware and software needs; how to withdraw; paper copies | Before other disclosures at sign-up |
| **Electronic Fund Transfer disclosures (Reg E)** | Liability for unauthorized transfers; how to report errors; timelines; contact details | Sign-up and on the first transfer |
| **Cardholder Agreement** | From the card issuer (Stripe's bank partner) | Getting a card (today a "card terms" link to `/terms`) |
| **Biometric consent and retention policy** | What's collected, why, how long, who receives it (Persona), destruction schedule | Before the identity check |
| **Fee schedule** | Every fee, or a clear "no fees" | Public page |
| **Savings / interest terms** | Only if interest stays: rate, how it's calculated, early withdrawal (Reg DD language if bank-provided) | Fixed deposits |
| **Investing disclosures** | Alpaca's agreements (already accepted in the app), "not FDIC insured, may lose value", crypto risk | Investing (already shown) |
| **Complaints policy** | How to complain, response times, escalation | Help page |

## 5. Engineering follow-ups that support the legal work

1. **Store consents**: document, version, time and IP, for terms, privacy, E-SIGN, biometrics, card terms and brokerage agreements.
2. **Disputes and error resolution**: report a problem on a transaction; track it to the Reg E deadlines.
3. **Monthly statements** (Reg E periodic statements, if required for the product).
4. **Complaints intake** with tracking.
5. **Sanctions screening (OFAC)** at sign-up and on payments, plus transaction monitoring (also asked for by the bank partner).
6. **Translate the corrected marketing copy** into the other 9 languages, or hide those languages until reviewed.
7. **Business address and legal entity name** in Terms, Privacy, emails and the footer once confirmed.

## 6. Questions for counsel

1. With a bank partner holding funds in an FBO account, does Hoardrun still need any state licences (for sends between members, for example)?
2. Can fixed deposits continue in any form, and on what terms?
3. Do venture funds, circles and company listings need to be restructured, limited to accredited investors, or removed before launch?
4. Is the AI assistant's scope acceptable, and what wording should it carry?
5. Arbitration: include it or not, given the partner's preference?
6. Which states' biometric laws apply at launch, and is Persona's consent flow enough with a Hoardrun notice?
