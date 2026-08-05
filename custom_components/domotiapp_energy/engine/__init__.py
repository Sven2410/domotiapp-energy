"""Calculation engine for DomotiApp Energy (SPEC.md §16 and §17).

Calculating and phrasing are strictly separated:

``Calculator -> EnergyMetrics -> Advisor -> AdviceItem[] -> CoachProvider``

Only :mod:`.reason_codes` exists so far; the calculator, completeness check,
advisor and providers follow in phase 4.
"""
