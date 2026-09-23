"""Reference tables the generator samples from.

Sections are limited to the corridors ntes-adapter actually covers, so
every section planned here has a real data source behind it rather than
being purely invented. The station codes GHY/LMG/RNY are verified real
(see ntes-adapter/README.md), though real-world section adjacency is
not, and the km ranges are illustrative.

Defect and block data for these sections is still synthetic -- only
corridor availability comes from real NTES-derived data, and only for
blocks falling in a window the adapter has observations for (see
app/ntes_bridge.py).
"""

from app.models.enums import Department, BlockType

# (section_name, km_start, km_end)
SECTIONS = [
    ("GHY-LMG", 0.0, 180.0),
    ("LMG-RNY", 180.0, 300.0),
]

# Sections app/ntes_bridge.py enriches with real NTES predicted-availability
# data. Currently every configured section, but the bridge stays written
# against this list rather than SECTIONS so adding a section without a real
# data source doesn't silently claim one.
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
