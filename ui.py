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
        self.font = pygame.font.Font(None, 28)

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
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 28)
        self.turn = 1
        self.current_player = "Attacker"

        # End turn button - bigger
        self.end_turn_button = Button(
            screen_width - 150, 10, 140, 45,
            "End Phase", (150, 80, 80)
        )

    def update(self, turn: int, current_player: str):
        """Update turn info."""
        self.turn = turn
        self.current_player = current_player

    def draw(self, screen: pygame.Surface):
        """Draw the turn UI."""
        # Background panel - bigger
        panel_rect = pygame.Rect(10, 10, 250, 75)
        pygame.draw.rect(screen, (40, 40, 40, 200), panel_rect, border_radius=10)
        pygame.draw.rect(screen, (80, 80, 80), panel_rect, 2, border_radius=10)

        # Turn number
        turn_text = self.font.render(f"Turn: {self.turn}", True, (255, 255, 255))
        screen.blit(turn_text, (20, 15))

        # Current player
        player_color = (255, 100, 100) if self.current_player == "Attacker" else (100, 150, 255)
        player_text = self.small_font.render(f"Phase: {self.current_player}", True, player_color)
        screen.blit(player_text, (20, 48))

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
        self.end_turn_button.x = screen_width - 150


class DeckUI:
    """UI for the draw deck."""

    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
        self.width = 100
        self.height = 140
        self.is_hovered = False
        self.font = pygame.font.Font(None, 26)

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


class CombatLogUI:
    """UI for displaying combat results with card images."""

    # Mini card size for combat display
    CARD_WIDTH = 60
    CARD_HEIGHT = 84

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.is_visible = False
        self.combat_results = []
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 20)
        self.title_font = pygame.font.Font(None, 36)

        self.width = 600
        self.height = 500
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2

        # Card image cache
        self._card_cache: dict[str, pygame.Surface] = {}

    def _get_mini_card(self, card_id: str) -> pygame.Surface:
        """Get or create a mini card image."""
        if card_id in self._card_cache:
            return self._card_cache[card_id]

        import os
        import cards_database as db

        surf = pygame.Surface((self.CARD_WIDTH, self.CARD_HEIGHT), pygame.SRCALPHA)

        # Card background
        pygame.draw.rect(surf, (240, 230, 210),
                        (0, 0, self.CARD_WIDTH, self.CARD_HEIGHT), border_radius=4)
        pygame.draw.rect(surf, (139, 90, 43),
                        (0, 0, self.CARD_WIDTH, self.CARD_HEIGHT), 2, border_radius=4)

        # Try to load unit image
        unit_path = os.path.join("resources", "Units", f"{card_id}.png")
        if not os.path.exists(unit_path):
            unit_path = os.path.join("resources", "Units", f"{card_id}.jpg")

        if os.path.exists(unit_path):
            try:
                unit_img = pygame.image.load(unit_path).convert_alpha()
                img_rect = unit_img.get_rect()
                scale = min(
                    (self.CARD_WIDTH - 6) / img_rect.width,
                    (self.CARD_HEIGHT - 30) / img_rect.height
                )
                new_size = (int(img_rect.width * scale), int(img_rect.height * scale))
                unit_img = pygame.transform.smoothscale(unit_img, new_size)
                img_x = (self.CARD_WIDTH - new_size[0]) // 2
                surf.blit(unit_img, (img_x, 14))
            except pygame.error:
                pass

        # Card info
        card_info = db.get_card_info(card_id)
        if card_info:
            tiny_font = pygame.font.Font(None, 12)
            name = card_info[db.IDX_NAME][:8]
            attack = card_info[db.IDX_ATTACK]
            health = card_info[db.IDX_HEALTH]

            # Name at top
            name_text = tiny_font.render(name, True, (50, 40, 30))
            name_rect = name_text.get_rect(centerx=self.CARD_WIDTH // 2, top=2)
            surf.blit(name_text, name_rect)

            # Stats at bottom
            stats_y = self.CARD_HEIGHT - 10
            pygame.draw.circle(surf, (200, 60, 60), (10, stats_y), 7)
            atk_text = tiny_font.render(str(attack), True, (255, 255, 255))
            surf.blit(atk_text, atk_text.get_rect(center=(10, stats_y)))

            pygame.draw.circle(surf, (60, 160, 60), (self.CARD_WIDTH - 10, stats_y), 7)
            hp_text = tiny_font.render(str(health), True, (255, 255, 255))
            surf.blit(hp_text, hp_text.get_rect(center=(self.CARD_WIDTH - 10, stats_y)))

        self._card_cache[card_id] = surf
        return surf

    def show(self, combat_results: list):
        """Show combat results."""
        self.combat_results = combat_results
        self.is_visible = True

    def hide(self):
        """Hide the panel."""
        self.is_visible = False

    def draw(self, screen: pygame.Surface):
        """Draw the combat log with card images."""
        if not self.is_visible:
            return

        # Overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        # Panel
        panel_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(screen, (40, 35, 35), panel_rect, border_radius=10)
        pygame.draw.rect(screen, (150, 80, 80), panel_rect, 3, border_radius=10)

        # Title
        title = self.title_font.render("COMBAT PHASE", True, (255, 200, 100))
        title_rect = title.get_rect(center=(self.x + self.width // 2, self.y + 28))
        screen.blit(title, title_rect)

        # Continue button
        continue_rect = pygame.Rect(self.x + self.width // 2 - 70, self.y + self.height - 50,
                                    140, 40)
        mouse_pos = pygame.mouse.get_pos()
        btn_color = (100, 150, 100) if continue_rect.collidepoint(mouse_pos) else (70, 120, 70)
        pygame.draw.rect(screen, btn_color, continue_rect, border_radius=6)
        pygame.draw.rect(screen, (100, 180, 100), continue_rect, 2, border_radius=6)
        continue_text = self.font.render("Continue", True, (255, 255, 255))
        screen.blit(continue_text, continue_text.get_rect(center=continue_rect.center))

        # Combat results
        if not self.combat_results:
            no_combat = self.font.render("No combat occurred this turn.", True, (150, 150, 150))
            screen.blit(no_combat, no_combat.get_rect(center=(self.x + self.width // 2, self.y + 150)))
            return

        y_offset = self.y + 55
        for result in self.combat_results:
            # Location header
            loc_text = self.font.render(f"Battle at {result.location}", True, (255, 200, 100))
            screen.blit(loc_text, (self.x + 20, y_offset))
            y_offset += 28

            # Draw attacks as card vs card with arrows
            attacks_shown = 0
            for attack in result.attacks:
                if attacks_shown >= 3:  # Limit to 3 attacks per location
                    more = self.small_font.render(f"  +{len(result.attacks) - 3} more attacks...", True, (150, 150, 150))
                    screen.blit(more, (self.x + 30, y_offset))
                    y_offset += 20
                    break

                # Get card images
                attacker_card = self._get_mini_card(attack["attacker_card"])
                defender_card = self._get_mini_card(attack["defender_card"])

                # Position cards
                card_y = y_offset
                attacker_x = self.x + 50
                defender_x = self.x + 220

                # Draw attacker card
                screen.blit(attacker_card, (attacker_x, card_y))

                # Draw arrow with damage
                arrow_start = (attacker_x + self.CARD_WIDTH + 5, card_y + self.CARD_HEIGHT // 2)
                arrow_end = (defender_x - 5, card_y + self.CARD_HEIGHT // 2)
                side_color = (255, 100, 100) if attack["attacker_side"] == "attacker" else (100, 150, 255)

                pygame.draw.line(screen, side_color, arrow_start, arrow_end, 3)
                # Arrow head
                pygame.draw.polygon(screen, side_color, [
                    arrow_end,
                    (arrow_end[0] - 8, arrow_end[1] - 5),
                    (arrow_end[0] - 8, arrow_end[1] + 5)
                ])

                # Damage text
                dmg_text = self.small_font.render(f"{attack['damage']} dmg", True, (255, 255, 150))
                dmg_rect = dmg_text.get_rect(center=((arrow_start[0] + arrow_end[0]) // 2, arrow_start[1] - 12))
                screen.blit(dmg_text, dmg_rect)

                # Draw defender card
                screen.blit(defender_card, (defender_x, card_y))

                # Casualties indicator
                casualty_x = defender_x + self.CARD_WIDTH + 15
                if attack["attacker_card"] in result.attacker_casualties:
                    skull = self.small_font.render("DEAD", True, (255, 100, 100))
                    screen.blit(skull, (attacker_x, card_y + self.CARD_HEIGHT + 2))
                if attack["defender_card"] in result.defender_casualties:
                    skull = self.small_font.render("DEAD", True, (255, 100, 100))
                    screen.blit(skull, (defender_x, card_y + self.CARD_HEIGHT + 2))

                y_offset += self.CARD_HEIGHT + 25
                attacks_shown += 1

            # Outcome
            if result.attacker_won:
                outcome = self.font.render("Attacker wins!", True, (255, 150, 100))
                screen.blit(outcome, (self.x + 350, y_offset - self.CARD_HEIGHT - 10))
            elif result.defender_won:
                outcome = self.font.render("Defender holds!", True, (100, 150, 255))
                screen.blit(outcome, (self.x + 350, y_offset - self.CARD_HEIGHT - 10))

            y_offset += 15

            # Don't overflow
            if y_offset > self.y + self.height - 100:
                more_text = self.small_font.render("... more battles not shown", True, (150, 150, 150))
                screen.blit(more_text, (self.x + 20, y_offset))
                break

    def handle_click(self, pos: tuple) -> bool:
        """Handle click. Returns True if panel should close."""
        if not self.is_visible:
            return False

        # Continue button
        continue_rect = pygame.Rect(self.x + self.width // 2 - 70, self.y + self.height - 50,
                                    140, 40)
        if continue_rect.collidepoint(pos):
            self.hide()
            return True

        return False

    def resize(self, screen_width: int, screen_height: int):
        """Handle resize."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2


class GameOverUI:
    """UI for displaying game over screen."""

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.is_visible = False
        self.winner = None
        self.font = pygame.font.Font(None, 48)
        self.small_font = pygame.font.Font(None, 24)

    def show(self, winner: str):
        """Show game over with winner."""
        self.winner = winner
        self.is_visible = True

    def hide(self):
        """Hide the panel."""
        self.is_visible = False

    def draw(self, screen: pygame.Surface):
        """Draw the game over screen."""
        if not self.is_visible:
            return

        # Full overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 220))
        screen.blit(overlay, (0, 0))

        # Winner text
        if self.winner == "Attacker":
            text = "ATTACKER WINS!"
            color = (255, 100, 100)
        else:
            text = "DEFENDER WINS!"
            color = (100, 150, 255)

        winner_text = self.font.render(text, True, color)
        winner_rect = winner_text.get_rect(center=(self.screen_width // 2, self.screen_height // 2 - 30))
        screen.blit(winner_text, winner_rect)

        # Subtitle
        subtitle = self.small_font.render("The enemy Avatar has been destroyed!", True, (200, 200, 200))
        subtitle_rect = subtitle.get_rect(center=(self.screen_width // 2, self.screen_height // 2 + 20))
        screen.blit(subtitle, subtitle_rect)

        # Restart hint
        hint = self.small_font.render("Press ESC to quit or close the window", True, (150, 150, 150))
        hint_rect = hint.get_rect(center=(self.screen_width // 2, self.screen_height // 2 + 60))
        screen.blit(hint, hint_rect)

    def resize(self, screen_width: int, screen_height: int):
        """Handle resize."""
        self.screen_width = screen_width
        self.screen_height = screen_height
