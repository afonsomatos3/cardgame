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
                 color: tuple, blocked_by: list = None, is_capturable: bool = False):
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

        # Area control state
        self.is_capturable = is_capturable
        self.controller: Player | None = None
        self.capture_power_attacker = 0
        self.capture_power_defender = 0
        self.capture_threshold_attacker = 5
        self.capture_threshold_defender = 5

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

        # Determine color based on control state
        if self.controller == Player.ATTACKER:
            base_color = (180, 80, 80)  # Red for attacker controlled
        elif self.controller == Player.DEFENDER:
            base_color = (80, 80, 180)  # Blue for defender controlled
        else:
            base_color = (100, 100, 100)  # Grey for neutral/contested

        # Background with transparency
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        alpha = 180 if self.is_hovered else 140
        color_with_alpha = (*base_color, alpha)
        pygame.draw.rect(surface, color_with_alpha, (0, 0, self.width, self.height),
                        border_radius=10)
        screen.blit(surface, (self.x, self.y))

        # Border - colored based on control
        if self.is_hovered:
            border_color = (255, 255, 255)
        elif self.controller == Player.ATTACKER:
            border_color = (255, 120, 120)
        elif self.controller == Player.DEFENDER:
            border_color = (120, 120, 255)
        else:
            border_color = (150, 150, 150)
        pygame.draw.rect(screen, border_color, rect, 2, border_radius=10)

        # Location name
        text = font.render(self.name, True, (255, 255, 255))
        text_rect = text.get_rect(center=(self.x + self.width // 2, self.y + 15))
        screen.blit(text, text_rect)

        # Card count indicators
        small_font = pygame.font.Font(None, 20)

        # Determine visibility - complete fog of war when no presence
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

        # FOG OF WAR: Only show enemy info if player has presence
        # If no presence, show NOTHING about enemy - complete information blackout
        if can_see_opponent:
            if opp_count > 0:
                opp_text = small_font.render(f"{opp_label}: {opp_count}", True, opp_color)
                screen.blit(opp_text, (self.x + 5, self.y + 45))
        # When can_see_opponent is False, show nothing at all about enemy presence

        # Show blocked indicator
        if self.blocked_by:
            blocked_text = small_font.render(f"({', '.join(self.blocked_by)} blocked)",
                                             True, (180, 180, 180))
            blocked_rect = blocked_text.get_rect(
                center=(self.x + self.width // 2, self.y + self.height - 10)
            )
            screen.blit(blocked_text, blocked_rect)

        # Draw capture progress for capturable locations (only if player has presence)
        # FOG OF WAR: completely hide capture progress when no troops present
        if self.is_capturable:
            can_see_progress = current_player is None or self.player_has_presence(current_player) or self.player_has_scout(current_player)
            self._draw_capture_progress(screen, small_font, current_player, can_see_progress)

    def _draw_capture_progress(self, screen: pygame.Surface, font: pygame.font.Font,
                               current_player: Player = None, can_see: bool = True):
        """Draw capture progress bars for this location."""
        # If already controlled, show control indicator (always visible)
        if self.controller is not None:
            control_color = (255, 100, 100) if self.controller == Player.ATTACKER else (100, 100, 255)
            control_text = "ATK" if self.controller == Player.ATTACKER else "DEF"
            indicator = font.render(f"[{control_text}]", True, control_color)
            indicator_rect = indicator.get_rect(
                center=(self.x + self.width // 2, self.y + self.height - 22)
            )
            screen.blit(indicator, indicator_rect)
            return

        # If player can't see progress (no troops there), show "???"
        if not can_see:
            unknown = font.render("[ ? / ? ]", True, (150, 150, 150))
            unknown_rect = unknown.get_rect(
                center=(self.x + self.width // 2, self.y + self.height - 22)
            )
            screen.blit(unknown, unknown_rect)
            return

        # Draw progress bars for uncaptured location
        bar_width = self.width - 20
        bar_height = 6
        bar_x = self.x + 10
        bar_y = self.y + self.height - 28

        # Calculate progress (capped at 100%)
        atk_progress = min(1.0, self.capture_power_attacker / max(1, self.capture_threshold_attacker))
        def_progress = min(1.0, self.capture_power_defender / max(1, self.capture_threshold_defender))

        # Attacker progress bar (red)
        pygame.draw.rect(screen, (80, 40, 40), (bar_x, bar_y, bar_width, bar_height), border_radius=3)
        if atk_progress > 0:
            pygame.draw.rect(screen, (255, 100, 100),
                           (bar_x, bar_y, int(bar_width * atk_progress), bar_height), border_radius=3)

        # Defender progress bar (blue)
        pygame.draw.rect(screen, (40, 40, 80), (bar_x, bar_y + 8, bar_width, bar_height), border_radius=3)
        if def_progress > 0:
            pygame.draw.rect(screen, (100, 100, 255),
                           (bar_x, bar_y + 8, int(bar_width * def_progress), bar_height), border_radius=3)

        # Show power/threshold text
        micro_font = pygame.font.Font(None, 14)
        atk_text = micro_font.render(f"{self.capture_power_attacker}/{self.capture_threshold_attacker}",
                                     True, (255, 150, 150))
        def_text = micro_font.render(f"{self.capture_power_defender}/{self.capture_threshold_defender}",
                                     True, (150, 150, 255))
        screen.blit(atk_text, (bar_x + bar_width + 2, bar_y - 2))
        screen.blit(def_text, (bar_x + bar_width + 2, bar_y + 6))


class Battlefield:
    """The battlefield containing all location zones."""

    # Adjacency for drawing arrows
    CONNECTIONS = [
        ("Camp", "Forest"),
        ("Camp", "Gate"),
        ("Camp", "Walls"),
        ("Forest", "Walls"),
        ("Forest", "Sewers"),
        ("Gate", "Courtyard"),
        ("Walls", "Courtyard"),
        ("Walls", "Keep"),
        ("Sewers", "Keep"),
        ("Courtyard", "Keep"),
    ]

    # Layout rows (from attacker perspective - bottom to top)
    # Row 0 (bottom): Camp, Forest
    # Row 1 (middle): Gate, Walls, Sewers
    # Row 2 (top): Courtyard, Keep
    LAYOUT = {
        "Camp": (0, 0),      # row 0, position 0 (left)
        "Forest": (0, 1),    # row 0, position 1 (right)
        "Gate": (1, 0),      # row 1, position 0 (left)
        "Walls": (1, 1),     # row 1, position 1 (center)
        "Sewers": (1, 2),    # row 1, position 2 (right)
        "Courtyard": (2, 0), # row 2, position 0 (left)
        "Keep": (2, 1),      # row 2, position 1 (right)
    }

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.scale = 1.0
        self.locations: dict[str, LocationZone] = {}
        self.selected_location: LocationZone | None = None
        self.font = pygame.font.Font(None, 24)
        self.current_player: Player = Player.ATTACKER

        self._calculate_scale()
        self._create_locations()

    def _calculate_scale(self):
        """Calculate scale based on screen size."""
        # Base size is 1280x720
        scale_x = self.screen_width / 1280
        scale_y = self.screen_height / 720
        self.scale = min(scale_x, scale_y)

    def _create_locations(self):
        """Create the battlefield locations based on current player POV.

        Layout (from attacker POV - bottom to top):
        Row 2 (top):    Courtyard    Keep
        Row 1 (middle): Gate    Walls    Sewers
        Row 0 (bottom): Camp    Forest

        Defender POV flips vertically (Keep/Courtyard at bottom).
        """
        center_x = self.screen_width // 2
        center_y = self.screen_height // 2

        # Larger zone sizes - stretched to fill more screen
        zone_width = int(170 * self.scale)
        zone_height = int(90 * self.scale)
        h_spacing = int(200 * self.scale)
        v_spacing = int(115 * self.scale)

        # Row Y positions (3 rows)
        row_ys = [
            center_y + v_spacing,       # Row 0 (bottom for attacker)
            center_y,                   # Row 1 (middle)
            center_y - v_spacing,       # Row 2 (top for attacker)
        ]

        # Flip for defender POV
        if self.current_player == Player.DEFENDER:
            row_ys = list(reversed(row_ys))

        # X positions for each row
        # Row 0 & 2: 2 items (spread wider)
        # Row 1: 3 items
        def get_x_for_row(row, pos, num_items):
            if num_items == 2:
                offset = h_spacing * 0.6
                return center_x + (pos - 0.5) * offset * 2
            else:  # 3 items
                return center_x + (pos - 1) * h_spacing

        # Location colors, blocked status, and capturable flag
        # Format: (color, blocked_by, is_capturable)
        loc_props = {
            "Camp": ((180, 100, 80), ["Defender"], False),
            "Forest": ((34, 100, 34), ["Defender"], False),
            "Gate": ((100, 80, 60), [], True),      # Capturable
            "Walls": ((128, 128, 128), [], True),   # Capturable
            "Sewers": ((60, 60, 80), [], True),     # Capturable
            "Courtyard": ((160, 140, 100), ["Attacker"], False),
            "Keep": ((139, 90, 43), ["Attacker"], False),
        }

        self.locations.clear()

        for name, (row, pos) in self.LAYOUT.items():
            # Determine number of items in this row
            num_in_row = 2 if row in [0, 2] else 3

            # Calculate position
            x = get_x_for_row(row, pos, num_in_row) - zone_width // 2
            y = row_ys[row] - zone_height // 2

            color, blocked, is_capturable = loc_props[name]

            self.locations[name] = LocationZone(
                name, int(x), int(y),
                zone_width, zone_height,
                color, blocked, is_capturable
            )

    def set_current_player(self, player: Player):
        """Set the current player for visibility calculations and POV flip."""
        if self.current_player != player:
            # Save card data before recreating locations
            saved_cards = {}
            for name, loc in self.locations.items():
                saved_cards[name] = {
                    "attacker": loc.attacker_cards.copy(),
                    "defender": loc.defender_cards.copy()
                }

            self.current_player = player
            self._create_locations()

            # Restore card data
            for name, cards in saved_cards.items():
                if name in self.locations:
                    self.locations[name].attacker_cards = cards["attacker"]
                    self.locations[name].defender_cards = cards["defender"]

    def _draw_arrow(self, screen: pygame.Surface, start: tuple, end: tuple, color: tuple):
        """Draw an arrow between two points."""
        import math

        # Draw the line
        pygame.draw.line(screen, color, start, end, 2)

        # Calculate arrow head
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        arrow_size = 8 * self.scale

        # Arrow head points
        left_angle = angle + math.pi * 0.8
        right_angle = angle - math.pi * 0.8

        left_point = (
            end[0] - arrow_size * math.cos(left_angle),
            end[1] - arrow_size * math.sin(left_angle)
        )
        right_point = (
            end[0] - arrow_size * math.cos(right_angle),
            end[1] - arrow_size * math.sin(right_angle)
        )

        pygame.draw.polygon(screen, color, [end, left_point, right_point])

    def _draw_connection(self, screen: pygame.Surface, loc1_name: str, loc2_name: str):
        """Draw a bidirectional connection between two locations."""
        loc1 = self.locations.get(loc1_name)
        loc2 = self.locations.get(loc2_name)
        if not loc1 or not loc2:
            return

        # Get center points
        c1 = (loc1.x + loc1.width // 2, loc1.y + loc1.height // 2)
        c2 = (loc2.x + loc2.width // 2, loc2.y + loc2.height // 2)

        # Calculate points on the edge of each zone
        import math
        angle = math.atan2(c2[1] - c1[1], c2[0] - c1[0])

        # Offset from center to edge
        offset1_x = (loc1.width // 2 + 5) * math.cos(angle)
        offset1_y = (loc1.height // 2 + 5) * math.sin(angle)
        offset2_x = (loc2.width // 2 + 5) * math.cos(angle)
        offset2_y = (loc2.height // 2 + 5) * math.sin(angle)

        start = (c1[0] + offset1_x, c1[1] + offset1_y)
        end = (c2[0] - offset2_x, c2[1] - offset2_y)

        # Draw line with subtle color
        color = (80, 80, 80)
        pygame.draw.line(screen, color, start, end, max(1, int(2 * self.scale)))

    def draw(self, screen: pygame.Surface):
        """Draw the entire battlefield."""
        # Draw battlefield background (stretched to fill more screen)
        bf_width = int(650 * self.scale)
        bf_height = int(420 * self.scale)
        bf_rect = pygame.Rect(
            self.screen_width // 2 - bf_width // 2,
            self.screen_height // 2 - bf_height // 2,
            bf_width, bf_height
        )
        pygame.draw.rect(screen, (40, 40, 45), bf_rect, border_radius=15)
        pygame.draw.rect(screen, (70, 70, 75), bf_rect, 2, border_radius=15)

        # Draw connections first (behind locations)
        for loc1, loc2 in self.CONNECTIONS:
            self._draw_connection(screen, loc1, loc2)

        # Draw section labels based on POV
        font_size = max(16, int(22 * self.scale))
        label_font = pygame.font.Font(None, font_size)

        if self.current_player == Player.ATTACKER:
            # Attacker POV: Defender at top, Attacker at bottom
            top_label = "DEFENDER TERRITORY"
            top_color = (100, 100, 200)
            bottom_label = "YOUR TERRITORY (ATTACKER)"
            bottom_color = (200, 100, 100)
        else:
            # Defender POV: Attacker at top, Defender at bottom
            top_label = "ATTACKER TERRITORY"
            top_color = (200, 100, 100)
            bottom_label = "YOUR TERRITORY (DEFENDER)"
            bottom_color = (100, 100, 200)

        # Top label
        top_surface = label_font.render(top_label, True, top_color)
        top_rect = top_surface.get_rect(center=(self.screen_width // 2, bf_rect.top + int(14 * self.scale)))
        screen.blit(top_surface, top_rect)

        # Bottom label
        bottom_surface = label_font.render(bottom_label, True, bottom_color)
        bottom_rect = bottom_surface.get_rect(center=(self.screen_width // 2, bf_rect.bottom - int(14 * self.scale)))
        screen.blit(bottom_surface, bottom_rect)

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
        self._calculate_scale()
        self._create_locations()

    def move_card(self, from_loc: str, to_loc: str, card_index: int, player: Player) -> bool:
        """Move a card visually between locations."""
        from_location = self.locations.get(from_loc)
        to_location = self.locations.get(to_loc)

        if not from_location or not to_location:
            return False

        # Get the card list
        if player == Player.ATTACKER:
            cards = from_location.attacker_cards
            dest_cards = to_location.attacker_cards
        else:
            cards = from_location.defender_cards
            dest_cards = to_location.defender_cards

        if card_index < 0 or card_index >= len(cards):
            return False

        # Move the card
        card = cards.pop(card_index)
        dest_cards.append(card)
        return True

    def sync_capture_state(self, game_manager):
        """Sync capture state from GameManager to location zones."""
        for name, location in self.locations.items():
            # Always sync controller (for color display)
            location.controller = game_manager.location_control.get(name)

            # Sync capture progress for capturable locations
            if location.is_capturable:
                info = game_manager.get_location_capture_info(name)
                location.capture_power_attacker = info.get("attacker_power", 0)
                location.capture_power_defender = info.get("defender_power", 0)
                location.capture_threshold_attacker = info.get("attacker_threshold", 5)
                location.capture_threshold_defender = info.get("defender_threshold", 5)

            # Update blocked_by based on actual access (considering conquests)
            new_blocked = []
            if not game_manager.can_place_at_location(name, Player.ATTACKER):
                new_blocked.append("Attacker")
            if not game_manager.can_place_at_location(name, Player.DEFENDER):
                new_blocked.append("Defender")
            location.blocked_by = new_blocked


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
        self.height = 450
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2

        # Cache for card thumbnail images
        self._card_cache: dict[str, pygame.Surface] = {}

        # Movement state
        self.selected_card_index: int | None = None
        self.game_manager = None  # Set from main.py
        self.battlefield = None   # Set from main.py for visual updates
        self._card_rects: list[pygame.Rect] = []  # Track clickable card areas
        self._move_buttons: list[tuple[pygame.Rect, str]] = []  # (rect, destination)

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
            special = card_info[db.IDX_SPECIAL] if len(card_info) > db.IDX_SPECIAL else ""

            tiny_font = pygame.font.Font(None, 14)
            micro_font = pygame.font.Font(None, 11)

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

            # Special text area (if card has special ability)
            if special:
                special_y = self.THUMB_HEIGHT - 35
                # Draw special text background
                special_bg = pygame.Surface((self.THUMB_WIDTH - 4, 28), pygame.SRCALPHA)
                pygame.draw.rect(special_bg, (240, 220, 180, 180), (0, 0, self.THUMB_WIDTH - 4, 28), border_radius=2)
                pygame.draw.rect(special_bg, (139, 90, 43), (0, 0, self.THUMB_WIDTH - 4, 28), 1, border_radius=2)
                thumb.blit(special_bg, (2, special_y))
                # Wrap and render special text
                words = special.split()
                lines = []
                current_line = []
                for word in words:
                    test_line = ' '.join(current_line + [word])
                    if micro_font.size(test_line)[0] < self.THUMB_WIDTH - 6:
                        current_line.append(word)
                    else:
                        if current_line:
                            lines.append(' '.join(current_line))
                        current_line = [word]
                if current_line:
                    lines.append(' '.join(current_line))
                for i, line in enumerate(lines[:1]):  # Max 1 line for thumbnail
                    special_text = micro_font.render(line[:20], True, (50, 40, 30))
                    text_rect = special_text.get_rect(centerx=self.THUMB_WIDTH // 2, y=special_y + 4)
                    thumb.blit(special_text, text_rect)

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
        self.selected_card_index = None
        self._card_rects = []
        self._move_buttons = []

    def hide(self):
        """Hide the panel."""
        self.is_visible = False
        self.location = None
        self.selected_card_index = None
        self._card_rects = []
        self._move_buttons = []

    def draw(self, screen: pygame.Surface):
        """Draw the location panel with card images."""
        if not self.is_visible or not self.location:
            return

        # Clear tracking lists
        self._card_rects = []
        self._move_buttons = []

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
            own_label = "Your Cards (Attacker) - Click to select for movement:"
            opp_label = "Enemy Cards (Defender):"
            own_color = (255, 100, 100)
            opp_color = (100, 150, 255)
        else:
            own_cards = self.location.defender_cards
            opp_cards = self.location.attacker_cards
            own_label = "Your Cards (Defender) - Click to select for movement:"
            opp_label = "Enemy Cards (Attacker):"
            own_color = (100, 150, 255)
            opp_color = (255, 100, 100)

        # Your cards section
        own_label_surface = self.small_font.render(own_label, True, own_color)
        screen.blit(own_label_surface, (self.x + 20, self.y + 60))
        self._draw_own_cards_row(screen, own_cards, self.x + 20, self.y + 80)

        # Movement section (if a card is selected)
        move_section_y = self.y + 200
        self._draw_movement_section(screen, own_cards, move_section_y)

        # Divider
        mid_y = self.y + 260
        pygame.draw.line(screen, (100, 90, 80),
                        (self.x + 20, mid_y),
                        (self.x + self.width - 20, mid_y), 1)

        # Enemy cards section - FOG OF WAR: hide completely when no visibility
        if can_see_opponent:
            opp_label_surface = self.small_font.render(opp_label, True, opp_color)
            screen.blit(opp_label_surface, (self.x + 20, mid_y + 10))
            self._draw_cards_row(screen, opp_cards, self.x + 20, mid_y + 30, True)
        else:
            # Complete fog of war - no information about enemy presence
            fog_label = "Enemy Cards: [NO INTEL]"
            fog_surface = self.small_font.render(fog_label, True, (100, 100, 100))
            screen.blit(fog_surface, (self.x + 20, mid_y + 10))

            # Draw fog of war visual
            fog_text = self.font.render("No troops in area - enemy hidden", True, (120, 120, 120))
            fog_rect = fog_text.get_rect(center=(self.x + self.width // 2, mid_y + 80))
            screen.blit(fog_text, fog_rect)

    def _draw_cards_row(self, screen: pygame.Surface, cards: list,
                        x: int, y: int, visible: bool):
        """Draw a row of card thumbnails (for opponent cards)."""
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
                is_tapped = card_data.get("is_tapped", False)
                thumb = self._get_card_thumbnail(card_id, card_info)
            else:
                is_tapped = False
                thumb = self._get_card_back_thumbnail()

            screen.blit(thumb, (card_x, y))

            # Draw tapped indicator for visible cards
            if visible and is_tapped:
                tapped_overlay = pygame.Surface((self.THUMB_WIDTH, self.THUMB_HEIGHT), pygame.SRCALPHA)
                pygame.draw.rect(tapped_overlay, (80, 80, 80, 150),
                               (0, 0, self.THUMB_WIDTH, self.THUMB_HEIGHT), border_radius=5)
                screen.blit(tapped_overlay, (card_x, y))
                tapped_font = pygame.font.Font(None, 16)
                tapped_text = tapped_font.render("TAPPED", True, (255, 200, 100))
                text_rect = tapped_text.get_rect(center=(card_x + self.THUMB_WIDTH // 2, y + self.THUMB_HEIGHT // 2))
                screen.blit(tapped_text, text_rect)

    def _draw_own_cards_row(self, screen: pygame.Surface, cards: list, x: int, y: int):
        """Draw a row of own card thumbnails with selection support."""
        if not cards:
            no_cards = self.small_font.render("No cards here", True, (150, 150, 150))
            screen.blit(no_cards, (x, y + 40))
            return

        spacing = 10
        for i, card_data in enumerate(cards):
            card_x = x + i * (self.THUMB_WIDTH + spacing)

            # Don't draw if it goes off panel
            if card_x + self.THUMB_WIDTH > self.x + self.width - 20:
                more = self.small_font.render(f"+{len(cards) - i} more", True, (150, 150, 150))
                screen.blit(more, (card_x, y + 40))
                break

            card_id = card_data.get("card_id", "Unknown")
            card_info = card_data.get("card_info", [])
            is_tapped = card_data.get("is_tapped", False)
            thumb = self._get_card_thumbnail(card_id, card_info)

            # Track card rect for click detection
            card_rect = pygame.Rect(card_x, y, self.THUMB_WIDTH, self.THUMB_HEIGHT)
            self._card_rects.append((card_rect, i))

            # Draw selection highlight
            if self.selected_card_index == i:
                highlight = pygame.Surface((self.THUMB_WIDTH + 6, self.THUMB_HEIGHT + 6), pygame.SRCALPHA)
                pygame.draw.rect(highlight, (255, 200, 50, 180),
                               (0, 0, self.THUMB_WIDTH + 6, self.THUMB_HEIGHT + 6), border_radius=7)
                screen.blit(highlight, (card_x - 3, y - 3))

            screen.blit(thumb, (card_x, y))

            # Draw tapped indicator (gray overlay with "TAPPED" text)
            if is_tapped:
                tapped_overlay = pygame.Surface((self.THUMB_WIDTH, self.THUMB_HEIGHT), pygame.SRCALPHA)
                pygame.draw.rect(tapped_overlay, (80, 80, 80, 150),
                               (0, 0, self.THUMB_WIDTH, self.THUMB_HEIGHT), border_radius=5)
                screen.blit(tapped_overlay, (card_x, y))
                # Draw "TAPPED" text
                tapped_font = pygame.font.Font(None, 16)
                tapped_text = tapped_font.render("TAPPED", True, (255, 200, 100))
                text_rect = tapped_text.get_rect(center=(card_x + self.THUMB_WIDTH // 2, y + self.THUMB_HEIGHT // 2))
                screen.blit(tapped_text, text_rect)

    def _draw_movement_section(self, screen: pygame.Surface, own_cards: list, y: int):
        """Draw the movement section with destination buttons."""
        # Check if movement is possible
        can_move = self.game_manager and self.game_manager.can_move_card(self.current_player)

        if self.selected_card_index is not None and 0 <= self.selected_card_index < len(own_cards):
            selected_card = own_cards[self.selected_card_index]
            card_name = selected_card.get("card_id", "Unknown")

            # Show selected card name
            select_text = f"Selected: {card_name}"
            select_surface = self.small_font.render(select_text, True, (255, 200, 50))
            screen.blit(select_surface, (self.x + 20, y))

            if not can_move:
                # Already moved this phase
                moved_text = self.small_font.render("(Already moved this phase)", True, (150, 100, 100))
                screen.blit(moved_text, (self.x + 20, y + 20))
            elif self.game_manager:
                # Show adjacent locations to move to
                move_text = self.small_font.render("Move to:", True, (200, 200, 200))
                screen.blit(move_text, (self.x + 20, y + 20))

                # Get adjacent locations
                adjacent = self.game_manager.get_adjacent_locations(self.location.name)
                btn_x = self.x + 90
                btn_y = y + 18
                btn_height = 22
                btn_spacing = 5

                for dest in adjacent:
                    # Check if player can be at that location
                    if self.game_manager.can_place_at_location(dest, self.current_player):
                        # Calculate button width based on text
                        btn_text = self.small_font.render(dest, True, (255, 255, 255))
                        btn_width = btn_text.get_width() + 16
                        btn_rect = pygame.Rect(btn_x, btn_y, btn_width, btn_height)

                        # Draw button
                        pygame.draw.rect(screen, (70, 130, 70), btn_rect, border_radius=4)
                        pygame.draw.rect(screen, (100, 180, 100), btn_rect, 1, border_radius=4)
                        text_rect = btn_text.get_rect(center=btn_rect.center)
                        screen.blit(btn_text, text_rect)

                        # Track button for click detection
                        self._move_buttons.append((btn_rect, dest))

                        btn_x += btn_width + btn_spacing
        else:
            # No card selected
            if own_cards:
                hint = "Click a card above to select it for movement"
            else:
                hint = "No cards to move"

            if not can_move and own_cards:
                hint = "Already moved a card this phase"

            hint_surface = self.small_font.render(hint, True, (150, 150, 150))
            screen.blit(hint_surface, (self.x + 20, y))

    def handle_click(self, pos: tuple) -> str | bool:
        """Handle click on panel.

        Returns:
            - True if panel should close
            - "moved" if a card was moved
            - False otherwise
        """
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

        # Check move button clicks
        for btn_rect, destination in self._move_buttons:
            if btn_rect.collidepoint(pos):
                if self._execute_move(destination):
                    return "moved"
                return False

        # Check card selection clicks
        for card_rect, index in self._card_rects:
            if card_rect.collidepoint(pos):
                if self.selected_card_index == index:
                    # Deselect if clicking same card
                    self.selected_card_index = None
                else:
                    self.selected_card_index = index
                return False

        return False

    def _execute_move(self, destination: str) -> bool:
        """Execute the card movement."""
        if not self.game_manager or not self.location or self.selected_card_index is None:
            return False

        # Execute move in game manager
        success = self.game_manager.move_card(
            self.location.name,
            destination,
            self.selected_card_index,
            self.current_player
        )

        if success and self.battlefield:
            # Update battlefield visual
            self.battlefield.move_card(
                self.location.name,
                destination,
                self.selected_card_index,
                self.current_player
            )

        # Clear selection after move
        self.selected_card_index = None
        return success

    def resize(self, screen_width: int, screen_height: int):
        """Handle screen resize."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2
