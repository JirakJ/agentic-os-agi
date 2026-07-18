---
name: consulting-invoicing
description: Produce monthly AI-consulting and training invoices with correct Czech invoicing fields, engagement summaries, and follow-up emails. Use whenever the user mentions invoice, faktura, billing, consulting hours, training session billing, or month-end client paperwork.
license: MIT
metadata:
  version: "3.0.0"
---

# Consulting Invoicing

## Inputs to collect first
Client entity + billing address, engagement (training/consulting/retainer), period, unit
(hours/days/fixed), rate + currency, PO/reference if the client requires one, and the
user's supplier details (kept in `40-entities/jakubjirak-billing.md` in the vault - read it;
if missing, ask once and create it).

## Procedure
1. Assemble line items from the period's daily notes and calendar mentions of the client
   (vault search: client entity link). Present the draft table for confirmation BEFORE
   generating anything.
2. Generate the invoice as clean HTML -> PDF-ready A4: supplier and client blocks, invoice
   number `YYYYNNN` (increment from `50-projects/invoicing.md` ledger), issue + due dates
   (default due: 14 days), line items, subtotal, VAT handling per the supplier note
   (non-VAT-payer: state "Neni platce DPH" / VAT payer: 21% breakdown), total, bank
   account + variable symbol = invoice number.
3. Update the ledger note `50-projects/invoicing.md`: number, client, amount, status: sent.
4. Draft the delivery email: one-paragraph engagement value summary + invoice attached +
   due date. Offer a polite reminder draft scheduled at due+3 days.

## Validation
- Invoice number unique and sequential in the ledger; totals recomputed and cross-checked;
  every mandatory Czech field present (supplier ICO/DIC block from the billing note).
