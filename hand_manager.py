"""Hand manager for arranging cards in an oval layout."""

import math
import pygame
from card import Card, CARD_WIDTH


class HandManager:
    """Manages a player's hand of cards with oval layout."""

    def __init__(self, screen_width: int, screen_height: int, is_bottom: bool = True):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.is_bottom = is_bottom
        self.cards: list[Card] = []

        # Oval parameters - adjusted so cards are visible
        self.center_x = screen_width // 2
        if is_bottom:
            self.center_y = screen_height + 50  # Cards visible at bottom
        else:
            self.center_y = -50  # Cards visible at top

        self.radius_x = screen_width * 0.35
        self.radius_y = 80

        self.focused_card: Card | None = None
        self.dragging_card: Card | None = None

    def add_card(self, card: Card):
        """Add a card to the hand."""
        self.cards.append(card)
        self._reorganize_hand()

    def remove_card(self, card: Card):
        """Remove a card from the hand."""
        if card in self.cards:
            self.cards.remove(card)
            self._reorganize_hand()

    def _reorganize_hand(self):
        """Reorganize cards in oval layout."""
        if not self.cards:
            return

        num_cards = len(self.cards)
        arc_span = min(math.pi * 0.6, num_cards * 0.15)
        start_angle = math.pi / 2 - arc_span / 2
        end_angle = math.pi / 2 + arc_span / 2

        for i, card in enumerate(self.cards):
            if num_cards == 1:
                angle = math.pi / 2
            else:
                angle = start_angle + (end_angle - start_angle) * (i / (num_cards - 1))

            x = self.center_x + self.radius_x * math.cos(angle)

            if self.is_bottom:
                y = self.center_y - self.radius_y * math.sin(angle)
            else:
                y = self.center_y + self.radius_y * math.sin(angle)

            # Calculate rotation angle
            rotation = 0
            if self.is_bottom:
                rotation = (angle - math.pi / 2) * 30
            else:
                rotation = -(angle - math.pi / 2) * 30

            card.set_hand_position(x, y, rotation)

    def update(self, dt: float):
        """Update all cards."""
        for card in self.cards:
            card.update(dt)

    def draw(self, screen: pygame.Surface):
        """Draw all cards, with focused/dragged card on top."""
        # Draw non-focused cards first
        for card in self.cards:
            if card != self.focused_card and card != self.dragging_card:
                card.draw(screen)

        # Draw focused card on top
        if self.focused_card and self.focused_card != self.dragging_card:
            self.focused_card.draw(screen)

        # Draw dragging card on very top
        if self.dragging_card:
            self.dragging_card.draw(screen)

    def handle_mouse_motion(self, mouse_pos: tuple):
        """Handle mouse movement for hover effects."""
        if self.dragging_card:
            self.dragging_card.update_drag(mouse_pos)
            return

        # Check for hover
        new_focus = None
        for card in reversed(self.cards):
            if card.contains_point(mouse_pos):
                new_focus = card
                break

        if new_focus != self.focused_card:
            if self.focused_card:
                self.focused_card.set_focus(False)
            if new_focus:
                new_focus.set_focus(True)
            self.focused_card = new_focus

    def handle_mouse_down(self, mouse_pos: tuple) -> Card | None:
        """Handle mouse button down, returns card if one is picked up."""
        for card in reversed(self.cards):
            if card.contains_point(mouse_pos):
                card.start_drag(mouse_pos)
                self.dragging_card = card
                return card
        return None

    def handle_mouse_up(self, mouse_pos: tuple) -> Card | None:
        """Handle mouse button up, returns the dropped card."""
        dropped_card = self.dragging_card
        if self.dragging_card:
            self.dragging_card.end_drag()
            self.dragging_card = None
        return dropped_card

    def return_card_to_hand(self, card: Card):
        """Return a card to its position in hand."""
        if card in self.cards:
            card.return_to_hand()
            self.dragging_card = None

    def resize(self, screen_width: int, screen_height: int):
        """Handle screen resize."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.center_x = screen_width // 2

        if self.is_bottom:
            self.center_y = screen_height + 50
        else:
            self.center_y = -50

        self.radius_x = screen_width * 0.35
        self._reorganize_hand()

    def get_card_at(self, pos: tuple) -> Card | None:
        """Get the card at a specific position."""
        for card in reversed(self.cards):
            if card.contains_point(pos):
                return card
        return None
