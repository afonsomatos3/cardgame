"""Main menu and deck builder for WarMasterMind."""

import pygame
import os
import utility.cards_database as db


class MainMenu:
    """Main menu screen."""

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.is_visible = True

        self.title_font = pygame.font.Font(None, 72)
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)

        # Audio manager reference (set by main.py)
        self.audio_manager = None

        # Mute button state
        self.mute_button_pressed = False
        self.mute_press_time = 0

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
             "text": "Start Game", "action": "start_game", "color": (70, 130, 70),
             "is_pressed": False, "press_time": 0},
            {"rect": pygame.Rect(center_x, start_y + 70, btn_width, btn_height),
             "text": "Edit Attacker Deck", "action": "deck_attacker", "color": (150, 80, 80),
             "is_pressed": False, "press_time": 0},
            {"rect": pygame.Rect(center_x, start_y + 140, btn_width, btn_height),
             "text": "Edit Defender Deck", "action": "deck_defender", "color": (80, 80, 150),
             "is_pressed": False, "press_time": 0},
            {"rect": pygame.Rect(center_x, start_y + 210, btn_width, btn_height),
             "text": "Quit", "action": "quit", "color": (100, 100, 100),
             "is_pressed": False, "press_time": 0},
        ]
        self.press_duration = 0.1

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
            is_pressed = btn.get("is_pressed", False)

            # Button color
            color = btn["color"]
            if is_pressed:
                color = tuple(max(c - 30, 0) for c in color)
            elif is_hovered:
                color = tuple(min(c + 40, 255) for c in color)

            # Scale down when pressed
            draw_rect = rect
            if is_pressed:
                shrink = 3
                draw_rect = pygame.Rect(rect.x + shrink, rect.y + shrink,
                                       rect.width - shrink * 2, rect.height - shrink * 2)

            pygame.draw.rect(screen, color, draw_rect, border_radius=10)
            pygame.draw.rect(screen, (200, 200, 200) if is_hovered else (100, 100, 100),
                           draw_rect, 2, border_radius=10)

            # Button text
            text = self.font.render(btn["text"], True, (255, 255, 255))
            text_rect = text.get_rect(center=draw_rect.center)
            screen.blit(text, text_rect)

        # Mute button (top right)
        mute_rect = pygame.Rect(self.screen_width - 60, 10, 50, 50)
        is_muted = self.audio_manager.is_music_muted() if self.audio_manager else False
        mute_hovered = mute_rect.collidepoint(mouse_pos)

        mute_color = (80, 80, 80)
        if self.mute_button_pressed:
            mute_color = (50, 50, 50)
        elif mute_hovered:
            mute_color = (100, 100, 100)

        draw_mute_rect = mute_rect
        if self.mute_button_pressed:
            shrink = 2
            draw_mute_rect = pygame.Rect(mute_rect.x + shrink, mute_rect.y + shrink,
                                        mute_rect.width - shrink * 2, mute_rect.height - shrink * 2)

        pygame.draw.rect(screen, mute_color, draw_mute_rect, border_radius=8)
        pygame.draw.rect(screen, (150, 150, 150) if mute_hovered else (100, 100, 100),
                        draw_mute_rect, 2, border_radius=8)

        # Speaker icon (simple text representation)
        icon_text = "M" if is_muted else "S"  # M for Muted, S for Sound
        icon_color = (150, 100, 100) if is_muted else (100, 200, 100)
        icon = self.font.render(icon_text, True, icon_color)
        icon_rect = icon.get_rect(center=draw_mute_rect.center)
        screen.blit(icon, icon_rect)

        # Instructions
        inst = self.small_font.render("Click to select an option", True, (100, 100, 100))
        inst_rect = inst.get_rect(center=(self.screen_width // 2, self.screen_height - 50))
        screen.blit(inst, inst_rect)

    def handle_click(self, pos: tuple) -> str | None:
        """Handle click. Returns action if a button was clicked."""
        if not self.is_visible:
            return None

        # Check mute button
        mute_rect = pygame.Rect(self.screen_width - 60, 10, 50, 50)
        if mute_rect.collidepoint(pos):
            self.mute_button_pressed = True
            self.mute_press_time = 0
            if self.audio_manager:
                self.audio_manager.toggle_mute()
            return None

        for btn in self.buttons:
            if btn["rect"].collidepoint(pos):
                btn["is_pressed"] = True
                btn["press_time"] = 0
                self.result = btn["action"]
                if btn["action"] != "quit":
                    self.hide()
                return btn["action"]

        return None

    def update(self, dt: float):
        """Update button animations."""
        for btn in self.buttons:
            if btn.get("is_pressed", False):
                btn["press_time"] = btn.get("press_time", 0) + dt
                if btn["press_time"] >= self.press_duration:
                    btn["is_pressed"] = False

        # Update mute button animation
        if self.mute_button_pressed:
            self.mute_press_time += dt
            if self.mute_press_time >= self.press_duration:
                self.mute_button_pressed = False

    def resize(self, screen_width: int, screen_height: int):
        """Handle resize."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._create_buttons()


class DeckBuilder:
    """Deck builder screen for customizing player decks."""

    # Bigger card size for better visibility
    CARD_WIDTH = 160
    CARD_HEIGHT = 224

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.is_visible = False
        self.player_type = "attacker"  # or "defender"

        self.title_font = pygame.font.Font(None, 48)
        self.font = pygame.font.Font(None, 28)
        self.small_font = pygame.font.Font(None, 22)
        self.card_font = pygame.font.Font(None, 18)

        # All available cards (except Avatar which is always in hand)
        self.all_cards = [cid for cid in db.CARDS_DATA.keys() if cid != "Avatar"]

        # Current deck
        self.deck: list[str] = []

        # Default decks
        self.default_attacker_deck = ["Footman", "Footman", "Archer", "Eagle", "Knight"]
        self.default_defender_deck = ["Footman", "Footman", "Knight", "War_Hound", "Guardian"]

        # Card image cache
        self._card_cache: dict[str, pygame.Surface] = {}

        # Scroll offset for card list (in pixels)
        self.scroll_offset = 0
        self.max_scroll = 0
        self.scroll_speed = 40  # pixels per scroll tick

        # Cards area for scroll bounds
        self.cards_area_rect = pygame.Rect(0, 0, 0, 0)

        # Button animation state
        self.button_states = {
            "clear": {"is_pressed": False, "press_time": 0},
            "reset": {"is_pressed": False, "press_time": 0},
            "done": {"is_pressed": False, "press_time": 0},
        }
        self.press_duration = 0.1

    def _get_card_image(self, card_id: str) -> pygame.Surface:
        """Get or create a card image."""
        if card_id in self._card_cache:
            return self._card_cache[card_id]

        surf = pygame.Surface((self.CARD_WIDTH, self.CARD_HEIGHT), pygame.SRCALPHA)

        # Card background
        pygame.draw.rect(surf, (240, 230, 210),
                        (0, 0, self.CARD_WIDTH, self.CARD_HEIGHT), border_radius=8)
        pygame.draw.rect(surf, (139, 90, 43),
                        (0, 0, self.CARD_WIDTH, self.CARD_HEIGHT), 3, border_radius=8)

        # Try to load unit image
        unit_path = os.path.join("resources", "Units", f"{card_id}.png")
        if not os.path.exists(unit_path):
            unit_path = os.path.join("resources", "Units", f"{card_id}.jpg")

        if os.path.exists(unit_path):
            try:
                unit_img = pygame.image.load(unit_path).convert_alpha()
                img_rect = unit_img.get_rect()
                scale = min(
                    (self.CARD_WIDTH - 16) / img_rect.width,
                    (self.CARD_HEIGHT - 90) / img_rect.height
                )
                new_size = (int(img_rect.width * scale), int(img_rect.height * scale))
                unit_img = pygame.transform.smoothscale(unit_img, new_size)
                img_x = (self.CARD_WIDTH - new_size[0]) // 2
                surf.blit(unit_img, (img_x, 30))
            except pygame.error:
                pass

        # Card info
        card_info = db.get_card_info(card_id)
        if card_info:
            name = card_info[db.IDX_NAME]
            attack = card_info[db.IDX_ATTACK]
            health = card_info[db.IDX_HEALTH]
            cost = card_info[db.IDX_COST]
            special = card_info[db.IDX_SKILLS] if len(card_info) > db.IDX_SKILLS else ""

            # Name at top (bigger font)
            name_font = pygame.font.Font(None, 22)
            name_text = name_font.render(name[:16], True, (50, 40, 30))
            name_rect = name_text.get_rect(centerx=self.CARD_WIDTH // 2, top=6)
            surf.blit(name_text, name_rect)

            # Cost circle (bigger)
            pygame.draw.circle(surf, (70, 130, 180), (18, 18), 14)
            pygame.draw.circle(surf, (50, 100, 150), (18, 18), 14, 2)
            cost_font = pygame.font.Font(None, 24)
            cost_text = cost_font.render(str(cost), True, (255, 255, 255))
            surf.blit(cost_text, cost_text.get_rect(center=(18, 18)))

            # Special ability text area (if has special)
            if special:
                special_y = self.CARD_HEIGHT - 60
                special_bg = pygame.Surface((self.CARD_WIDTH - 8, 35), pygame.SRCALPHA)
                pygame.draw.rect(special_bg, (240, 220, 180, 200),
                               (0, 0, self.CARD_WIDTH - 8, 35), border_radius=4)
                pygame.draw.rect(special_bg, (139, 90, 43),
                               (0, 0, self.CARD_WIDTH - 8, 35), 1, border_radius=4)
                surf.blit(special_bg, (4, special_y))

                # Wrap special text
                micro_font = pygame.font.Font(None, 14)
                words = special.split()
                lines = []
                current_line = []
                for word in words:
                    test_line = ' '.join(current_line + [word])
                    if micro_font.size(test_line)[0] < self.CARD_WIDTH - 14:
                        current_line.append(word)
                    else:
                        if current_line:
                            lines.append(' '.join(current_line))
                        current_line = [word]
                if current_line:
                    lines.append(' '.join(current_line))

                for i, line in enumerate(lines[:2]):  # Max 2 lines
                    line_text = micro_font.render(line, True, (50, 40, 30))
                    line_rect = line_text.get_rect(centerx=self.CARD_WIDTH // 2, y=special_y + 4 + i * 14)
                    surf.blit(line_text, line_rect)

            # Stats at bottom (bigger)
            stats_y = self.CARD_HEIGHT - 18
            stat_font = pygame.font.Font(None, 26)

            # Attack circle
            pygame.draw.circle(surf, (200, 60, 60), (20, stats_y), 14)
            pygame.draw.circle(surf, (150, 40, 40), (20, stats_y), 14, 2)
            atk_text = stat_font.render(str(attack), True, (255, 255, 255))
            surf.blit(atk_text, atk_text.get_rect(center=(20, stats_y)))

            # Health circle
            pygame.draw.circle(surf, (60, 160, 60), (self.CARD_WIDTH - 20, stats_y), 14)
            pygame.draw.circle(surf, (40, 120, 40), (self.CARD_WIDTH - 20, stats_y), 14, 2)
            hp_text = stat_font.render(str(health), True, (255, 255, 255))
            surf.blit(hp_text, hp_text.get_rect(center=(self.CARD_WIDTH - 20, stats_y)))

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

        # Available cards section (left side with scrolling)
        avail_label = self.font.render("Available Cards (click to add, scroll to browse):", True, (200, 200, 200))
        screen.blit(avail_label, (30, 80))

        # Calculate cards layout
        cards_per_row = 3
        start_x = 30
        start_y = 115
        spacing = 20
        row_height = self.CARD_HEIGHT + spacing + 25

        # Calculate total content height and max scroll
        total_rows = (len(self.all_cards) + cards_per_row - 1) // cards_per_row
        total_content_height = total_rows * row_height
        visible_height = self.screen_height - start_y - 100  # Leave room for buttons
        self.max_scroll = max(0, total_content_height - visible_height)

        # Clamp scroll offset
        self.scroll_offset = max(0, min(self.scroll_offset, self.max_scroll))

        # Cards display area (for clipping and scroll detection)
        cards_area_width = cards_per_row * (self.CARD_WIDTH + spacing) + 40
        self.cards_area_rect = pygame.Rect(start_x - 10, start_y - 5,
                                           cards_area_width, visible_height + 10)

        # Draw cards area background
        pygame.draw.rect(screen, (35, 40, 45), self.cards_area_rect, border_radius=10)
        pygame.draw.rect(screen, (60, 60, 65), self.cards_area_rect, 2, border_radius=10)

        # Create clipping region for cards
        clip_rect = pygame.Rect(start_x - 5, start_y, cards_area_width - 10, visible_height)
        screen.set_clip(clip_rect)

        # Draw available cards with scroll offset
        for i, card_id in enumerate(self.all_cards):
            row = i // cards_per_row
            col = i % cards_per_row
            x = start_x + col * (self.CARD_WIDTH + spacing)
            y = start_y + row * row_height - self.scroll_offset

            # Skip cards outside visible area
            if y + self.CARD_HEIGHT < start_y - 10 or y > start_y + visible_height + 10:
                continue

            card_img = self._get_card_image(card_id)
            screen.blit(card_img, (x, y))

            # Show count in deck
            count = self.deck.count(card_id)
            if count > 0:
                # Draw count badge
                badge_x = x + self.CARD_WIDTH - 25
                badge_y = y + 5
                pygame.draw.circle(screen, (100, 200, 100), (badge_x, badge_y), 16)
                pygame.draw.circle(screen, (60, 150, 60), (badge_x, badge_y), 16, 2)
                count_text = self.font.render(str(count), True, (255, 255, 255))
                screen.blit(count_text, count_text.get_rect(center=(badge_x, badge_y)))

        # Reset clipping
        screen.set_clip(None)

        # Draw scrollbar if needed
        if self.max_scroll > 0:
            scrollbar_x = start_x + cards_area_width - 25
            scrollbar_y = start_y + 5
            scrollbar_height = visible_height - 10
            scrollbar_width = 12

            # Scrollbar track
            track_rect = pygame.Rect(scrollbar_x, scrollbar_y, scrollbar_width, scrollbar_height)
            pygame.draw.rect(screen, (50, 50, 55), track_rect, border_radius=6)

            # Scrollbar thumb
            thumb_ratio = visible_height / total_content_height
            thumb_height = max(30, int(scrollbar_height * thumb_ratio))
            thumb_pos = int((self.scroll_offset / self.max_scroll) * (scrollbar_height - thumb_height))
            thumb_rect = pygame.Rect(scrollbar_x, scrollbar_y + thumb_pos, scrollbar_width, thumb_height)
            pygame.draw.rect(screen, (100, 100, 110), thumb_rect, border_radius=6)
            pygame.draw.rect(screen, (130, 130, 140), thumb_rect, 1, border_radius=6)

        # Current deck section (right side)
        deck_x = self.screen_width - 300
        deck_label = self.font.render(f"Your Deck ({len(self.deck)} cards):", True, (200, 200, 200))
        screen.blit(deck_label, (deck_x, 80))

        # Deck panel background
        deck_panel_rect = pygame.Rect(deck_x - 10, 110, 290, self.screen_height - 200)
        pygame.draw.rect(screen, (35, 40, 45), deck_panel_rect, border_radius=10)
        pygame.draw.rect(screen, (60, 60, 65), deck_panel_rect, 2, border_radius=10)

        # Draw deck cards (in a list)
        max_visible_deck = min(15, (self.screen_height - 250) // 38)
        for i, card_id in enumerate(self.deck[:max_visible_deck]):
            y = 120 + i * 38
            card_info = db.get_card_info(card_id)
            name = card_info[db.IDX_NAME] if card_info else card_id
            cost = card_info[db.IDX_COST] if card_info else 0

            # Card entry background
            entry_rect = pygame.Rect(deck_x, y, 260, 34)
            pygame.draw.rect(screen, (50, 55, 60), entry_rect, border_radius=6)
            pygame.draw.rect(screen, (70, 70, 75), entry_rect, 1, border_radius=6)

            # Cost indicator
            pygame.draw.circle(screen, (70, 130, 180), (deck_x + 18, y + 17), 12)
            cost_text = self.small_font.render(str(cost), True, (255, 255, 255))
            screen.blit(cost_text, cost_text.get_rect(center=(deck_x + 18, y + 17)))

            # Card name
            name_text = self.small_font.render(name, True, (255, 255, 255))
            screen.blit(name_text, (deck_x + 38, y + 8))

            # Remove button
            remove_rect = pygame.Rect(deck_x + 215, y + 5, 40, 24)
            mouse_pos = pygame.mouse.get_pos()
            remove_color = (180, 70, 70) if remove_rect.collidepoint(mouse_pos) else (150, 60, 60)
            pygame.draw.rect(screen, remove_color, remove_rect, border_radius=5)
            remove_text = self.small_font.render("X", True, (255, 255, 255))
            screen.blit(remove_text, remove_text.get_rect(center=remove_rect.center))

        if len(self.deck) > max_visible_deck:
            more = self.small_font.render(f"...and {len(self.deck) - max_visible_deck} more",
                                          True, (150, 150, 150))
            screen.blit(more, (deck_x + 10, 120 + max_visible_deck * 38))

        # Buttons at bottom
        btn_y = self.screen_height - 70
        mouse_pos = pygame.mouse.get_pos()

        # Helper to draw animated button
        def draw_button(rect, color, text, state_key):
            is_pressed = self.button_states[state_key]["is_pressed"]
            is_hovered = rect.collidepoint(mouse_pos)

            draw_color = color
            if is_pressed:
                draw_color = tuple(max(c - 30, 0) for c in color)
            elif is_hovered:
                draw_color = tuple(min(c + 30, 255) for c in color)

            draw_rect = rect
            if is_pressed:
                shrink = 2
                draw_rect = pygame.Rect(rect.x + shrink, rect.y + shrink,
                                       rect.width - shrink * 2, rect.height - shrink * 2)

            pygame.draw.rect(screen, draw_color, draw_rect, border_radius=8)
            pygame.draw.rect(screen, (100, 100, 100), draw_rect, 2, border_radius=8)
            btn_text = self.font.render(text, True, (255, 255, 255))
            screen.blit(btn_text, btn_text.get_rect(center=draw_rect.center))

        # Clear deck button
        clear_rect = pygame.Rect(30, btn_y, 150, 45)
        draw_button(clear_rect, (150, 80, 80), "Clear Deck", "clear")

        # Reset to default button
        reset_rect = pygame.Rect(200, btn_y, 180, 45)
        draw_button(reset_rect, (80, 80, 150), "Reset Default", "reset")

        # Done button
        done_rect = pygame.Rect(self.screen_width - 180, btn_y, 150, 45)
        draw_button(done_rect, (70, 130, 70), "Done", "done")

        # Instructions
        inst = self.small_font.render("Click cards to add. Use mouse wheel to scroll. Avatar always starts in hand.",
                                      True, (100, 100, 100))
        screen.blit(inst, (30, self.screen_height - 25))

    def handle_scroll(self, scroll_y: int):
        """Handle mouse wheel scrolling.

        Args:
            scroll_y: Positive for scroll up, negative for scroll down
        """
        if not self.is_visible:
            return

        # Scroll in opposite direction (natural scrolling)
        self.scroll_offset -= scroll_y * self.scroll_speed

        # Clamp scroll offset
        self.scroll_offset = max(0, min(self.scroll_offset, self.max_scroll))

    def handle_click(self, pos: tuple) -> str | None:
        """Handle click. Returns 'done' if done button clicked."""
        if not self.is_visible:
            return None

        # Check available cards (with scroll offset)
        cards_per_row = 3
        start_x = 30
        start_y = 115
        spacing = 20
        row_height = self.CARD_HEIGHT + spacing + 25
        visible_height = self.screen_height - start_y - 100

        # Only check cards if click is in the cards area
        if self.cards_area_rect.collidepoint(pos):
            for i, card_id in enumerate(self.all_cards):
                row = i // cards_per_row
                col = i % cards_per_row
                x = start_x + col * (self.CARD_WIDTH + spacing)
                y = start_y + row * row_height - self.scroll_offset

                # Skip cards outside visible area
                if y + self.CARD_HEIGHT < start_y or y > start_y + visible_height:
                    continue

                card_rect = pygame.Rect(x, y, self.CARD_WIDTH, self.CARD_HEIGHT)
                if card_rect.collidepoint(pos):
                    self.deck.append(card_id)
                    return None

        # Check deck remove buttons
        deck_x = self.screen_width - 300
        max_visible_deck = min(15, (self.screen_height - 250) // 38)
        for i, card_id in enumerate(self.deck[:max_visible_deck]):
            y = 120 + i * 38
            remove_rect = pygame.Rect(deck_x + 215, y + 5, 40, 24)
            if remove_rect.collidepoint(pos):
                self.deck.remove(card_id)
                return None

        # Check bottom buttons
        btn_y = self.screen_height - 70

        # Clear deck
        clear_rect = pygame.Rect(30, btn_y, 150, 45)
        if clear_rect.collidepoint(pos):
            self.button_states["clear"]["is_pressed"] = True
            self.button_states["clear"]["press_time"] = 0
            self.deck = []
            return None

        # Reset default
        reset_rect = pygame.Rect(200, btn_y, 180, 45)
        if reset_rect.collidepoint(pos):
            self.button_states["reset"]["is_pressed"] = True
            self.button_states["reset"]["press_time"] = 0
            if self.player_type == "attacker":
                self.deck = self.default_attacker_deck.copy()
            else:
                self.deck = self.default_defender_deck.copy()
            return None

        # Done
        done_rect = pygame.Rect(self.screen_width - 180, btn_y, 150, 45)
        if done_rect.collidepoint(pos):
            self.button_states["done"]["is_pressed"] = True
            self.button_states["done"]["press_time"] = 0
            self.hide()
            return "done"

        return None

    def update(self, dt: float):
        """Update button animations."""
        for state in self.button_states.values():
            if state["is_pressed"]:
                state["press_time"] += dt
                if state["press_time"] >= self.press_duration:
                    state["is_pressed"] = False

    def resize(self, screen_width: int, screen_height: int):
        """Handle resize."""
        self.screen_width = screen_width
        self.screen_height = screen_height
