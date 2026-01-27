"""WarMasterMind - A card game implemented in Pygame."""

import pygame
import sys

from utility.game_manager import GameManager, Player
from utility.card import Card, set_card_scale
from utility.hand_manager import HandManager
from utility.battlefield import Battlefield, LocationPanel
from utility.ui import TurnUI, DeckUI, DrawMenu, ReinforcementUI, CombatLogUI, GameOverUI
from utility.menu import MainMenu, DeckBuilder
from utility.audio_manager import AudioManager
import utility.cards_database as db


# Screen settings
BASE_WIDTH = 1280
BASE_HEIGHT = 720
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

# Colors
BG_COLOR = (30, 35, 40)

# Game states
STATE_MENU = "menu"
STATE_DECK_BUILDER = "deck_builder"
STATE_GAME = "game"


def calculate_scale(width: int, height: int) -> float:
    """Calculate scale factor based on screen size."""
    scale_x = width / BASE_WIDTH
    scale_y = height / BASE_HEIGHT
    return min(scale_x, scale_y)


class Game:
    """Main game class."""

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("WarMasterMind")

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT),
                                               pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.running = True

        self.screen_width = SCREEN_WIDTH
        self.screen_height = SCREEN_HEIGHT

        # Game state
        self.state = STATE_MENU

        # Custom decks (can be modified in deck builder)
        self.attacker_deck = ["Footman", "Footman", "Archer", "Eagle", "Knight"]
        self.defender_deck = ["Footman", "Footman", "Knight", "War_Hound", "Guardian"]

        # Audio manager
        self.audio_manager = AudioManager()
        self.audio_manager.play_music()  # Try to play background music

        # Main menu and deck builder
        self.main_menu = MainMenu(self.screen_width, self.screen_height)
        self.main_menu.audio_manager = self.audio_manager  # Share audio manager
        self.deck_builder = DeckBuilder(self.screen_width, self.screen_height)

        # Game components (initialized when game starts)
        self.game_manager = None
        self.turn_ui = None
        self.battlefield = None
        self.location_panel = None
        self.attacker_hand = None
        self.defender_hand = None
        self.deck_ui = None
        self.draw_menu = None
        self.reinforcement_ui = None
        self.combat_log_ui = None
        self.game_over_ui = None
        self.dragging_card = None
        self.dragging_from_hand = None

    def _init_game(self):
        """Initialize a new game with current deck settings."""
        # Initialize game manager with custom decks
        self.game_manager = GameManager()
        self.game_manager.player_decks[Player.ATTACKER] = self.attacker_deck.copy()
        self.game_manager.player_decks[Player.DEFENDER] = self.defender_deck.copy()
        self.game_manager.on_turn_changed = self._on_turn_changed
        self.game_manager.on_card_arrived = self._on_card_arrived

        # Initialize UI components
        self.turn_ui = TurnUI(self.screen_width)
        self.battlefield = Battlefield(self.screen_width, self.screen_height)
        self.location_panel = LocationPanel(self.screen_width, self.screen_height)
        # Give location panel access to game state for movement
        self.location_panel.game_manager = self.game_manager
        self.location_panel.battlefield = self.battlefield

        # Hand managers for both players
        self.attacker_hand = HandManager(self.screen_width, self.screen_height, is_bottom=True)
        self.defender_hand = HandManager(self.screen_width, self.screen_height, is_bottom=False)

        # Deck UI - positioned for bigger size
        self.deck_ui = DeckUI(self.screen_width - 120, self.screen_height - 180)

        # Draw menu
        self.draw_menu = DrawMenu(self.screen_width, self.screen_height)

        # Reinforcement UI
        self.reinforcement_ui = ReinforcementUI(self.screen_width - 150, 80)

        # Combat log UI
        self.combat_log_ui = CombatLogUI(self.screen_width, self.screen_height)

        # Game over UI
        self.game_over_ui = GameOverUI(self.screen_width, self.screen_height)

        # Currently dragging card
        self.dragging_card: Card | None = None
        self.dragging_from_hand: HandManager | None = None

        # Give starting cards to both players
        self._setup_starting_hands()

        # Update hand positions based on current player
        self._update_hand_positions()

    def _setup_starting_hands(self):
        """Setup starting hands for both players."""
        # Each player starts with Avatar in hand
        for player, hand_mgr in [(Player.ATTACKER, self.attacker_hand),
                                  (Player.DEFENDER, self.defender_hand)]:
            avatar_info = db.get_card_info("Avatar")
            if avatar_info:
                card = Card("Avatar")
                hand_mgr.add_card(card)
                self.game_manager.add_card_to_hand("Avatar", avatar_info, player)

    def _on_turn_changed(self, turn: int, current_player: str):
        """Callback when turn changes."""
        self.turn_ui.update(turn, current_player)
        # Update battlefield visibility for current player
        self.battlefield.set_current_player(self.game_manager.current_player)
        # Swap hand positions based on current player
        self._update_hand_positions()

    def _update_hand_positions(self):
        """Update hand positions based on current player (current player's hand at bottom)."""
        if self.game_manager.current_player == Player.ATTACKER:
            # Attacker at bottom, defender at top
            self.attacker_hand.is_bottom = True
            self.defender_hand.is_bottom = False
        else:
            # Defender at bottom, attacker at top
            self.attacker_hand.is_bottom = False
            self.defender_hand.is_bottom = True

        # Recalculate positions
        self.attacker_hand.resize(self.screen_width, self.screen_height)
        self.defender_hand.resize(self.screen_width, self.screen_height)

    def _resolve_combat(self):
        """Resolve combat at all locations and sync battlefield."""
        # Run combat in game manager
        combat_results = self.game_manager.resolve_all_combat()

        # Sync battlefield visuals with game manager state
        self._sync_battlefield_from_manager()

        # Show combat log if there were battles
        if combat_results:
            self.combat_log_ui.show(combat_results)

        # Check win condition
        winner = self.game_manager.check_win_condition()
        if winner:
            winner_name = "Attacker" if winner == Player.ATTACKER else "Defender"
            self.game_over_ui.show(winner_name)

    def _sync_battlefield_from_manager(self):
        """Sync battlefield visual state with game manager state."""
        for location_name in self.game_manager.LOCATIONS:
            # Aggregate cards from all zones for visual display
            all_atk = []
            all_def = []
            for zone in ["attacker_zone", "middle_zone", "defender_zone"]:
                zone_data = self.game_manager.battlefield_cards[location_name][zone]
                all_atk.extend(zone_data["attacker"])
                all_def.extend(zone_data["defender"])

            if location_name in self.battlefield.locations:
                loc = self.battlefield.locations[location_name]
                loc.attacker_cards = all_atk
                loc.defender_cards = all_def

        # Sync capture state for area control display
        self.battlefield.sync_capture_state(self.game_manager)

    def _on_card_arrived(self, card_id: str, card_info: list, player: Player):
        """Callback when a card arrives in hand."""
        card = Card(card_id)

        if player == Player.ATTACKER:
            self.attacker_hand.add_card(card)
        else:
            self.defender_hand.add_card(card)

        self.game_manager.add_card_to_hand(card_id, card_info, player)

    def _get_current_hand(self) -> HandManager:
        """Get the hand manager for the current player."""
        if self.game_manager.current_player == Player.ATTACKER:
            return self.attacker_hand
        return self.defender_hand

    def _get_current_deck(self) -> list:
        """Get the deck for the current player."""
        return self.game_manager.get_deck(self.game_manager.current_player)

    def handle_events(self):
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.VIDEORESIZE:
                self._handle_resize(event.w, event.h)

            elif event.type == pygame.MOUSEMOTION:
                self._handle_mouse_motion(event.pos)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    # Handle menu state
                    if self.state == STATE_MENU:
                        action = self.main_menu.handle_click(event.pos)
                        if action == "start_game":
                            self._init_game()
                            self.state = STATE_GAME
                        elif action == "deck_attacker":
                            self.deck_builder.show("attacker", self.attacker_deck)
                            self.state = STATE_DECK_BUILDER
                        elif action == "deck_defender":
                            self.deck_builder.show("defender", self.defender_deck)
                            self.state = STATE_DECK_BUILDER
                        elif action == "quit":
                            self.running = False
                    elif self.state == STATE_DECK_BUILDER:
                        result = self.deck_builder.handle_click(event.pos)
                        if result == "done":
                            # Save the edited deck
                            if self.deck_builder.player_type == "attacker":
                                self.attacker_deck = self.deck_builder.get_deck()
                            else:
                                self.defender_deck = self.deck_builder.get_deck()
                            # Show the main menu again
                            self.main_menu.show()
                            self.state = STATE_MENU
                    elif self.state == STATE_GAME:
                        # Check game over first (blocks all interaction)
                        if self.game_over_ui.is_visible:
                            continue

                        # Check combat log
                        if self.combat_log_ui.is_visible:
                            if self.combat_log_ui.handle_click(event.pos):
                                # Check win condition after closing combat log
                                winner = self.game_manager.check_win_condition()
                                if winner:
                                    winner_name = "Attacker" if winner == Player.ATTACKER else "Defender"
                                    self.game_over_ui.show(winner_name)
                            continue

                        self._handle_mouse_down(event.pos)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:  # Left click
                    if self.state == STATE_GAME:
                        self._handle_mouse_up(event.pos)

            elif event.type == pygame.MOUSEWHEEL:
                # Handle mouse wheel scrolling
                if self.state == STATE_DECK_BUILDER:
                    self.deck_builder.handle_scroll(event.y)

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == STATE_MENU:
                        self.running = False
                    elif self.state == STATE_DECK_BUILDER:
                        # Go back to menu
                        if self.deck_builder.player_type == "attacker":
                            self.attacker_deck = self.deck_builder.get_deck()
                        else:
                            self.defender_deck = self.deck_builder.get_deck()
                        # Show the main menu again
                        self.main_menu.show()
                        self.state = STATE_MENU
                    elif self.state == STATE_GAME:
                        if self.game_over_ui.is_visible:
                            self.running = False
                        elif self.combat_log_ui.is_visible:
                            self.combat_log_ui.hide()
                        elif self.location_panel.is_visible:
                            self.location_panel.hide()
                        elif self.draw_menu.is_visible:
                            self.draw_menu.hide()
                        else:
                            self.running = False

    def _handle_resize(self, width: int, height: int):
        """Handle window resize."""
        self.screen_width = width
        self.screen_height = height
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)

        # Resize menu and deck builder
        self.main_menu.resize(width, height)
        self.deck_builder.resize(width, height)

        # Only resize game components if game is initialized
        if self.state == STATE_GAME:
            # Calculate and apply scale
            scale = calculate_scale(width, height)
            set_card_scale(scale)

            self.turn_ui.resize(width)
            self.battlefield.resize(width, height)
            self.location_panel.resize(width, height)
            self.attacker_hand.resize(width, height)
            self.defender_hand.resize(width, height)
            self.draw_menu.resize(width, height)
            self.combat_log_ui.resize(width, height)
            self.game_over_ui.resize(width, height)

            # Scale UI positions
            self.deck_ui.x = width - int(120 * scale)
            self.deck_ui.y = height - int(180 * scale)
            self.reinforcement_ui.x = width - int(160 * scale)

    def _handle_mouse_motion(self, pos: tuple):
        """Handle mouse motion."""
        if self.state != STATE_GAME:
            return

        self.turn_ui.handle_mouse_motion(pos)
        self.battlefield.handle_mouse_motion(pos)
        self.deck_ui.handle_mouse_motion(pos)

        # Handle hand hover only for current player
        current_hand = self._get_current_hand()
        current_hand.handle_mouse_motion(pos)

        if self.dragging_card:
            self.dragging_card.update_drag(pos)

    def _handle_mouse_down(self, pos: tuple):
        """Handle mouse button down."""
        # Check draw menu first
        if self.draw_menu.is_visible:
            result = self.draw_menu.handle_click(pos)
            if result and result != "close":
                # Draw the selected card
                player = self.game_manager.current_player
                self.game_manager.draw_card_from_deck(result, player)
            return

        # Check location panel
        if self.location_panel.is_visible:
            self.location_panel.handle_click(pos)
            return

        # Check end turn button
        if self.turn_ui.handle_click(pos):
            prev_turn = self.game_manager.current_turn
            self.game_manager.end_turn()

            # If turn number increased, both players passed - resolve combat
            if self.game_manager.current_turn > prev_turn:
                self._resolve_combat()
            return

        # Check deck click
        if self.deck_ui.contains_point(pos):
            player = self.game_manager.current_player
            if self.game_manager.can_draw_card(player):
                deck = self._get_current_deck()
                if deck:
                    self.draw_menu.show(deck)
            return

        # Check battlefield location click
        location = self.battlefield.get_location_at(pos)
        if location and not self.dragging_card:
            self.location_panel.show(location, self.game_manager.current_player)
            return

        # Check card pickup from current player's hand
        current_hand = self._get_current_hand()
        card = current_hand.handle_mouse_down(pos)
        if card:
            self.dragging_card = card
            self.dragging_from_hand = current_hand

    def _handle_mouse_up(self, pos: tuple):
        """Handle mouse button up."""
        if not self.dragging_card or not self.dragging_from_hand:
            return

        # Check if dropped on a battlefield location
        location = self.battlefield.get_location_at(pos)
        card_placed = False

        if location:
            player = self.game_manager.current_player

            # Check if placement is valid
            if location.can_place(player):
                # Get card info
                card_info = db.get_card_info(self.dragging_card.card_id)

                if card_info:
                    # Place on battlefield
                    card_data = {
                        "card_id": self.dragging_card.card_id,
                        "card_info": card_info
                    }

                    self.battlefield.place_card(location.name, card_data, player)
                    self.game_manager.place_card_on_battlefield(
                        location.name, self.dragging_card.card_id,
                        card_info, player
                    )

                    # Remove from hand (this also clears dragging state)
                    self.dragging_from_hand.remove_card(self.dragging_card)
                    self.game_manager.remove_card_from_hand(
                        self.dragging_card.card_id, player
                    )
                    card_placed = True

        # End dragging state on the card
        self.dragging_card.end_drag()

        # Clear hand manager's dragging state
        self.dragging_from_hand.dragging_card = None

        # Return card to hand position if not placed
        if not card_placed:
            self.dragging_card.return_to_hand()

        self.dragging_card = None
        self.dragging_from_hand = None

    def update(self, dt: float):
        """Update game state."""
        if self.state == STATE_MENU:
            self.main_menu.update(dt)
        elif self.state == STATE_DECK_BUILDER:
            self.deck_builder.update(dt)
        elif self.state == STATE_GAME:
            self.turn_ui.update_animation(dt)
            self.attacker_hand.update(dt)
            self.defender_hand.update(dt)

            # Update reinforcement UI
            player = self.game_manager.current_player
            reinforcements = self.game_manager.get_hand_reinforcements(player)
            self.reinforcement_ui.update(reinforcements)

            # Sync battlefield state (including capture progress)
            self._sync_battlefield_from_manager()

    def draw(self):
        """Draw the game."""
        self.screen.fill(BG_COLOR)

        if self.state == STATE_MENU:
            # Draw main menu
            self.main_menu.draw(self.screen)
        elif self.state == STATE_DECK_BUILDER:
            # Draw deck builder
            self.deck_builder.draw(self.screen)
        elif self.state == STATE_GAME:
            # Draw battlefield
            self.battlefield.draw(self.screen)

            # Draw both hands (opponent hand shown face-down)
            if self.game_manager.current_player == Player.ATTACKER:
                # Draw defender hand (opponent) - face down
                self.defender_hand.draw(self.screen, face_down=True)
                # Draw attacker hand (current player) - face up
                self.attacker_hand.draw(self.screen, face_down=False)
            else:
                # Draw attacker hand (opponent) - face down
                self.attacker_hand.draw(self.screen, face_down=True)
                # Draw defender hand (current player) - face up
                self.defender_hand.draw(self.screen, face_down=False)

            # Draw UI
            self.turn_ui.draw(self.screen)
            player = self.game_manager.current_player
            can_draw = self.game_manager.can_draw_card(player)
            self.deck_ui.draw(self.screen, len(self._get_current_deck()), can_draw)
            self.reinforcement_ui.draw(self.screen)

            # Draw location panel (on top)
            self.location_panel.draw(self.screen)

            # Draw draw menu (on top)
            self.draw_menu.draw(self.screen)

            # Draw combat log (on top of everything else)
            self.combat_log_ui.draw(self.screen)

            # Draw game over (very top)
            self.game_over_ui.draw(self.screen)

            # Draw help text
            self._draw_help()

        pygame.display.flip()

    def _draw_help(self):
        """Draw help text."""
        font = pygame.font.Font(None, 18)
        help_text = [
            "Click DECK to draw cards | Drag cards to battlefield locations",
            "Click locations to see placed cards | ESC to close panels/quit"
        ]

        for i, text in enumerate(help_text):
            surface = font.render(text, True, (120, 120, 120))
            self.screen.blit(surface, (10, self.screen_height - 35 + i * 16))

    def run(self):
        """Main game loop."""
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0

            self.handle_events()
            self.update(dt)
            self.draw()

        self.audio_manager.cleanup()
        pygame.quit()
        sys.exit()


def main():
    """Entry point."""
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
