"""Synthetic asset records for local runs and tests.

These rows mirror the BigQuery `assets` schema in
`infra/terraform/environments/dev/schemas/assets.json`. They are demonstration
data: sites, dates and statuses are invented and are not operational records.
"""
from __future__ import annotations

SAMPLE_ASSETS = [
    {
        "asset_id": "TR-1042",
        "asset_type": "33/11 kV transformer",
        "site": "Ashford Grid",
        "criticality": 5,
        "commissioned": "2009-03-12",
        "last_inspection": "2026-09-02",
        "next_inspection": "2027-09-02",
        "status": "in service",
        "notes": "Annual dissolved gas analysis. Do not top up oil before sampling.",
    },
    {
        "asset_id": "TC-2210",
        "asset_type": "track circuit",
        "site": "Wembley Central",
        "criticality": 4,
        "commissioned": "2015-07-21",
        "last_inspection": "2026-10-14",
        "next_inspection": "2027-04-14",
        "status": "in service",
        "notes": "Fail-safe signalling asset. Last failure restored in 42 minutes.",
    },
    {
        "asset_id": "GV-0317",
        "asset_type": "district gas governor",
        "site": "Camden",
        "criticality": 3,
        "commissioned": "2012-01-30",
        "last_inspection": "2026-06-20",
        "next_inspection": "2027-06-20",
        "status": "in service",
        "notes": "Annual service; five-year pressure test due 2029.",
    },
    {
        "asset_id": "WM-1180",
        "asset_type": "distribution water main",
        "site": "Islington",
        "criticality": 4,
        "commissioned": "1998-11-05",
        "last_inspection": "2026-08-01",
        "next_inspection": "2027-08-01",
        "status": "in service",
        "notes": "Inside a district metered area with nightly minimum-flow analysis.",
    },
    {
        "asset_id": "SW-0455",
        "asset_type": "high-voltage switchgear",
        "site": "Willesden",
        "criticality": 5,
        "commissioned": "2007-05-18",
        "last_inspection": "2026-11-01",
        "next_inspection": "2027-05-01",
        "status": "in service",
        "notes": "Switching only under permit-to-work. No live work without authorisation.",
    },
    {
        "asset_id": "TR-9999",
        "asset_type": "33/11 kV transformer",
        "site": "Old Oak",
        "criticality": 1,
        "commissioned": "1991-02-14",
        "last_inspection": "2024-03-10",
        "next_inspection": None,
        "status": "decommissioned",
        "notes": "Isolated and drained. Retained in the register for cable records.",
    },
    {
        "asset_id": "LC-0088",
        "asset_type": "level crossing",
        "site": "Enfield",
        "criticality": 4,
        "commissioned": "2018-09-09",
        "last_inspection": "2026-10-28",
        "next_inspection": "2026-11-28",
        "status": "in service",
        "notes": "Full barriers with obstacle detection. Monthly inspection.",
    },
]
