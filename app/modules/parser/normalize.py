import yaml
from pathlib import Path

# Load the skill map once when the module is imported
SKILL_MAP_PATH = Path(__file__).parent / "skill_map.yaml"

def load_skill_map() -> dict:
    """Load canonical skill mappings from YAML file."""
    with open(SKILL_MAP_PATH, "r") as f:
        return yaml.safe_load(f)

# Build a reverse lookup: variation -> canonical
# e.g. "React.js" -> "React", "ReactJS" -> "React"
def build_reverse_map(skill_map: dict) -> dict:
    reverse = {}
    for canonical, variations in skill_map.items():
        if variations:
            for variation in variations:
                reverse[variation.lower()] = canonical
    return reverse

SKILL_MAP = load_skill_map()
REVERSE_MAP = build_reverse_map(SKILL_MAP)

def normalize_skill(skill: str) -> str:
    """Normalize a single skill name to its canonical form."""
    return REVERSE_MAP.get(skill.lower(), skill)

def normalize_skills(skills: list) -> list:
    """Normalize a list of skills, removing duplicates."""
    normalized = [normalize_skill(skill) for skill in skills]
    # Remove duplicates while preserving order
    seen = set()
    result = []
    for skill in normalized:
        if skill.lower() not in seen:
            seen.add(skill.lower())
            result.append(skill)
    return result