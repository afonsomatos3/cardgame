"""Game manager handling game state, turns, and battlefield logic."""

from enum import Enum
from typing import Callable
import cards_database as db
import random


class Player(Enum):
    ATTACKER = 0
    DEFENDER = 1


class CombatResult:
    """Stores the result of combat at a location."""

    def __init__(self, location: str):
        self.location = location
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

        self._init_battlefield()

    def _init_battlefield(self):
        """Initialize battlefield structure."""
        for location in self.LOCATIONS:
            self.battlefield_cards[location] = {"attacker": [], "defender": []}

    def can_place_at_location(self, location: str, player: Player) -> bool:
        """Check if a player can place cards at a location."""
        if player == Player.ATTACKER:
            return location not in self.ATTACKER_BLOCKED
        else:
            return location not in self.DEFENDER_BLOCKED

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
                                   card_info: list, player: Player) -> bool:
        """Place a card from hand to battlefield."""
        if location not in self.LOCATIONS:
            print(f"Invalid location: {location}")
            return False

        if not self.can_place_at_location(location, player):
            player_name = "Attacker" if player == Player.ATTACKER else "Defender"
            print(f"{player_name} cannot place cards at {location} - blocked!")
            return False

        card_entry = {
            "card_id": card_id,
            "card_info": card_info
        }

        player_key = "attacker" if player == Player.ATTACKER else "defender"
        self.battlefield_cards[location][player_key].append(card_entry)

        player_name = "Attacker" if player == Player.ATTACKER else "Defender"
        print(f"Card placed: {card_id} at {location} by {player_name}")

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
            print("Defender's phase begins")
            if self.on_turn_changed:
                self.on_turn_changed(self.current_turn, "Defender")
        else:
            self.defender_has_passed = True

            if self.attacker_has_passed and self.defender_has_passed:
                print(f"=== Both players passed - processing turn {self.current_turn} ===")
                self.process_turn()

                self.attacker_has_passed = False
                self.defender_has_passed = False
                # Reset all flags for new turn
                self.attacker_has_drawn = False
                self.defender_has_drawn = False
                self.attacker_has_moved = False
                self.defender_has_moved = False
                self.current_turn += 1
                self.current_player = Player.ATTACKER

                print(f"=== Turn {self.current_turn} begins - Attacker's phase ===")
                if self.on_turn_changed:
                    self.on_turn_changed(self.current_turn, "Attacker")

    def get_cards_at_location(self, location: str, player: Player) -> list:
        """Get cards at a location for a specific player."""
        if location not in self.battlefield_cards:
            return []
        player_key = "attacker" if player == Player.ATTACKER else "defender"
        return self.battlefield_cards[location][player_key]

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
        """Check if a player can move a card this phase."""
        if player == Player.ATTACKER:
            return not self.attacker_has_moved
        else:
            return not self.defender_has_moved

    def move_card(self, from_loc: str, to_loc: str, card_index: int, player: Player) -> bool:
        """Move a card from one location to an adjacent location.

        Args:
            from_loc: Source location
            to_loc: Destination location
            card_index: Index of card in the player's cards at from_loc
            player: The player moving the card

        Returns:
            True if move was successful
        """
        # Check if player can move
        if not self.can_move_card(player):
            print(f"{'Attacker' if player == Player.ATTACKER else 'Defender'} already moved this phase!")
            return False

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

        # Get player's cards at source location
        player_key = "attacker" if player == Player.ATTACKER else "defender"
        source_cards = self.battlefield_cards[from_loc][player_key]

        if card_index < 0 or card_index >= len(source_cards):
            print(f"Invalid card index: {card_index}")
            return False

        # Move the card
        card = source_cards.pop(card_index)
        self.battlefield_cards[to_loc][player_key].append(card)

        # Mark that player has moved
        if player == Player.ATTACKER:
            self.attacker_has_moved = True
        else:
            self.defender_has_moved = True

        player_name = "Attacker" if player == Player.ATTACKER else "Defender"
        print(f"{player_name} moved {card['card_id']} from {from_loc} to {to_loc}")

        return True

    # ========== COMBAT SYSTEM ==========

    def resolve_all_combat(self) -> list[CombatResult]:
        """Resolve combat at all contested locations.

        Returns a list of CombatResult objects describing what happened.
        """
        results = []

        for location in self.LOCATIONS:
            attacker_cards = self.battlefield_cards[location]["attacker"]
            defender_cards = self.battlefield_cards[location]["defender"]

            # Combat only happens if both sides have cards
            if attacker_cards and defender_cards:
                result = self._resolve_location_combat(location)
                if result:
                    results.append(result)

        return results

    def _resolve_location_combat(self, location: str) -> CombatResult | None:
        """Resolve combat at a single location.

        Combat rules:
        1. Each card attacks one enemy card (random targeting)
        2. All attacks happen simultaneously
        3. Damage is dealt based on attack value
        4. Cards with current_health <= 0 are destroyed
        """
        result = CombatResult(location)

        attacker_cards = self.battlefield_cards[location]["attacker"]
        defender_cards = self.battlefield_cards[location]["defender"]

        if not attacker_cards or not defender_cards:
            return None

        # Initialize current_health if not set
        for card in attacker_cards + defender_cards:
            if "current_health" not in card:
                card["current_health"] = card["card_info"][db.IDX_HEALTH]

        # Calculate damage to deal (before removing any cards)
        damage_to_attackers = {}  # card index -> total damage
        damage_to_defenders = {}

        # Attacker's cards attack defender's cards
        for i, atk_card in enumerate(attacker_cards):
            if defender_cards:
                # Pick a random target
                target_idx = random.randint(0, len(defender_cards) - 1)
                damage = atk_card["card_info"][db.IDX_ATTACK]

                if target_idx not in damage_to_defenders:
                    damage_to_defenders[target_idx] = 0
                damage_to_defenders[target_idx] += damage

                result.attacks.append({
                    "attacker_side": "attacker",
                    "attacker_card": atk_card["card_id"],
                    "defender_card": defender_cards[target_idx]["card_id"],
                    "damage": damage
                })

        # Defender's cards attack attacker's cards
        for i, def_card in enumerate(defender_cards):
            if attacker_cards:
                # Pick a random target
                target_idx = random.randint(0, len(attacker_cards) - 1)
                damage = def_card["card_info"][db.IDX_ATTACK]

                if target_idx not in damage_to_attackers:
                    damage_to_attackers[target_idx] = 0
                damage_to_attackers[target_idx] += damage

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

        # Remove dead cards (iterate backwards to avoid index issues)
        for i in range(len(attacker_cards) - 1, -1, -1):
            if attacker_cards[i]["current_health"] <= 0:
                dead_card = attacker_cards.pop(i)
                result.attacker_casualties.append(dead_card["card_id"])
                print(f"[COMBAT] {dead_card['card_id']} (Attacker) was destroyed at {location}!")

        for i in range(len(defender_cards) - 1, -1, -1):
            if defender_cards[i]["current_health"] <= 0:
                dead_card = defender_cards.pop(i)
                result.defender_casualties.append(dead_card["card_id"])
                print(f"[COMBAT] {dead_card['card_id']} (Defender) was destroyed at {location}!")

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

        # Check battlefield for Avatars
        for location in self.LOCATIONS:
            for card in self.battlefield_cards[location]["attacker"]:
                if card["card_id"] == "Avatar":
                    attacker_has_avatar = True
            for card in self.battlefield_cards[location]["defender"]:
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

    def get_card_health(self, location: str, player: Player, card_index: int) -> tuple[int, int] | None:
        """Get current and max health for a card on the battlefield.

        Returns (current_health, max_health) or None if card not found.
        """
        player_key = "attacker" if player == Player.ATTACKER else "defender"
        cards = self.battlefield_cards[location][player_key]

        if 0 <= card_index < len(cards):
            card = cards[card_index]
            max_health = card["card_info"][db.IDX_HEALTH]
            current_health = card.get("current_health", max_health)
            return (current_health, max_health)

        return None
