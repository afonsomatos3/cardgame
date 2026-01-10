"""WarMasterMind - A card game implemented in Pygame."""

import pygame
import sys

from game_manager import GameManager, Player
from card import Card
from hand_manager import HandManager
from battlefield import Battlefield, LocationPanel
from ui import TurnUI, DeckUI, DrawMenu, ReinforcementUI
import cards_database as db


# Screen settings
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

# Colors
BG_COLOR = (30, 35, 40)


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

        # Initialize game manager
        self.game_manager = GameManager()
        self.game_manager.on_turn_changed = self._on_turn_changed
        self.game_manager.on_card_arrived = self._on_card_arrived

        # Initialize UI components
        self.turn_ui = TurnUI(self.screen_width)
        self.battlefield = Battlefield(self.screen_width, self.screen_height)
        self.location_panel = LocationPanel(self.screen_width, self.screen_height)

        # Hand managers for both players
        self.attacker_hand = HandManager(self.screen_width, self.screen_height, is_bottom=True)
        self.defender_hand = HandManager(self.screen_width, self.screen_height, is_bottom=False)

        # Deck UI
        self.deck_ui = DeckUI(self.screen_width - 100, self.screen_height - 150)

        # Draw menu
        self.draw_menu = DrawMenu(self.screen_width, self.screen_height)

        # Reinforcement UI
        self.reinforcement_ui = ReinforcementUI(self.screen_width - 150, 80)

        # Currently dragging card
        self.dragging_card: Card | None = None
        self.dragging_from_hand: HandManager | None = None

        # Give starting cards to both players
        self._setup_starting_hands()

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
                    self._handle_mouse_down(event.pos)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:  # Left click
                    self._handle_mouse_up(event.pos)

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.location_panel.is_visible:
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

        self.turn_ui.resize(width)
        self.battlefield.resize(width, height)
        self.location_panel.resize(width, height)
        self.attacker_hand.resize(width, height)
        self.defender_hand.resize(width, height)
        self.draw_menu.resize(width, height)
        self.deck_ui.x = width - 100
        self.deck_ui.y = height - 150
        self.reinforcement_ui.x = width - 150

    def _handle_mouse_motion(self, pos: tuple):
        """Handle mouse motion."""
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
            self.game_manager.end_turn()
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
        self.attacker_hand.update(dt)
        self.defender_hand.update(dt)

        # Update reinforcement UI
        player = self.game_manager.current_player
        reinforcements = self.game_manager.get_hand_reinforcements(player)
        self.reinforcement_ui.update(reinforcements)

    def draw(self):
        """Draw the game."""
        self.screen.fill(BG_COLOR)

        # Draw battlefield
        self.battlefield.draw(self.screen)

        # Draw both hands (opponent hand shown smaller/hidden)
        if self.game_manager.current_player == Player.ATTACKER:
            # Draw defender hand (opponent) - could be hidden in future
            self.defender_hand.draw(self.screen)
            # Draw attacker hand (current player)
            self.attacker_hand.draw(self.screen)
        else:
            self.attacker_hand.draw(self.screen)
            self.defender_hand.draw(self.screen)

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

        pygame.quit()
        sys.exit()


def main():
    """Entry point."""
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
