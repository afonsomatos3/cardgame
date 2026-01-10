"""Card class for visual representation and interaction."""

import pygame
import os
import cards_database as db

# Card dimensions
CARD_WIDTH = 125
CARD_HEIGHT = 175
CARD_FOCUS_SCALE = 1.3


class Card:
    """Visual card representation with drag and drop support."""

    def __init__(self, card_id: str, x: float = 0, y: float = 0):
        self.card_id = card_id
        self.card_info = db.get_card_info(card_id) or []

        self.x = x
        self.y = y
        self.target_x = x
        self.target_y = y
        self.angle = 0
        self.target_angle = 0

        self.width = CARD_WIDTH
        self.height = CARD_HEIGHT
        self.scale = 1.0
        self.target_scale = 1.0

        self.is_dragging = False
        self.is_focused = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0

        self.original_x = x
        self.original_y = y

        # Visual surfaces
        self.base_surface = None
        self.unit_image = None
        self._load_assets()

    def _load_assets(self):
        """Load card image assets."""
        # Try to load unit image
        unit_path = os.path.join("resources", "Units", f"{self.card_id}.png")
        if not os.path.exists(unit_path):
            unit_path = os.path.join("resources", "Units", f"{self.card_id}.jpg")

        if os.path.exists(unit_path):
            try:
                self.unit_image = pygame.image.load(unit_path).convert_alpha()
                # Scale to fit card
                img_rect = self.unit_image.get_rect()
                scale_factor = min(
                    (self.width - 20) / img_rect.width,
                    (self.height - 60) / img_rect.height
                )
                new_size = (int(img_rect.width * scale_factor),
                           int(img_rect.height * scale_factor))
                self.unit_image = pygame.transform.smoothscale(self.unit_image, new_size)
            except pygame.error:
                self.unit_image = None

        self._render_base_surface()

    def _render_base_surface(self):
        """Render the base card surface."""
        self.base_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

        # Card background
        pygame.draw.rect(self.base_surface, (240, 230, 210),
                        (0, 0, self.width, self.height), border_radius=8)
        # Card border
        pygame.draw.rect(self.base_surface, (139, 90, 43),
                        (0, 0, self.width, self.height), 3, border_radius=8)

        # Unit image
        if self.unit_image:
            img_rect = self.unit_image.get_rect()
            img_x = (self.width - img_rect.width) // 2
            self.base_surface.blit(self.unit_image, (img_x, 25))

        # Get card info
        if self.card_info:
            name = self.card_info[db.IDX_NAME]
            cost = self.card_info[db.IDX_COST]
            attack = self.card_info[db.IDX_ATTACK]
            health = self.card_info[db.IDX_HEALTH]

            font_small = pygame.font.Font(None, 18)
            font_medium = pygame.font.Font(None, 22)

            # Name at top
            name_surface = font_medium.render(name, True, (50, 40, 30))
            name_rect = name_surface.get_rect(centerx=self.width // 2, top=5)
            self.base_surface.blit(name_surface, name_rect)

            # Cost circle in top-left
            pygame.draw.circle(self.base_surface, (70, 130, 180), (18, 18), 14)
            pygame.draw.circle(self.base_surface, (50, 100, 150), (18, 18), 14, 2)
            cost_text = font_medium.render(str(cost), True, (255, 255, 255))
            cost_rect = cost_text.get_rect(center=(18, 18))
            self.base_surface.blit(cost_text, cost_rect)

            # Stats at bottom
            stats_y = self.height - 22

            # Attack (left)
            pygame.draw.circle(self.base_surface, (200, 60, 60), (22, stats_y), 12)
            atk_text = font_small.render(str(attack), True, (255, 255, 255))
            atk_rect = atk_text.get_rect(center=(22, stats_y))
            self.base_surface.blit(atk_text, atk_rect)

            # Health (right)
            pygame.draw.circle(self.base_surface, (60, 160, 60), (self.width - 22, stats_y), 12)
            hp_text = font_small.render(str(health), True, (255, 255, 255))
            hp_rect = hp_text.get_rect(center=(self.width - 22, stats_y))
            self.base_surface.blit(hp_text, hp_rect)

    def update(self, dt: float):
        """Update card position and scale with smooth interpolation."""
        lerp_speed = 10.0 * dt

        if not self.is_dragging:
            self.x += (self.target_x - self.x) * lerp_speed
            self.y += (self.target_y - self.y) * lerp_speed
            self.angle += (self.target_angle - self.angle) * lerp_speed

        self.scale += (self.target_scale - self.scale) * lerp_speed

    def draw(self, screen: pygame.Surface):
        """Draw the card to the screen."""
        if self.base_surface is None:
            return

        # Scale the surface
        scaled_width = int(self.width * self.scale)
        scaled_height = int(self.height * self.scale)

        if self.angle != 0:
            rotated = pygame.transform.rotozoom(self.base_surface, self.angle, self.scale)
        else:
            rotated = pygame.transform.smoothscale(self.base_surface, (scaled_width, scaled_height))

        # Draw centered at position
        rect = rotated.get_rect(center=(self.x, self.y))
        screen.blit(rotated, rect)

        # Draw shadow when dragging
        if self.is_dragging:
            shadow = pygame.Surface((scaled_width + 10, scaled_height + 10), pygame.SRCALPHA)
            pygame.draw.rect(shadow, (0, 0, 0, 50),
                           (5, 5, scaled_width, scaled_height), border_radius=8)
            shadow_rect = shadow.get_rect(center=(self.x + 5, self.y + 5))
            screen.blit(shadow, shadow_rect)

    def get_rect(self) -> pygame.Rect:
        """Get the card's bounding rectangle."""
        scaled_width = int(self.width * self.scale)
        scaled_height = int(self.height * self.scale)
        return pygame.Rect(
            self.x - scaled_width // 2,
            self.y - scaled_height // 2,
            scaled_width,
            scaled_height
        )

    def contains_point(self, point: tuple) -> bool:
        """Check if a point is inside the card."""
        return self.get_rect().collidepoint(point)

    def start_drag(self, mouse_pos: tuple):
        """Start dragging the card."""
        self.is_dragging = True
        self.drag_offset_x = self.x - mouse_pos[0]
        self.drag_offset_y = self.y - mouse_pos[1]
        self.original_x = self.target_x
        self.original_y = self.target_y
        self.target_scale = CARD_FOCUS_SCALE

    def update_drag(self, mouse_pos: tuple):
        """Update position while dragging."""
        if self.is_dragging:
            self.x = mouse_pos[0] + self.drag_offset_x
            self.y = mouse_pos[1] + self.drag_offset_y

    def end_drag(self):
        """End dragging the card."""
        self.is_dragging = False
        self.target_scale = 1.0

    def return_to_hand(self):
        """Return card to its hand position."""
        self.target_x = self.original_x
        self.target_y = self.original_y
        self.is_dragging = False
        self.target_scale = 1.0

    def set_focus(self, focused: bool):
        """Set focus state for hover effect."""
        self.is_focused = focused
        if focused and not self.is_dragging:
            self.target_scale = CARD_FOCUS_SCALE
            self.target_y = self.original_y - 30
        elif not self.is_dragging:
            self.target_scale = 1.0
            self.target_y = self.original_y

    def set_hand_position(self, x: float, y: float, angle: float = 0):
        """Set the target position in hand."""
        self.target_x = x
        self.target_y = y
        self.target_angle = angle
        self.original_x = x
        self.original_y = y
