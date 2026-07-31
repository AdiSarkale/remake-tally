"""GST helpers — mirrors src/lib/erp/gst.ts on the frontend.

Intra-state (same GSTIN state code) -> CGST + SGST, each half the rate.
Inter-state (different state code)  -> IGST at the full rate.
"""

from __future__ import annotations

from dataclasses import dataclass


def state_code(gstin: str | None) -> str:
    """First two digits of a GSTIN identify the state."""
    return (gstin or "").strip()[:2]


def is_inter_state(company_gstin: str | None, party_gstin: str | None) -> bool:
    company, party = state_code(company_gstin), state_code(party_gstin)
    if not company or not party:
        return False
    return company != party


@dataclass
class LineTax:
    taxable: float
    cgst: float
    sgst: float
    igst: float
    total: float


def compute_line(
    *, quantity: float, rate: float, discount_percent: float, gst_rate: float, inter_state: bool
) -> LineTax:
    gross = quantity * rate
    taxable = round(gross * (1 - (discount_percent or 0) / 100), 2)
    tax = round(taxable * gst_rate / 100, 2)
    if inter_state:
        cgst = sgst = 0.0
        igst = tax
    else:
        cgst = round(tax / 2, 2)
        sgst = round(tax - cgst, 2)
        igst = 0.0
    return LineTax(taxable=taxable, cgst=cgst, sgst=sgst, igst=igst, total=round(taxable + tax, 2))


def round_off(amount: float) -> tuple[float, float]:
    """Return (rounded_grand_total, round_off_delta)."""
    rounded = round(amount)
    return float(rounded), round(rounded - amount, 2)
