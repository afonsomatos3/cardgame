"""UI components for the game."""

import pygame


class Button:
    """A simple clickable button."""

    def __init__(self, x: int, y: int, width: int, height: int,
                 text: str, color: tuple = (70, 130, 180),
                 text_color: tuple = (255, 255, 255)):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.text = text
        self.color = color
        self.hover_color = tuple(min(c + 30, 255) for c in color)
        self.text_color = text_color
        self.is_hovered = False
        self.font = pygame.font.Font(None, 24)

    def get_rect(self) -> pygame.Rect:
        """Get button rectangle."""
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def contains_point(self, pos: tuple) -> bool:
        """Check if point is inside button."""
        return self.get_rect().collidepoint(pos)

    def draw(self, screen: pygame.Surface):
        """Draw the button."""
        color = self.hover_color if self.is_hovered else self.color
        rect = self.get_rect()

        pygame.draw.rect(screen, color, rect, border_radius=8)
        pygame.draw.rect(screen, (50, 50, 50), rect, 2, border_radius=8)

        text_surface = self.font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(center=rect.center)
        screen.blit(text_surface, text_rect)

    def handle_mouse_motion(self, pos: tuple):
        """Handle mouse motion for hover effect."""
        self.is_hovered = self.contains_point(pos)


class TurnUI:
    """UI for displaying turn information."""

    def __init__(self, screen_width: int):
        self.screen_width = screen_width
        self.font = pygame.font.Font(None, 28)
        self.small_font = pygame.font.Font(None, 22)
        self.turn = 1
        self.current_player = "Attacker"

        # End turn button
        self.end_turn_button = Button(
            screen_width - 120, 10, 110, 35,
            "End Phase", (150, 80, 80)
        )

    def update(self, turn: int, current_player: str):
        """Update turn info."""
        self.turn = turn
        self.current_player = current_player

    def draw(self, screen: pygame.Surface):
        """Draw the turn UI."""
        # Background panel
        panel_rect = pygame.Rect(10, 10, 200, 60)
        pygame.draw.rect(screen, (40, 40, 40, 200), panel_rect, border_radius=8)
        pygame.draw.rect(screen, (80, 80, 80), panel_rect, 2, border_radius=8)

        # Turn number
        turn_text = self.font.render(f"Turn: {self.turn}", True, (255, 255, 255))
        screen.blit(turn_text, (20, 18))

        # Current player
        player_color = (255, 100, 100) if self.current_player == "Attacker" else (100, 150, 255)
        player_text = self.small_font.render(f"Phase: {self.current_player}", True, player_color)
        screen.blit(player_text, (20, 42))

        # Draw end turn button
        self.end_turn_button.draw(screen)

    def handle_mouse_motion(self, pos: tuple):
        """Handle mouse motion."""
        self.end_turn_button.handle_mouse_motion(pos)

    def handle_click(self, pos: tuple) -> bool:
        """Handle click, returns True if end turn button was clicked."""
        return self.end_turn_button.contains_point(pos)

    def resize(self, screen_width: int):
        """Handle screen resize."""
        self.screen_width = screen_width
        self.end_turn_button.x = screen_width - 120


class DeckUI:
    """UI for the draw deck."""

    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
        self.width = 80
        self.height = 110
        self.is_hovered = False
        self.font = pygame.font.Font(None, 20)

    def get_rect(self) -> pygame.Rect:
        """Get deck rectangle."""
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def contains_point(self, pos: tuple) -> bool:
        """Check if point is inside deck."""
        return self.get_rect().collidepoint(pos)

    def draw(self, screen: pygame.Surface, cards_remaining: int, can_draw: bool = True):
        """Draw the deck."""
        rect = self.get_rect()

        # Draw stacked card effect (grayed out if can't draw)
        for i in range(min(3, cards_remaining)):
            offset = i * 2
            card_rect = pygame.Rect(self.x + offset, self.y - offset,
                                   self.width, self.height)
            if can_draw:
                pygame.draw.rect(screen, (80, 60, 40), card_rect, border_radius=5)
                pygame.draw.rect(screen, (60, 40, 20), card_rect, 2, border_radius=5)
            else:
                pygame.draw.rect(screen, (50, 50, 50), card_rect, border_radius=5)
                pygame.draw.rect(screen, (40, 40, 40), card_rect, 2, border_radius=5)

        # Highlight if hovered and can draw
        if self.is_hovered and cards_remaining > 0 and can_draw:
            pygame.draw.rect(screen, (255, 255, 100), rect, 3, border_radius=5)

        # Card count
        text_color = (200, 200, 200) if can_draw else (100, 100, 100)
        count_text = self.font.render(f"{cards_remaining}", True, text_color)
        count_rect = count_text.get_rect(center=(self.x + self.width // 2,
                                                  self.y + self.height // 2))
        screen.blit(count_text, count_rect)

        # Label
        label_color = (150, 150, 150) if can_draw else (80, 80, 80)
        label = self.font.render("DECK", True, label_color)
        label_rect = label.get_rect(center=(self.x + self.width // 2,
                                            self.y + self.height + 15))
        screen.blit(label, label_rect)

        # Show "Already drew" message if can't draw
        if not can_draw and cards_remaining > 0:
            msg = self.font.render("(1/turn)", True, (150, 100, 100))
            msg_rect = msg.get_rect(center=(self.x + self.width // 2,
                                            self.y + self.height + 30))
            screen.blit(msg, msg_rect)

    def handle_mouse_motion(self, pos: tuple):
        """Handle mouse motion."""
        self.is_hovered = self.contains_point(pos)


class DrawMenu:
    """Menu for selecting cards to draw from deck."""

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.is_visible = False
        self.available_cards: list[str] = []
        self.card_buttons: list[tuple[pygame.Rect, str]] = []
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 20)

        self.width = 350
        self.height = 400
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2

    def show(self, available_cards: list[str]):
        """Show the draw menu with available cards."""
        self.available_cards = available_cards
        self.is_visible = True
        self._create_buttons()

    def hide(self):
        """Hide the menu."""
        self.is_visible = False

    def _create_buttons(self):
        """Create buttons for each card."""
        self.card_buttons = []
        button_height = 40
        spacing = 5
        start_y = self.y + 50

        for i, card_id in enumerate(self.available_cards):
            rect = pygame.Rect(self.x + 20, start_y + i * (button_height + spacing),
                              self.width - 40, button_height)
            self.card_buttons.append((rect, card_id))

    def draw(self, screen: pygame.Surface):
        """Draw the menu."""
        if not self.is_visible:
            return

        # Overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, 0))

        # Panel
        panel_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(screen, (50, 50, 50), panel_rect, border_radius=10)
        pygame.draw.rect(screen, (100, 100, 100), panel_rect, 3, border_radius=10)

        # Title
        title = self.font.render("Select Card to Draw", True, (255, 255, 255))
        title_rect = title.get_rect(center=(self.x + self.width // 2, self.y + 25))
        screen.blit(title, title_rect)

        # Close button
        close_rect = pygame.Rect(self.x + self.width - 30, self.y + 5, 25, 25)
        pygame.draw.rect(screen, (150, 50, 50), close_rect, border_radius=5)
        close_text = self.font.render("X", True, (255, 255, 255))
        close_text_rect = close_text.get_rect(center=close_rect.center)
        screen.blit(close_text, close_text_rect)

        # Card buttons
        mouse_pos = pygame.mouse.get_pos()
        for rect, card_id in self.card_buttons:
            is_hovered = rect.collidepoint(mouse_pos)
            color = (80, 80, 80) if is_hovered else (60, 60, 60)

            pygame.draw.rect(screen, color, rect, border_radius=5)
            pygame.draw.rect(screen, (100, 100, 100), rect, 1, border_radius=5)

            # Card name
            import cards_database as db
            info = db.get_card_info(card_id)
            name = info[db.IDX_NAME] if info else card_id
            cost = info[db.IDX_COST] if info else 0

            name_text = self.font.render(name, True, (255, 255, 255))
            screen.blit(name_text, (rect.x + 10, rect.y + 5))

            cost_text = self.small_font.render(f"Cost: {cost} turns", True, (150, 200, 255))
            screen.blit(cost_text, (rect.x + 10, rect.y + 22))

        if not self.card_buttons:
            empty_text = self.font.render("Deck is empty!", True, (200, 150, 150))
            empty_rect = empty_text.get_rect(center=(self.x + self.width // 2,
                                                     self.y + self.height // 2))
            screen.blit(empty_text, empty_rect)

    def handle_click(self, pos: tuple) -> str | None:
        """Handle click, returns card_id if a card was selected, 'close' if closed."""
        if not self.is_visible:
            return None

        # Close button
        close_rect = pygame.Rect(self.x + self.width - 30, self.y + 5, 25, 25)
        if close_rect.collidepoint(pos):
            self.hide()
            return "close"

        # Card buttons
        for rect, card_id in self.card_buttons:
            if rect.collidepoint(pos):
                self.hide()
                return card_id

        # Click outside
        panel_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        if not panel_rect.collidepoint(pos):
            self.hide()
            return "close"

        return None

    def resize(self, screen_width: int, screen_height: int):
        """Handle screen resize."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2
        if self.is_visible:
            self._create_buttons()


class ReinforcementUI:
    """UI for showing incoming reinforcement cards."""

    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
        self.font = pygame.font.Font(None, 20)
        self.reinforcements: list[dict] = []

    def update(self, reinforcements: list[dict]):
        """Update the reinforcement list."""
        self.reinforcements = reinforcements

    def draw(self, screen: pygame.Surface):
        """Draw the reinforcement queue."""
        if not self.reinforcements:
            return

        # Title
        title = self.font.render("Incoming:", True, (200, 200, 200))
        screen.blit(title, (self.x, self.y))

        # List cards
        for i, entry in enumerate(self.reinforcements[:5]):  # Show max 5
            card_id = entry.get("card_id", "?")
            turns = entry.get("turns_remaining", 0)
            text = self.font.render(f"  {card_id}: {turns}t", True, (150, 200, 150))
            screen.blit(text, (self.x, self.y + 18 + i * 16))
