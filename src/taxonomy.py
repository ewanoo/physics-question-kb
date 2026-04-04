"""
KS3 Physics topic taxonomy for Year 8 UK curriculum.
Used for question classification and coverage analysis.
"""

from __future__ import annotations

TAXONOMY: dict[str, dict] = {
    "energy": {
        "label": "Energy",
        "subtopics": {
            "energy.stores": "Energy stores and transfers",
            "energy.conservation": "Conservation of energy",
            "energy.resources": "Energy resources (renewable and non-renewable)",
            "energy.efficiency": "Efficiency and reducing energy waste",
            "energy.power": "Power and energy cost calculations",
            "energy.food": "Energy in food and the human body",
        },
        "target_count": 30,
    },
    "forces": {
        "label": "Forces",
        "subtopics": {
            "forces.types": "Contact and non-contact forces",
            "forces.gravity": "Gravity and weight",
            "forces.friction": "Friction and air resistance",
            "forces.balanced": "Balanced and unbalanced forces",
            "forces.speed": "Speed, distance, and time",
            "forces.pressure": "Pressure in solids, liquids, and gases",
            "forces.moments": "Moments and levers",
            "forces.springs": "Stretching and Hooke's law",
        },
        "target_count": 40,
    },
    "waves": {
        "label": "Waves",
        "subtopics": {
            "waves.properties": "Wave properties (amplitude, frequency, wavelength)",
            "waves.sound": "Sound waves and hearing",
            "waves.light": "Light, reflection, and refraction",
            "waves.colour": "Colour and filters",
            "waves.em_spectrum": "The electromagnetic spectrum",
        },
        "target_count": 30,
    },
    "electricity": {
        "label": "Electricity and Magnetism",
        "subtopics": {
            "electricity.circuits": "Series and parallel circuits",
            "electricity.current_voltage": "Current, voltage, and resistance",
            "electricity.static": "Static electricity",
            "electricity.magnets": "Magnets and magnetic fields",
            "electricity.electromagnets": "Electromagnets and their uses",
        },
        "target_count": 30,
    },
    "matter": {
        "label": "Matter",
        "subtopics": {
            "matter.particles": "Particle model of matter",
            "matter.states": "Solids, liquids, and gases",
            "matter.changes": "Changes of state",
            "matter.density": "Density and floating/sinking",
            "matter.gas_pressure": "Gas pressure and temperature",
        },
        "target_count": 25,
    },
    "space": {
        "label": "Space",
        "subtopics": {
            "space.solar_system": "The Solar System",
            "space.earth_moon": "The Earth, Moon, and Sun",
            "space.seasons": "Day, night, and seasons",
            "space.gravity": "Gravity and orbits in space",
        },
        "target_count": 20,
    },
}

# Flat list of all valid topic slugs
ALL_TOPIC_SLUGS: list[str] = []
for _group in TAXONOMY.values():
    ALL_TOPIC_SLUGS.extend(_group["subtopics"].keys())

# Top-level topic slugs only
TOP_LEVEL_TOPICS: list[str] = list(TAXONOMY.keys())

# Minimum questions per subtopic (70% of target, distributed across subtopics)
SUBTOPIC_MINIMUM = 5


def get_subtopics(top_level: str) -> dict[str, str]:
    """Return subtopics dict for a top-level topic."""
    if top_level not in TAXONOMY:
        raise ValueError(f"Unknown topic: {top_level}. Valid: {TOP_LEVEL_TOPICS}")
    return TAXONOMY[top_level]["subtopics"]


def is_valid_topic(slug: str) -> bool:
    """Check if a topic slug is valid (either top-level or subtopic)."""
    return slug in TOP_LEVEL_TOPICS or slug in ALL_TOPIC_SLUGS


def get_topic_label(slug: str) -> str:
    """Get a human-readable label for a topic slug."""
    if slug in TAXONOMY:
        return TAXONOMY[slug]["label"]
    for group_data in TAXONOMY.values():
        if slug in group_data["subtopics"]:
            return group_data["subtopics"][slug]
    return slug


def get_parent_topic(subtopic_slug: str) -> str | None:
    """Get the parent top-level topic for a subtopic slug."""
    for top_level, group_data in TAXONOMY.items():
        if subtopic_slug in group_data["subtopics"]:
            return top_level
    return None


def get_target_count(top_level: str) -> int:
    """Get the target question count for a top-level topic."""
    return TAXONOMY.get(top_level, {}).get("target_count", 20)
