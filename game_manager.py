"""Game manager handling game state, turns, and battlefield logic."""

from enum import Enum
from typing import Callable
import cards_database as db


class Player(Enum):
    ATTACKER = 0
    DEFENDER = 1


class GameManager:
    """Manages the entire game state."""

    LOCATIONS = ["Keep", "Gate", "Courtyard", "Forest", "Walls", "Sewers"]
    ATTACKER_BLOCKED = ["Keep", "Courtyard"]
    DEFENDER_BLOCKED = ["Forest"]

    def __init__(self):
        self.current_turn = 1
        self.current_player = Player.ATTACKER
        self.attacker_has_passed = False
        self.defender_has_passed = False

        # Track if player has drawn a card this phase (1 draw per phase)
        self.attacker_has_drawn = False
        self.defender_has_drawn = False

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
            # Reset defender's draw flag for their new phase
            self.defender_has_drawn = False
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
                # Reset draw flags for new turn
                self.attacker_has_drawn = False
                self.defender_has_drawn = False
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
