"""Card database containing all card definitions."""

# Card structure: [Type, Subtype, Species, Attack, Health, Cost, Name, Skills, OnPlay]
# Index:           0      1        2        3       4       5     6     7       8

CARDS_DATA = {
    "Avatar": [
        "Unit", "Leader", "", 2, 2, 0, "Avatar",
        "",
        "Your very representation in the battlefield. Don't let it die or you loose!"
    ],
    "Footman": [
        "Unit", "", "Human", 2, 2, 2, "Footman", "", ""
    ],
    "Archer": [
        "Unit", "Ranged", "Human", 3, 2, 3, "Archer", ""
    ],
    "Knight_Commander": [
        "Unit", "Aura_Atk", "Human", 4, 4, 5, "Knight Commander",
        "+1 damage to all humans in the area"
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
        "Destructive: Can target Stations"
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
    # === INFANTRY ===
    "Pikeman": [
        "Unit", "AntiCavalry", "Human", 2, 3, 2, "Pikeman",
        "Deals double damage to mounted units"
    ],
    "Shieldbearer": [
        "Unit", "Taunt", "Human", 1, 5, 3, "Shieldbearer",
        "Mark: Enemies must attack this unit first"
    ],
    "Berserker": [
        "Unit", "Frenzy", "Human", 5, 2, 4, "Berserker",
        "Enraged: Gains +2 attack when damaged"
    ],
    "Militia": [
        "Unit", "", "Human", 1, 2, 1, "Militia", ""
    ],
    "Veteran": [
        "Unit", "", "Human", 3, 4, 4, "Veteran", ""
    ],
    "Bannerman": [
        "Unit", "Inspire", "Human", 2, 2, 3, "Bannerman",
        "Allies in same area gain +1 attack"
    ],
    # === RANGED ===
    "Crossbowman": [
        "Unit", "Ranged,Piercing", "Human", 4, 2, 4, "Crossbowman",
        "Trueshot: Ignores 1 point of enemy health"
    ],
    "Longbowman": [
        "Unit", "Ranged", "Human", 2, 2, 3, "Longbowman",
        "Longsight:Can attack adjacent areas"
    ],
    "Javeliner": [
        "Unit", "Ranged", "Human", 2, 2, 2, "Javeliner", ""
    ],
    # === CAVALRY ===
    "Light_Cavalry": [
        "Unit", "Mounted,Swift", "Human", 2, 2, 3, "Light Cavalry",
        "Nimble:Can move twice per turn"
    ],
    "Heavy_Cavalry": [
        "Unit", "Mounted,Charge", "Human", 4, 4, 5, "Heavy Cavalry",
        "Empowered Strike:Deals +2 damage on first attack"
    ],
    # === SIEGE ===
    "Catapult": [
        "Unit", "Machinery,Siege", "", 4, 3, 5, "Catapult",
        "Destructive: Can target Stations"
    ],
    "Battering_Ram": [
        "Unit", "Machinery,Siege", "", 6, 6, 8, "Battering Ram",
        "Destructive:Double damage to Stations"
    ],
    "Ballista": [
        "Unit", "Machinery,Ranged", "", 5, 2, 5, "Ballista",
        "Piercing shots ignore armor"
    ],
    # === MYSTICAL CREATURES ===
    "Dire_Wolf": [
        "Unit", "Scout,Pack", "Beast", 2, 2, 2, "Dire Wolf",
        "Gains +1 attack per other wolf in area"
    ],
    "War_Bear": [
        "Unit", "Intimidate", "Beast", 4, 5, 5, "War Bear",
        "Weakening: Enemies deal -1 damage"
    ],
    "Wyvern": [
        "Unit", "Flying,Ranged", "Dragon", 3, 3, 6, "Wyvern",
        "Dextrous:Can attack without being attacked back"
    ],
    "Griffin": [
        "Unit", "Flying,Mounted", "Beast", 4, 4, 6, "Griffin",
        "Flying: ignores terrain restrictions"
    ],
    "Basilisk": [
        "Unit", "Petrify", "Beast", 2, 4, 5, "Basilisk",
        "Empowered Strike: First attack stuns enemy for 1 turn"
    ],
    "Shadow_Hound": [
        "Unit", "Scout,Stealth", "Beast", 2, 1, 2, "Shadow Hound",
        "Hidden: Cannot be seen by non-scouts"
    ],
    # === MAGIC UNITS ===
    "Battle_Mage": [
        "Unit", "Ranged,Magic", "Human", 3, 2, 4, "Battle Mage",
        "Attacks deal magic damage (ignores armor)"
    ],
    "Healer": [
        "Unit", "Support", "Human", 0, 2, 3, "Healer",
        "Heals 1 health to all allies at end of turn"
    ],
    "Warlock": [
        "Unit", "Magic,Curse", "Human", 2, 3, 4, "Warlock",
        "On play: enemy unit loses 1 attack"
    ],
    "Necromancer": [
        "Unit", "Magic,Summon", "Human", 2, 2, 5, "Necromancer",
        "Last Whisper: summons a Skeleton"
    ],
    "Druid": [
        "Unit", "Magic,Nature", "Human", 1, 3, 3, "Druid",
        "Beasts in same area gain +1/+1"
    ],
    # === SPECIAL UNITS ===
    "Spy": [
        "Unit", "Scout,Stealth", "Human", 1, 1, 2, "Spy",
        "Reveals all enemy cards in area"
    ],
    "Assassin": [
        "Unit", "Stealth,Execute", "Human", 4, 1, 4, "Assassin",
        "On play: deal 2 damage to weakest enemy"
    ],
    "Saboteur": [
        "Unit", "Stealth", "Human", 1, 2, 3, "Saboteur",
        "On play: destroy enemy siege weapon"
    ],
    "Champion": [
        "Unit", "Duel", "Human", 5, 5, 6, "Champion",
        "Enforcing:Forces 1v1 combat with strongest enemy"
    ],
    "Royal_Guard": [
        "Unit", "Bodyguard", "Human", 3, 4, 4, "Royal Guard",
        "Reflective: Redirects damage from your Avatar to self"
    ],
    "War_Drummer": [
        "Unit", "Inspire", "Human", 0, 2, 2, "War Drummer",
        "All allies gain +1 attack"
    ],
    # === UNDEAD ===
    "Skeleton": [
        "Unit", "Undead", "Undead", 1, 1, 1, "Skeleton", ""
    ],
    "Zombie": [
        "Unit", "Undead,Slow", "Undead", 2, 3, 2, "Zombie",
        "Slow: Takes 1 extra turn to arrive"
    ],
    "Wraith": [
        "Unit", "Undead,Ethereal", "Undead", 3, 2, 4, "Wraith",
        "Takes half damage from non-magic attacks"
    ],
    "Death_Knight": [
        "Unit", "Undead,Mounted", "Undead", 4, 4, 5, "Death Knight",
        "Heals 1 when it kills an enemy"
    ],
    # === ELITE UNITS ===
    "Templar": [
        "Unit", "Holy", "Human", 3, 4, 5, "Templar",
        "Deals double damage to Undead"
    ],
    "Inquisitor": [
        "Unit", "Holy,Magic", "Human", 2, 3, 4, "Inquisitor",
        "Reveals and damages Stealth units"
    ],
    "General": [
        "Unit", "Commander", "Human", 3, 4, 6, "General",
        "All allies gain +1/+1"
    ],
    "Executioner": [
        "Unit", "Execute", "Human", 5, 3, 5, "Executioner",
        "Execute:Instantly kills enemies with 2 or less health"
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
IDX_SKILLS = 7
IDX_ON_PLAY = 8


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
