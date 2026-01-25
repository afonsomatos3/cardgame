"""WarMasterMind Thin Client - Multiplayer game client."""

import pygame
import sys
import os
import json
import math
from pathlib import Path

from network import NetworkClient


# Screen settings
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

# Colors
BG_COLOR = (30, 35, 40)
WHITE = (255, 255, 255)
GRAY = (150, 150, 150)
DARK_GRAY = (80, 80, 80)
RED = (255, 100, 100)
BLUE = (100, 150, 255)
GREEN = (100, 200, 100)
GOLD = (255, 200, 50)

# Game states
STATE_LOGIN = "login"
STATE_LOBBY = "lobby"
STATE_FRIENDS = "friends"
STATE_DECK_BUILDER = "deck_builder"
STATE_MATCHMAKING = "matchmaking"
STATE_MATCH_START = "match_start"
STATE_GAME = "game"
STATE_COMBAT_SELECT = "combat_select"
STATE_GAME_OVER = "game_over"

# Card dimensions - BIGGER cards
CARD_WIDTH = 160
CARD_HEIGHT = 224
CARD_FOCUS_SCALE = 1.35  # Much bigger on hover for readability

# Deck building card size - optimized
DECK_CARD_WIDTH = 110
DECK_CARD_HEIGHT = 154


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation."""
    return a + (b - a) * t


def ease_out_cubic(t: float) -> float:
    """Cubic ease out for smooth animations."""
    return 1 - pow(1 - t, 3)


def ease_out_back(t: float) -> float:
    """Ease out with slight overshoot for bouncy feel."""
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)


class AnimatedValue:
    """Smoothly animated float value."""

    def __init__(self, value: float = 0, speed: float = 8.0):
        self.current = value
        self.target = value
        self.speed = speed
        self.velocity = 0

    def set(self, value: float, instant: bool = False):
        self.target = value
        if instant:
            self.current = value
            self.velocity = 0

    def update(self, dt: float):
        diff = self.target - self.current
        self.velocity = diff * self.speed
        self.current += self.velocity * dt

        # Snap if close enough
        if abs(diff) < 0.01:
            self.current = self.target

    @property
    def value(self) -> float:
        return self.current

    @property
    def is_animating(self) -> bool:
        return abs(self.target - self.current) > 0.01


class AnimatedCard:
    """Card with smooth hover and drag animations."""

    def __init__(self, card_data: dict, x: float, y: float):
        self.card_data = card_data
        self.card_id = card_data.get("card_id", "Unknown")

        # Position with smooth animation
        self.x = AnimatedValue(x, speed=12.0)
        self.y = AnimatedValue(y, speed=12.0)
        self.original_x = x
        self.original_y = y

        # Scale and rotation
        self.scale = AnimatedValue(1.0, speed=15.0)
        self.angle = AnimatedValue(0, speed=10.0)
        self.hover_offset = AnimatedValue(0, speed=18.0)

        # Glow effect for selection
        self.glow = AnimatedValue(0, speed=10.0)
        self.glow_pulse = 0

        # State
        self.is_hovered = False
        self.is_selected = False
        self.is_dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0

        # Shadow
        self.shadow_offset = AnimatedValue(3, speed=12.0)

    def set_position(self, x: float, y: float, angle: float = 0):
        """Set card target position."""
        self.x.set(x)
        self.y.set(y)
        self.angle.set(angle)
        self.original_x = x
        self.original_y = y

    def set_hover(self, hovered: bool):
        """Set hover state with animation."""
        if hovered != self.is_hovered:
            self.is_hovered = hovered
            if hovered and not self.is_dragging:
                self.scale.set(CARD_FOCUS_SCALE)
                self.hover_offset.set(-40)  # Move up more
                self.shadow_offset.set(12)
                self.angle.set(0)  # Straighten on hover
            elif not self.is_dragging:
                self.scale.set(1.0)
                self.hover_offset.set(0)
                self.shadow_offset.set(3)

    def set_selected(self, selected: bool):
        """Set selected state."""
        self.is_selected = selected
        self.glow.set(1.0 if selected else 0)

    def start_drag(self, mouse_pos: tuple):
        """Start dragging the card."""
        self.is_dragging = True
        self.drag_offset_x = self.x.current - mouse_pos[0]
        self.drag_offset_y = self.y.current - mouse_pos[1]
        self.scale.set(CARD_FOCUS_SCALE)
        self.shadow_offset.set(20)
        self.angle.set(0)

    def update_drag(self, mouse_pos: tuple):
        """Update drag position."""
        if self.is_dragging:
            self.x.set(mouse_pos[0] + self.drag_offset_x, instant=True)
            self.y.set(mouse_pos[1] + self.drag_offset_y, instant=True)

    def end_drag(self):
        """End dragging."""
        self.is_dragging = False
        self.scale.set(1.0)
        self.shadow_offset.set(3)

    def return_to_position(self):
        """Return to original position with animation."""
        self.x.set(self.original_x)
        self.y.set(self.original_y)
        self.is_dragging = False
        self.scale.set(1.0)
        self.shadow_offset.set(3)

    def update(self, dt: float):
        """Update all animations."""
        self.x.update(dt)
        self.y.update(dt)
        self.scale.update(dt)
        self.angle.update(dt)
        self.hover_offset.update(dt)
        self.glow.update(dt)
        self.shadow_offset.update(dt)

        # Pulse glow when selected
        if self.is_selected:
            self.glow_pulse += dt * 3

    def get_rect(self) -> pygame.Rect:
        """Get card bounding rectangle."""
        w = int(CARD_WIDTH * self.scale.value)
        h = int(CARD_HEIGHT * self.scale.value)
        return pygame.Rect(
            int(self.x.value - w // 2),
            int(self.y.value + self.hover_offset.value - h // 2),
            w, h
        )

    def contains_point(self, pos: tuple) -> bool:
        """Check if point is inside card."""
        return self.get_rect().collidepoint(pos)


class UIAnimation:
    """Helper for UI element animations."""

    def __init__(self):
        self.animations = {}

    def start(self, key: str, duration: float = 0.3):
        """Start a new animation."""
        self.animations[key] = {"progress": 0, "duration": duration, "active": True}

    def update(self, dt: float):
        """Update all animations."""
        for key, anim in list(self.animations.items()):
            if anim["active"]:
                anim["progress"] += dt / anim["duration"]
                if anim["progress"] >= 1.0:
                    anim["progress"] = 1.0
                    anim["active"] = False

    def get(self, key: str, default: float = 1.0) -> float:
        """Get animation progress (0-1) with easing."""
        if key in self.animations:
            return ease_out_cubic(self.animations[key]["progress"])
        return default

    def is_active(self, key: str) -> bool:
        """Check if animation is still running."""
        return key in self.animations and self.animations[key]["active"]


class DrawMenu:
    """Menu for selecting cards to draw with turns to arrive display."""

    CARD_WIDTH = 130
    CARD_HEIGHT = 182
    CARDS_PER_ROW = 4

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.is_visible = False
        self.available_cards = []
        self.cards_info = {}
        self.card_rects = []
        self.hovered_card = None

        self.font = pygame.font.Font(None, 28)
        self.small_font = pygame.font.Font(None, 20)
        self.tiny_font = pygame.font.Font(None, 15)

        self.width = 650
        self.height = 550
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2

        self.scroll_offset = 0
        self.max_visible_rows = 2

        # Animation
        self.anim = UIAnimation()
        self.panel_scale = AnimatedValue(0, speed=12.0)

        self._card_cache = {}

    def _render_card(self, card_id: str) -> pygame.Surface:
        """Render a card for the draw menu."""
        if card_id in self._card_cache:
            return self._card_cache[card_id]

        surf = pygame.Surface((self.CARD_WIDTH, self.CARD_HEIGHT), pygame.SRCALPHA)

        # Card background with gradient effect
        pygame.draw.rect(surf, (245, 235, 220),
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
                    (self.CARD_WIDTH - 12) / img_rect.width,
                    (self.CARD_HEIGHT - 85) / img_rect.height
                )
                new_size = (int(img_rect.width * scale), int(img_rect.height * scale))
                unit_img = pygame.transform.smoothscale(unit_img, new_size)
                img_x = (self.CARD_WIDTH - new_size[0]) // 2
                surf.blit(unit_img, (img_x, 35))
            except pygame.error:
                pass

        # Card info
        card_info = self.cards_info.get(card_id, {})
        name = card_info.get("name", card_id)
        attack = card_info.get("attack", 0)
        health = card_info.get("health", 0)
        cost = card_info.get("cost", 0)
        special = card_info.get("special", "")

        # Name at top
        name_text = self.small_font.render(name[:16], True, (50, 40, 30))
        name_rect = name_text.get_rect(centerx=self.CARD_WIDTH // 2, top=4)
        surf.blit(name_text, name_rect)

        # Cost circle (shows turns to arrive)
        pygame.draw.circle(surf, (70, 130, 180), (18, 18), 14)
        pygame.draw.circle(surf, (50, 100, 150), (18, 18), 14, 2)
        cost_text = self.small_font.render(str(cost), True, WHITE)
        surf.blit(cost_text, cost_text.get_rect(center=(18, 18)))

        # "Turns" label
        turns_text = self.tiny_font.render("turns", True, (70, 130, 180))
        surf.blit(turns_text, turns_text.get_rect(centerx=18, top=33))

        # Stats at bottom
        stats_y = self.CARD_HEIGHT - 20

        # Attack
        pygame.draw.circle(surf, (200, 60, 60), (20, stats_y), 14)
        pygame.draw.circle(surf, (150, 40, 40), (20, stats_y), 14, 2)
        atk_text = self.small_font.render(str(attack), True, WHITE)
        surf.blit(atk_text, atk_text.get_rect(center=(20, stats_y)))

        # Health
        pygame.draw.circle(surf, (60, 160, 60), (self.CARD_WIDTH - 20, stats_y), 14)
        pygame.draw.circle(surf, (40, 120, 40), (self.CARD_WIDTH - 20, stats_y), 14, 2)
        hp_text = self.small_font.render(str(health), True, WHITE)
        surf.blit(hp_text, hp_text.get_rect(center=(self.CARD_WIDTH - 20, stats_y)))

        # Special ability text
        if special:
            special_y = self.CARD_HEIGHT - 60
            special_bg = pygame.Surface((self.CARD_WIDTH - 10, 38), pygame.SRCALPHA)
            pygame.draw.rect(special_bg, (240, 220, 180, 230),
                           (0, 0, self.CARD_WIDTH - 10, 38), border_radius=4)
            surf.blit(special_bg, (5, special_y))

            words = special.split()
            lines = []
            current_line = []
            for word in words:
                test_line = ' '.join(current_line + [word])
                if self.tiny_font.size(test_line)[0] < self.CARD_WIDTH - 14:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(' '.join(current_line))

            for i, line in enumerate(lines[:2]):
                special_text = self.tiny_font.render(line, True, (50, 40, 30))
                text_rect = special_text.get_rect(centerx=self.CARD_WIDTH // 2,
                                                  y=special_y + 4 + i * 16)
                surf.blit(special_text, text_rect)

        self._card_cache[card_id] = surf
        return surf

    def show(self, deck_cards: list, cards_info: dict):
        """Show the draw menu with animation."""
        self.available_cards = deck_cards
        self.cards_info = cards_info
        self.is_visible = True
        self.scroll_offset = 0
        self.panel_scale.set(1.0)
        self.anim.start("open", 0.25)
        self._update_card_rects()

    def hide(self):
        """Hide the menu."""
        self.is_visible = False
        self.panel_scale.set(0)

    def _update_card_rects(self):
        """Update card positions for scroll."""
        self.card_rects = []
        spacing = 18
        start_x = self.x + 35
        start_y = self.y + 75

        for i, card_id in enumerate(self.available_cards):
            row = i // self.CARDS_PER_ROW - self.scroll_offset
            col = i % self.CARDS_PER_ROW

            if row < 0 or row >= self.max_visible_rows:
                continue

            x = start_x + col * (self.CARD_WIDTH + spacing)
            y = start_y + row * (self.CARD_HEIGHT + spacing + 12)

            rect = pygame.Rect(x, y, self.CARD_WIDTH, self.CARD_HEIGHT)
            self.card_rects.append((rect, card_id))

    def update(self, dt: float):
        """Update animations."""
        self.panel_scale.update(dt)
        self.anim.update(dt)

    def draw(self, screen: pygame.Surface):
        """Draw the draw menu."""
        if not self.is_visible:
            return

        # Overlay with fade
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        alpha = max(0, min(255, int(180 * self.panel_scale.value)))
        overlay.fill((0, 0, 0, alpha))
        screen.blit(overlay, (0, 0))

        # Animated panel scale
        scale = self.panel_scale.value
        if scale < 0.01:
            return

        scaled_w = int(self.width * scale)
        scaled_h = int(self.height * scale)
        panel_x = self.screen_width // 2 - scaled_w // 2
        panel_y = self.screen_height // 2 - scaled_h // 2

        # Panel with shadow
        shadow_rect = pygame.Rect(panel_x + 8, panel_y + 8, scaled_w, scaled_h)
        pygame.draw.rect(screen, (0, 0, 0, 100), shadow_rect, border_radius=12)

        panel_rect = pygame.Rect(panel_x, panel_y, scaled_w, scaled_h)
        pygame.draw.rect(screen, (55, 55, 60), panel_rect, border_radius=12)
        pygame.draw.rect(screen, (100, 100, 105), panel_rect, 3, border_radius=12)

        if scale < 0.9:
            return

        # Title
        title = self.font.render("Select Card to Draw (Cost = Turns to Arrive)", True, WHITE)
        title_rect = title.get_rect(center=(self.x + self.width // 2, self.y + 32))
        screen.blit(title, title_rect)

        # Close button
        close_rect = pygame.Rect(self.x + self.width - 38, self.y + 10, 30, 30)
        mouse_pos = pygame.mouse.get_pos()
        close_hovered = close_rect.collidepoint(mouse_pos)
        close_color = (200, 70, 70) if close_hovered else (160, 55, 55)
        pygame.draw.rect(screen, close_color, close_rect, border_radius=6)
        close_text = self.font.render("X", True, WHITE)
        screen.blit(close_text, close_text.get_rect(center=close_rect.center))

        # Draw cards
        for rect, card_id in self.card_rects:
            is_hovered = rect.collidepoint(mouse_pos)

            # Hover effect - slight scale up
            if is_hovered:
                hover_scale = 1.08
                new_w = int(rect.width * hover_scale)
                new_h = int(rect.height * hover_scale)
                draw_x = rect.centerx - new_w // 2
                draw_y = rect.centery - new_h // 2 - 5

                # Glow
                glow_surf = pygame.Surface((new_w + 20, new_h + 20), pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (255, 255, 150, 60),
                               (0, 0, new_w + 20, new_h + 20), border_radius=12)
                screen.blit(glow_surf, (draw_x - 10, draw_y - 10))

                card_surf = self._render_card(card_id)
                scaled_card = pygame.transform.smoothscale(card_surf, (new_w, new_h))
                screen.blit(scaled_card, (draw_x, draw_y))
            else:
                card_surf = self._render_card(card_id)
                screen.blit(card_surf, rect.topleft)

        # Scroll indicators
        total_rows = (len(self.available_cards) + self.CARDS_PER_ROW - 1) // self.CARDS_PER_ROW

        if self.scroll_offset > 0:
            arrow_rect = pygame.Rect(self.x + self.width // 2 - 20, self.y + 55, 40, 20)
            pygame.draw.polygon(screen, GRAY, [
                (arrow_rect.centerx, arrow_rect.top),
                (arrow_rect.left, arrow_rect.bottom),
                (arrow_rect.right, arrow_rect.bottom)
            ])

        if self.scroll_offset + self.max_visible_rows < total_rows:
            arrow_rect = pygame.Rect(self.x + self.width // 2 - 20, self.y + self.height - 55, 40, 20)
            pygame.draw.polygon(screen, GRAY, [
                (arrow_rect.left, arrow_rect.top),
                (arrow_rect.right, arrow_rect.top),
                (arrow_rect.centerx, arrow_rect.bottom)
            ])

        # Empty deck message
        if not self.available_cards:
            empty_text = self.font.render("Deck is empty!", True, (200, 150, 150))
            empty_rect = empty_text.get_rect(center=(self.x + self.width // 2,
                                                      self.y + self.height // 2))
            screen.blit(empty_text, empty_rect)

        # Card count
        count_text = self.small_font.render(f"{len(self.available_cards)} cards in deck", True, GRAY)
        count_rect = count_text.get_rect(center=(self.x + self.width // 2,
                                                  self.y + self.height - 22))
        screen.blit(count_text, count_rect)

    def handle_click(self, pos: tuple) -> str | None:
        """Handle click. Returns card_id if selected, 'close' if closed."""
        if not self.is_visible:
            return None

        close_rect = pygame.Rect(self.x + self.width - 38, self.y + 10, 30, 30)
        if close_rect.collidepoint(pos):
            self.hide()
            return "close"

        total_rows = (len(self.available_cards) + self.CARDS_PER_ROW - 1) // self.CARDS_PER_ROW
        if self.scroll_offset > 0:
            up_rect = pygame.Rect(self.x + self.width // 2 - 20, self.y + 55, 40, 20)
            if up_rect.collidepoint(pos):
                self.scroll_offset -= 1
                self._update_card_rects()
                return None

        if self.scroll_offset + self.max_visible_rows < total_rows:
            down_rect = pygame.Rect(self.x + self.width // 2 - 20, self.y + self.height - 55, 40, 20)
            if down_rect.collidepoint(pos):
                self.scroll_offset += 1
                self._update_card_rects()
                return None

        for rect, card_id in self.card_rects:
            if rect.collidepoint(pos):
                self.hide()
                return card_id

        panel_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        if not panel_rect.collidepoint(pos):
            self.hide()
            return "close"

        return None

    def resize(self, screen_width: int, screen_height: int):
        """Handle resize."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2
        if self.is_visible:
            self._update_card_rects()


class LocationPanel:
    """Panel showing detailed cards at a location with movement support."""

    THUMB_WIDTH = 90
    THUMB_HEIGHT = 126

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.is_visible = False
        self.location_name = ""
        self.own_cards = []
        self.enemy_cards = []
        self.can_see_enemy = False
        self.cards_info = {}
        self.can_move = False
        self.adjacent_locations = []

        self.font = pygame.font.Font(None, 26)
        self.small_font = pygame.font.Font(None, 22)

        self.width = 580
        self.height = 480
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2

        self._card_cache = {}
        self._card_rects = []
        self._move_buttons = []
        self.selected_card_index = None
        self.hovered_card_index = None

        # Animation
        self.panel_scale = AnimatedValue(0, speed=14.0)

    def _get_card_thumbnail(self, card_id: str, card_info: dict) -> pygame.Surface:
        """Get card thumbnail."""
        cache_key = f"loc_{card_id}"
        if cache_key in self._card_cache:
            return self._card_cache[cache_key]

        thumb = pygame.Surface((self.THUMB_WIDTH, self.THUMB_HEIGHT), pygame.SRCALPHA)

        pygame.draw.rect(thumb, (245, 235, 220),
                        (0, 0, self.THUMB_WIDTH, self.THUMB_HEIGHT), border_radius=6)
        pygame.draw.rect(thumb, (139, 90, 43),
                        (0, 0, self.THUMB_WIDTH, self.THUMB_HEIGHT), 2, border_radius=6)

        unit_path = os.path.join("resources", "Units", f"{card_id}.png")
        if not os.path.exists(unit_path):
            unit_path = os.path.join("resources", "Units", f"{card_id}.jpg")

        if os.path.exists(unit_path):
            try:
                unit_img = pygame.image.load(unit_path).convert_alpha()
                img_rect = unit_img.get_rect()
                scale = min(
                    (self.THUMB_WIDTH - 10) / img_rect.width,
                    (self.THUMB_HEIGHT - 45) / img_rect.height
                )
                new_size = (int(img_rect.width * scale), int(img_rect.height * scale))
                unit_img = pygame.transform.smoothscale(unit_img, new_size)
                img_x = (self.THUMB_WIDTH - new_size[0]) // 2
                thumb.blit(unit_img, (img_x, 22))
            except pygame.error:
                pass

        name = card_info.get("name", card_id)[:14]
        attack = card_info.get("attack", 0)
        health = card_info.get("health", 0)

        tiny_font = pygame.font.Font(None, 15)

        name_text = tiny_font.render(name, True, (50, 40, 30))
        name_rect = name_text.get_rect(centerx=self.THUMB_WIDTH // 2, top=4)
        thumb.blit(name_text, name_rect)

        stats_y = self.THUMB_HEIGHT - 15
        pygame.draw.circle(thumb, (200, 60, 60), (16, stats_y), 10)
        atk_text = tiny_font.render(str(attack), True, WHITE)
        thumb.blit(atk_text, atk_text.get_rect(center=(16, stats_y)))

        pygame.draw.circle(thumb, (60, 160, 60), (self.THUMB_WIDTH - 16, stats_y), 10)
        hp_text = tiny_font.render(str(health), True, WHITE)
        thumb.blit(hp_text, hp_text.get_rect(center=(self.THUMB_WIDTH - 16, stats_y)))

        self._card_cache[cache_key] = thumb
        return thumb

    def _get_card_back(self) -> pygame.Surface:
        """Get face-down card."""
        if "_back" in self._card_cache:
            return self._card_cache["_back"]

        thumb = pygame.Surface((self.THUMB_WIDTH, self.THUMB_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(thumb, (60, 50, 45),
                        (0, 0, self.THUMB_WIDTH, self.THUMB_HEIGHT), border_radius=6)
        pygame.draw.rect(thumb, (100, 80, 60),
                        (0, 0, self.THUMB_WIDTH, self.THUMB_HEIGHT), 2, border_radius=6)

        font = pygame.font.Font(None, 36)
        text = font.render("?", True, (100, 85, 70))
        text_rect = text.get_rect(center=(self.THUMB_WIDTH // 2, self.THUMB_HEIGHT // 2))
        thumb.blit(text, text_rect)

        self._card_cache["_back"] = thumb
        return thumb

    def show(self, location_name: str, own_cards: list, enemy_cards: list,
             can_see_enemy: bool, cards_info: dict, can_move: bool = False,
             adjacent_locations: list = None):
        """Show the panel."""
        self.location_name = location_name
        self.own_cards = own_cards
        self.enemy_cards = enemy_cards
        self.can_see_enemy = can_see_enemy
        self.cards_info = cards_info
        self.can_move = can_move
        self.adjacent_locations = adjacent_locations or []
        self.is_visible = True
        self.selected_card_index = None
        self._card_rects = []
        self._move_buttons = []
        self.panel_scale.set(1.0)

    def hide(self):
        """Hide the panel."""
        self.is_visible = False
        self.selected_card_index = None
        self.panel_scale.set(0)

    def update(self, dt: float):
        """Update animations."""
        self.panel_scale.update(dt)

    def draw(self, screen: pygame.Surface):
        """Draw the panel."""
        if not self.is_visible:
            return

        self._card_rects = []
        self._move_buttons = []

        # Overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        alpha = max(0, min(255, int(180 * self.panel_scale.value)))
        overlay.fill((0, 0, 0, alpha))
        screen.blit(overlay, (0, 0))

        scale = self.panel_scale.value
        if scale < 0.01:
            return

        scaled_w = int(self.width * scale)
        scaled_h = int(self.height * scale)
        panel_x = self.screen_width // 2 - scaled_w // 2
        panel_y = self.screen_height // 2 - scaled_h // 2

        # Shadow
        shadow_rect = pygame.Rect(panel_x + 6, panel_y + 6, scaled_w, scaled_h)
        pygame.draw.rect(screen, (0, 0, 0, 80), shadow_rect, border_radius=12)

        # Panel
        panel_rect = pygame.Rect(panel_x, panel_y, scaled_w, scaled_h)
        pygame.draw.rect(screen, (60, 58, 55), panel_rect, border_radius=12)
        pygame.draw.rect(screen, (100, 95, 88), panel_rect, 3, border_radius=12)

        if scale < 0.9:
            return

        mouse_pos = pygame.mouse.get_pos()

        # Title
        title = self.font.render(f"Location: {self.location_name}", True, WHITE)
        title_rect = title.get_rect(center=(self.x + self.width // 2, self.y + 28))
        screen.blit(title, title_rect)

        # Close button
        close_rect = pygame.Rect(self.x + self.width - 32, self.y + 8, 26, 26)
        close_hovered = close_rect.collidepoint(mouse_pos)
        pygame.draw.rect(screen, (180, 60, 60) if close_hovered else (150, 50, 50),
                        close_rect, border_radius=6)
        close_text = self.font.render("X", True, WHITE)
        screen.blit(close_text, close_text.get_rect(center=close_rect.center))

        # Your cards
        own_label = self.small_font.render("Your Cards:", True, GREEN)
        screen.blit(own_label, (self.x + 20, self.y + 58))

        self._draw_own_cards_row(screen, self.own_cards, self.x + 20, self.y + 82, mouse_pos)

        # Movement section
        if self.selected_card_index is not None and self.can_move:
            self._draw_movement_section(screen, self.y + 220, mouse_pos)

        # Divider
        mid_y = self.y + 260
        pygame.draw.line(screen, (100, 95, 88),
                        (self.x + 20, mid_y), (self.x + self.width - 20, mid_y), 2)

        # Enemy cards
        if self.can_see_enemy:
            enemy_label = self.small_font.render("Enemy Cards:", True, RED)
            screen.blit(enemy_label, (self.x + 20, mid_y + 15))
            self._draw_cards_row(screen, self.enemy_cards, self.x + 20, mid_y + 40, True)
        else:
            fog_label = self.small_font.render("Enemy Cards: [NO INTEL]", True, DARK_GRAY)
            screen.blit(fog_label, (self.x + 20, mid_y + 15))
            fog_text = self.font.render("No presence - enemy hidden", True, (110, 110, 110))
            fog_rect = fog_text.get_rect(center=(self.x + self.width // 2, mid_y + 90))
            screen.blit(fog_text, fog_rect)

    def _draw_own_cards_row(self, screen: pygame.Surface, cards: list, x: int, y: int, mouse_pos: tuple):
        """Draw own cards with selection."""
        if not cards:
            no_cards = self.small_font.render("No cards", True, GRAY)
            screen.blit(no_cards, (x, y + 40))
            return

        spacing = 12
        for i, card in enumerate(cards):
            card_x = x + i * (self.THUMB_WIDTH + spacing)

            if card_x + self.THUMB_WIDTH > self.x + self.width - 20:
                more = self.small_font.render(f"+{len(cards) - i} more", True, GRAY)
                screen.blit(more, (card_x, y + 50))
                break

            card_id = card.get("card_id", "Unknown")
            card_info = self.cards_info.get(card_id, card)

            card_rect = pygame.Rect(card_x, y, self.THUMB_WIDTH, self.THUMB_HEIGHT)
            self._card_rects.append((card_rect, i, card))

            is_hovered = card_rect.collidepoint(mouse_pos)
            is_selected = self.selected_card_index == i

            # Selection glow
            if is_selected:
                glow = pygame.Surface((self.THUMB_WIDTH + 12, self.THUMB_HEIGHT + 12), pygame.SRCALPHA)
                pygame.draw.rect(glow, (255, 200, 50, 150),
                               (0, 0, self.THUMB_WIDTH + 12, self.THUMB_HEIGHT + 12), border_radius=8)
                screen.blit(glow, (card_x - 6, y - 6))

            # Hover effect
            if is_hovered and not is_selected:
                hover = pygame.Surface((self.THUMB_WIDTH + 6, self.THUMB_HEIGHT + 6), pygame.SRCALPHA)
                pygame.draw.rect(hover, (255, 255, 255, 60),
                               (0, 0, self.THUMB_WIDTH + 6, self.THUMB_HEIGHT + 6), border_radius=7)
                screen.blit(hover, (card_x - 3, y - 3))

            thumb = self._get_card_thumbnail(card_id, card_info)
            screen.blit(thumb, (card_x, y))

            # Status indicator (tapped, just placed, or moved)
            can_move = card.get("can_move", True)
            is_tapped = card.get("is_tapped", False)
            has_moved = card.get("has_moved_this_turn", False)

            if is_tapped or not can_move:
                tapped_overlay = pygame.Surface((self.THUMB_WIDTH, self.THUMB_HEIGHT), pygame.SRCALPHA)
                pygame.draw.rect(tapped_overlay, (80, 80, 80, 160),
                               (0, 0, self.THUMB_WIDTH, self.THUMB_HEIGHT), border_radius=6)
                screen.blit(tapped_overlay, (card_x, y))
                tapped_font = pygame.font.Font(None, 18)

                # Determine label
                if has_moved:
                    label = "MOVED"
                elif not can_move:
                    label = "NEW"  # Just placed this turn
                else:
                    label = "TAPPED"

                tapped_text = tapped_font.render(label, True, (255, 200, 100))
                text_rect = tapped_text.get_rect(center=(card_x + self.THUMB_WIDTH // 2, y + self.THUMB_HEIGHT // 2))
                screen.blit(tapped_text, text_rect)

    def _draw_cards_row(self, screen: pygame.Surface, cards: list, x: int, y: int, visible: bool):
        """Draw enemy cards row."""
        if not cards:
            no_cards = self.small_font.render("No cards", True, GRAY)
            screen.blit(no_cards, (x, y + 40))
            return

        spacing = 12
        for i, card in enumerate(cards):
            card_x = x + i * (self.THUMB_WIDTH + spacing)

            if card_x + self.THUMB_WIDTH > self.x + self.width - 20:
                more = self.small_font.render(f"+{len(cards) - i} more", True, GRAY)
                screen.blit(more, (card_x, y + 50))
                break

            card_id = card.get("card_id", "Unknown")
            card_info = self.cards_info.get(card_id, card)

            if visible:
                thumb = self._get_card_thumbnail(card_id, card_info)
            else:
                thumb = self._get_card_back()

            screen.blit(thumb, (card_x, y))

            if visible and card.get("is_tapped"):
                tapped_overlay = pygame.Surface((self.THUMB_WIDTH, self.THUMB_HEIGHT), pygame.SRCALPHA)
                pygame.draw.rect(tapped_overlay, (80, 80, 80, 150),
                               (0, 0, self.THUMB_WIDTH, self.THUMB_HEIGHT), border_radius=6)
                screen.blit(tapped_overlay, (card_x, y))
                tapped_font = pygame.font.Font(None, 17)
                tapped_text = tapped_font.render("TAPPED", True, (255, 200, 100))
                screen.blit(tapped_text, tapped_text.get_rect(center=(card_x + self.THUMB_WIDTH // 2,
                                                                       y + self.THUMB_HEIGHT // 2)))

    def _draw_movement_section(self, screen: pygame.Surface, y: int, mouse_pos: tuple):
        """Draw movement options."""
        selected_card = self.own_cards[self.selected_card_index]
        card_name = selected_card.get("card_id", "Unknown")

        select_text = f"Move {card_name} to:"
        select_surface = self.small_font.render(select_text, True, GOLD)
        screen.blit(select_surface, (self.x + 20, y))

        if not selected_card.get("can_move", True):
            has_moved = selected_card.get("has_moved_this_turn", False)
            if has_moved:
                reason = "(Already moved this turn)"
            else:
                reason = "(Cannot move on the turn it was placed)"
            cant_move = self.small_font.render(reason, True, (180, 100, 100))
            screen.blit(cant_move, (self.x + 20, y + 22))
            return

        btn_x = self.x + 20
        btn_y = y + 25
        for dest in self.adjacent_locations:
            btn_text = self.small_font.render(dest, True, WHITE)
            btn_width = btn_text.get_width() + 20
            btn_rect = pygame.Rect(btn_x, btn_y, btn_width, 26)

            is_hovered = btn_rect.collidepoint(mouse_pos)
            btn_color = (80, 150, 80) if is_hovered else (65, 125, 65)
            pygame.draw.rect(screen, btn_color, btn_rect, border_radius=5)
            pygame.draw.rect(screen, (100, 180, 100), btn_rect, 1, border_radius=5)
            screen.blit(btn_text, btn_text.get_rect(center=btn_rect.center))

            self._move_buttons.append((btn_rect, dest))
            btn_x += btn_width + 10

    def handle_click(self, pos: tuple) -> dict | bool:
        """Handle click. Returns action dict or True to close."""
        if not self.is_visible:
            return False

        close_rect = pygame.Rect(self.x + self.width - 32, self.y + 8, 26, 26)
        if close_rect.collidepoint(pos):
            self.hide()
            return True

        panel_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        if not panel_rect.collidepoint(pos):
            self.hide()
            return True

        # Move buttons
        for btn_rect, destination in self._move_buttons:
            if btn_rect.collidepoint(pos):
                if self.selected_card_index is not None:
                    card = self.own_cards[self.selected_card_index]
                    if card.get("can_move", True):
                        return {
                            "action": "move",
                            "from_location": self.location_name,
                            "to_location": destination,
                            "card_index": self.selected_card_index
                        }

        # Card selection
        for card_rect, index, card in self._card_rects:
            if card_rect.collidepoint(pos):
                if self.selected_card_index == index:
                    self.selected_card_index = None
                else:
                    self.selected_card_index = index
                return False

        return False

    def resize(self, screen_width: int, screen_height: int):
        """Handle resize."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2


class CombatSelector:
    """UI for selecting combat targets (Hearthstone-style)."""

    CARD_WIDTH = 100
    CARD_HEIGHT = 140

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.is_visible = False

        self.location_name = ""
        self.zone_name = "middle_zone"
        self.blocker_side = "defender"
        self.attacker_cards = []  # Cards attacking this zone
        self.defender_cards = []  # Our cards that can block
        self.cards_info = {}

        self.assignments = {}  # attacker_index -> defender_index or None
        self.selected_attacker = None

        self.font = pygame.font.Font(None, 28)
        self.small_font = pygame.font.Font(None, 22)

        self.width = 700
        self.height = 520
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2

        self._card_cache = {}
        self._attacker_rects = []
        self._defender_rects = []

        self.panel_scale = AnimatedValue(0, speed=14.0)

    def _render_card(self, card_id: str, card_info: dict) -> pygame.Surface:
        """Render a card for combat."""
        cache_key = f"combat_{card_id}"
        if cache_key in self._card_cache:
            return self._card_cache[cache_key]

        surf = pygame.Surface((self.CARD_WIDTH, self.CARD_HEIGHT), pygame.SRCALPHA)

        pygame.draw.rect(surf, (245, 235, 220),
                        (0, 0, self.CARD_WIDTH, self.CARD_HEIGHT), border_radius=6)
        pygame.draw.rect(surf, (139, 90, 43),
                        (0, 0, self.CARD_WIDTH, self.CARD_HEIGHT), 2, border_radius=6)

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
                surf.blit(unit_img, (img_x, 24))
            except pygame.error:
                pass

        name = card_info.get("name", card_id)[:12]
        attack = card_info.get("attack", 0)
        health = card_info.get("health", 0)

        tiny_font = pygame.font.Font(None, 16)

        name_text = tiny_font.render(name, True, (50, 40, 30))
        name_rect = name_text.get_rect(centerx=self.CARD_WIDTH // 2, top=4)
        surf.blit(name_text, name_rect)

        stats_y = self.CARD_HEIGHT - 14
        pygame.draw.circle(surf, (200, 60, 60), (14, stats_y), 10)
        atk_text = tiny_font.render(str(attack), True, WHITE)
        surf.blit(atk_text, atk_text.get_rect(center=(14, stats_y)))

        pygame.draw.circle(surf, (60, 160, 60), (self.CARD_WIDTH - 14, stats_y), 10)
        hp_text = tiny_font.render(str(health), True, WHITE)
        surf.blit(hp_text, hp_text.get_rect(center=(self.CARD_WIDTH - 14, stats_y)))

        self._card_cache[cache_key] = surf
        return surf

    def show(self, location_name: str, zone_name: str, attacker_cards: list,
             defender_cards: list, cards_info: dict, blocker_side: str = "defender"):
        """Show combat selector for a specific zone."""
        self.location_name = location_name
        self.zone_name = zone_name
        self.blocker_side = blocker_side
        self.attacker_cards = attacker_cards
        self.defender_cards = defender_cards
        self.cards_info = cards_info
        self.assignments = {}
        self.selected_attacker = None
        self.is_visible = True
        self.panel_scale.set(1.0)

    def hide(self):
        """Hide selector."""
        self.is_visible = False
        self.panel_scale.set(0)

    def update(self, dt: float):
        """Update animations."""
        self.panel_scale.update(dt)

    def draw(self, screen: pygame.Surface):
        """Draw the combat selector."""
        if not self.is_visible:
            return

        self._attacker_rects = []
        self._defender_rects = []

        # Overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        alpha = max(0, min(255, int(200 * self.panel_scale.value)))
        overlay.fill((0, 0, 0, alpha))
        screen.blit(overlay, (0, 0))

        scale = self.panel_scale.value
        if scale < 0.01:
            return

        scaled_w = int(self.width * scale)
        scaled_h = int(self.height * scale)
        panel_x = self.screen_width // 2 - scaled_w // 2
        panel_y = self.screen_height // 2 - scaled_h // 2

        # Panel
        panel_rect = pygame.Rect(panel_x, panel_y, scaled_w, scaled_h)
        pygame.draw.rect(screen, (50, 45, 45), panel_rect, border_radius=12)
        pygame.draw.rect(screen, (150, 80, 80), panel_rect, 3, border_radius=12)

        if scale < 0.9:
            return

        mouse_pos = pygame.mouse.get_pos()

        # Title - include zone info
        zone_display = self.zone_name.replace("_", " ").title()
        title = self.font.render(f"COMBAT at {self.location_name} ({zone_display})", True, (255, 200, 100))
        title_rect = title.get_rect(center=(self.x + self.width // 2, self.y + 28))
        screen.blit(title, title_rect)

        subtitle = self.small_font.render("Choose which of your cards blocks each attacker", True, GRAY)
        sub_rect = subtitle.get_rect(center=(self.x + self.width // 2, self.y + 52))
        screen.blit(subtitle, sub_rect)

        # Attackers (top row)
        atk_label = self.small_font.render("ATTACKING:", True, RED)
        screen.blit(atk_label, (self.x + 20, self.y + 75))

        atk_start_x = self.x + 30
        atk_y = self.y + 100
        spacing = 15

        for i, card in enumerate(self.attacker_cards):
            card_x = atk_start_x + i * (self.CARD_WIDTH + spacing)
            card_id = card.get("card_id", "Unknown")
            card_info = self.cards_info.get(card_id, card)

            card_rect = pygame.Rect(card_x, atk_y, self.CARD_WIDTH, self.CARD_HEIGHT)
            self._attacker_rects.append((card_rect, i))

            is_selected = self.selected_attacker == i
            is_assigned = i in self.assignments

            # Highlight selected
            if is_selected:
                glow = pygame.Surface((self.CARD_WIDTH + 10, self.CARD_HEIGHT + 10), pygame.SRCALPHA)
                pygame.draw.rect(glow, (255, 100, 100, 180),
                               (0, 0, self.CARD_WIDTH + 10, self.CARD_HEIGHT + 10), border_radius=8)
                screen.blit(glow, (card_x - 5, atk_y - 5))

            card_surf = self._render_card(card_id, card_info)
            screen.blit(card_surf, (card_x, atk_y))

            # Show assignment
            if is_assigned:
                def_idx = self.assignments[i]
                if def_idx is not None:
                    arrow_start = (card_x + self.CARD_WIDTH // 2, atk_y + self.CARD_HEIGHT + 5)
                    def_card_x = atk_start_x + def_idx * (self.CARD_WIDTH + spacing)
                    arrow_end = (def_card_x + self.CARD_WIDTH // 2, self.y + 295)
                    pygame.draw.line(screen, GOLD, arrow_start, arrow_end, 3)
                    # Arrow head
                    pygame.draw.polygon(screen, GOLD, [
                        arrow_end,
                        (arrow_end[0] - 6, arrow_end[1] - 10),
                        (arrow_end[0] + 6, arrow_end[1] - 10)
                    ])

        # Defenders (bottom row)
        def_label = self.small_font.render("YOUR BLOCKERS:", True, GREEN)
        screen.blit(def_label, (self.x + 20, self.y + 270))

        def_y = self.y + 295

        for i, card in enumerate(self.defender_cards):
            card_x = atk_start_x + i * (self.CARD_WIDTH + spacing)
            card_id = card.get("card_id", "Unknown")
            card_info = self.cards_info.get(card_id, card)

            card_rect = pygame.Rect(card_x, def_y, self.CARD_WIDTH, self.CARD_HEIGHT)
            self._defender_rects.append((card_rect, i))

            # Check if assigned
            assigned_to = [k for k, v in self.assignments.items() if v == i]
            is_assigned = len(assigned_to) > 0

            is_hovered = card_rect.collidepoint(mouse_pos) and self.selected_attacker is not None

            if is_hovered:
                glow = pygame.Surface((self.CARD_WIDTH + 8, self.CARD_HEIGHT + 8), pygame.SRCALPHA)
                pygame.draw.rect(glow, (100, 255, 100, 120),
                               (0, 0, self.CARD_WIDTH + 8, self.CARD_HEIGHT + 8), border_radius=7)
                screen.blit(glow, (card_x - 4, def_y - 4))

            card_surf = self._render_card(card_id, card_info)
            screen.blit(card_surf, (card_x, def_y))

            if is_assigned:
                badge = pygame.Surface((24, 24), pygame.SRCALPHA)
                pygame.draw.circle(badge, GOLD, (12, 12), 12)
                num_text = self.small_font.render(str(len(assigned_to)), True, (50, 40, 30))
                badge.blit(num_text, num_text.get_rect(center=(12, 12)))
                screen.blit(badge, (card_x + self.CARD_WIDTH - 20, def_y - 5))

        # Instructions
        if self.selected_attacker is not None:
            inst = self.small_font.render("Click a defender to assign, or click attacker again to unassign",
                                          True, (200, 200, 150))
        else:
            inst = self.small_font.render("Click an attacker to select it, then click a defender to block",
                                          True, GRAY)
        inst_rect = inst.get_rect(center=(self.x + self.width // 2, self.y + self.height - 55))
        screen.blit(inst, inst_rect)

        # Confirm button
        confirm_rect = pygame.Rect(self.x + self.width // 2 - 70, self.y + self.height - 45, 140, 38)
        confirm_hovered = confirm_rect.collidepoint(mouse_pos)
        pygame.draw.rect(screen, (80, 150, 80) if confirm_hovered else (60, 120, 60),
                        confirm_rect, border_radius=8)
        pygame.draw.rect(screen, (100, 180, 100), confirm_rect, 2, border_radius=8)
        confirm_text = self.font.render("Confirm", True, WHITE)
        screen.blit(confirm_text, confirm_text.get_rect(center=confirm_rect.center))

    def handle_click(self, pos: tuple) -> dict | None:
        """Handle click. Returns combat assignments or None."""
        if not self.is_visible:
            return None

        # Confirm button
        confirm_rect = pygame.Rect(self.x + self.width // 2 - 70, self.y + self.height - 45, 140, 38)
        if confirm_rect.collidepoint(pos):
            # Convert single blocker indices to lists (server expects lists)
            list_assignments = {}
            for atk_idx, blocker_idx in self.assignments.items():
                if blocker_idx is not None:
                    list_assignments[atk_idx] = [blocker_idx]
                else:
                    list_assignments[atk_idx] = []
            result = {
                "action": "combat_assignments",
                "location": self.location_name,
                "assignments": list_assignments
            }
            self.hide()
            return result

        # Attacker selection
        for rect, idx in self._attacker_rects:
            if rect.collidepoint(pos):
                if self.selected_attacker == idx:
                    # Unassign
                    if idx in self.assignments:
                        del self.assignments[idx]
                    self.selected_attacker = None
                else:
                    self.selected_attacker = idx
                return None

        # Defender selection (assign)
        if self.selected_attacker is not None:
            for rect, idx in self._defender_rects:
                if rect.collidepoint(pos):
                    self.assignments[self.selected_attacker] = idx
                    self.selected_attacker = None
                    return None

        return None

    def resize(self, screen_width: int, screen_height: int):
        """Handle resize."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2


class ThinClient:
    """Thin client for WarMasterMind multiplayer with smooth animations."""

    CONNECTIONS = [
        ("Camp", "Forest"), ("Camp", "Gate"), ("Camp", "Walls"),
        ("Forest", "Walls"), ("Forest", "Sewers"),
        ("Gate", "Courtyard"), ("Walls", "Courtyard"), ("Walls", "Keep"),
        ("Sewers", "Keep"), ("Courtyard", "Keep"),
    ]

    LAYOUT = {
        "Camp": (0, 0), "Forest": (0, 1),
        "Gate": (1, 0), "Walls": (1, 1), "Sewers": (1, 2),
        "Courtyard": (2, 0), "Keep": (2, 1),
    }

    ADJACENCY = {
        "Camp": ["Forest", "Gate", "Walls"],
        "Forest": ["Camp", "Walls", "Sewers"],
        "Gate": ["Camp", "Courtyard"],
        "Walls": ["Camp", "Forest", "Courtyard", "Keep"],
        "Sewers": ["Forest", "Keep"],
        "Courtyard": ["Gate", "Walls", "Keep"],
        "Keep": ["Walls", "Sewers", "Courtyard"],
    }

    def __init__(self, server_url: str = "ws://localhost:8765"):
        pygame.init()
        pygame.mixer.init()
        pygame.display.set_caption("WarMasterMind - Online")

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.running = True

        self.screen_width = SCREEN_WIDTH
        self.screen_height = SCREEN_HEIGHT

        # Music
        self.game_music_playing = False

        self.title_font = pygame.font.Font(None, 72)
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)

        self.network = NetworkClient(server_url)
        self.network.on_game_state = self._on_game_state
        self.network.on_match_found = self._on_match_found
        self.network.on_action_result = self._on_action_result
        self.network.on_error = self._on_error
        self.network.on_register_result = self._on_register_result
        self.network.on_friends_list = self._on_friends_list
        self.network.on_friend_request = self._on_friend_request
        self.network.on_friend_request_result = self._on_friend_request_result
        self.network.on_friend_status = self._on_friend_status

        self.state = STATE_LOGIN
        self.game_state = None
        self.match_info = None
        self.match_transition_timer = 0.0
        self.match_transition_duration = 3.5
        self.role_flip_speed = 0.15  # Speed of role flip animation
        self.waiting_for_combat = None  # Location where waiting for opponent's blocker assignment
        self.error_message = None
        self.error_timer = 0
        self.success_message = None
        self.success_timer = 0

        self.username_input = ""
        self.password_input = ""
        self.active_input = "username"
        self.is_registering = False

        self.friends_list = []
        self.pending_requests = []
        self.friend_input = ""

        self.current_deck = []
        self.deck_name = "My Deck"
        self.deck_scroll = 0
        self.card_scroll = 0
        self.user_decks = []
        self.available_cards = {}

        self.selected_card = None
        self.selected_location = None
        self.hovered_location = None
        self.your_role = "attacker"
        self.locations = {}

        self.hand_cards: list[AnimatedCard] = []
        self.focused_hand_card: AnimatedCard | None = None
        self.dragging_card: AnimatedCard | None = None
        self.opponent_hand_count = 0  # Track opponent's hand card count

        self._card_cache = {}
        self._reinforcement_rects = []  # For hover detection on incoming cards

        self.draw_menu = DrawMenu(self.screen_width, self.screen_height)
        self.location_panel = LocationPanel(self.screen_width, self.screen_height)
        self.combat_selector = CombatSelector(self.screen_width, self.screen_height)

        self.ui_anim = UIAnimation()
        self.turn_flash = 0
        self.bg_particles = []
        self.reinforcements = []

        self._setup_locations()
        self._init_particles()

    def _init_particles(self):
        import random
        self.bg_particles = []
        for _ in range(30):
            self.bg_particles.append({
                "x": random.randint(0, self.screen_width),
                "y": random.randint(0, self.screen_height),
                "size": random.uniform(1, 3),
                "speed": random.uniform(10, 30),
                "alpha": random.randint(20, 60)
            })

    def _update_particles(self, dt: float):
        import random
        for p in self.bg_particles:
            p["y"] -= p["speed"] * dt
            if p["y"] < -10:
                p["y"] = self.screen_height + 10
                p["x"] = random.randint(0, self.screen_width)

    def _draw_particles(self, screen: pygame.Surface):
        for p in self.bg_particles:
            surf = pygame.Surface((int(p["size"] * 2), int(p["size"] * 2)), pygame.SRCALPHA)
            pygame.draw.circle(surf, (100, 100, 120, p["alpha"]),
                             (int(p["size"]), int(p["size"])), int(p["size"]))
            screen.blit(surf, (int(p["x"]), int(p["y"])))

    def _setup_locations(self):
        center_x = self.screen_width // 2
        center_y = self.screen_height // 2 - 40
        zone_width, zone_height = 155, 85
        h_spacing, v_spacing = 185, 105

        row_ys = [center_y + v_spacing, center_y, center_y - v_spacing]
        if self.your_role == "defender":
            row_ys = list(reversed(row_ys))

        self.locations.clear()
        for name, (row, pos) in self.LAYOUT.items():
            num_in_row = 2 if row in [0, 2] else 3
            x = center_x + ((pos - 0.5) * h_spacing * 1.2 if num_in_row == 2 else (pos - 1) * h_spacing)
            self.locations[name] = pygame.Rect(int(x - zone_width // 2), int(row_ys[row] - zone_height // 2),
                                               zone_width, zone_height)

    def _on_game_state(self, state: dict):
        old_turn = self.game_state.get("turn") if self.game_state else 0
        self.game_state = state
        new_role = state.get("your_role", "attacker")
        if new_role != self.your_role:
            self.your_role = new_role
            self._setup_locations()
        self.reinforcements = state.get("reinforcements", [])
        self._update_hand_cards()
        if state.get("turn", 0) > old_turn:
            self.turn_flash = 1.0

        # Check for game over (winner in game state)
        winner = state.get("winner")
        if winner:
            self.winner = winner
            self.state = STATE_GAME_OVER
            return

        # Handle combat phase (Hearthstone-style blocker assignment with zones)
        combat_state = state.get("combat_state")
        if combat_state:
            if combat_state.get("is_your_turn_to_assign"):
                # Blocker side needs to assign blockers
                location = combat_state.get("location", "")
                zone = combat_state.get("zone", "middle_zone")
                attackers = combat_state.get("attackers", [])
                blockers = combat_state.get("your_blockers", [])
                blocker_side = combat_state.get("blocker_side", "defender")
                self.combat_selector.show(location, zone, attackers, blockers, self.available_cards, blocker_side)
                self.state = STATE_COMBAT_SELECT
            else:
                # Waiting for opponent to assign blockers
                self.combat_selector.hide()
                self.waiting_for_combat = combat_state.get("location", "")
        else:
            # Combat phase ended or not in combat
            if self.state == STATE_COMBAT_SELECT:
                self.combat_selector.hide()
                self.state = STATE_GAME
            self.waiting_for_combat = None

    def _update_hand_cards(self):
        if not self.game_state:
            self.hand_cards = []
            return
        hand = self.game_state.get("hand", [])
        self.opponent_hand_count = self.game_state.get("opponent_hand_count", 0)
        current_ids = {c.get("card_id") for c in hand}
        self.hand_cards = [c for c in self.hand_cards if c.card_id in current_ids]
        existing_ids = {c.card_id for c in self.hand_cards}
        for card_data in hand:
            if card_data.get("card_id") not in existing_ids:
                self.hand_cards.append(AnimatedCard(card_data, self.screen_width // 2, self.screen_height + 100))
        self._reorganize_hand()

    def _reorganize_hand(self):
        if not self.hand_cards:
            return
        num = len(self.hand_cards)
        hand_y = self.screen_height - 160
        center_x = self.screen_width // 2
        arc_span = min(math.pi * 0.35, num * 0.08)
        start_a, end_a = math.pi / 2 - arc_span / 2, math.pi / 2 + arc_span / 2
        radius_x, radius_y = self.screen_width * 0.32, 120
        for i, card in enumerate(self.hand_cards):
            angle = math.pi / 2 if num == 1 else start_a + (end_a - start_a) * (i / (num - 1))
            x = center_x + radius_x * math.cos(angle)
            y = hand_y + 60 - radius_y * math.sin(angle)
            card.set_position(x, y, (angle - math.pi / 2) * 20)

    def _play_game_music(self):
        """Play background music for the match."""
        if self.game_music_playing:
            return
        try:
            music_path = os.path.join("resources", "Songs", "CastleSong.mp3")
            if os.path.exists(music_path):
                pygame.mixer.music.load(music_path)
                pygame.mixer.music.set_volume(0.5)  # 50% volume
                pygame.mixer.music.play(-1)  # Loop infinitely
                self.game_music_playing = True
                print(f"[MUSIC] Playing game music: {music_path}")
        except Exception as e:
            print(f"[MUSIC] Error loading music: {e}")

    def _stop_game_music(self):
        """Stop the background music."""
        if self.game_music_playing:
            try:
                pygame.mixer.music.stop()
                self.game_music_playing = False
                print("[MUSIC] Stopping game music")
            except Exception as e:
                print(f"[MUSIC] Error stopping music: {e}")

    def _on_match_found(self, data): self.match_info = data; self.match_transition_timer = 0.0; self.state = STATE_MATCH_START; self._play_game_music()
    def _on_action_result(self, data):
        if data.get("winner"): self.state = STATE_GAME_OVER; self.winner = data["winner"]
    def _on_error(self, e): self.error_message = e; self.error_timer = 3.0
    def _on_register_result(self, ok, msg):
        if ok: self.success_message = msg; self.success_timer = 3.0; self.is_registering = False; self.password_input = ""
        else: self.error_message = msg; self.error_timer = 3.0
    def _on_friends_list(self, f): self.friends_list = f
    def _on_friend_request(self, d): self.success_message = f"Friend request from {d.get('from_username', '?')}!"; self.success_timer = 3.0
    def _on_friend_request_result(self, d):
        if d.get("success"): self.success_message = d.get("message", "Success!"); self.success_timer = 2.0; self.network.get_friends()
        else: self.error_message = d.get("message", "Failed"); self.error_timer = 3.0
    def _on_friend_status(self, d):
        if d.get("action") == "accepted": self.success_message = f"{d.get('friend_username', '?')} accepted!"; self.success_timer = 3.0

    def connect(self) -> bool: return self.network.connect()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: self.running = False
            elif event.type == pygame.VIDEORESIZE:
                self.screen_width, self.screen_height = event.w, event.h
                self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                self._setup_locations(); self._reorganize_hand()
                self.draw_menu.resize(event.w, event.h)
                self.location_panel.resize(event.w, event.h)
                self.combat_selector.resize(event.w, event.h)
                # Clear sized deck card cache on resize
                self._card_cache = {k: v for k, v in self._card_cache.items() if not k.startswith("deck_") or k.count("_") < 3}
            elif event.type == pygame.MOUSEMOTION: self._handle_mouse_motion(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: self._handle_click(event.pos)
                elif event.button == 4: self._handle_scroll(1)
                elif event.button == 5: self._handle_scroll(-1)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1: self._handle_mouse_up(event.pos)
            elif event.type == pygame.KEYDOWN: self._handle_key(event)

    def _handle_scroll(self, d):
        if self.state == STATE_DECK_BUILDER:
            mouse_pos = pygame.mouse.get_pos()
            dx = self.screen_width - 300

            # Check if mouse is over deck list area (right panel)
            deck_list_y = 100
            deck_list_height = self.screen_height - 130
            deck_item_height = 35
            visible_items = deck_list_height // deck_item_height

            if not hasattr(self, 'deck_scroll'):
                self.deck_scroll = 0

            # If mouse is over deck list panel, scroll the deck
            if mouse_pos[0] >= dx:
                max_deck_scroll = max(0, len(self.current_deck) - visible_items)
                if d > 0:
                    self.deck_scroll = max(0, self.deck_scroll - 1)
                else:
                    self.deck_scroll = min(max_deck_scroll, self.deck_scroll + 1)
            else:
                # Scroll available cards grid
                cpr = 5
                rows = 2
                cards_per_page = cpr * rows
                max_scroll = max(0, (len(self.available_cards) - cards_per_page) // cpr + 1)
                if d > 0:
                    self.card_scroll = max(0, self.card_scroll - 1)
                else:
                    self.card_scroll = min(max_scroll, self.card_scroll + 1)

    def _handle_mouse_motion(self, pos):
        if self.draw_menu.is_visible or self.location_panel.is_visible or self.combat_selector.is_visible: return
        self.hovered_location = None
        if self.state == STATE_GAME:
            for name, rect in self.locations.items():
                if rect.collidepoint(pos): self.hovered_location = name; break
            if self.dragging_card: self.dragging_card.update_drag(pos)
            else:
                new_focus = None
                for card in reversed(self.hand_cards):
                    if card.contains_point(pos): new_focus = card; break
                if new_focus != self.focused_hand_card:
                    if self.focused_hand_card: self.focused_hand_card.set_hover(False)
                    if new_focus: new_focus.set_hover(True)
                    self.focused_hand_card = new_focus

    def _handle_click(self, pos):
        if self.draw_menu.is_visible:
            r = self.draw_menu.handle_click(pos)
            if r and r != "close": self.network.draw_card(r)
            return
        if self.location_panel.is_visible:
            r = self.location_panel.handle_click(pos)
            if isinstance(r, dict) and r.get("action") == "move":
                self.network.move_card(r["from_location"], r["to_location"], r["card_index"])
                self.location_panel.hide()
            return
        if self.combat_selector.is_visible:
            r = self.combat_selector.handle_click(pos)
            if r: self.network.send({"type": "game_action", "action": r})
            return
        if self.state == STATE_LOGIN: self._handle_login_click(pos)
        elif self.state == STATE_LOBBY: self._handle_lobby_click(pos)
        elif self.state == STATE_FRIENDS: self._handle_friends_click(pos)
        elif self.state == STATE_DECK_BUILDER: self._handle_deck_builder_click(pos)
        elif self.state == STATE_GAME: self._handle_game_click(pos)
        elif self.state == STATE_GAME_OVER: self.state = STATE_LOBBY; self.game_state = None; self._stop_game_music()
        elif self.state == STATE_MATCH_START: self.state = STATE_GAME

    def _handle_mouse_up(self, pos):
        if self.state == STATE_GAME and self.dragging_card:
            for name, rect in self.locations.items():
                if rect.collidepoint(pos): self.network.place_card(self.dragging_card.card_id, name); break
            self.dragging_card.return_to_position(); self.dragging_card = None

    def _handle_login_click(self, pos):
        ur = pygame.Rect(self.screen_width // 2 - 150, 280, 300, 40)
        pr = pygame.Rect(self.screen_width // 2 - 150, 340, 300, 40)
        sr = pygame.Rect(self.screen_width // 2 - 100, 420, 200, 50)
        tr = pygame.Rect(self.screen_width // 2 - 100, 490, 200, 30)
        if ur.collidepoint(pos): self.active_input = "username"
        elif pr.collidepoint(pos): self.active_input = "password"
        elif sr.collidepoint(pos) and self.username_input and self.password_input:
            (self.network.register if self.is_registering else self.network.login)(self.username_input, self.password_input)
        elif tr.collidepoint(pos): self.is_registering = not self.is_registering

    def _handle_lobby_click(self, pos):
        if pygame.Rect(self.screen_width // 2 - 100, 300, 200, 50).collidepoint(pos): self.network.find_match(); self.state = STATE_MATCHMAKING
        elif pygame.Rect(self.screen_width // 2 - 100, 370, 200, 50).collidepoint(pos): self.state = STATE_FRIENDS; self.network.get_friends(); self.network.send({"type": "get_pending_requests"})
        elif pygame.Rect(self.screen_width // 2 - 100, 440, 200, 50).collidepoint(pos): self.state = STATE_DECK_BUILDER; self.network.get_decks(); self.network.get_cards()

    def _handle_friends_click(self, pos):
        if pygame.Rect(20, 20, 100, 40).collidepoint(pos): self.state = STATE_LOBBY; return
        if pygame.Rect(self.screen_width // 2 + 80, 120, 80, 40).collidepoint(pos) and self.friend_input:
            self.network.send_friend_request(self.friend_input); self.friend_input = ""

    def _handle_deck_builder_click(self, pos):
        if pygame.Rect(20, 20, 100, 40).collidepoint(pos): self.state = STATE_LOBBY; return
        if pygame.Rect(self.screen_width - 120, 20, 100, 40).collidepoint(pos) and self.current_deck:
            self.network.save_deck(self.deck_name, self.current_deck, is_active=True); return
        if pygame.Rect(self.screen_width - 230, 20, 100, 40).collidepoint(pos): self.current_deck = []; return

        cards_list = sorted(self.available_cards.keys())
        # Match the drawing code: 5 columns, 2 rows with calculated sizes
        cpr = 5
        rows = 2
        deck_panel_width = 310
        available_width = self.screen_width - 40 - deck_panel_width
        sp = 10
        card_w = (available_width - sp * (cpr - 1)) // cpr
        available_height = self.screen_height - 180
        max_card_h = (available_height - sp * (rows - 1)) // rows
        card_h = min(int(card_w * 1.4), max_card_h)
        cards_per_page = rows * cpr
        vs = self.card_scroll * cpr

        for i, cid in enumerate(cards_list[vs:vs + cards_per_page]):
            r, c = i // cpr, i % cpr
            rect = pygame.Rect(20 + c * (card_w + sp), 100 + r * (card_h + sp), card_w, card_h)
            if rect.collidepoint(pos) and len(self.current_deck) < 30 and self.current_deck.count(cid) < 2:
                self.current_deck.append(cid); return

        # Handle deck list clicks (scrollable)
        dx = self.screen_width - 300
        deck_list_y = 100
        deck_item_height = 35
        deck_list_height = self.screen_height - 130
        visible_items = deck_list_height // deck_item_height

        if not hasattr(self, 'deck_scroll'):
            self.deck_scroll = 0

        for i in range(visible_items):
            deck_idx = i + self.deck_scroll
            if deck_idx >= len(self.current_deck):
                break
            cr = pygame.Rect(dx, deck_list_y + i * deck_item_height, 260, deck_item_height - 3)
            if cr.collidepoint(pos):
                self.current_deck.pop(deck_idx)
                # Adjust scroll if needed
                max_deck_scroll = max(0, len(self.current_deck) - visible_items)
                self.deck_scroll = min(self.deck_scroll, max_deck_scroll)
                return

    def _handle_game_click(self, pos):
        if not self.game_state: return
        for card in reversed(self.hand_cards):
            if card.contains_point(pos): card.start_drag(pos); self.dragging_card = card; return
        for name, rect in self.locations.items():
            if rect.collidepoint(pos): self._show_location_panel(name); return
        if pygame.Rect(self.screen_width - 150, 20, 130, 40).collidepoint(pos) and self.game_state.get("is_your_turn"):
            self.network.end_turn(); return
        if pygame.Rect(self.screen_width - 120, self.screen_height - 180, 100, 140).collidepoint(pos):
            if self.game_state.get("is_your_turn") and self.game_state.get("can_draw"):
                dc = self.game_state.get("deck_cards", [])
                if dc: self.draw_menu.show(dc, self.available_cards)

    def _show_location_panel(self, loc):
        if not self.game_state: return
        bf = self.game_state.get("battlefield", {}).get(loc, {})

        # Aggregate cards from all zones (new 3-zone structure)
        zones = bf.get("zones", {})
        own = []
        ec = []
        for zone_name in ["attacker_zone", "middle_zone", "defender_zone"]:
            zone_data = zones.get(zone_name, {})
            own.extend(zone_data.get("own_cards", []))
            if bf.get("can_see"):
                ec.extend(zone_data.get("enemy_cards", []) or [])

        self.location_panel.show(loc, own, ec, bf.get("can_see", False), self.available_cards,
                                self.game_state.get("is_your_turn", False), self.ADJACENCY.get(loc, []))

    def _handle_key(self, event):
        if self.state == STATE_LOGIN:
            if event.key == pygame.K_TAB: self.active_input = "password" if self.active_input == "username" else "username"
            elif event.key == pygame.K_RETURN and self.username_input and self.password_input:
                (self.network.register if self.is_registering else self.network.login)(self.username_input, self.password_input)
            elif event.key == pygame.K_BACKSPACE:
                if self.active_input == "username": self.username_input = self.username_input[:-1]
                else: self.password_input = self.password_input[:-1]
            elif event.unicode.isprintable() and len(event.unicode) == 1:
                if self.active_input == "username" and len(self.username_input) < 20: self.username_input += event.unicode
                elif self.active_input == "password" and len(self.password_input) < 30: self.password_input += event.unicode
        elif self.state == STATE_FRIENDS:
            if event.key == pygame.K_ESCAPE: self.state = STATE_LOBBY
            elif event.key == pygame.K_BACKSPACE: self.friend_input = self.friend_input[:-1]
            elif event.unicode.isprintable() and len(event.unicode) == 1 and len(self.friend_input) < 20: self.friend_input += event.unicode
        elif self.state == STATE_DECK_BUILDER and event.key == pygame.K_ESCAPE: self.state = STATE_LOBBY
        elif event.key == pygame.K_ESCAPE:
            if self.state == STATE_MATCHMAKING: self.network.cancel_match(); self.state = STATE_LOBBY
            elif self.state == STATE_GAME:
                if self.draw_menu.is_visible: self.draw_menu.hide()
                elif self.location_panel.is_visible: self.location_panel.hide()

    def update(self, dt: float):
        for msg in self.network.process_messages():
            if msg.get("type") == "pending_requests": self.pending_requests = msg.get("incoming", [])
            elif msg.get("type") == "decks":
                self.user_decks = msg.get("decks", [])
                for d in self.user_decks:
                    if d.get("is_active"): self.current_deck = d.get("cards", [])[:]; self.deck_name = d.get("name", "My Deck"); break
            elif msg.get("type") == "cards": self.available_cards = msg.get("cards", {})
            elif msg.get("type") == "deck_saved": self.success_message = "Deck saved!"; self.success_timer = 2.0; self.network.get_decks()
        if self.network.authenticated and self.state == STATE_LOGIN: self.state = STATE_LOBBY; self.network.get_cards()
        if self.error_timer > 0: self.error_timer -= dt;
        if self.error_timer <= 0: self.error_message = None
        if self.success_timer > 0: self.success_timer -= dt
        if self.success_timer <= 0: self.success_message = None
        if self.turn_flash > 0: self.turn_flash -= dt * 2
        for c in self.hand_cards: c.update(dt)
        self.draw_menu.update(dt); self.location_panel.update(dt); self.combat_selector.update(dt)
        self.ui_anim.update(dt); self._update_particles(dt)

    def draw(self):
        self.screen.fill(BG_COLOR); self._draw_particles(self.screen)
        if self.state == STATE_LOGIN: self._draw_login()
        elif self.state == STATE_LOBBY: self._draw_lobby()
        elif self.state == STATE_FRIENDS: self._draw_friends()
        elif self.state == STATE_DECK_BUILDER: self._draw_deck_builder()
        elif self.state == STATE_MATCHMAKING: self._draw_matchmaking()
        elif self.state == STATE_MATCH_START: self._draw_match_start_transition()
        elif self.state in [STATE_GAME, STATE_COMBAT_SELECT]: self._draw_game()
        elif self.state == STATE_GAME_OVER: self._draw_game_over()
        if self.error_message:
            es = self.font.render(self.error_message, True, RED)
            er = es.get_rect(center=(self.screen_width // 2, 50))
            pygame.draw.rect(self.screen, (50, 30, 30), er.inflate(20, 10), border_radius=5)
            self.screen.blit(es, er)
        if self.success_message:
            ss = self.font.render(self.success_message, True, GREEN)
            sr = ss.get_rect(center=(self.screen_width // 2, 50))
            pygame.draw.rect(self.screen, (30, 50, 30), sr.inflate(20, 10), border_radius=5)
            self.screen.blit(ss, sr)
        st = "Connected" if self.network.connected else "Disconnected"
        self.screen.blit(self.small_font.render(st, True, GREEN if self.network.connected else RED), (10, 10))
        pygame.display.flip()

    def _draw_login(self):
        self.screen.blit(self.title_font.render("WarMasterMind", True, (255, 200, 100)),
                        self.title_font.render("WarMasterMind", True, (255, 200, 100)).get_rect(center=(self.screen_width // 2, 120)))
        self.screen.blit(self.small_font.render("Online Multiplayer", True, GRAY),
                        self.small_font.render("Online Multiplayer", True, GRAY).get_rect(center=(self.screen_width // 2, 170)))
        mode = "Register New Account" if self.is_registering else "Login"
        self.screen.blit(self.font.render(mode, True, WHITE), self.font.render(mode, True, WHITE).get_rect(center=(self.screen_width // 2, 230)))
        ur = pygame.Rect(self.screen_width // 2 - 150, 280, 300, 40)
        pygame.draw.rect(self.screen, (100, 100, 150) if self.active_input == "username" else (70, 70, 80), ur, border_radius=5)
        pygame.draw.rect(self.screen, WHITE if self.active_input == "username" else GRAY, ur, 2, border_radius=5)
        self.screen.blit(self.small_font.render("Username:", True, GRAY), (ur.x, ur.y - 20))
        self.screen.blit(self.font.render(self.username_input, True, WHITE), (ur.x + 10, ur.y + 8))
        pr = pygame.Rect(self.screen_width // 2 - 150, 340, 300, 40)
        pygame.draw.rect(self.screen, (100, 100, 150) if self.active_input == "password" else (70, 70, 80), pr, border_radius=5)
        pygame.draw.rect(self.screen, WHITE if self.active_input == "password" else GRAY, pr, 2, border_radius=5)
        self.screen.blit(self.small_font.render("Password:", True, GRAY), (pr.x, pr.y - 20))
        self.screen.blit(self.font.render("*" * len(self.password_input), True, WHITE), (pr.x + 10, pr.y + 8))
        sr = pygame.Rect(self.screen_width // 2 - 100, 420, 200, 50)
        pygame.draw.rect(self.screen, (70, 130, 70), sr, border_radius=8)
        st = "Register" if self.is_registering else "Login"
        self.screen.blit(self.font.render(st, True, WHITE), self.font.render(st, True, WHITE).get_rect(center=sr.center))
        tt = "Already have account? Login" if self.is_registering else "Need account? Register"
        self.screen.blit(self.small_font.render(tt, True, BLUE), self.small_font.render(tt, True, BLUE).get_rect(center=(self.screen_width // 2, 500)))

    def _draw_lobby(self):
        self.screen.blit(self.title_font.render("Lobby", True, WHITE), self.title_font.render("Lobby", True, WHITE).get_rect(center=(self.screen_width // 2, 100)))
        self.screen.blit(self.font.render(f"Welcome, {self.network.username}!", True, GREEN),
                        self.font.render(f"Welcome, {self.network.username}!", True, GREEN).get_rect(center=(self.screen_width // 2, 180)))
        for rect, txt, col in [(pygame.Rect(self.screen_width // 2 - 100, 300, 200, 50), "Find Match", (70, 130, 70)),
                               (pygame.Rect(self.screen_width // 2 - 100, 370, 200, 50), "Friends", (70, 100, 150)),
                               (pygame.Rect(self.screen_width // 2 - 100, 440, 200, 50), "Deck Builder", (130, 100, 70))]:
            pygame.draw.rect(self.screen, col, rect, border_radius=8)
            self.screen.blit(self.font.render(txt, True, WHITE), self.font.render(txt, True, WHITE).get_rect(center=rect.center))

    def _draw_friends(self):
        br = pygame.Rect(20, 20, 100, 40); pygame.draw.rect(self.screen, (100, 70, 70), br, border_radius=5)
        self.screen.blit(self.small_font.render("< Back", True, WHITE), self.small_font.render("< Back", True, WHITE).get_rect(center=br.center))
        self.screen.blit(self.title_font.render("Friends", True, WHITE), self.title_font.render("Friends", True, WHITE).get_rect(center=(self.screen_width // 2, 70)))
        self.screen.blit(self.font.render("Add Friend:", True, GRAY), (self.screen_width // 2 - 150, 95))
        ir = pygame.Rect(self.screen_width // 2 - 150, 120, 220, 40)
        pygame.draw.rect(self.screen, (70, 70, 80), ir, border_radius=5); pygame.draw.rect(self.screen, WHITE, ir, 2, border_radius=5)
        self.screen.blit(self.font.render(self.friend_input, True, WHITE), (ir.x + 10, ir.y + 8))
        ab = pygame.Rect(self.screen_width // 2 + 80, 120, 80, 40); pygame.draw.rect(self.screen, (70, 130, 70), ab, border_radius=5)
        self.screen.blit(self.small_font.render("Add", True, WHITE), self.small_font.render("Add", True, WHITE).get_rect(center=ab.center))
        self.screen.blit(self.font.render(f"Friends ({len(self.friends_list)})", True, GREEN), (self.screen_width // 2 - 150, 200))
        for i, f in enumerate(self.friends_list[:8]):
            y = 230 + i * 35
            pygame.draw.circle(self.screen, GREEN if f.get("is_online") else GRAY, (self.screen_width // 2 - 145, y + 10), 5)
            self.screen.blit(self.small_font.render(f.get("username", "?"), True, WHITE), (self.screen_width // 2 - 130, y))

    def _draw_deck_builder(self):
        br = pygame.Rect(20, 20, 100, 40); pygame.draw.rect(self.screen, (100, 70, 70), br, border_radius=5)
        self.screen.blit(self.small_font.render("< Back", True, WHITE), self.small_font.render("< Back", True, WHITE).get_rect(center=br.center))
        self.screen.blit(self.title_font.render("Deck Builder", True, WHITE), self.title_font.render("Deck Builder", True, WHITE).get_rect(center=(self.screen_width // 2, 40)))
        sv = pygame.Rect(self.screen_width - 120, 20, 100, 40)
        pygame.draw.rect(self.screen, (70, 130, 70) if self.current_deck else (70, 70, 70), sv, border_radius=5)
        self.screen.blit(self.small_font.render("Save Deck", True, WHITE), self.small_font.render("Save Deck", True, WHITE).get_rect(center=sv.center))
        cl = pygame.Rect(self.screen_width - 230, 20, 100, 40); pygame.draw.rect(self.screen, (130, 70, 70), cl, border_radius=5)
        self.screen.blit(self.small_font.render("Clear", True, WHITE), self.small_font.render("Clear", True, WHITE).get_rect(center=cl.center))
        self.screen.blit(self.font.render("Available Cards (click to add)", True, (200, 200, 100)), (20, 70))
        cards_list = sorted(self.available_cards.keys())

        # Fixed 5 columns, 2 rows - cap card height to ensure 2 rows fit
        cpr = 5  # Fixed 5 columns
        rows = 2  # Fixed 2 rows
        deck_panel_width = 310  # Space for deck list on right
        available_width = self.screen_width - 40 - deck_panel_width  # 20px margin each side
        sp = 10  # Spacing between cards
        card_w = (available_width - sp * (cpr - 1)) // cpr

        # Calculate max card height that allows 2 rows to fit
        available_height = self.screen_height - 180  # Space for cards (below header)
        max_card_h = (available_height - sp * (rows - 1)) // rows
        card_h = min(int(card_w * 1.4), max_card_h)  # Use smaller of aspect ratio or max height

        vs = self.card_scroll * cpr
        cards_per_page = rows * cpr
        for i, cid in enumerate(cards_list[vs:vs + cards_per_page]):
            r, c = i // cpr, i % cpr
            x, y = 20 + c * (card_w + sp), 100 + r * (card_h + sp)
            self.screen.blit(self._render_deck_card_sized(cid, card_w, card_h), (x, y))
            cp = self.current_deck.count(cid)
            if cp > 0:
                pygame.draw.circle(self.screen, GREEN, (x + card_w - 18, y + 8), 12)
                self.screen.blit(self.small_font.render(str(cp), True, WHITE),
                                self.small_font.render(str(cp), True, WHITE).get_rect(center=(x + card_w - 18, y + 8)))

        # Draw deck list panel on right with scrollbar
        dx = self.screen_width - 300
        self.screen.blit(self.font.render(f"Your Deck ({len(self.current_deck)}/30)", True, GREEN), (dx, 70))

        # Deck list area
        deck_list_y = 100
        deck_item_height = 35
        deck_list_height = self.screen_height - 130  # Leave margin at bottom
        visible_items = deck_list_height // deck_item_height

        # Initialize deck scroll if not present
        if not hasattr(self, 'deck_scroll'):
            self.deck_scroll = 0

        # Clamp deck scroll
        max_deck_scroll = max(0, len(self.current_deck) - visible_items)
        self.deck_scroll = max(0, min(self.deck_scroll, max_deck_scroll))

        # Draw visible deck items
        for i in range(visible_items):
            deck_idx = i + self.deck_scroll
            if deck_idx >= len(self.current_deck):
                break
            cid = self.current_deck[deck_idx]
            ci = self.available_cards.get(cid, {})
            cr = pygame.Rect(dx, deck_list_y + i * deck_item_height, 260, deck_item_height - 3)
            pygame.draw.rect(self.screen, (60, 65, 55), cr, border_radius=5)
            pygame.draw.rect(self.screen, (80, 85, 75), cr, 1, border_radius=5)
            pygame.draw.circle(self.screen, (70, 130, 180), (dx + 18, cr.centery), 12)
            self.screen.blit(self.small_font.render(str(ci.get("cost", 0)), True, WHITE),
                            self.small_font.render(str(ci.get("cost", 0)), True, WHITE).get_rect(center=(dx + 18, cr.centery)))
            self.screen.blit(self.small_font.render(ci.get("name", cid), True, WHITE), (dx + 38, cr.y + 8))
            self.screen.blit(self.small_font.render("X", True, RED), (cr.right - 25, cr.y + 8))

        # Draw scrollbar if needed
        if len(self.current_deck) > visible_items:
            scrollbar_x = dx + 265
            scrollbar_height = deck_list_height
            scrollbar_rect = pygame.Rect(scrollbar_x, deck_list_y, 15, scrollbar_height)
            pygame.draw.rect(self.screen, (40, 40, 45), scrollbar_rect, border_radius=4)

            # Scrollbar thumb
            thumb_height = max(30, scrollbar_height * visible_items // len(self.current_deck))
            thumb_y = deck_list_y + (scrollbar_height - thumb_height) * self.deck_scroll // max_deck_scroll if max_deck_scroll > 0 else deck_list_y
            thumb_rect = pygame.Rect(scrollbar_x + 2, thumb_y, 11, thumb_height)
            pygame.draw.rect(self.screen, (100, 100, 110), thumb_rect, border_radius=4)

    def _render_deck_card(self, cid: str) -> pygame.Surface:
        ck = f"deck_{cid}"
        if ck in self._card_cache: return self._card_cache[ck]
        s = pygame.Surface((DECK_CARD_WIDTH, DECK_CARD_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(s, (245, 235, 220), (0, 0, DECK_CARD_WIDTH, DECK_CARD_HEIGHT), border_radius=6)
        pygame.draw.rect(s, (139, 90, 43), (0, 0, DECK_CARD_WIDTH, DECK_CARD_HEIGHT), 2, border_radius=6)
        up = os.path.join("resources", "Units", f"{cid}.png")
        if not os.path.exists(up): up = os.path.join("resources", "Units", f"{cid}.jpg")
        if os.path.exists(up):
            try:
                ui = pygame.image.load(up).convert_alpha(); ir = ui.get_rect()
                sc = min((DECK_CARD_WIDTH - 10) / ir.width, (DECK_CARD_HEIGHT - 55) / ir.height)
                ns = (int(ir.width * sc), int(ir.height * sc)); ui = pygame.transform.smoothscale(ui, ns)
                s.blit(ui, ((DECK_CARD_WIDTH - ns[0]) // 2, 22))
            except: pass
        ci = self.available_cards.get(cid, {}); tf = pygame.font.Font(None, 16)
        s.blit(tf.render(ci.get("name", cid)[:14], True, (50, 40, 30)),
              tf.render(ci.get("name", cid)[:14], True, (50, 40, 30)).get_rect(centerx=DECK_CARD_WIDTH // 2, top=4))
        pygame.draw.circle(s, (70, 130, 180), (14, 14), 10)
        s.blit(tf.render(str(ci.get("cost", 0)), True, WHITE), tf.render(str(ci.get("cost", 0)), True, WHITE).get_rect(center=(14, 14)))
        sy = DECK_CARD_HEIGHT - 14
        pygame.draw.circle(s, (200, 60, 60), (14, sy), 10)
        s.blit(tf.render(str(ci.get("attack", 0)), True, WHITE), tf.render(str(ci.get("attack", 0)), True, WHITE).get_rect(center=(14, sy)))
        pygame.draw.circle(s, (60, 160, 60), (DECK_CARD_WIDTH - 14, sy), 10)
        s.blit(tf.render(str(ci.get("health", 0)), True, WHITE), tf.render(str(ci.get("health", 0)), True, WHITE).get_rect(center=(DECK_CARD_WIDTH - 14, sy)))
        self._card_cache[ck] = s; return s

    def _render_deck_card_sized(self, cid: str, width: int, height: int) -> pygame.Surface:
        """Render a deck card with custom size and text."""
        ck = f"deck_{cid}_{width}_{height}"
        if ck in self._card_cache:
            return self._card_cache[ck]

        s = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(s, (245, 235, 220), (0, 0, width, height), border_radius=6)
        pygame.draw.rect(s, (139, 90, 43), (0, 0, width, height), 2, border_radius=6)

        ci = self.available_cards.get(cid, {})
        tf = pygame.font.Font(None, max(12, width // 8))
        tiny_font = pygame.font.Font(None, max(10, width // 10))

        # Card name at top
        name = ci.get("name", cid)[:16]
        name_surf = tf.render(name, True, (50, 40, 30))
        s.blit(name_surf, name_surf.get_rect(centerx=width // 2, top=4))

        # Unit image (drawn first so badges appear on top)
        img_top = 22
        img_height = height - 70  # Leave room for text and stats
        up = os.path.join("resources", "Units", f"{cid}.png")
        if not os.path.exists(up):
            up = os.path.join("resources", "Units", f"{cid}.jpg")
        if os.path.exists(up):
            try:
                ui = pygame.image.load(up).convert_alpha()
                ir = ui.get_rect()
                sc = min((width - 10) / ir.width, img_height / ir.height)
                ns = (int(ir.width * sc), int(ir.height * sc))
                ui = pygame.transform.smoothscale(ui, ns)
                s.blit(ui, ((width - ns[0]) // 2, img_top))
            except:
                pass

        # Cost badge (top-left) - drawn AFTER image so it appears on top
        cost_radius = max(8, width // 12)
        pygame.draw.circle(s, (70, 130, 180), (cost_radius + 4, cost_radius + 4), cost_radius)
        cost_text = tiny_font.render(str(ci.get("cost", 0)), True, WHITE)
        s.blit(cost_text, cost_text.get_rect(center=(cost_radius + 4, cost_radius + 4)))

        # Card text/special ability (below image)
        text_y = img_top + img_height + 2
        special = ci.get("special", "")
        if special:
            # Wrap text to fit card width
            text_font = pygame.font.Font(None, max(10, width // 11))
            words = special.split()
            lines = []
            current_line = ""
            max_text_width = width - 8
            for word in words:
                test_line = current_line + " " + word if current_line else word
                if text_font.size(test_line)[0] <= max_text_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)

            # Draw up to 2 lines of text
            for i, line in enumerate(lines[:2]):
                if i == 1 and len(lines) > 2:
                    line = line[:len(line)-3] + "..."
                text_surf = text_font.render(line, True, (70, 60, 50))
                s.blit(text_surf, (4, text_y + i * (text_font.get_height() + 1)))

        # Attack/Health stats at bottom
        stats_y = height - 14
        stat_radius = max(8, width // 12)
        pygame.draw.circle(s, (200, 60, 60), (stat_radius + 4, stats_y), stat_radius)
        atk_text = tiny_font.render(str(ci.get("attack", 0)), True, WHITE)
        s.blit(atk_text, atk_text.get_rect(center=(stat_radius + 4, stats_y)))

        pygame.draw.circle(s, (60, 160, 60), (width - stat_radius - 4, stats_y), stat_radius)
        hp_text = tiny_font.render(str(ci.get("health", 0)), True, WHITE)
        s.blit(hp_text, hp_text.get_rect(center=(width - stat_radius - 4, stats_y)))

        self._card_cache[ck] = s
        return s

    def _draw_matchmaking(self):
        self.screen.blit(self.title_font.render("Finding Match...", True, WHITE),
                        self.title_font.render("Finding Match...", True, WHITE).get_rect(center=(self.screen_width // 2, self.screen_height // 2 - 50)))
        dots = "." * (int(pygame.time.get_ticks() / 500) % 4)
        self.screen.blit(self.font.render(dots, True, GRAY), (self.screen_width // 2 + 150, self.screen_height // 2 - 50))
        self.screen.blit(self.small_font.render("Press ESC to cancel", True, GRAY),
                        self.small_font.render("Press ESC to cancel", True, GRAY).get_rect(center=(self.screen_width // 2, self.screen_height // 2 + 50)))

    def _draw_game(self):
        if not self.game_state:
            self.screen.blit(self.font.render("Loading...", True, WHITE),
                           self.font.render("Loading...", True, WHITE).get_rect(center=(self.screen_width // 2, self.screen_height // 2))); return
        self._draw_opponent_info(); self._draw_opponent_hand(); self._draw_battlefield(); self._draw_hand(); self._draw_turn_info(); self._draw_deck(); self._draw_reinforcements()
        self.draw_menu.draw(self.screen); self.location_panel.draw(self.screen); self.combat_selector.draw(self.screen)

    def _draw_match_start_transition(self):
        """Draw the match start transition with player info and role assignment."""
        # Background overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.fill((20, 20, 30))
        self.screen.blit(overlay, (0, 0))
        
        progress = min(1.0, self.match_transition_timer / self.match_transition_duration)
        
        if not self.match_info:
            return
        
        # Extract player info
        your_name = self.match_info.get("your_name", "You")
        your_wins = self.match_info.get("your_wins", 0)
        your_losses = self.match_info.get("your_losses", 0)
        opponent_name = self.match_info.get("opponent_name", "Opponent")
        opponent_wins = self.match_info.get("opponent_wins", 0)
        opponent_losses = self.match_info.get("opponent_losses", 0)
        your_role = self.match_info.get("role", "attacker")
        
        center_x = self.screen_width // 2
        center_y = self.screen_height // 2
        
        # Main title with fade in
        title_alpha = int(255 * min(1.0, progress * 2))
        title_text = pygame.font.Font(None, 64).render("MATCH START", True, (255, 200, 50))
        title_surf = pygame.Surface((self.screen_width, 100), pygame.SRCALPHA)
        title_colored = pygame.Surface(title_text.get_size(), pygame.SRCALPHA)
        title_colored.blit(title_text, (0, 0))
        title_colored.set_alpha(title_alpha)
        title_rect = title_colored.get_rect(center=(center_x, center_y - 200))
        self.screen.blit(title_colored, title_rect)
        
        # Left side - Your info
        left_x = center_x - 300
        info_y = center_y - 50
        
        your_name_font = pygame.font.Font(None, 48)
        your_name_text = your_name_font.render(your_name, True, (100, 200, 255))
        self.screen.blit(your_name_text, (left_x - your_name_text.get_width() // 2, info_y))
        
        record_font = pygame.font.Font(None, 36)
        record_text = record_font.render(f"{your_wins}W - {your_losses}L", True, (150, 150, 150))
        self.screen.blit(record_text, (left_x - record_text.get_width() // 2, info_y + 60))
        
        # Right side - Opponent info
        right_x = center_x + 300
        
        opponent_name_text = your_name_font.render(opponent_name, True, (255, 100, 100))
        self.screen.blit(opponent_name_text, (right_x - opponent_name_text.get_width() // 2, info_y))
        
        opp_record_text = record_font.render(f"{opponent_wins}W - {opponent_losses}L", True, (150, 150, 150))
        self.screen.blit(opp_record_text, (right_x - opp_record_text.get_width() // 2, info_y + 60))
        
        # Role assignment animation (flipping effect)
        flip_progress = (progress - 0.3) / 0.4 if progress > 0.3 else 0  # Start after 0.3s
        flip_progress = max(0, min(1.0, flip_progress))
        
        if flip_progress > 0:
            role_y = center_y + 80
            role_size = int(40 + flip_progress * 20)
            role_font = pygame.font.Font(None, role_size)
            
            # Flip animation
            flip_angle = flip_progress * 360
            if flip_angle < 180:
                # First half of flip - show random text
                import random
                random.seed(int(flip_angle / 10))
                roles = ["ATTACKER", "DEFENDER"]
                display_role = random.choice(roles)
                role_color = RED if display_role == "ATTACKER" else BLUE
            else:
                # Second half - show actual role
                display_role = your_role.upper()
                role_color = RED if your_role == "attacker" else BLUE
            
            role_text = role_font.render(f"You are: {display_role}", True, role_color)
            role_alpha = int(255 * min(1.0, flip_progress))
            role_text.set_alpha(role_alpha)
            self.screen.blit(role_text, role_text.get_rect(center=(center_x, role_y)))
        
        # VS text in the middle
        vs_progress = max(0, min(1.0, (progress - 0.15) * 1.5))
        if vs_progress > 0:
            vs_font = pygame.font.Font(None, 72)
            vs_text = vs_font.render("VS", True, (255, 255, 100))
            vs_alpha = int(255 * vs_progress)
            vs_text.set_alpha(vs_alpha)
            self.screen.blit(vs_text, vs_text.get_rect(center=(center_x, center_y + 20)))
        
        # Skip message at the end
        skip_progress = max(0, progress - 0.7)
        if skip_progress > 0:
            skip_font = pygame.font.Font(None, 24)
            skip_text = skip_font.render("Click to continue...", True, (150, 150, 150))
            skip_alpha = int(200 * skip_progress * 2 * (1 - (skip_progress - 0.5) ** 2))
            skip_text.set_alpha(max(0, min(255, skip_alpha)))
            self.screen.blit(skip_text, skip_text.get_rect(center=(center_x, self.screen_height - 50)))
        # Show waiting message when opponent is assigning blockers
        if self.waiting_for_combat:
            wait_text = self.font.render(f"Waiting for opponent to assign blockers at {self.waiting_for_combat}...", True, GOLD)
            wait_rect = wait_text.get_rect(center=(self.screen_width // 2, 60))
            pygame.draw.rect(self.screen, (40, 40, 45, 200), wait_rect.inflate(20, 10), border_radius=8)
            self.screen.blit(wait_text, wait_rect)

    def _draw_battlefield(self):
        bw, bh = 560, 360
        br = pygame.Rect(self.screen_width // 2 - bw // 2, self.screen_height // 2 - 40 - bh // 2, bw, bh)
        pygame.draw.rect(self.screen, (42, 42, 48), br, border_radius=15); pygame.draw.rect(self.screen, (72, 72, 78), br, 2, border_radius=15)
        lf = pygame.font.Font(None, 20)
        if self.your_role == "attacker": tl, tc, bl, bc = "DEFENDER TERRITORY", BLUE, "YOUR TERRITORY (ATTACKER)", RED
        else: tl, tc, bl, bc = "ATTACKER TERRITORY", RED, "YOUR TERRITORY (DEFENDER)", BLUE
        self.screen.blit(lf.render(tl, True, tc), lf.render(tl, True, tc).get_rect(center=(self.screen_width // 2, br.top + 14)))
        self.screen.blit(lf.render(bl, True, bc), lf.render(bl, True, bc).get_rect(center=(self.screen_width // 2, br.bottom - 14)))
        for l1, l2 in self.CONNECTIONS: self._draw_connection(l1, l2)
        for nm, rect in self.locations.items():
            bf = self.game_state.get("battlefield", {}).get(nm, {}); ct = bf.get("controller")
            col = (150, 70, 70) if ct == "attacker" else (70, 70, 150) if ct == "defender" else (80, 80, 85)
            if nm == self.hovered_location: col = tuple(min(c + 35, 255) for c in col)
            pygame.draw.rect(self.screen, col, rect, border_radius=8); pygame.draw.rect(self.screen, (120, 120, 125), rect, 2, border_radius=8)
            self.screen.blit(self.small_font.render(nm, True, WHITE), self.small_font.render(nm, True, WHITE).get_rect(centerx=rect.centerx, top=rect.top + 6))

            # Count cards from all zones (new 3-zone structure)
            zones = bf.get("zones", {})
            oc = 0  # Own card count
            ec = 0  # Enemy card count
            for zone_name in ["attacker_zone", "middle_zone", "defender_zone"]:
                zone_data = zones.get(zone_name, {})
                oc += len(zone_data.get("own_cards", []))
                ec += zone_data.get("enemy_count", 0)

            cy = rect.top + 32
            if oc > 0: self.screen.blit(self.small_font.render(f"You: {oc}", True, GREEN), (rect.left + 6, cy))
            if bf.get("can_see") and ec: self.screen.blit(self.small_font.render(f"Enemy: {ec}", True, RED), (rect.left + 6, cy + 18))
            elif not bf.get("can_see"): self.screen.blit(self.small_font.render("???", True, DARK_GRAY), (rect.left + 6, cy + 18))

            # Draw capture progress for capturable locations
            cap_info = bf.get("capture_info")
            if cap_info and cap_info.get("capturable") and not cap_info.get("controller"):
                tiny = pygame.font.Font(None, 12)
                your_role = self.game_state.get("your_role", "attacker")
                your_power = cap_info.get(f"{your_role}_power", 0)
                your_threshold = cap_info.get(f"{your_role}_threshold", 5)
                enemy_role = "defender" if your_role == "attacker" else "attacker"
                enemy_power = cap_info.get(f"{enemy_role}_power", 0)
                enemy_threshold = cap_info.get(f"{enemy_role}_threshold", 5)

                # Draw TWO progress bars at bottom of location
                bar_width = (rect.width - 16) // 2 - 2
                bar_height = 4

                # Your progress (green bar on left)
                your_bar_y = rect.bottom - 8
                your_progress = min(1.0, your_power / your_threshold) if your_threshold > 0 else 0
                pygame.draw.rect(self.screen, (30, 30, 30), (rect.left + 6, your_bar_y, bar_width, bar_height), border_radius=2)
                if your_progress > 0:
                    pygame.draw.rect(self.screen, (60, 180, 60), (rect.left + 6, your_bar_y, int(bar_width * your_progress), bar_height), border_radius=2)

                # Enemy progress (red bar on right)
                enemy_bar_x = rect.left + 10 + bar_width
                enemy_progress = min(1.0, enemy_power / enemy_threshold) if enemy_threshold > 0 else 0
                pygame.draw.rect(self.screen, (30, 30, 30), (enemy_bar_x, your_bar_y, bar_width, bar_height), border_radius=2)
                if enemy_progress > 0:
                    pygame.draw.rect(self.screen, (180, 60, 60), (enemy_bar_x, your_bar_y, int(bar_width * enemy_progress), bar_height), border_radius=2)

                # Show power text
                your_text = tiny.render(f"{your_power}/{your_threshold}", True, GREEN)
                enemy_text = tiny.render(f"{enemy_power}/{enemy_threshold}", True, RED)
                self.screen.blit(your_text, (rect.left + 6, your_bar_y - 9))
                self.screen.blit(enemy_text, (enemy_bar_x, your_bar_y - 9))

    def _draw_connection(self, l1: str, l2: str):
        r1, r2 = self.locations.get(l1), self.locations.get(l2)
        if not r1 or not r2: return
        c1, c2 = r1.center, r2.center; a = math.atan2(c2[1] - c1[1], c2[0] - c1[0])
        o1x, o1y = (r1.width // 2 + 4) * math.cos(a), (r1.height // 2 + 4) * math.sin(a)
        o2x, o2y = (r2.width // 2 + 4) * math.cos(a), (r2.height // 2 + 4) * math.sin(a)
        pygame.draw.line(self.screen, (70, 70, 75), (c1[0] + o1x, c1[1] + o1y), (c2[0] - o2x, c2[1] - o2y), 2)

    def _draw_opponent_hand(self):
        """Draw opponent's hand cards (card backs) at the top of the screen."""
        num_cards = self.opponent_hand_count
        if num_cards == 0:
            return
        
        # Card back dimensions
        card_w, card_h = CARD_WIDTH, CARD_HEIGHT
        hand_y = 80
        center_x = self.screen_width // 2
        
        # Create arc positioning similar to player's hand but at top
        arc_span = min(math.pi * 0.35, num_cards * 0.08)
        start_a, end_a = math.pi * 1.5 - arc_span / 2, math.pi * 1.5 + arc_span / 2
        radius_x, radius_y = self.screen_width * 0.32, 120
        
        for i in range(num_cards):
            angle = math.pi * 1.5 if num_cards == 1 else start_a + (end_a - start_a) * (i / (num_cards - 1))
            x = center_x + radius_x * math.cos(angle)
            y = hand_y - 60 - radius_y * math.sin(angle)
            
            # Calculate rotation for card back based on position
            rotation = (angle - math.pi * 1.5) * 20
            
            # Render card back
            self._draw_card_back(int(x), int(y), rotation)
    
    def _draw_card_back(self, x: int, y: int, rotation: float = 0):
        """Draw a card back (face down) at specified position."""
        card_w, card_h = CARD_WIDTH, CARD_HEIGHT
        
        # Create card back surface
        card_back = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        
        # Draw card back with border
        pygame.draw.rect(card_back, (40, 80, 120), (0, 0, card_w, card_h), border_radius=8)
        pygame.draw.rect(card_back, (100, 140, 180), (0, 0, card_w, card_h), 3, border_radius=8)
        
        # Draw pattern on card back
        pattern_color = (60, 100, 140)
        for row in range(4):
            for col in range(3):
                px = 15 + col * (card_w - 30) // 2
                py = 30 + row * (card_h - 60) // 3
                pygame.draw.circle(card_back, pattern_color, (px, py), 8)
        
        # Draw decorative border inside
        pygame.draw.rect(card_back, (80, 120, 160), (8, 8, card_w - 16, card_h - 16), 2, border_radius=6)
        
        # Apply rotation if needed
        if rotation != 0:
            card_back = pygame.transform.rotozoom(card_back, rotation, 1.0)
        
        # Get rotated rect for positioning
        card_rect = card_back.get_rect(center=(x, y))
        self.screen.blit(card_back, card_rect)

    def _draw_hand(self):
        for c in self.hand_cards:
            if c != self.focused_hand_card and c != self.dragging_card: self._draw_animated_card(c)
        if self.focused_hand_card and self.focused_hand_card != self.dragging_card: self._draw_animated_card(self.focused_hand_card)
        if self.dragging_card: self._draw_animated_card(self.dragging_card)

    def _draw_animated_card(self, card: AnimatedCard):
        cd, cid = card.card_data, card.card_id
        w, h = int(CARD_WIDTH * card.scale.value), int(CARD_HEIGHT * card.scale.value)
        ck = f"hand_{cid}"
        if ck not in self._card_cache:
            s = pygame.Surface((CARD_WIDTH, CARD_HEIGHT), pygame.SRCALPHA)
            pygame.draw.rect(s, (245, 235, 220), (0, 0, CARD_WIDTH, CARD_HEIGHT), border_radius=8)
            pygame.draw.rect(s, (139, 90, 43), (0, 0, CARD_WIDTH, CARD_HEIGHT), 3, border_radius=8)
            up = os.path.join("resources", "Units", f"{cid}.png")
            if not os.path.exists(up): up = os.path.join("resources", "Units", f"{cid}.jpg")
            if os.path.exists(up):
                try:
                    ui = pygame.image.load(up).convert_alpha(); ir = ui.get_rect()
                    sc = min((CARD_WIDTH - 12) / ir.width, (CARD_HEIGHT - 55) / ir.height)
                    ns = (int(ir.width * sc), int(ir.height * sc)); ui = pygame.transform.smoothscale(ui, ns)
                    s.blit(ui, ((CARD_WIDTH - ns[0]) // 2, 26))
                except: pass
            nm = cd.get("name", cid)[:14]; atk, hp, cost = cd.get("attack", 0), cd.get("health", 0), cd.get("cost", 0)
            sp = cd.get("special", ""); sf, tf = pygame.font.Font(None, 18), pygame.font.Font(None, 14)
            s.blit(sf.render(nm, True, (50, 40, 30)), sf.render(nm, True, (50, 40, 30)).get_rect(centerx=CARD_WIDTH // 2, top=5))
            pygame.draw.circle(s, (70, 130, 180), (16, 16), 12)
            s.blit(sf.render(str(cost), True, WHITE), sf.render(str(cost), True, WHITE).get_rect(center=(16, 16)))
            if sp:
                sy = CARD_HEIGHT - 58
                sb = pygame.Surface((CARD_WIDTH - 8, 32), pygame.SRCALPHA)
                pygame.draw.rect(sb, (240, 220, 180, 220), (0, 0, CARD_WIDTH - 8, 32), border_radius=4)
                s.blit(sb, (4, sy))
                ws = sp.split(); ls, cl = [], []
                for wd in ws:
                    if tf.size(' '.join(cl + [wd]))[0] < CARD_WIDTH - 12: cl.append(wd)
                    else:
                        if cl: ls.append(' '.join(cl))
                        cl = [wd]
                if cl: ls.append(' '.join(cl))
                for i, ln in enumerate(ls[:2]):
                    lt = tf.render(ln, True, (50, 40, 30)); s.blit(lt, lt.get_rect(centerx=CARD_WIDTH // 2, y=sy + 3 + i * 14))
            sty = CARD_HEIGHT - 18
            pygame.draw.circle(s, (200, 60, 60), (16, sty), 12)
            s.blit(sf.render(str(atk), True, WHITE), sf.render(str(atk), True, WHITE).get_rect(center=(16, sty)))
            pygame.draw.circle(s, (60, 160, 60), (CARD_WIDTH - 16, sty), 12)
            s.blit(sf.render(str(hp), True, WHITE), sf.render(str(hp), True, WHITE).get_rect(center=(CARD_WIDTH - 16, sty)))
            self._card_cache[ck] = s
        bs = self._card_cache[ck]
        rs = pygame.transform.rotozoom(bs, card.angle.value, card.scale.value) if card.angle.value != 0 else pygame.transform.smoothscale(bs, (w, h))
        dx = int(card.x.value - rs.get_width() // 2); dy = int(card.y.value + card.hover_offset.value - rs.get_height() // 2)
        if card.shadow_offset.value > 3:
            sh = pygame.Surface((w + 10, h + 10), pygame.SRCALPHA)
            pygame.draw.rect(sh, (0, 0, 0, 50), (5, 5, w, h), border_radius=8)
            self.screen.blit(sh, (dx + int(card.shadow_offset.value) - 5, dy + int(card.shadow_offset.value) - 5))
        if card.glow.value > 0:
            ga = int(100 * card.glow.value * (0.7 + 0.3 * math.sin(card.glow_pulse)))
            gl = pygame.Surface((w + 16, h + 16), pygame.SRCALPHA)
            pygame.draw.rect(gl, (255, 200, 50, ga), (0, 0, w + 16, h + 16), border_radius=10)
            self.screen.blit(gl, (dx - 8, dy - 8))
        self.screen.blit(rs, (dx, dy))

    def _draw_turn_info(self):
        tn = self.game_state.get("turn", 1); iyt = self.game_state.get("is_your_turn", False); yr = self.game_state.get("your_role", "")
        if self.turn_flash > 0:
            fl = pygame.Surface((self.screen_width, 60), pygame.SRCALPHA); fl.fill((255, 255, 255, int(50 * self.turn_flash)))
            self.screen.blit(fl, (0, 40))
        self.screen.blit(self.font.render(f"Turn {tn}", True, WHITE), (20, 50))
        pt, pc = ("YOUR TURN", GREEN) if iyt else ("OPPONENT'S TURN", RED)
        self.screen.blit(self.font.render(pt, True, pc), (20, 85))
        self.screen.blit(self.small_font.render(f"You are: {yr.upper()}", True, RED if yr == "attacker" else BLUE), (20, 120))
        if iyt:
            etr = pygame.Rect(self.screen_width - 180, 15, 160, 55)
            pygame.draw.rect(self.screen, (150, 100, 50), etr, border_radius=8)
            btn_font = pygame.font.Font(None, 36)
            self.screen.blit(btn_font.render("End Turn", True, WHITE), btn_font.render("End Turn", True, WHITE).get_rect(center=etr.center))

    def _draw_opponent_info(self):
        """Display opponent's hand card count and role."""
        opp_hand_count = self.game_state.get("opponent_hand_count", 0)
        opp_role = "DEFENDER" if self.game_state.get("your_role") == "attacker" else "ATTACKER"
        opp_role_color = BLUE if opp_role == "DEFENDER" else RED
        
        # Display opponent role and hand count at top right
        role_text = self.small_font.render(f"Opponent: {opp_role}", True, opp_role_color)
        hand_text = self.font.render(f"Cards: {opp_hand_count}", True, WHITE)
        
        self.screen.blit(role_text, (self.screen_width - role_text.get_width() - 20, 20))
        self.screen.blit(hand_text, (self.screen_width - hand_text.get_width() - 20, 50))

    def _draw_deck(self):
        dc = self.game_state.get("deck_count", 0); cd = self.game_state.get("can_draw", False)
        dr = pygame.Rect(self.screen_width - 150, self.screen_height - 210, 130, 180)
        for i in range(min(3, dc)):
            cr = pygame.Rect(dr.x + i * 3, dr.y - i * 3, 130, 180)
            pygame.draw.rect(self.screen, (85, 65, 45) if cd else (55, 55, 55), cr, border_radius=8)
            pygame.draw.rect(self.screen, (65, 45, 25), cr, 3, border_radius=8)
        self.screen.blit(self.font.render(str(dc), True, WHITE), self.font.render(str(dc), True, WHITE).get_rect(center=dr.center))
        lb = "CLICK TO DRAW" if cd else "DRAWN"
        btn_font = pygame.font.Font(None, 28)
        self.screen.blit(btn_font.render(lb, True, GRAY), btn_font.render(lb, True, GRAY).get_rect(centerx=dr.centerx, top=dr.bottom + 8))

    def _draw_reinforcements(self):
        if not self.reinforcements:
            return

        x, y = 20, 150
        self.screen.blit(self.small_font.render("Incoming:", True, (200, 200, 200)), (x, y))

        # Small card dimensions
        thumb_w, thumb_h = 50, 70
        spacing = 8
        mouse_pos = pygame.mouse.get_pos()

        # Store rects for hover detection
        self._reinforcement_rects = []

        for i, e in enumerate(self.reinforcements[:6]):
            card_id = e.get('card_id', '?')
            turns = e.get('turns_remaining', 0)
            card_x = x + i * (thumb_w + spacing)
            card_y = y + 22

            card_rect = pygame.Rect(card_x, card_y, thumb_w, thumb_h)
            self._reinforcement_rects.append((card_rect, card_id, turns))

            is_hovered = card_rect.collidepoint(mouse_pos)

            # Draw small card thumbnail
            thumb = self._render_reinforcement_thumb(card_id, thumb_w, thumb_h)
            self.screen.blit(thumb, (card_x, card_y))

            # Draw turns remaining badge
            badge_x = card_x + thumb_w - 12
            badge_y = card_y + 4
            pygame.draw.circle(self.screen, (70, 130, 180), (badge_x, badge_y), 10)
            turns_text = self.small_font.render(str(turns), True, WHITE)
            self.screen.blit(turns_text, turns_text.get_rect(center=(badge_x, badge_y)))

            # If hovered, draw enlarged card
            if is_hovered:
                big_w, big_h = 130, 182
                big_x = card_x
                big_y = card_y + thumb_h + 10

                # Make sure it doesn't go off screen
                if big_x + big_w > self.screen_width:
                    big_x = self.screen_width - big_w - 10
                if big_y + big_h > self.screen_height:
                    big_y = card_y - big_h - 10

                # Draw shadow
                pygame.draw.rect(self.screen, (0, 0, 0, 100),
                               (big_x + 4, big_y + 4, big_w, big_h), border_radius=8)

                # Draw enlarged card
                big_card = self._render_reinforcement_card(card_id, big_w, big_h)
                self.screen.blit(big_card, (big_x, big_y))

                # Draw turns remaining on big card
                pygame.draw.circle(self.screen, (70, 130, 180), (big_x + big_w - 18, big_y + 18), 14)
                turns_big = self.font.render(str(turns), True, WHITE)
                self.screen.blit(turns_big, turns_big.get_rect(center=(big_x + big_w - 18, big_y + 18)))

                # Label
                label = self.small_font.render(f"Arrives in {turns} turn{'s' if turns != 1 else ''}", True, GOLD)
                self.screen.blit(label, (big_x, big_y + big_h + 5))

    def _render_reinforcement_thumb(self, card_id: str, width: int, height: int) -> pygame.Surface:
        """Render a small reinforcement card thumbnail."""
        cache_key = f"reinf_thumb_{card_id}_{width}_{height}"
        if cache_key in self._card_cache:
            return self._card_cache[cache_key]

        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(surf, (60, 55, 50), (0, 0, width, height), border_radius=4)
        pygame.draw.rect(surf, (100, 90, 70), (0, 0, width, height), 2, border_radius=4)

        # Try to load unit image
        up = os.path.join("resources", "Units", f"{card_id}.png")
        if not os.path.exists(up):
            up = os.path.join("resources", "Units", f"{card_id}.jpg")
        if os.path.exists(up):
            try:
                ui = pygame.image.load(up).convert_alpha()
                ir = ui.get_rect()
                sc = min((width - 4) / ir.width, (height - 4) / ir.height)
                ns = (int(ir.width * sc), int(ir.height * sc))
                ui = pygame.transform.smoothscale(ui, ns)
                surf.blit(ui, ((width - ns[0]) // 2, (height - ns[1]) // 2))
            except:
                pass

        self._card_cache[cache_key] = surf
        return surf

    def _render_reinforcement_card(self, card_id: str, width: int, height: int) -> pygame.Surface:
        """Render an enlarged reinforcement card with full details."""
        cache_key = f"reinf_big_{card_id}_{width}_{height}"
        if cache_key in self._card_cache:
            return self._card_cache[cache_key]

        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(surf, (245, 235, 220), (0, 0, width, height), border_radius=8)
        pygame.draw.rect(surf, (139, 90, 43), (0, 0, width, height), 3, border_radius=8)

        ci = self.available_cards.get(card_id, {})
        tf = pygame.font.Font(None, 18)
        tiny = pygame.font.Font(None, 14)

        # Card name
        name = ci.get("name", card_id)[:16]
        name_surf = tf.render(name, True, (50, 40, 30))
        surf.blit(name_surf, name_surf.get_rect(centerx=width // 2, top=6))

        # Unit image
        img_top = 24
        img_height = height - 65
        up = os.path.join("resources", "Units", f"{card_id}.png")
        if not os.path.exists(up):
            up = os.path.join("resources", "Units", f"{card_id}.jpg")
        if os.path.exists(up):
            try:
                ui = pygame.image.load(up).convert_alpha()
                ir = ui.get_rect()
                sc = min((width - 10) / ir.width, img_height / ir.height)
                ns = (int(ir.width * sc), int(ir.height * sc))
                ui = pygame.transform.smoothscale(ui, ns)
                surf.blit(ui, ((width - ns[0]) // 2, img_top))
            except:
                pass

        # Special text
        special = ci.get("special", "")
        if special:
            text_y = img_top + img_height + 2
            words = special.split()
            line = ""
            for w in words:
                test = line + " " + w if line else w
                if tiny.size(test)[0] <= width - 8:
                    line = test
                else:
                    break
            if len(line) < len(special):
                line = line[:len(line)-3] + "..."
            text_surf = tiny.render(line, True, (70, 60, 50))
            surf.blit(text_surf, (4, text_y))

        # Stats
        stats_y = height - 14
        pygame.draw.circle(surf, (200, 60, 60), (14, stats_y), 10)
        atk = tiny.render(str(ci.get("attack", 0)), True, WHITE)
        surf.blit(atk, atk.get_rect(center=(14, stats_y)))

        pygame.draw.circle(surf, (60, 160, 60), (width - 14, stats_y), 10)
        hp = tiny.render(str(ci.get("health", 0)), True, WHITE)
        surf.blit(hp, hp.get_rect(center=(width - 14, stats_y)))

        self._card_cache[cache_key] = surf
        return surf

    def _draw_game_over(self):
        ov = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA); ov.fill((0, 0, 0, 200)); self.screen.blit(ov, (0, 0))
        wn = getattr(self, 'winner', 'unknown'); yr = self.game_state.get("your_role", "") if self.game_state else ""
        rt, rc = ("VICTORY!", GREEN) if wn == yr else ("DEFEAT", RED)
        self.screen.blit(self.title_font.render(rt, True, rc), self.title_font.render(rt, True, rc).get_rect(center=(self.screen_width // 2, self.screen_height // 2 - 50)))
        self.screen.blit(self.font.render("Click anywhere to return to lobby", True, WHITE),
                        self.font.render("Click anywhere to return to lobby", True, WHITE).get_rect(center=(self.screen_width // 2, self.screen_height // 2 + 50)))

    def run(self):
        if not self.connect(): print("Failed to connect!"); return
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events(); self.update(dt); self.draw()
        self.network.disconnect(); pygame.quit()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="WarMasterMind Client")
    parser.add_argument("--server", default="ws://localhost:8765", help="Server URL")
    args = parser.parse_args()
    ThinClient(args.server).run()


if __name__ == "__main__":
    main()