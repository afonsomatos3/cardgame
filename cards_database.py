"""Card database containing all card definitions."""

# Card structure: [Type, Species, Attack, Health, Cost, Name, SpecialText]
# Index:           0      1        2       3       4     5      6

CARDS_DATA = {
    "Avatar": [
        "Unit", "Leader", "", 2, 2, 0, "Avatar",
        "Your very representation in the battlefield. Don't let it die or you loose!"
    ],
    "Footman": [
        "Unit", "", "Human", 2, 2, 2, "Footman", ""
    ],
    "Archer": [
        "Unit", "Ranged", "Human", 3, 2, 3, "Archer", ""
    ],
    "Knight_Commander": [
        "Unit", "", "Human", 4, 4, 5, "Knight Commander",
        "It gives +1 damage to all humans in the area"
    ],
    "Eagle": [
        "Unit", "Ranged,Scout", "Eagle", 0, 1, 1, "Eagle",
        "It cannot scout over closed areas"
    ],
    "War_Hound": [
        "Unit", "Scout", "Dog", 1, 1, 1, "War Hound", ""
    ],
    "Knight": [
        "Unit", "", "Human", 3, 3, 3, "Knight", ""
    ],
    "Trebuchet": [
        "Unit", "Machinery", "", 5, 5, 7, "Trebuchet",
        "Can target Stations"
    ],
    "Guardian": [
        "Unit", "", "Human", 2, 4, 3, "Guardian", ""
    ],
    "Spearman": [
        "Unit", "", "Human", 3, 2, 2, "Spearman", ""
    ],
    "Mercenary": [
        "Unit", "", "Human", 2, 2, 2, "Mercenary", ""
    ],
    "Mentor": [
        "Unit", "", "Human", 1, 2, 2, "Mentor", ""
    ],
    "Warrior": [
        "Unit", "", "Human", 3, 3, 3, "Warrior", ""
    ],
}

# Card info indices
IDX_TYPE = 0
IDX_SUBTYPE = 1
IDX_SPECIES = 2
IDX_ATTACK = 3
IDX_HEALTH = 4
IDX_COST = 5
IDX_NAME = 6
IDX_SPECIAL = 7


def get_card_info(card_id: str) -> list | None:
    """Get card info by card ID."""
    return CARDS_DATA.get(card_id)


def get_card_cost(card_id: str) -> int:
    """Get card cost by card ID."""
    info = CARDS_DATA.get(card_id)
    if info:
        return info[IDX_COST]
    return 0


def get_all_card_ids() -> list:
    """Get all available card IDs."""
    return list(CARDS_DATA.keys())
