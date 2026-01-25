"""Game manager handling game state, turns, and battlefield logic."""

from enum import Enum
from typing import Callable
import utility.cards_database as db
import random


class Player(Enum):
    ATTACKER = 0
    DEFENDER = 1


class GamePhase(Enum):
    MAIN = 0
    DECLARE_ATTACKERS = 1
    DECLARE_BLOCKERS = 2
    COMBAT_DAMAGE = 3


class AbilityProcessor:
    """Processes card abilities and applies their effects."""

    @staticmethod
    def get_subtypes(card_info: list) -> list[str]:
        """Extract subtypes from card info."""
        if len(card_info) > db.IDX_SUBTYPE and card_info[db.IDX_SUBTYPE]:
            return [s.strip() for s in card_info[db.IDX_SUBTYPE].split(",")]
        return []

    @staticmethod
    def has_subtype(card_info: list, subtype: str) -> bool:
        """Check if card has a specific subtype."""
        return subtype in AbilityProcessor.get_subtypes(card_info)

    @staticmethod
    def get_species(card_info: list) -> str:
        """Get the species of a card."""
        if len(card_info) > db.IDX_SPECIES:
            return card_info[db.IDX_SPECIES]
        return ""

    @staticmethod
    def process_on_play(game_manager, location: str, card_data: dict, player,
                       zone: str = "middle_zone") -> list[str]:
        """Process on-play abilities when a card enters the battlefield.

        Abilities affect cards in the same zone.
        Returns a list of effect messages for the combat log.
        """
        effects = []
        card_info = card_data.get("card_info", [])
        card_id = card_data.get("card_id", "Unknown")
        subtypes = AbilityProcessor.get_subtypes(card_info)
        player_key = "attacker" if player == Player.ATTACKER else "defender"
        enemy_key = "defender" if player == Player.ATTACKER else "attacker"

        zone_data = game_manager.battlefield_cards[location][zone]

        # Assassin: On play, deal 2 damage to weakest enemy in zone
        if "Execute" in subtypes and card_id == "Assassin":
            enemy_cards = zone_data[enemy_key]
            if enemy_cards:
                # Find weakest enemy (lowest health)
                weakest_idx = 0
                weakest_health = enemy_cards[0].get("current_health",
                    enemy_cards[0]["card_info"][db.IDX_HEALTH])
                for i, enemy in enumerate(enemy_cards):
                    health = enemy.get("current_health", enemy["card_info"][db.IDX_HEALTH])
                    if health < weakest_health:
                        weakest_health = health
                        weakest_idx = i

                enemy_cards[weakest_idx]["current_health"] = enemy_cards[weakest_idx].get(
                    "current_health", enemy_cards[weakest_idx]["card_info"][db.IDX_HEALTH]) - 2
                enemy_name = enemy_cards[weakest_idx]["card_id"]
                effects.append(f"Assassin deals 2 damage to {enemy_name}!")

                # Check if killed
                if enemy_cards[weakest_idx]["current_health"] <= 0:
                    dead = enemy_cards.pop(weakest_idx)
                    effects.append(f"{dead['card_id']} was slain by the Assassin!")

        # Warlock: On play, enemy unit loses 1 attack
        if "Curse" in subtypes:
            enemy_cards = zone_data[enemy_key]
            if enemy_cards:
                # Curse the first enemy
                target = enemy_cards[0]
                if "attack_modifier" not in target:
                    target["attack_modifier"] = 0
                target["attack_modifier"] -= 1
                effects.append(f"Warlock curses {target['card_id']} (-1 attack)!")

        # Saboteur: On play, destroy enemy siege weapon in zone
        if "Stealth" in subtypes and card_id == "Saboteur":
            enemy_cards = zone_data[enemy_key]
            for i in range(len(enemy_cards) - 1, -1, -1):
                enemy = enemy_cards[i]
                enemy_subtypes = AbilityProcessor.get_subtypes(enemy.get("card_info", []))
                if "Siege" in enemy_subtypes or "Machinery" in enemy_subtypes:
                    destroyed = enemy_cards.pop(i)
                    effects.append(f"Saboteur destroyed {destroyed['card_id']}!")
                    break  # Only destroy one

        # Spy: Reveals all enemy cards (handled in visibility)
        if "Scout" in subtypes and card_id == "Spy":
            effects.append(f"Spy reveals all enemy positions at {location}!")

        # Inspire abilities (Bannerman, War Drummer) - affect allies in same zone
        if "Inspire" in subtypes:
            ally_cards = zone_data[player_key]
            for ally in ally_cards:
                if ally != card_data:  # Don't buff self
                    if "attack_modifier" not in ally:
                        ally["attack_modifier"] = 0
                    ally["attack_modifier"] += 1
            if len(ally_cards) > 1:
                effects.append(f"{card_id} inspires allies (+1 attack)!")

        # Commander ability (General)
        if "Commander" in subtypes:
            ally_cards = zone_data[player_key]
            for ally in ally_cards:
                if ally != card_data:
                    if "attack_modifier" not in ally:
                        ally["attack_modifier"] = 0
                    if "health_modifier" not in ally:
                        ally["health_modifier"] = 0
                    ally["attack_modifier"] += 1
                    ally["health_modifier"] += 1
                    ally["current_health"] = ally.get("current_health",
                        ally["card_info"][db.IDX_HEALTH]) + 1
            if len(ally_cards) > 1:
                effects.append(f"{card_id} rallies allies (+1/+1)!")

        # Druid: Beasts gain +1/+1 in same zone
        if "Nature" in subtypes:
            ally_cards = zone_data[player_key]
            buffed_any = False
            for ally in ally_cards:
                if AbilityProcessor.get_species(ally.get("card_info", [])) == "Beast":
                    if "attack_modifier" not in ally:
                        ally["attack_modifier"] = 0
                    if "health_modifier" not in ally:
                        ally["health_modifier"] = 0
                    ally["attack_modifier"] += 1
                    ally["health_modifier"] += 1
                    ally["current_health"] = ally.get("current_health",
                        ally["card_info"][db.IDX_HEALTH]) + 1
                    buffed_any = True
            if buffed_any:
                effects.append(f"Druid empowers nearby beasts (+1/+1)!")

        return effects

    @staticmethod
    def get_effective_attack(card_data: dict) -> int:
        """Get the effective attack value including modifiers."""
        base_attack = card_data["card_info"][db.IDX_ATTACK]
        modifier = card_data.get("attack_modifier", 0)
        return max(0, base_attack + modifier)

    @staticmethod
    def process_combat_modifiers(game_manager, location: str,
                                  attacker_cards: list, defender_cards: list) -> dict:
        """Process combat modifiers before damage is dealt.

        Returns a dict with attack/defense modifiers for each card.
        """
        modifiers = {
            "attacker": {},  # card_index -> {"attack": int, "damage_reduction": int}
            "defender": {}
        }

        # Process Taunt (Shieldbearer) - enemies must attack this unit
        for side, cards in [("attacker", attacker_cards), ("defender", defender_cards)]:
            for i, card in enumerate(cards):
                subtypes = AbilityProcessor.get_subtypes(card.get("card_info", []))

                if side not in modifiers:
                    modifiers[side] = {}
                if i not in modifiers[side]:
                    modifiers[side][i] = {"attack": 0, "damage_reduction": 0, "must_be_targeted": False}

                # Taunt
                if "Taunt" in subtypes:
                    modifiers[side][i]["must_be_targeted"] = True

                # Berserker: +2 attack when damaged
                if "Frenzy" in subtypes:
                    max_health = card["card_info"][db.IDX_HEALTH]
                    current_health = card.get("current_health", max_health)
                    if current_health < max_health:
                        modifiers[side][i]["attack"] = 2

                # Charge: +damage on first attack (check if has_charged flag not set)
                if "Charge" in subtypes and not card.get("has_charged", False):
                    charge_bonus = 2 if "Heavy_Cavalry" in card.get("card_id", "") else 1
                    modifiers[side][i]["attack"] = modifiers[side][i].get("attack", 0) + charge_bonus

                # Intimidate (War Bear): enemies deal -1 damage
                if "Intimidate" in subtypes:
                    enemy_side = "defender" if side == "attacker" else "attacker"
                    enemy_cards = defender_cards if side == "attacker" else attacker_cards
                    for j in range(len(enemy_cards)):
                        if j not in modifiers[enemy_side]:
                            modifiers[enemy_side][j] = {"attack": 0, "damage_reduction": 0}
                        modifiers[enemy_side][j]["attack"] = modifiers[enemy_side][j].get("attack", 0) - 1

                # Pack (Dire Wolf): +1 attack per other wolf
                if "Pack" in subtypes:
                    wolf_count = sum(1 for c in cards if "Dire_Wolf" in c.get("card_id", "") and c != card)
                    modifiers[side][i]["attack"] = modifiers[side][i].get("attack", 0) + wolf_count

                # AntiCavalry (Pikeman): double damage to mounted
                if "AntiCavalry" in subtypes:
                    modifiers[side][i]["anti_mounted"] = True

        return modifiers

    @staticmethod
    def process_end_of_turn(game_manager, location: str) -> list[str]:
        """Process end-of-turn abilities at a location (all zones).

        Returns list of effect messages.
        """
        effects = []

        for zone in ["attacker_zone", "middle_zone", "defender_zone"]:
            zone_data = game_manager.battlefield_cards[location][zone]
            for player_key in ["attacker", "defender"]:
                cards = zone_data[player_key]

                for card in cards:
                    subtypes = AbilityProcessor.get_subtypes(card.get("card_info", []))

                    # Healer: heal 1 health to all allies in same zone
                    if "Support" in subtypes and card.get("card_id") == "Healer":
                        healed_any = False
                        for ally in cards:
                            max_health = ally["card_info"][db.IDX_HEALTH] + ally.get("health_modifier", 0)
                            current = ally.get("current_health", max_health)
                            if current < max_health:
                                ally["current_health"] = min(max_health, current + 1)
                                healed_any = True
                        if healed_any:
                            effects.append(f"Healer restores 1 health to allies at {location}/{zone}")

        return effects

    @staticmethod
    def process_on_death(game_manager, location: str, card_data: dict, player,
                        zone: str = "middle_zone") -> list[str]:
        """Process on-death abilities.

        Returns list of effect messages.
        """
        effects = []
        subtypes = AbilityProcessor.get_subtypes(card_data.get("card_info", []))
        player_key = "attacker" if player == Player.ATTACKER else "defender"

        # Necromancer: summon a Skeleton in the same zone
        if "Summon" in subtypes and card_data.get("card_id") == "Necromancer":
            skeleton_info = db.get_card_info("Skeleton")
            if skeleton_info:
                skeleton = {
                    "card_id": "Skeleton",
                    "card_info": skeleton_info,
                    "is_tapped": True,
                    "current_health": skeleton_info[db.IDX_HEALTH],
                    "zone": zone
                }
                game_manager.battlefield_cards[location][zone][player_key].append(skeleton)
                effects.append("Necromancer's death summons a Skeleton!")

        return effects


class CombatResult:
    """Stores the result of combat at a location/zone."""

    def __init__(self, location: str, zone: str = "middle_zone"):
        self.location = location
        self.zone = zone
        self.attacks: list[dict] = []  # [{attacker, defender, damage, killed}]
        self.attacker_casualties: list[str] = []
        self.defender_casualties: list[str] = []
        self.attacker_won = False
        self.defender_won = False


class GameManager:
    """Manages the entire game state."""

    LOCATIONS = ["Keep", "Gate", "Courtyard", "Forest", "Walls", "Sewers", "Camp"]
    ATTACKER_BLOCKED = ["Keep", "Courtyard"]
    DEFENDER_BLOCKED = ["Forest", "Camp"]

    # Adjacency map - which locations connect to which
    ADJACENCY = {
        "Camp": ["Forest", "Gate", "Walls"],
        "Forest": ["Camp", "Walls", "Sewers"],
        "Gate": ["Camp", "Courtyard"],
        "Walls": ["Camp", "Forest", "Courtyard", "Keep"],
        "Sewers": ["Forest", "Keep"],
        "Courtyard": ["Gate", "Walls", "Keep"],
        "Keep": ["Courtyard", "Sewers", "Walls"],
    }

    def __init__(self):
        self.current_turn = 1
        self.current_player = Player.ATTACKER
        self.attacker_has_passed = False
        self.defender_has_passed = False

        # Track if player has drawn a card this phase (1 draw per phase)
        self.attacker_has_drawn = False
        self.defender_has_drawn = False

        # Track if player has moved a card this phase (1 move per phase)
        self.attacker_has_moved = False
        self.defender_has_moved = False

        # Reinforcement queue: [{card_id, card_info, turns_remaining, player}, ...]
        self.hand_reinforcement_queue: list[dict] = []

        # Battlefield cards: {location: {attacker: [], defender: []}}
        self.battlefield_cards: dict[str, dict] = {}

        # Player hands: {Player: [card_instances]}
        self.player_hands: dict[Player, list] = {
            Player.ATTACKER: [],
            Player.DEFENDER: []
        }

        # Player decks (Avatar is NOT in deck - it starts in hand)
        self.player_decks: dict[Player, list] = {
            Player.ATTACKER: ["Footman", "Footman", "Archer", "Eagle", "Knight"],
            Player.DEFENDER: ["Footman", "Footman", "Knight", "War_Hound", "Guardian"]
        }

        # Callbacks for events
        self.on_turn_changed: Callable | None = None
        self.on_card_placed: Callable | None = None
        self.on_card_arrived: Callable | None = None
        self.on_location_captured: Callable | None = None

        # ========== AREA CONTROL SYSTEM ==========
        self.CAPTURABLE_LOCATIONS = ["Gate", "Walls", "Sewers"]
        self.CAPTURE_THRESHOLD = 5

        # Location control state: {location: Player or None}
        self.location_control: dict[str, Player | None] = {
            "Camp": Player.ATTACKER,
            "Forest": Player.ATTACKER,
            "Gate": None,
            "Walls": None,
            "Sewers": None,
            "Courtyard": Player.DEFENDER,
            "Keep": Player.DEFENDER,
        }

        # Accumulated capture power: {location: {"attacker": int, "defender": int}}
        self.capture_power: dict[str, dict[str, int]] = {
            loc: {"attacker": 0, "defender": 0} for loc in self.LOCATIONS
        }

        # Bonus card draws from controlled areas
        self.attacker_bonus_draws = 0
        self.defender_bonus_draws = 0

        # ========== TAPPED COMBAT SYSTEM ==========
        self.combat_phase = GamePhase.MAIN
        self.pending_attackers: list[dict] = []  # [{location, card_index, player, card}]
        self.pending_blocks: dict[int, list[int]] = {}  # attacker_idx -> [blocker_indices]

        self._init_battlefield()

    def _init_battlefield(self):
        """Initialize battlefield structure with 3 zones per location.

        Each location has:
        - attacker_zone: Attacker's home turf (attacker is blocker here)
        - middle_zone: Contested zone (first to place troops is blocker)
        - defender_zone: Defender's home turf (defender is blocker here)

        To conquer, you need troops in the middle_zone.
        Troops in enemy's zone give 2x capture power.
        """
        for location in self.LOCATIONS:
            self.battlefield_cards[location] = {
                "attacker_zone": {"attacker": [], "defender": []},
                "middle_zone": {"attacker": [], "defender": [], "first_placer": None},
                "defender_zone": {"attacker": [], "defender": []}
            }

    def can_place_at_location(self, location: str, player: Player) -> bool:
        """Check if a player can place cards at a location.

        A player can access a location if:
        1. It's not in their blocked list, OR
        2. They control an adjacent capturable location that connects to it
        """
        if player == Player.ATTACKER:
            blocked_list = self.ATTACKER_BLOCKED
        else:
            blocked_list = self.DEFENDER_BLOCKED

        # If not blocked, always allowed
        if location not in blocked_list:
            return True

        # Check if player has captured an adjacent location that grants access
        # Get all locations adjacent to the blocked location
        adjacent_locs = self.ADJACENCY.get(location, [])

        for adj_loc in adjacent_locs:
            # Check if this adjacent location is capturable and controlled by player
            if adj_loc in self.CAPTURABLE_LOCATIONS:
                if self.location_control.get(adj_loc) == player:
                    # Player controls an adjacent capturable location
                    # This grants access to the blocked territory
                    return True

        return False

    def draw_card_to_queue(self, card_id: str, player: Player) -> bool:
        """Draw a card - adds it to hand reinforcement queue."""
        card_info = db.get_card_info(card_id)
        if not card_info:
            print(f"Card not found in database: {card_id}")
            return False

        cost = card_info[db.IDX_COST]

        queue_entry = {
            "card_id": card_id,
            "card_info": card_info,
            "turns_remaining": cost,
            "player": player
        }

        self.hand_reinforcement_queue.append(queue_entry)

        player_name = "Attacker" if player == Player.ATTACKER else "Defender"
        print(f"Card drawn: {card_id} by {player_name}, arriving in {cost} turns")

        return True

    def can_draw_card(self, player: Player) -> bool:
        """Check if a player can draw a card this phase."""
        if player == Player.ATTACKER:
            return not self.attacker_has_drawn
        else:
            return not self.defender_has_drawn

    def draw_card_from_deck(self, card_id: str, player: Player) -> bool:
        """Draw a specific card from the player's deck to the queue."""
        # Check if player can draw
        if not self.can_draw_card(player):
            print(f"{'Attacker' if player == Player.ATTACKER else 'Defender'} already drew a card this phase!")
            return False

        deck = self.player_decks[player]
        if card_id in deck:
            deck.remove(card_id)
            result = self.draw_card_to_queue(card_id, player)
            if result:
                # Mark that this player has drawn
                if player == Player.ATTACKER:
                    self.attacker_has_drawn = True
                else:
                    self.defender_has_drawn = True
            return result
        return False

    def place_card_on_battlefield(self, location: str, card_id: str,
                                   card_info: list, player: Player,
                                   zone: str = "middle_zone") -> bool:
        """Place a card from hand to battlefield in a specific zone.

        Args:
            location: The battlefield location (Gate, Walls, etc.)
            card_id: The card ID
            card_info: Card info from database
            player: The player placing the card
            zone: One of "attacker_zone", "middle_zone", "defender_zone"
        """
        if location not in self.LOCATIONS:
            print(f"Invalid location: {location}")
            return False

        valid_zones = ["attacker_zone", "middle_zone", "defender_zone"]
        if zone not in valid_zones:
            print(f"Invalid zone: {zone}")
            return False

        if not self.can_place_at_location(location, player):
            player_name = "Attacker" if player == Player.ATTACKER else "Defender"
            print(f"{player_name} cannot place cards at {location} - blocked!")
            return False

        card_entry = {
            "card_id": card_id,
            "card_info": card_info,
            "is_tapped": False,
            "current_health": card_info[db.IDX_HEALTH],
            "turn_placed": self.current_turn,
            "has_moved_this_turn": False,
            "zone": zone  # Track which zone the card is in
        }

        player_key = "attacker" if player == Player.ATTACKER else "defender"
        zone_data = self.battlefield_cards[location][zone]
        zone_data[player_key].append(card_entry)

        # Track first placer in middle zone (determines who is blocker)
        if zone == "middle_zone" and zone_data["first_placer"] is None:
            zone_data["first_placer"] = player_key
            print(f"[ZONE] {player_key} is first to middle_zone at {location} - they will be blockers!")

        player_name = "Attacker" if player == Player.ATTACKER else "Defender"
        print(f"Card placed: {card_id} at {location}/{zone} by {player_name}")

        # Process on-play abilities (in the same zone)
        ability_effects = AbilityProcessor.process_on_play(self, location, card_entry, player, zone)
        for effect in ability_effects:
            print(f"[ABILITY] {effect}")

        if self.on_card_placed:
            self.on_card_placed(location, card_entry, player_name)

        return True

    def process_turn(self) -> list:
        """Process turn - decrease cooldowns and move cards to hand."""
        arrived_cards = []

        for i in range(len(self.hand_reinforcement_queue) - 1, -1, -1):
            entry = self.hand_reinforcement_queue[i]
            entry["turns_remaining"] -= 1

            if entry["turns_remaining"] <= 0:
                arrived_cards.append(entry)
                self.hand_reinforcement_queue.pop(i)

                # Add the card to the player's hand
                self.add_card_to_hand(entry["card_id"], entry["card_info"], entry["player"])

                player_name = "Attacker" if entry["player"] == Player.ATTACKER else "Defender"
                print(f"Card arrived in hand: {entry['card_id']} for {player_name}")

                if self.on_card_arrived:
                    self.on_card_arrived(entry["card_id"], entry["card_info"], entry["player"])

        return arrived_cards

    def end_turn(self):
        """End current player's phase."""
        player_name = "Attacker" if self.current_player == Player.ATTACKER else "Defender"
        print(f"{player_name} ended their phase")

        if self.current_player == Player.ATTACKER:
            self.attacker_has_passed = True
            self.current_player = Player.DEFENDER
            # Reset defender's flags for their new phase
            self.defender_has_drawn = False
            self.defender_has_moved = False
            # Untap defender's cards at start of their turn
            self.untap_cards(Player.DEFENDER)
            print("Defender's phase begins")
            if self.on_turn_changed:
                self.on_turn_changed(self.current_turn, "Defender")
        else:
            self.defender_has_passed = True

            if self.attacker_has_passed and self.defender_has_passed:
                print(f"=== Both players passed - processing turn {self.current_turn} ===")
                self.process_turn()

                # Process end-of-turn abilities at all locations
                for loc in self.LOCATIONS:
                    effects = AbilityProcessor.process_end_of_turn(self, loc)
                    for effect in effects:
                        print(f"[ABILITY] {effect}")

                # Accumulate capture power and check for captures
                self.accumulate_capture_power()
                self.check_captures()

                self.attacker_has_passed = False
                self.defender_has_passed = False
                # Reset all flags for new turn
                self.attacker_has_drawn = False
                self.defender_has_drawn = False
                self.attacker_has_moved = False
                self.defender_has_moved = False
                self.current_turn += 1
                self.current_player = Player.ATTACKER

                # Untap attacker's cards at start of their turn
                self.untap_cards(Player.ATTACKER)

                print(f"=== Turn {self.current_turn} begins - Attacker's phase ===")
                if self.on_turn_changed:
                    self.on_turn_changed(self.current_turn, "Attacker")

    def get_cards_at_location(self, location: str, player: Player) -> list:
        """Get all cards at a location for a specific player (across all zones)."""
        if location not in self.battlefield_cards:
            return []
        player_key = "attacker" if player == Player.ATTACKER else "defender"
        all_cards = []
        for zone in ["attacker_zone", "middle_zone", "defender_zone"]:
            all_cards.extend(self.battlefield_cards[location][zone][player_key])
        return all_cards

    def get_cards_in_zone(self, location: str, zone: str, player: Player) -> list:
        """Get cards at a specific zone for a player."""
        if location not in self.battlefield_cards:
            return []
        if zone not in self.battlefield_cards[location]:
            return []
        player_key = "attacker" if player == Player.ATTACKER else "defender"
        return self.battlefield_cards[location][zone][player_key]

    def get_zone_data(self, location: str, zone: str) -> dict:
        """Get full zone data including both players' cards and first_placer."""
        if location not in self.battlefield_cards:
            return {}
        return self.battlefield_cards[location].get(zone, {})

    def get_blocker_side(self, location: str, zone: str) -> str:
        """Determine who is the blocker in a zone.

        Returns "attacker" or "defender" indicating who assigns blockers.
        - attacker_zone: attacker is blocker
        - defender_zone: defender is blocker
        - middle_zone: first_placer is blocker (or None if empty)
        """
        if zone == "attacker_zone":
            return "attacker"
        elif zone == "defender_zone":
            return "defender"
        elif zone == "middle_zone":
            zone_data = self.battlefield_cards[location][zone]
            return zone_data.get("first_placer")  # Could be None
        return None

    def get_hand_reinforcements(self, player: Player) -> list:
        """Get cards coming to hand for a specific player."""
        return [e for e in self.hand_reinforcement_queue if e["player"] == player]

    def get_current_player_string(self) -> str:
        """Get current player as string."""
        return "Attacker" if self.current_player == Player.ATTACKER else "Defender"

    def is_player_turn(self, player: Player) -> bool:
        """Check if it's a specific player's turn."""
        return self.current_player == player

    def get_deck(self, player: Player) -> list:
        """Get the deck for a player."""
        return self.player_decks[player]

    def add_card_to_hand(self, card_id: str, card_info: list, player: Player):
        """Add a card directly to player's hand."""
        self.player_hands[player].append({
            "card_id": card_id,
            "card_info": card_info
        })

    def remove_card_from_hand(self, card_id: str, player: Player) -> dict | None:
        """Remove a card from player's hand and return it."""
        hand = self.player_hands[player]
        for i, card in enumerate(hand):
            if card["card_id"] == card_id:
                return hand.pop(i)
        return None

    def get_hand(self, player: Player) -> list:
        """Get the hand for a player."""
        return self.player_hands[player]

    def are_adjacent(self, loc1: str, loc2: str) -> bool:
        """Check if two locations are adjacent."""
        if loc1 not in self.ADJACENCY:
            return False
        return loc2 in self.ADJACENCY[loc1]

    def get_adjacent_locations(self, location: str) -> list:
        """Get all locations adjacent to the given location."""
        return self.ADJACENCY.get(location, [])

    def can_move_card(self, player: Player) -> bool:
        """Check if a player has any cards that can move this phase."""
        player_key = "attacker" if player == Player.ATTACKER else "defender"
        for location in self.LOCATIONS:
            for zone in ["attacker_zone", "middle_zone", "defender_zone"]:
                for card in self.battlefield_cards[location][zone][player_key]:
                    if self.can_specific_card_move(card):
                        return True
        return False

    def can_specific_card_move(self, card: dict) -> bool:
        """Check if a specific card can move this turn.

        A card can move if:
        1. It was NOT placed this turn (turn_placed < current_turn)
        2. It has NOT already moved this turn (has_moved_this_turn == False)
        """
        turn_placed = card.get("turn_placed", 0)
        has_moved = card.get("has_moved_this_turn", False)

        # Can't move on the turn it was placed
        if turn_placed >= self.current_turn:
            return False

        # Can only move once per turn
        if has_moved:
            return False

        return True

    def move_card(self, from_loc: str, to_loc: str, card_index: int, player: Player,
                  from_zone: str = None, to_zone: str = "middle_zone") -> bool:
        """Move a card from one location/zone to another.

        Args:
            from_loc: Source location
            to_loc: Destination location
            card_index: Index of card in the player's cards at from_loc/from_zone
            player: The player moving the card
            from_zone: Source zone (if None, searches all zones)
            to_zone: Destination zone (defaults to middle_zone)

        Returns:
            True if move was successful
        """
        # Check if locations exist
        if from_loc not in self.LOCATIONS or to_loc not in self.LOCATIONS:
            print(f"Invalid location: {from_loc} or {to_loc}")
            return False

        # Check if locations are adjacent
        if not self.are_adjacent(from_loc, to_loc):
            print(f"{from_loc} and {to_loc} are not adjacent!")
            return False

        # Check if player can be at destination
        if not self.can_place_at_location(to_loc, player):
            player_name = "Attacker" if player == Player.ATTACKER else "Defender"
            print(f"{player_name} cannot move to {to_loc} - blocked!")
            return False

        player_key = "attacker" if player == Player.ATTACKER else "defender"

        # Find the card in source location
        card = None
        source_zone = from_zone
        source_cards = None

        if from_zone:
            # Look in specific zone
            source_cards = self.battlefield_cards[from_loc][from_zone][player_key]
            if card_index < 0 or card_index >= len(source_cards):
                print(f"Invalid card index: {card_index}")
                return False
            card = source_cards[card_index]
        else:
            # Search all zones for the card
            running_idx = 0
            for zone in ["attacker_zone", "middle_zone", "defender_zone"]:
                zone_cards = self.battlefield_cards[from_loc][zone][player_key]
                if running_idx + len(zone_cards) > card_index:
                    local_idx = card_index - running_idx
                    source_cards = zone_cards
                    source_zone = zone
                    card = zone_cards[local_idx]
                    card_index = local_idx  # Update to local index
                    break
                running_idx += len(zone_cards)

            if card is None:
                print(f"Invalid card index: {card_index}")
                return False

        # Check if this specific card can move
        if not self.can_specific_card_move(card):
            if card.get("turn_placed", 0) >= self.current_turn:
                print(f"Card {card['card_id']} cannot move on the turn it was placed!")
            else:
                print(f"Card {card['card_id']} has already moved this turn!")
            return False

        # Move the card
        card = source_cards.pop(card_index)
        card["has_moved_this_turn"] = True  # Mark card as having moved
        card["zone"] = to_zone

        # Add to destination
        dest_zone_data = self.battlefield_cards[to_loc][to_zone]
        dest_zone_data[player_key].append(card)

        # Track first placer in middle zone
        if to_zone == "middle_zone" and dest_zone_data["first_placer"] is None:
            dest_zone_data["first_placer"] = player_key
            print(f"[ZONE] {player_key} is first to middle_zone at {to_loc} - they will be blockers!")

        player_name = "Attacker" if player == Player.ATTACKER else "Defender"
        print(f"{player_name} moved {card['card_id']} from {from_loc}/{source_zone} to {to_loc}/{to_zone}")

        return True

    # ========== COMBAT SYSTEM ==========

    def resolve_all_combat(self) -> list[CombatResult]:
        """Resolve combat at all contested locations (all zones).

        Returns a list of CombatResult objects describing what happened.
        """
        results = []

        for location in self.LOCATIONS:
            for zone in ["attacker_zone", "middle_zone", "defender_zone"]:
                zone_data = self.battlefield_cards[location][zone]
                attacker_cards = zone_data["attacker"]
                defender_cards = zone_data["defender"]

                # Combat only happens if both sides have cards in the zone
                if attacker_cards and defender_cards:
                    result = self._resolve_zone_combat(location, zone)
                    if result:
                        results.append(result)

        return results

    def _resolve_zone_combat(self, location: str, zone: str) -> CombatResult | None:
        """Resolve combat at a single zone within a location.

        Combat rules:
        1. Each card attacks one enemy card (Taunt units must be targeted first)
        2. All attacks happen simultaneously
        3. Damage is dealt based on attack value + modifiers
        4. Cards with current_health <= 0 are destroyed
        5. On-death abilities trigger
        """
        result = CombatResult(location, zone)

        zone_data = self.battlefield_cards[location][zone]
        attacker_cards = zone_data["attacker"]
        defender_cards = zone_data["defender"]

        if not attacker_cards or not defender_cards:
            return None

        # Initialize current_health if not set
        for card in attacker_cards + defender_cards:
            if "current_health" not in card:
                card["current_health"] = card["card_info"][db.IDX_HEALTH]

        # Get combat modifiers from abilities
        modifiers = AbilityProcessor.process_combat_modifiers(
            self, location, attacker_cards, defender_cards)

        # Find Taunt targets
        def get_taunt_targets(cards, mods, side):
            taunt_indices = []
            for i in range(len(cards)):
                if i in mods.get(side, {}) and mods[side][i].get("must_be_targeted", False):
                    taunt_indices.append(i)
            return taunt_indices

        defender_taunts = get_taunt_targets(defender_cards, modifiers, "defender")
        attacker_taunts = get_taunt_targets(attacker_cards, modifiers, "attacker")

        # Calculate damage to deal (before removing any cards)
        damage_to_attackers = {}  # card index -> total damage
        damage_to_defenders = {}

        # Attacker's cards attack defender's cards
        for i, atk_card in enumerate(attacker_cards):
            if defender_cards:
                # Taunt forces targeting, otherwise random
                if defender_taunts:
                    target_idx = random.choice(defender_taunts)
                else:
                    target_idx = random.randint(0, len(defender_cards) - 1)

                # Calculate damage with modifiers
                base_damage = AbilityProcessor.get_effective_attack(atk_card)
                atk_mod = modifiers.get("attacker", {}).get(i, {})
                damage = base_damage + atk_mod.get("attack", 0)

                # Anti-mounted bonus (Pikeman vs Cavalry)
                if atk_mod.get("anti_mounted", False):
                    target_subtypes = AbilityProcessor.get_subtypes(
                        defender_cards[target_idx].get("card_info", []))
                    if "Mounted" in target_subtypes:
                        damage *= 2
                        print(f"[ABILITY] Pikeman deals double damage to mounted unit!")

                # Piercing (Crossbowman) - ignore 1 health
                atk_subtypes = AbilityProcessor.get_subtypes(atk_card.get("card_info", []))
                if "Piercing" in atk_subtypes:
                    damage += 1  # Effectively ignores 1 point of health

                # Holy vs Undead (Templar)
                if "Holy" in atk_subtypes:
                    target_species = AbilityProcessor.get_species(
                        defender_cards[target_idx].get("card_info", []))
                    if target_species == "Undead":
                        damage *= 2
                        print(f"[ABILITY] Holy damage doubled against Undead!")

                # Ethereal (Wraith) - half damage from non-magic
                target_subtypes = AbilityProcessor.get_subtypes(
                    defender_cards[target_idx].get("card_info", []))
                if "Ethereal" in target_subtypes and "Magic" not in atk_subtypes:
                    damage = damage // 2
                    print(f"[ABILITY] Ethereal reduces non-magic damage!")

                damage = max(0, damage)

                if target_idx not in damage_to_defenders:
                    damage_to_defenders[target_idx] = 0
                damage_to_defenders[target_idx] += damage

                # Mark charge as used
                if "Charge" in atk_subtypes:
                    atk_card["has_charged"] = True

                result.attacks.append({
                    "attacker_side": "attacker",
                    "attacker_card": atk_card["card_id"],
                    "defender_card": defender_cards[target_idx]["card_id"],
                    "damage": damage
                })

        # Defender's cards attack attacker's cards
        for i, def_card in enumerate(defender_cards):
            if attacker_cards:
                # Taunt forces targeting
                if attacker_taunts:
                    target_idx = random.choice(attacker_taunts)
                else:
                    target_idx = random.randint(0, len(attacker_cards) - 1)

                # Calculate damage with modifiers
                base_damage = AbilityProcessor.get_effective_attack(def_card)
                def_mod = modifiers.get("defender", {}).get(i, {})
                damage = base_damage + def_mod.get("attack", 0)

                # Anti-mounted bonus
                if def_mod.get("anti_mounted", False):
                    target_subtypes = AbilityProcessor.get_subtypes(
                        attacker_cards[target_idx].get("card_info", []))
                    if "Mounted" in target_subtypes:
                        damage *= 2
                        print(f"[ABILITY] Pikeman deals double damage to mounted unit!")

                # Piercing
                def_subtypes = AbilityProcessor.get_subtypes(def_card.get("card_info", []))
                if "Piercing" in def_subtypes:
                    damage += 1

                # Holy vs Undead
                if "Holy" in def_subtypes:
                    target_species = AbilityProcessor.get_species(
                        attacker_cards[target_idx].get("card_info", []))
                    if target_species == "Undead":
                        damage *= 2
                        print(f"[ABILITY] Holy damage doubled against Undead!")

                # Ethereal defense
                target_subtypes = AbilityProcessor.get_subtypes(
                    attacker_cards[target_idx].get("card_info", []))
                if "Ethereal" in target_subtypes and "Magic" not in def_subtypes:
                    damage = damage // 2
                    print(f"[ABILITY] Ethereal reduces non-magic damage!")

                damage = max(0, damage)

                if target_idx not in damage_to_attackers:
                    damage_to_attackers[target_idx] = 0
                damage_to_attackers[target_idx] += damage

                # Mark charge as used
                if "Charge" in def_subtypes:
                    def_card["has_charged"] = True

                result.attacks.append({
                    "attacker_side": "defender",
                    "attacker_card": def_card["card_id"],
                    "defender_card": attacker_cards[target_idx]["card_id"],
                    "damage": damage
                })

        # Apply damage simultaneously
        for idx, damage in damage_to_attackers.items():
            if idx < len(attacker_cards):
                attacker_cards[idx]["current_health"] -= damage

        for idx, damage in damage_to_defenders.items():
            if idx < len(defender_cards):
                defender_cards[idx]["current_health"] -= damage

        # Remove dead cards and process on-death abilities
        for i in range(len(attacker_cards) - 1, -1, -1):
            if attacker_cards[i]["current_health"] <= 0:
                dead_card = attacker_cards.pop(i)
                result.attacker_casualties.append(dead_card["card_id"])
                print(f"[COMBAT] {dead_card['card_id']} (Attacker) was destroyed at {location}/{zone}!")

                # Process on-death abilities
                death_effects = AbilityProcessor.process_on_death(
                    self, location, dead_card, Player.ATTACKER, zone)
                for effect in death_effects:
                    print(f"[ABILITY] {effect}")

                # Death Knight heals when killing (check if killer was a Death Knight)
                for def_card in defender_cards:
                    if def_card.get("card_id") == "Death_Knight":
                        max_hp = def_card["card_info"][db.IDX_HEALTH]
                        def_card["current_health"] = min(max_hp,
                            def_card.get("current_health", max_hp) + 1)
                        print(f"[ABILITY] Death Knight heals from the kill!")

        for i in range(len(defender_cards) - 1, -1, -1):
            if defender_cards[i]["current_health"] <= 0:
                dead_card = defender_cards.pop(i)
                result.defender_casualties.append(dead_card["card_id"])
                print(f"[COMBAT] {dead_card['card_id']} (Defender) was destroyed at {location}/{zone}!")

                # Process on-death abilities
                death_effects = AbilityProcessor.process_on_death(
                    self, location, dead_card, Player.DEFENDER, zone)
                for effect in death_effects:
                    print(f"[ABILITY] {effect}")

                # Death Knight heals
                for atk_card in attacker_cards:
                    if atk_card.get("card_id") == "Death_Knight":
                        max_hp = atk_card["card_info"][db.IDX_HEALTH]
                        atk_card["current_health"] = min(max_hp,
                            atk_card.get("current_health", max_hp) + 1)
                        print(f"[ABILITY] Death Knight heals from the kill!")

        # Determine who won the engagement
        if not attacker_cards and defender_cards:
            result.defender_won = True
        elif attacker_cards and not defender_cards:
            result.attacker_won = True

        return result

    def check_win_condition(self) -> Player | None:
        """Check if either player has won by destroying the enemy Avatar.

        Returns the winning player, or None if game continues.
        """
        attacker_has_avatar = False
        defender_has_avatar = False

        # Check battlefield for Avatars (all zones)
        for location in self.LOCATIONS:
            for zone in ["attacker_zone", "middle_zone", "defender_zone"]:
                for card in self.battlefield_cards[location][zone]["attacker"]:
                    if card["card_id"] == "Avatar":
                        attacker_has_avatar = True
                for card in self.battlefield_cards[location][zone]["defender"]:
                    if card["card_id"] == "Avatar":
                        defender_has_avatar = True

        # Check hands for Avatars
        for card in self.player_hands[Player.ATTACKER]:
            if card["card_id"] == "Avatar":
                attacker_has_avatar = True
        for card in self.player_hands[Player.DEFENDER]:
            if card["card_id"] == "Avatar":
                defender_has_avatar = True

        # Check reinforcement queue
        for entry in self.hand_reinforcement_queue:
            if entry["card_id"] == "Avatar":
                if entry["player"] == Player.ATTACKER:
                    attacker_has_avatar = True
                else:
                    defender_has_avatar = True

        if not attacker_has_avatar:
            return Player.DEFENDER  # Defender wins
        if not defender_has_avatar:
            return Player.ATTACKER  # Attacker wins

        return None  # Game continues

    def get_card_health(self, location: str, player: Player, card_index: int,
                        zone: str = "middle_zone") -> tuple[int, int] | None:
        """Get current and max health for a card on the battlefield in a specific zone.

        Returns (current_health, max_health) or None if card not found.
        """
        player_key = "attacker" if player == Player.ATTACKER else "defender"
        cards = self.battlefield_cards[location][zone][player_key]

        if 0 <= card_index < len(cards):
            card = cards[card_index]
            max_health = card["card_info"][db.IDX_HEALTH]
            current_health = card.get("current_health", max_health)
            return (current_health, max_health)

        return None

    # ========== TAPPED COMBAT METHODS ==========

    def untap_cards(self, player: Player):
        """Untap all cards belonging to a player at start of their turn."""
        player_key = "attacker" if player == Player.ATTACKER else "defender"
        for location in self.LOCATIONS:
            for zone in ["attacker_zone", "middle_zone", "defender_zone"]:
                for card in self.battlefield_cards[location][zone][player_key]:
                    card["is_tapped"] = False
                    card["has_moved_this_turn"] = False  # Reset movement flag each turn

    def tap_card(self, location: str, card_index: int, player: Player,
                 zone: str = "middle_zone") -> bool:
        """Tap a card in a zone (mark as having attacked)."""
        player_key = "attacker" if player == Player.ATTACKER else "defender"
        cards = self.battlefield_cards[location][zone][player_key]
        if 0 <= card_index < len(cards):
            cards[card_index]["is_tapped"] = True
            return True
        return False

    def get_untapped_cards(self, location: str, player: Player,
                           zone: str = "middle_zone") -> list[tuple[int, dict]]:
        """Get all untapped cards at a location/zone for a player.

        Returns list of (index, card) tuples.
        """
        player_key = "attacker" if player == Player.ATTACKER else "defender"
        cards = self.battlefield_cards[location][zone][player_key]
        return [(i, c) for i, c in enumerate(cards) if not c.get("is_tapped", False)]

    def declare_attacker(self, location: str, card_index: int, player: Player,
                         zone: str = "middle_zone") -> bool:
        """Declare a card as an attacker. Taps the card."""
        player_key = "attacker" if player == Player.ATTACKER else "defender"
        cards = self.battlefield_cards[location][zone][player_key]

        if 0 <= card_index < len(cards):
            card = cards[card_index]
            if card.get("is_tapped", False):
                print(f"Card {card['card_id']} is already tapped!")
                return False

            card["is_tapped"] = True
            self.pending_attackers.append({
                "location": location,
                "card_index": card_index,
                "player": player,
                "card": card
            })
            print(f"{card['card_id']} declared as attacker at {location}")
            return True
        return False

    def declare_blocker(self, attacker_idx: int, location: str,
                        blocker_index: int, player: Player,
                        zone: str = "middle_zone") -> bool:
        """Assign a blocker to an attacker in a specific zone."""
        if attacker_idx >= len(self.pending_attackers):
            return False

        attacker = self.pending_attackers[attacker_idx]
        if attacker["location"] != location:
            print("Blocker must be at same location as attacker!")
            return False

        player_key = "attacker" if player == Player.ATTACKER else "defender"
        cards = self.battlefield_cards[location][zone][player_key]

        if 0 <= blocker_index < len(cards):
            blocker = cards[blocker_index]
            if blocker.get("is_tapped", False):
                print(f"Card {blocker['card_id']} is tapped and cannot block!")
                return False

            if attacker_idx not in self.pending_blocks:
                self.pending_blocks[attacker_idx] = []
            self.pending_blocks[attacker_idx].append(blocker_index)
            print(f"{blocker['card_id']} blocking {attacker['card']['card_id']}")
            return True
        return False

    def clear_combat_state(self):
        """Clear pending attackers and blockers."""
        self.pending_attackers = []
        self.pending_blocks = {}
        self.combat_phase = GamePhase.MAIN

    # ========== HEARTHSTONE-STYLE COMBAT ==========

    def get_combat_locations(self) -> list[str]:
        """Get all locations where combat will occur (both sides have cards in same zone)."""
        combat_locs = []
        for location in self.LOCATIONS:
            # Check each zone for combat
            for zone in ["attacker_zone", "middle_zone", "defender_zone"]:
                zone_data = self.battlefield_cards[location][zone]
                if zone_data["attacker"] and zone_data["defender"]:
                    # Combat in this zone - add location if not already added
                    if location not in combat_locs:
                        combat_locs.append(location)
                    break
        return combat_locs

    def get_combat_zones_at_location(self, location: str) -> list[dict]:
        """Get all zones with combat at a location, with blocker assignment info.

        Returns list of dicts with:
        - zone: zone name
        - blocker_side: who assigns blockers ("attacker" or "defender")
        - attacker_cards: list of attacking cards
        - defender_cards: list of defending cards
        """
        combat_zones = []
        for zone in ["attacker_zone", "middle_zone", "defender_zone"]:
            zone_data = self.battlefield_cards[location][zone]
            if zone_data["attacker"] and zone_data["defender"]:
                blocker_side = self.get_blocker_side(location, zone)
                combat_zones.append({
                    "zone": zone,
                    "blocker_side": blocker_side,
                    "attacker_cards": zone_data["attacker"],
                    "defender_cards": zone_data["defender"]
                })
        return combat_zones

    def get_attackers_at_location(self, location: str, attacking_player: Player) -> list[dict]:
        """Get all cards that will attack at a location (across all zones).

        In area control, the player who doesn't control the area is the attacker.
        If no one controls it, both sides attack.
        """
        player_key = "attacker" if attacking_player == Player.ATTACKER else "defender"
        all_cards = []
        idx = 0
        for zone in ["attacker_zone", "middle_zone", "defender_zone"]:
            for c in self.battlefield_cards[location][zone][player_key]:
                all_cards.append({"index": idx, "card": c, "zone": zone})
                idx += 1
        return all_cards

    def resolve_combat_with_assignments(self, location: str,
                                        assignments: dict[int, list[int]],
                                        attacker_side: str = "attacker",
                                        zone: str = "middle_zone") -> CombatResult:
        """Resolve combat at a location/zone using blocker assignments.

        Args:
            location: The battlefield location
            assignments: Dict mapping attacker index to list of blocker indices
                         e.g., {0: [1, 2], 1: [], 2: [0]} means:
                         - Attacker 0 is blocked by blockers 1 and 2
                         - Attacker 1 is unblocked
                         - Attacker 2 is blocked by blocker 0
            attacker_side: "attacker" or "defender" - who is attacking
            zone: The zone where combat is happening

        Returns:
            CombatResult with combat details
        """
        result = CombatResult(location)
        result.zone = zone  # Add zone to result
        defender_side = "defender" if attacker_side == "attacker" else "attacker"

        zone_data = self.battlefield_cards[location][zone]
        attacker_cards = zone_data[attacker_side]
        defender_cards = zone_data[defender_side]

        if not attacker_cards or not defender_cards:
            return result

        # Initialize current_health if not set
        for card in attacker_cards + defender_cards:
            if "current_health" not in card:
                card["current_health"] = card["card_info"][db.IDX_HEALTH]

        # Get combat modifiers
        modifiers = AbilityProcessor.process_combat_modifiers(
            self, location, attacker_cards, defender_cards)

        # Track damage to apply
        damage_to_attackers = {}  # attacker index -> damage
        damage_to_defenders = {}  # defender index -> damage

        # Find taunt cards among defenders - they MUST be assigned as blockers if present
        taunt_indices = []
        for i, card in enumerate(defender_cards):
            subtypes = AbilityProcessor.get_subtypes(card.get("card_info", []))
            if "Taunt" in subtypes:
                taunt_indices.append(i)

        # Process each attacker
        print(f"[COMBAT-GM] Processing {len(attacker_cards)} attackers with assignments: {assignments}")
        for atk_idx, atk_card in enumerate(attacker_cards):
            blocker_indices = assignments.get(atk_idx, [])
            print(f"[COMBAT-GM] Attacker {atk_idx} ({atk_card['card_id']}) has blockers: {blocker_indices}")

            # Get attacker's damage
            base_damage = AbilityProcessor.get_effective_attack(atk_card)
            atk_mod = modifiers.get(attacker_side, {}).get(atk_idx, {})
            atk_damage = base_damage + atk_mod.get("attack", 0)
            print(f"[COMBAT-GM]   Attacker damage: {atk_damage} (base: {base_damage})")

            atk_subtypes = AbilityProcessor.get_subtypes(atk_card.get("card_info", []))

            if blocker_indices:
                # Attacker is blocked - damage is split among blockers
                # For simplicity, attacker deals full damage to first blocker
                primary_blocker_idx = blocker_indices[0]

                if primary_blocker_idx < len(defender_cards):
                    blocker = defender_cards[primary_blocker_idx]

                    # Apply damage modifiers
                    damage = atk_damage

                    # Anti-mounted bonus
                    if atk_mod.get("anti_mounted", False):
                        blocker_subtypes = AbilityProcessor.get_subtypes(blocker.get("card_info", []))
                        if "Mounted" in blocker_subtypes:
                            damage *= 2

                    # Piercing
                    if "Piercing" in atk_subtypes:
                        damage += 1

                    # Holy vs Undead
                    if "Holy" in atk_subtypes:
                        blocker_species = AbilityProcessor.get_species(blocker.get("card_info", []))
                        if blocker_species == "Undead":
                            damage *= 2

                    # Ethereal defense
                    blocker_subtypes = AbilityProcessor.get_subtypes(blocker.get("card_info", []))
                    if "Ethereal" in blocker_subtypes and "Magic" not in atk_subtypes:
                        damage = damage // 2

                    damage = max(0, damage)

                    if primary_blocker_idx not in damage_to_defenders:
                        damage_to_defenders[primary_blocker_idx] = 0
                    damage_to_defenders[primary_blocker_idx] += damage

                    result.attacks.append({
                        "attacker_side": attacker_side,
                        "attacker_card": atk_card["card_id"],
                        "defender_card": blocker["card_id"],
                        "damage": damage,
                        "blocked": True
                    })

                # Blocker(s) deal damage back to attacker
                for blocker_idx in blocker_indices:
                    if blocker_idx < len(defender_cards):
                        blocker = defender_cards[blocker_idx]
                        blocker_damage = AbilityProcessor.get_effective_attack(blocker)
                        def_mod = modifiers.get(defender_side, {}).get(blocker_idx, {})
                        blocker_damage += def_mod.get("attack", 0)

                        # Ethereal on attacker
                        if "Ethereal" in atk_subtypes:
                            blocker_subtypes = AbilityProcessor.get_subtypes(blocker.get("card_info", []))
                            if "Magic" not in blocker_subtypes:
                                blocker_damage = blocker_damage // 2

                        blocker_damage = max(0, blocker_damage)

                        if atk_idx not in damage_to_attackers:
                            damage_to_attackers[atk_idx] = 0
                        damage_to_attackers[atk_idx] += blocker_damage

            else:
                # Unblocked attacker - contributes to capture power instead
                # (In Hearthstone, unblocked minions hit face. Here they help capture)
                result.attacks.append({
                    "attacker_side": attacker_side,
                    "attacker_card": atk_card["card_id"],
                    "defender_card": None,
                    "damage": atk_damage,
                    "blocked": False,
                    "capture_contribution": atk_damage
                })

            # Mark charge as used
            if "Charge" in atk_subtypes:
                atk_card["has_charged"] = True

        # Apply damage simultaneously
        for idx, damage in damage_to_attackers.items():
            if idx < len(attacker_cards):
                attacker_cards[idx]["current_health"] -= damage

        for idx, damage in damage_to_defenders.items():
            if idx < len(defender_cards):
                defender_cards[idx]["current_health"] -= damage

        # Remove dead cards
        attacker_player = Player.ATTACKER if attacker_side == "attacker" else Player.DEFENDER
        defender_player = Player.DEFENDER if attacker_side == "attacker" else Player.ATTACKER

        for i in range(len(attacker_cards) - 1, -1, -1):
            if attacker_cards[i]["current_health"] <= 0:
                dead_card = attacker_cards.pop(i)
                result.attacker_casualties.append(dead_card["card_id"])
                print(f"[COMBAT] {dead_card['card_id']} ({attacker_side}) was destroyed at {location}!")

                # Process on-death abilities
                death_effects = AbilityProcessor.process_on_death(
                    self, location, dead_card, attacker_player, zone)
                for effect in death_effects:
                    print(f"[ABILITY] {effect}")

        for i in range(len(defender_cards) - 1, -1, -1):
            if defender_cards[i]["current_health"] <= 0:
                dead_card = defender_cards.pop(i)
                result.defender_casualties.append(dead_card["card_id"])
                print(f"[COMBAT] {dead_card['card_id']} ({defender_side}) was destroyed at {location}/{zone}!")

                # Process on-death abilities
                death_effects = AbilityProcessor.process_on_death(
                    self, location, dead_card, defender_player, zone)
                for effect in death_effects:
                    print(f"[ABILITY] {effect}")

        return result

    # ========== AREA CONTROL METHODS ==========

    def get_max_draws(self, player: Player) -> int:
        """Get max draws per turn for a player (base 1 + controlled capturable areas)."""
        base = 1
        bonus = self.attacker_bonus_draws if player == Player.ATTACKER else self.defender_bonus_draws
        return base + bonus

    def get_draws_remaining(self, player: Player) -> int:
        """Get remaining draws for this phase."""
        max_draws = self.get_max_draws(player)
        if player == Player.ATTACKER:
            drawn = 1 if self.attacker_has_drawn else 0
        else:
            drawn = 1 if self.defender_has_drawn else 0
        return max(0, max_draws - drawn)

    def accumulate_capture_power(self):
        """Add attack power to capture progress at each capturable location.

        Capture power rules:
        - Only troops in middle_zone contribute to capture
        - Troops in enemy's zone (attacker in defender_zone, defender in attacker_zone)
          give 2x capture power
        - To capture, you need at least one troop in middle_zone
        """
        for location in self.CAPTURABLE_LOCATIONS:
            if self.location_control[location] is not None:
                continue  # Already captured, skip

            atk_power = 0
            def_power = 0

            # Get cards from each zone
            atk_zone = self.battlefield_cards[location]["attacker_zone"]
            mid_zone = self.battlefield_cards[location]["middle_zone"]
            def_zone = self.battlefield_cards[location]["defender_zone"]

            # Attacker's power:
            # - Middle zone: 1x power
            # - Defender zone (enemy zone): 2x power
            for card in mid_zone["attacker"]:
                atk_power += card["card_info"][db.IDX_ATTACK]
            for card in def_zone["attacker"]:
                atk_power += card["card_info"][db.IDX_ATTACK] * 2  # 2x in enemy zone

            # Defender's power:
            # - Middle zone: 1x power
            # - Attacker zone (enemy zone): 2x power
            for card in mid_zone["defender"]:
                def_power += card["card_info"][db.IDX_ATTACK]
            for card in atk_zone["defender"]:
                def_power += card["card_info"][db.IDX_ATTACK] * 2  # 2x in enemy zone

            self.capture_power[location]["attacker"] += atk_power
            self.capture_power[location]["defender"] += def_power

            if atk_power > 0 or def_power > 0:
                print(f"[CAPTURE] {location}: Attacker +{atk_power} (total: {self.capture_power[location]['attacker']}), "
                      f"Defender +{def_power} (total: {self.capture_power[location]['defender']})")

    def get_capture_threshold(self, location: str, for_player: Player) -> int:
        """Get the capture threshold for a player at a location.

        Threshold = base (5) + sum of enemy card health if enemies present.
        """
        threshold = self.CAPTURE_THRESHOLD
        enemy_key = "defender" if for_player == Player.ATTACKER else "attacker"

        # Add enemy health from all zones to threshold
        for zone in ["attacker_zone", "middle_zone", "defender_zone"]:
            enemy_cards = self.battlefield_cards[location][zone][enemy_key]
            for card in enemy_cards:
                threshold += card.get("current_health", card["card_info"][db.IDX_HEALTH])

        return threshold

    def check_captures(self) -> list[tuple[str, Player]]:
        """Check if any locations are captured.

        To capture, you need troops in the middle_zone.
        Returns list of (location, new_controller) tuples.
        """
        captures = []

        for location in self.CAPTURABLE_LOCATIONS:
            if self.location_control[location] is not None:
                continue  # Already controlled

            mid_zone = self.battlefield_cards[location]["middle_zone"]

            # Must have troops in middle_zone to capture
            atk_in_middle = len(mid_zone["attacker"]) > 0
            def_in_middle = len(mid_zone["defender"]) > 0

            atk_threshold = self.get_capture_threshold(location, Player.ATTACKER)
            def_threshold = self.get_capture_threshold(location, Player.DEFENDER)

            atk_power = self.capture_power[location]["attacker"]
            def_power = self.capture_power[location]["defender"]

            # Check both players for capture eligibility (must be in middle zone!)
            atk_can_capture = atk_in_middle and atk_power >= atk_threshold
            def_can_capture = def_in_middle and def_power >= def_threshold

            # If both can capture simultaneously, the one with more power wins
            # If tied, location remains contested (no capture)
            if atk_can_capture and def_can_capture:
                if atk_power > def_power:
                    self.location_control[location] = Player.ATTACKER
                    captures.append((location, Player.ATTACKER))
                    self._on_location_captured(location, Player.ATTACKER)
                    print(f"[CAPTURE] Attacker captured {location} (power advantage)!")
                elif def_power > atk_power:
                    self.location_control[location] = Player.DEFENDER
                    captures.append((location, Player.DEFENDER))
                    self._on_location_captured(location, Player.DEFENDER)
                    print(f"[CAPTURE] Defender captured {location} (power advantage)!")
                else:
                    print(f"[CAPTURE] {location} remains contested - tied power!")
            elif atk_can_capture:
                self.location_control[location] = Player.ATTACKER
                captures.append((location, Player.ATTACKER))
                self._on_location_captured(location, Player.ATTACKER)
                print(f"[CAPTURE] Attacker captured {location}!")
            elif def_can_capture:
                self.location_control[location] = Player.DEFENDER
                captures.append((location, Player.DEFENDER))
                self._on_location_captured(location, Player.DEFENDER)
                print(f"[CAPTURE] Defender captured {location}!")

        return captures

    def _on_location_captured(self, location: str, player: Player):
        """Handle capture side effects."""
        # Update bonus draws
        if player == Player.ATTACKER:
            self.attacker_bonus_draws += 1
        else:
            self.defender_bonus_draws += 1

        # Reset capture power for this location
        self.capture_power[location] = {"attacker": 0, "defender": 0}

        # Callback for UI notification
        if self.on_location_captured:
            self.on_location_captured(location, player)

    def get_location_capture_info(self, location: str) -> dict:
        """Get capture information for a location.

        Returns dict with power, threshold, and control info.
        """
        if location not in self.CAPTURABLE_LOCATIONS:
            return {
                "capturable": False,
                "controller": self.location_control.get(location)
            }

        return {
            "capturable": True,
            "controller": self.location_control[location],
            "attacker_power": self.capture_power[location]["attacker"],
            "defender_power": self.capture_power[location]["defender"],
            "attacker_threshold": self.get_capture_threshold(location, Player.ATTACKER),
            "defender_threshold": self.get_capture_threshold(location, Player.DEFENDER),
        }
