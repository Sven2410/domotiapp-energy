"""Calculation engine for DomotiApp Energy (SPEC.md §16 and §17).

Calculating and phrasing are strictly separated:

``Calculator -> EnergyMetrics -> Advisor -> AdviceItem[] -> CoachProvider``

:mod:`.calculator` reads the configured entities and derives the metrics,
leaning on :mod:`.completeness` for the data quality checklist.
:mod:`.advisor` decides what to advise and :mod:`.providers` phrases it in
Dutch. :mod:`.reason_codes` is the shared vocabulary that ties the three
together, so no stage ever invents a reason of its own.
"""
