"""Battlefield visual and location management."""

import os
import pygame
from game_manager import Player
import cards_database as db


def card_has_scout(card_data: dict) -> bool:
    """Check if a card has the Scout ability."""
    card_info = card_data.get("card_info", [])
    if len(card_info) > db.IDX_SUBTYPE:
        subtype = card_info[db.IDX_SUBTYPE]
        return "Scout" in subtype
    return False


class LocationZone:
    """A zone on the battlefield where cards can be placed."""

    def __init__(self, name: str, x: int, y: int, width: int, height: int,
                 color: tuple, blocked_by: list = None):
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.color = color
        self.blocked_by = blocked_by or []
        self.is_hovered = False

        # Cards placed at this location
        self.attacker_cards: list = []
        self.defender_cards: list = []

    def get_rect(self) -> pygame.Rect:
        """Get the zone's rectangle."""
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def contains_point(self, point: tuple) -> bool:
        """Check if a point is inside the zone."""
        return self.get_rect().collidepoint(point)

    def can_place(self, player: Player) -> bool:
        """Check if a player can place cards here."""
        if player == Player.ATTACKER:
            return "Attacker" not in self.blocked_by
        else:
            return "Defender" not in self.blocked_by

    def player_has_presence(self, player: Player) -> bool:
        """Check if a player has any cards at this location."""
        if player == Player.ATTACKER:
            return len(self.attacker_cards) > 0
        else:
            return len(self.defender_cards) > 0

    def player_has_scout(self, player: Player) -> bool:
        """Check if a player has a scout at this location."""
        cards = self.attacker_cards if player == Player.ATTACKER else self.defender_cards
        return any(card_has_scout(card) for card in cards)

    def can_see_opponent(self, viewing_player: Player) -> bool:
        """Check if viewing_player can see opponent's cards here.

        A player can see opponent cards if:
        - They have any card at this location (combat engagement), OR
        - They have a Scout unit at this location
        """
        return self.player_has_presence(viewing_player) or self.player_has_scout(viewing_player)

    def draw(self, screen: pygame.Surface, font: pygame.font.Font,
             current_player: Player = None):
        """Draw the location zone."""
        rect = self.get_rect()

        # Background with transparency
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        alpha = 180 if self.is_hovered else 140
        color_with_alpha = (*self.color, alpha)
        pygame.draw.rect(surface, color_with_alpha, (0, 0, self.width, self.height),
                        border_radius=10)
        screen.blit(surface, (self.x, self.y))

        # Border
        border_color = (255, 255, 255) if self.is_hovered else (100, 100, 100)
        pygame.draw.rect(screen, border_color, rect, 2, border_radius=10)

        # Location name
        text = font.render(self.name, True, (255, 255, 255))
        text_rect = text.get_rect(center=(self.x + self.width // 2, self.y + 15))
        screen.blit(text, text_rect)

        # Card count indicators
        small_font = pygame.font.Font(None, 20)

        # Determine visibility
        can_see_opponent = current_player is None or self.can_see_opponent(current_player)

        # Show own cards count
        if current_player == Player.ATTACKER:
            own_count = len(self.attacker_cards)
            opp_count = len(self.defender_cards)
            own_color = (255, 100, 100)
            opp_color = (100, 100, 255)
            own_label = "You"
            opp_label = "Enemy"
        elif current_player == Player.DEFENDER:
            own_count = len(self.defender_cards)
            opp_count = len(self.attacker_cards)
            own_color = (100, 100, 255)
            opp_color = (255, 100, 100)
            own_label = "You"
            opp_label = "Enemy"
        else:
            # No player specified, show all
            own_count = len(self.attacker_cards)
            opp_count = len(self.defender_cards)
            own_color = (255, 100, 100)
            opp_color = (100, 100, 255)
            own_label = "Atk"
            opp_label = "Def"
            can_see_opponent = True

        if own_count > 0:
            own_text = small_font.render(f"{own_label}: {own_count}", True, own_color)
            screen.blit(own_text, (self.x + 5, self.y + 30))

        if can_see_opponent and opp_count > 0:
            opp_text = small_font.render(f"{opp_label}: {opp_count}", True, opp_color)
            screen.blit(opp_text, (self.x + 5, self.y + 45))
        elif not can_see_opponent:
            unknown_text = small_font.render(f"{opp_label}: ???", True, (150, 150, 150))
            screen.blit(unknown_text, (self.x + 5, self.y + 45))

        # Show blocked indicator
        if self.blocked_by:
            blocked_text = small_font.render(f"({', '.join(self.blocked_by)} blocked)",
                                             True, (180, 180, 180))
            blocked_rect = blocked_text.get_rect(
                center=(self.x + self.width // 2, self.y + self.height - 10)
            )
            screen.blit(blocked_text, blocked_rect)


class Battlefield:
    """The battlefield containing all location zones."""

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.locations: dict[str, LocationZone] = {}
        self.selected_location: LocationZone | None = None
        self.font = pygame.font.Font(None, 24)
        self.current_player: Player = Player.ATTACKER

        self._create_locations()

    def _create_locations(self):
        """Create the battlefield locations.

        Layout organized by access:
        - Top row (near Defender): Keep, Courtyard (Attacker blocked)
        - Middle row: Walls, Gate, Sewers (neutral - both can access)
        - Bottom row (near Attacker): Forest (Defender blocked)
        """
        center_x = self.screen_width // 2
        center_y = self.screen_height // 2

        zone_width = 140
        zone_height = 80
        spacing = 15

        # Three rows
        top_y = center_y - zone_height - spacing - zone_height // 2
        mid_y = center_y - zone_height // 2
        bottom_y = center_y + spacing + zone_height // 2

        # X positions
        left_x = center_x - zone_width - spacing // 2
        right_x = center_x + spacing // 2
        single_center_x = center_x - zone_width // 2

        # For middle row (3 zones)
        mid_left_x = center_x - zone_width * 1.5 - spacing
        mid_center_x = center_x - zone_width // 2
        mid_right_x = center_x + zone_width // 2 + spacing

        locations_config = [
            # Top row - Defender territory (Attacker blocked)
            ("Keep", left_x, top_y, (139, 90, 43), ["Attacker"]),
            ("Courtyard", right_x, top_y, (160, 140, 100), ["Attacker"]),
            # Middle row - Contested zones (both can access)
            ("Walls", mid_left_x, mid_y, (128, 128, 128), []),
            ("Gate", mid_center_x, mid_y, (100, 80, 60), []),
            ("Sewers", mid_right_x, mid_y, (60, 60, 80), []),
            # Bottom row - Attacker territory (Defender blocked)
            ("Forest", single_center_x, bottom_y, (34, 100, 34), ["Defender"]),
        ]

        for name, x, y, color, blocked in locations_config:
            self.locations[name] = LocationZone(name, int(x), int(y),
                                                zone_width, zone_height,
                                                color, blocked)

    def set_current_player(self, player: Player):
        """Set the current player for visibility calculations."""
        self.current_player = player

    def draw(self, screen: pygame.Surface):
        """Draw the entire battlefield."""
        # Draw battlefield background
        bf_rect = pygame.Rect(
            self.screen_width // 2 - 280,
            self.screen_height // 2 - 150,
            560, 300
        )
        pygame.draw.rect(screen, (50, 50, 50), bf_rect, border_radius=15)
        pygame.draw.rect(screen, (80, 80, 80), bf_rect, 3, border_radius=15)

        # Draw section labels
        label_font = pygame.font.Font(None, 20)

        # Defender territory label (top)
        def_label = label_font.render("- DEFENDER TERRITORY -", True, (100, 100, 200))
        def_rect = def_label.get_rect(center=(self.screen_width // 2, bf_rect.top + 15))
        screen.blit(def_label, def_rect)

        # Attacker territory label (bottom)
        atk_label = label_font.render("- ATTACKER TERRITORY -", True, (200, 100, 100))
        atk_rect = atk_label.get_rect(center=(self.screen_width // 2, bf_rect.bottom - 15))
        screen.blit(atk_label, atk_rect)

        # Draw all locations with current player visibility
        for location in self.locations.values():
            location.draw(screen, self.font, self.current_player)

    def handle_mouse_motion(self, mouse_pos: tuple):
        """Handle mouse movement for hover effects."""
        for location in self.locations.values():
            location.is_hovered = location.contains_point(mouse_pos)

    def get_location_at(self, pos: tuple) -> LocationZone | None:
        """Get the location at a specific position."""
        for location in self.locations.values():
            if location.contains_point(pos):
                return location
        return None

    def place_card(self, location_name: str, card_data: dict, player: Player) -> bool:
        """Place a card at a location."""
        if location_name not in self.locations:
            return False

        location = self.locations[location_name]
        if not location.can_place(player):
            return False

        if player == Player.ATTACKER:
            location.attacker_cards.append(card_data)
        else:
            location.defender_cards.append(card_data)

        return True

    def get_location(self, name: str) -> LocationZone | None:
        """Get a location by name."""
        return self.locations.get(name)

    def resize(self, screen_width: int, screen_height: int):
        """Handle screen resize."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._create_locations()


class LocationPanel:
    """Panel showing cards at a specific location with card images."""

    # Card thumbnail size
    THUMB_WIDTH = 75
    THUMB_HEIGHT = 105

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.is_visible = False
        self.location: LocationZone | None = None
        self.current_player: Player = Player.ATTACKER
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 20)

        # Panel dimensions - larger to fit card images
        self.width = 500
        self.height = 400
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2

        # Cache for card thumbnail images
        self._card_cache: dict[str, pygame.Surface] = {}

    def _get_card_thumbnail(self, card_id: str, card_info: list) -> pygame.Surface:
        """Get or create a thumbnail image for a card."""
        if card_id in self._card_cache:
            return self._card_cache[card_id]

        # Create thumbnail surface
        thumb = pygame.Surface((self.THUMB_WIDTH, self.THUMB_HEIGHT), pygame.SRCALPHA)

        # Card background
        pygame.draw.rect(thumb, (240, 230, 210),
                        (0, 0, self.THUMB_WIDTH, self.THUMB_HEIGHT), border_radius=5)
        pygame.draw.rect(thumb, (139, 90, 43),
                        (0, 0, self.THUMB_WIDTH, self.THUMB_HEIGHT), 2, border_radius=5)

        # Try to load unit image
        unit_path = os.path.join("resources", "Units", f"{card_id}.png")
        if not os.path.exists(unit_path):
            unit_path = os.path.join("resources", "Units", f"{card_id}.jpg")

        if os.path.exists(unit_path):
            try:
                unit_img = pygame.image.load(unit_path).convert_alpha()
                img_rect = unit_img.get_rect()
                scale = min(
                    (self.THUMB_WIDTH - 10) / img_rect.width,
                    (self.THUMB_HEIGHT - 40) / img_rect.height
                )
                new_size = (int(img_rect.width * scale), int(img_rect.height * scale))
                unit_img = pygame.transform.smoothscale(unit_img, new_size)
                img_x = (self.THUMB_WIDTH - new_size[0]) // 2
                thumb.blit(unit_img, (img_x, 18))
            except pygame.error:
                pass

        # Card name at top
        if card_info:
            name = card_info[db.IDX_NAME] if len(card_info) > db.IDX_NAME else card_id
            attack = card_info[db.IDX_ATTACK] if len(card_info) > db.IDX_ATTACK else 0
            health = card_info[db.IDX_HEALTH] if len(card_info) > db.IDX_HEALTH else 0
            cost = card_info[db.IDX_COST] if len(card_info) > db.IDX_COST else 0

            tiny_font = pygame.font.Font(None, 14)

            # Name
            name_text = tiny_font.render(name[:12], True, (50, 40, 30))
            name_rect = name_text.get_rect(centerx=self.THUMB_WIDTH // 2, top=3)
            thumb.blit(name_text, name_rect)

            # Cost circle
            pygame.draw.circle(thumb, (70, 130, 180), (12, 12), 9)
            cost_text = tiny_font.render(str(cost), True, (255, 255, 255))
            cost_rect = cost_text.get_rect(center=(12, 12))
            thumb.blit(cost_text, cost_rect)

            # Stats at bottom
            stats_y = self.THUMB_HEIGHT - 14
            pygame.draw.circle(thumb, (200, 60, 60), (14, stats_y), 8)
            atk_text = tiny_font.render(str(attack), True, (255, 255, 255))
            thumb.blit(atk_text, atk_text.get_rect(center=(14, stats_y)))

            pygame.draw.circle(thumb, (60, 160, 60), (self.THUMB_WIDTH - 14, stats_y), 8)
            hp_text = tiny_font.render(str(health), True, (255, 255, 255))
            thumb.blit(hp_text, hp_text.get_rect(center=(self.THUMB_WIDTH - 14, stats_y)))

        self._card_cache[card_id] = thumb
        return thumb

    def _get_card_back_thumbnail(self) -> pygame.Surface:
        """Get a face-down card thumbnail."""
        if "_back" in self._card_cache:
            return self._card_cache["_back"]

        thumb = pygame.Surface((self.THUMB_WIDTH, self.THUMB_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(thumb, (60, 45, 35),
                        (0, 0, self.THUMB_WIDTH, self.THUMB_HEIGHT), border_radius=5)
        pygame.draw.rect(thumb, (100, 70, 50),
                        (0, 0, self.THUMB_WIDTH, self.THUMB_HEIGHT), 2, border_radius=5)

        # Question mark
        font = pygame.font.Font(None, 30)
        text = font.render("?", True, (100, 80, 60))
        text_rect = text.get_rect(center=(self.THUMB_WIDTH // 2, self.THUMB_HEIGHT // 2))
        thumb.blit(text, text_rect)

        self._card_cache["_back"] = thumb
        return thumb

    def show(self, location: LocationZone, current_player: Player):
        """Show the panel for a location."""
        self.location = location
        self.current_player = current_player
        self.is_visible = True

    def hide(self):
        """Hide the panel."""
        self.is_visible = False
        self.location = None

    def draw(self, screen: pygame.Surface):
        """Draw the location panel with card images."""
        if not self.is_visible or not self.location:
            return

        # Semi-transparent overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, 0))

        # Panel background
        panel_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(screen, (60, 55, 50), panel_rect, border_radius=10)
        pygame.draw.rect(screen, (100, 90, 80), panel_rect, 3, border_radius=10)

        # Title
        title = self.font.render(f"Location: {self.location.name}", True, (255, 255, 255))
        title_rect = title.get_rect(center=(self.x + self.width // 2, self.y + 25))
        screen.blit(title, title_rect)

        # Close button
        close_rect = pygame.Rect(self.x + self.width - 30, self.y + 5, 25, 25)
        pygame.draw.rect(screen, (150, 50, 50), close_rect, border_radius=5)
        close_text = self.font.render("X", True, (255, 255, 255))
        close_text_rect = close_text.get_rect(center=close_rect.center)
        screen.blit(close_text, close_text_rect)

        # Divider
        pygame.draw.line(screen, (100, 90, 80),
                        (self.x + 20, self.y + 50),
                        (self.x + self.width - 20, self.y + 50), 2)

        # Determine what to show based on visibility
        can_see_opponent = self.location.can_see_opponent(self.current_player)

        # Get own and opponent cards based on current player
        if self.current_player == Player.ATTACKER:
            own_cards = self.location.attacker_cards
            opp_cards = self.location.defender_cards
            own_label = "Your Cards (Attacker):"
            opp_label = "Enemy Cards (Defender):"
            own_color = (255, 100, 100)
            opp_color = (100, 150, 255)
        else:
            own_cards = self.location.defender_cards
            opp_cards = self.location.attacker_cards
            own_label = "Your Cards (Defender):"
            opp_label = "Enemy Cards (Attacker):"
            own_color = (100, 150, 255)
            opp_color = (255, 100, 100)

        # Your cards section
        own_label_surface = self.small_font.render(own_label, True, own_color)
        screen.blit(own_label_surface, (self.x + 20, self.y + 60))
        self._draw_cards_row(screen, own_cards, self.x + 20, self.y + 80, True)

        # Divider
        mid_y = self.y + 200
        pygame.draw.line(screen, (100, 90, 80),
                        (self.x + 20, mid_y),
                        (self.x + self.width - 20, mid_y), 1)

        # Enemy cards section
        opp_label_surface = self.small_font.render(opp_label, True, opp_color)
        screen.blit(opp_label_surface, (self.x + 20, mid_y + 10))

        if can_see_opponent:
            self._draw_cards_row(screen, opp_cards, self.x + 20, mid_y + 30, True)
        else:
            self._draw_cards_row(screen, opp_cards, self.x + 20, mid_y + 30, False)

    def _draw_cards_row(self, screen: pygame.Surface, cards: list,
                        x: int, y: int, visible: bool):
        """Draw a row of card thumbnails."""
        if not cards:
            no_cards = self.small_font.render("No cards", True, (150, 150, 150))
            screen.blit(no_cards, (x, y + 40))
            return

        spacing = 10
        for i, card_data in enumerate(cards):
            card_x = x + i * (self.THUMB_WIDTH + spacing)

            # Don't draw if it goes off panel
            if card_x + self.THUMB_WIDTH > self.x + self.width - 20:
                # Show overflow indicator
                more = self.small_font.render(f"+{len(cards) - i} more", True, (150, 150, 150))
                screen.blit(more, (card_x, y + 40))
                break

            if visible:
                card_id = card_data.get("card_id", "Unknown")
                card_info = card_data.get("card_info", [])
                thumb = self._get_card_thumbnail(card_id, card_info)
            else:
                thumb = self._get_card_back_thumbnail()

            screen.blit(thumb, (card_x, y))

    def handle_click(self, pos: tuple) -> bool:
        """Handle click on panel. Returns True if panel should close."""
        if not self.is_visible:
            return False

        # Check close button
        close_rect = pygame.Rect(self.x + self.width - 30, self.y + 5, 25, 25)
        if close_rect.collidepoint(pos):
            self.hide()
            return True

        # Check if click is outside panel
        panel_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        if not panel_rect.collidepoint(pos):
            self.hide()
            return True

        return False

    def resize(self, screen_width: int, screen_height: int):
        """Handle screen resize."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2
