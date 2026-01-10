"""Main menu and deck builder for WarMasterMind."""

import pygame
import os
import cards_database as db


class MainMenu:
    """Main menu screen."""

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.is_visible = True

        self.title_font = pygame.font.Font(None, 72)
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)

        # Buttons
        self.buttons = []
        self._create_buttons()

        # Result when menu closes
        self.result = None  # "start_game", "deck_attacker", "deck_defender", "quit"

    def _create_buttons(self):
        """Create menu buttons."""
        btn_width = 280
        btn_height = 55
        center_x = self.screen_width // 2 - btn_width // 2
        start_y = self.screen_height // 2 - 50

        self.buttons = [
            {"rect": pygame.Rect(center_x, start_y, btn_width, btn_height),
             "text": "Start Game", "action": "start_game", "color": (70, 130, 70)},
            {"rect": pygame.Rect(center_x, start_y + 70, btn_width, btn_height),
             "text": "Edit Attacker Deck", "action": "deck_attacker", "color": (150, 80, 80)},
            {"rect": pygame.Rect(center_x, start_y + 140, btn_width, btn_height),
             "text": "Edit Defender Deck", "action": "deck_defender", "color": (80, 80, 150)},
            {"rect": pygame.Rect(center_x, start_y + 210, btn_width, btn_height),
             "text": "Quit", "action": "quit", "color": (100, 100, 100)},
        ]

    def show(self):
        """Show the menu."""
        self.is_visible = True
        self.result = None

    def hide(self):
        """Hide the menu."""
        self.is_visible = False

    def draw(self, screen: pygame.Surface):
        """Draw the main menu."""
        if not self.is_visible:
            return

        # Background
        screen.fill((30, 35, 40))

        # Title
        title = self.title_font.render("WarMasterMind", True, (255, 200, 100))
        title_rect = title.get_rect(center=(self.screen_width // 2, 120))
        screen.blit(title, title_rect)

        # Subtitle
        subtitle = self.small_font.render("A Strategic Card Battle Game", True, (150, 150, 150))
        sub_rect = subtitle.get_rect(center=(self.screen_width // 2, 170))
        screen.blit(subtitle, sub_rect)

        # Buttons
        mouse_pos = pygame.mouse.get_pos()
        for btn in self.buttons:
            rect = btn["rect"]
            is_hovered = rect.collidepoint(mouse_pos)

            # Button color
            color = btn["color"]
            if is_hovered:
                color = tuple(min(c + 40, 255) for c in color)

            pygame.draw.rect(screen, color, rect, border_radius=10)
            pygame.draw.rect(screen, (200, 200, 200) if is_hovered else (100, 100, 100),
                           rect, 2, border_radius=10)

            # Button text
            text = self.font.render(btn["text"], True, (255, 255, 255))
            text_rect = text.get_rect(center=rect.center)
            screen.blit(text, text_rect)

        # Instructions
        inst = self.small_font.render("Click to select an option", True, (100, 100, 100))
        inst_rect = inst.get_rect(center=(self.screen_width // 2, self.screen_height - 50))
        screen.blit(inst, inst_rect)

    def handle_click(self, pos: tuple) -> str | None:
        """Handle click. Returns action if a button was clicked."""
        if not self.is_visible:
            return None

        for btn in self.buttons:
            if btn["rect"].collidepoint(pos):
                self.result = btn["action"]
                if btn["action"] != "quit":
                    self.hide()
                return btn["action"]

        return None

    def resize(self, screen_width: int, screen_height: int):
        """Handle resize."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._create_buttons()


class DeckBuilder:
    """Deck builder screen for customizing player decks."""

    CARD_WIDTH = 100
    CARD_HEIGHT = 140

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.is_visible = False
        self.player_type = "attacker"  # or "defender"

        self.title_font = pygame.font.Font(None, 48)
        self.font = pygame.font.Font(None, 28)
        self.small_font = pygame.font.Font(None, 20)

        # All available cards (except Avatar which is always in hand)
        self.all_cards = [cid for cid in db.CARDS_DATA.keys() if cid != "Avatar"]

        # Current deck
        self.deck: list[str] = []

        # Default decks
        self.default_attacker_deck = ["Footman", "Footman", "Archer", "Eagle", "Knight"]
        self.default_defender_deck = ["Footman", "Footman", "Knight", "War_Hound", "Guardian"]

        # Card image cache
        self._card_cache: dict[str, pygame.Surface] = {}

        # Scroll offset for card list
        self.scroll_offset = 0

    def _get_card_image(self, card_id: str) -> pygame.Surface:
        """Get or create a card image."""
        if card_id in self._card_cache:
            return self._card_cache[card_id]

        surf = pygame.Surface((self.CARD_WIDTH, self.CARD_HEIGHT), pygame.SRCALPHA)

        # Card background
        pygame.draw.rect(surf, (240, 230, 210),
                        (0, 0, self.CARD_WIDTH, self.CARD_HEIGHT), border_radius=6)
        pygame.draw.rect(surf, (139, 90, 43),
                        (0, 0, self.CARD_WIDTH, self.CARD_HEIGHT), 2, border_radius=6)

        # Try to load unit image
        unit_path = os.path.join("resources", "Units", f"{card_id}.png")
        if not os.path.exists(unit_path):
            unit_path = os.path.join("resources", "Units", f"{card_id}.jpg")

        if os.path.exists(unit_path):
            try:
                unit_img = pygame.image.load(unit_path).convert_alpha()
                img_rect = unit_img.get_rect()
                scale = min(
                    (self.CARD_WIDTH - 10) / img_rect.width,
                    (self.CARD_HEIGHT - 50) / img_rect.height
                )
                new_size = (int(img_rect.width * scale), int(img_rect.height * scale))
                unit_img = pygame.transform.smoothscale(unit_img, new_size)
                img_x = (self.CARD_WIDTH - new_size[0]) // 2
                surf.blit(unit_img, (img_x, 20))
            except pygame.error:
                pass

        # Card info
        card_info = db.get_card_info(card_id)
        if card_info:
            name = card_info[db.IDX_NAME]
            attack = card_info[db.IDX_ATTACK]
            health = card_info[db.IDX_HEALTH]
            cost = card_info[db.IDX_COST]

            # Name at top
            name_text = self.small_font.render(name[:12], True, (50, 40, 30))
            name_rect = name_text.get_rect(centerx=self.CARD_WIDTH // 2, top=3)
            surf.blit(name_text, name_rect)

            # Cost circle
            pygame.draw.circle(surf, (70, 130, 180), (15, 15), 11)
            cost_text = self.small_font.render(str(cost), True, (255, 255, 255))
            surf.blit(cost_text, cost_text.get_rect(center=(15, 15)))

            # Stats at bottom
            stats_y = self.CARD_HEIGHT - 15
            pygame.draw.circle(surf, (200, 60, 60), (15, stats_y), 10)
            atk_text = self.small_font.render(str(attack), True, (255, 255, 255))
            surf.blit(atk_text, atk_text.get_rect(center=(15, stats_y)))

            pygame.draw.circle(surf, (60, 160, 60), (self.CARD_WIDTH - 15, stats_y), 10)
            hp_text = self.small_font.render(str(health), True, (255, 255, 255))
            surf.blit(hp_text, hp_text.get_rect(center=(self.CARD_WIDTH - 15, stats_y)))

        self._card_cache[card_id] = surf
        return surf

    def show(self, player_type: str, current_deck: list[str]):
        """Show the deck builder."""
        self.player_type = player_type
        self.deck = current_deck.copy()
        self.is_visible = True
        self.scroll_offset = 0

    def hide(self):
        """Hide the deck builder."""
        self.is_visible = False

    def get_deck(self) -> list[str]:
        """Get the current deck."""
        return self.deck.copy()

    def draw(self, screen: pygame.Surface):
        """Draw the deck builder."""
        if not self.is_visible:
            return

        # Background
        screen.fill((30, 35, 40))

        # Title
        player_name = "Attacker" if self.player_type == "attacker" else "Defender"
        title_color = (255, 100, 100) if self.player_type == "attacker" else (100, 150, 255)
        title = self.title_font.render(f"{player_name} Deck Builder", True, title_color)
        title_rect = title.get_rect(center=(self.screen_width // 2, 40))
        screen.blit(title, title_rect)

        # Available cards section (left side)
        avail_label = self.font.render("Available Cards (click to add):", True, (200, 200, 200))
        screen.blit(avail_label, (30, 80))

        # Draw available cards
        cards_per_row = 4
        start_x = 30
        start_y = 115
        spacing = 15

        for i, card_id in enumerate(self.all_cards):
            row = i // cards_per_row
            col = i % cards_per_row
            x = start_x + col * (self.CARD_WIDTH + spacing)
            y = start_y + row * (self.CARD_HEIGHT + spacing + 20)

            card_img = self._get_card_image(card_id)
            screen.blit(card_img, (x, y))

            # Show count in deck
            count = self.deck.count(card_id)
            if count > 0:
                count_text = self.font.render(f"x{count}", True, (100, 255, 100))
                screen.blit(count_text, (x + self.CARD_WIDTH - 25, y + self.CARD_HEIGHT + 2))

        # Current deck section (right side)
        deck_x = self.screen_width - 280
        deck_label = self.font.render(f"Your Deck ({len(self.deck)} cards):", True, (200, 200, 200))
        screen.blit(deck_label, (deck_x, 80))

        # Draw deck cards (smaller, in a list)
        for i, card_id in enumerate(self.deck[:10]):  # Show first 10
            y = 115 + i * 35
            card_info = db.get_card_info(card_id)
            name = card_info[db.IDX_NAME] if card_info else card_id

            # Card entry background
            entry_rect = pygame.Rect(deck_x, y, 240, 30)
            pygame.draw.rect(screen, (50, 50, 55), entry_rect, border_radius=5)

            # Card name
            name_text = self.small_font.render(name, True, (255, 255, 255))
            screen.blit(name_text, (deck_x + 10, y + 6))

            # Remove button
            remove_rect = pygame.Rect(deck_x + 200, y + 3, 35, 24)
            pygame.draw.rect(screen, (150, 60, 60), remove_rect, border_radius=4)
            remove_text = self.small_font.render("X", True, (255, 255, 255))
            screen.blit(remove_text, remove_text.get_rect(center=remove_rect.center))

        if len(self.deck) > 10:
            more = self.small_font.render(f"...and {len(self.deck) - 10} more", True, (150, 150, 150))
            screen.blit(more, (deck_x + 10, 115 + 10 * 35))

        # Buttons at bottom
        btn_y = self.screen_height - 70

        # Clear deck button
        clear_rect = pygame.Rect(30, btn_y, 150, 45)
        pygame.draw.rect(screen, (150, 80, 80), clear_rect, border_radius=8)
        clear_text = self.font.render("Clear Deck", True, (255, 255, 255))
        screen.blit(clear_text, clear_text.get_rect(center=clear_rect.center))

        # Reset to default button
        reset_rect = pygame.Rect(200, btn_y, 180, 45)
        pygame.draw.rect(screen, (80, 80, 150), reset_rect, border_radius=8)
        reset_text = self.font.render("Reset Default", True, (255, 255, 255))
        screen.blit(reset_text, reset_text.get_rect(center=reset_rect.center))

        # Done button
        done_rect = pygame.Rect(self.screen_width - 180, btn_y, 150, 45)
        pygame.draw.rect(screen, (70, 130, 70), done_rect, border_radius=8)
        done_text = self.font.render("Done", True, (255, 255, 255))
        screen.blit(done_text, done_text.get_rect(center=done_rect.center))

        # Instructions
        inst = self.small_font.render("Click cards to add to deck. Note: Avatar always starts in hand.",
                                      True, (100, 100, 100))
        screen.blit(inst, (30, self.screen_height - 25))

    def handle_click(self, pos: tuple) -> str | None:
        """Handle click. Returns 'done' if done button clicked."""
        if not self.is_visible:
            return None

        # Check available cards
        cards_per_row = 4
        start_x = 30
        start_y = 115
        spacing = 15

        for i, card_id in enumerate(self.all_cards):
            row = i // cards_per_row
            col = i % cards_per_row
            x = start_x + col * (self.CARD_WIDTH + spacing)
            y = start_y + row * (self.CARD_HEIGHT + spacing + 20)

            card_rect = pygame.Rect(x, y, self.CARD_WIDTH, self.CARD_HEIGHT)
            if card_rect.collidepoint(pos):
                self.deck.append(card_id)
                return None

        # Check deck remove buttons
        deck_x = self.screen_width - 280
        for i, card_id in enumerate(self.deck[:10]):
            y = 115 + i * 35
            remove_rect = pygame.Rect(deck_x + 200, y + 3, 35, 24)
            if remove_rect.collidepoint(pos):
                self.deck.remove(card_id)
                return None

        # Check bottom buttons
        btn_y = self.screen_height - 70

        # Clear deck
        clear_rect = pygame.Rect(30, btn_y, 150, 45)
        if clear_rect.collidepoint(pos):
            self.deck = []
            return None

        # Reset default
        reset_rect = pygame.Rect(200, btn_y, 180, 45)
        if reset_rect.collidepoint(pos):
            if self.player_type == "attacker":
                self.deck = self.default_attacker_deck.copy()
            else:
                self.deck = self.default_defender_deck.copy()
            return None

        # Done
        done_rect = pygame.Rect(self.screen_width - 180, btn_y, 150, 45)
        if done_rect.collidepoint(pos):
            self.hide()
            return "done"

        return None

    def resize(self, screen_width: int, screen_height: int):
        """Handle resize."""
        self.screen_width = screen_width
        self.screen_height = screen_height
