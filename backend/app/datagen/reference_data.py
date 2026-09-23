"""Reference tables the generator samples from. Real-sounding but made up:
section names follow Northern Railway station-code conventions, km ranges
are contiguous and non-overlapping per section.

GHY-LMG and LMG-RNY are the exception: these reuse the exact corridor
identifiers the ntes-adapter service is configured for (its station
codes GHY/LMG/RNY are verified real -- see ntes-adapter/README.md --
though real-world section adjacency still isn't). They're included here
so app/ntes_bridge.py has matching sections to enrich with real NTES
predicted-availability data; their km ranges are just as illustrative
as every other section's.
"""

from app.models.enums import Department, BlockType

# (section_name, km_start, km_end)
SECTIONS = [
    ("NDLS-GZB", 0.0, 25.0),
    ("GZB-SRE", 25.0, 160.0),
    ("SRE-MTC", 160.0, 200.0),
    ("MTC-PNP", 200.0, 250.0),
    ("GHY-LMG", 0.0, 180.0),  # NTES-integrated (see app/ntes_bridge.py)
    ("LMG-RNY", 180.0, 300.0),  # NTES-integrated (see app/ntes_bridge.py)
]

# Subset of SECTIONS that app/ntes_bridge.py enriches with real NTES
# predicted-availability data. Everything else stays purely synthetic --
# there's no real data for them.
NTES_INTEGRATED_SECTIONS = ["GHY-LMG", "LMG-RNY"]

DEPARTMENT_TASK_ID_PREFIX = {
    Department.ENGINEERING: "ENG",
    Department.TRD: "TRD",
    Department.SNT: "SNT",
}

DEFECT_TYPES = {
    Department.ENGINEERING: [
        "rail_fracture_risk",
        "ballast_deficiency",
        "track_geometry_defect",
        "joint_wear",
        "formation_failure",
    ],
    Department.TRD: [
        "ohe_wire_wear",
        "insulator_damage",
        "feeder_fault",
        "isolator_failure",
        "earthing_defect",
    ],
    Department.SNT: [
        "signal_relay_fault",
        "point_machine_defect",
        "cable_fault",
        "interlocking_fault",
        "level_crossing_fault",
    ],
}

# block_type_required weights per department: (traffic, power, traffic_and_power)
BLOCK_TYPE_WEIGHTS_BY_DEPT = {
    Department.ENGINEERING: {BlockType.TRAFFIC: 0.7, BlockType.POWER: 0.1, BlockType.TRAFFIC_AND_POWER: 0.2},
    Department.TRD: {BlockType.TRAFFIC: 0.1, BlockType.POWER: 0.7, BlockType.TRAFFIC_AND_POWER: 0.2},
    Department.SNT: {BlockType.TRAFFIC: 0.6, BlockType.POWER: 0.1, BlockType.TRAFFIC_AND_POWER: 0.3},
}

# block_type_possible weights for generated block opportunities
BLOCK_OPPORTUNITY_TYPE_WEIGHTS = {
    BlockType.TRAFFIC: 0.40,
    BlockType.POWER: 0.25,
    BlockType.TRAFFIC_AND_POWER: 0.35,
}

SEVERITY_WEIGHTS = {"A": 0.10, "B": 0.45, "C": 0.45}

EST_DURATION_CHOICES_MIN = [60, 90, 120, 150, 180, 240]

# Maintenance blocks run in traffic-light night windows.
NIGHT_WINDOWS = [(0, 0, 5, 0), (22, 0, 23, 59)]  # (start_h, start_m, end_h, end_m)
