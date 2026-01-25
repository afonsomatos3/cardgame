"""Network client for WarMasterMind multiplayer."""

import asyncio
import json
import threading
from queue import Queue, Empty
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed


class NetworkClient:
    """Handles WebSocket connection to game server."""

    def __init__(self, server_url: str = "ws://localhost:8765"):
        self.server_url = server_url
        self.websocket = None
        self.connected = False
        self.authenticated = False
        self.token = None
        self.user_id = None
        self.username = None

        # Message queues
        self.incoming_queue = Queue()
        self.outgoing_queue = Queue()

        # Threading
        self._receive_thread = None
        self._send_thread = None
        self._running = False

        # Callbacks
        self.on_game_state = None
        self.on_match_found = None
        self.on_action_result = None
        self.on_error = None
        self.on_register_result = None
        self.on_friends_list = None
        self.on_friend_request = None
        self.on_friend_request_result = None
        self.on_friend_status = None

        # Registration state
        self.register_success = False
        self.registered_user_id = None

    def connect(self) -> bool:
        """Connect to the server."""
        try:
            self.websocket = connect(self.server_url)
            self.connected = True
            self._running = True

            # Start receive thread
            self._receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._receive_thread.start()

            # Start send thread
            self._send_thread = threading.Thread(target=self._send_loop, daemon=True)
            self._send_thread.start()

            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from server."""
        self._running = False
        if self.websocket:
            try:
                self.websocket.close()
            except:
                pass
        self.connected = False
        self.authenticated = False

    def _receive_loop(self):
        """Background thread to receive messages."""
        while self._running and self.websocket:
            try:
                message = self.websocket.recv(timeout=0.1)
                data = json.loads(message)
                self.incoming_queue.put(data)
            except TimeoutError:
                continue
            except ConnectionClosed:
                self.connected = False
                break
            except Exception as e:
                print(f"Receive error: {e}")
                break

    def _send_loop(self):
        """Background thread to send messages."""
        while self._running and self.websocket:
            try:
                message = self.outgoing_queue.get(timeout=0.1)
                self.websocket.send(json.dumps(message))
            except Empty:
                continue
            except ConnectionClosed:
                self.connected = False
                break
            except Exception as e:
                print(f"Send error: {e}")
                break

    def send(self, message: dict):
        """Queue a message to send."""
        self.outgoing_queue.put(message)

    def process_messages(self) -> list:
        """Process all pending incoming messages. Call this in your game loop."""
        messages = []
        while True:
            try:
                msg = self.incoming_queue.get_nowait()
                messages.append(msg)
                self._handle_message(msg)
            except Empty:
                break
        return messages

    def _handle_message(self, msg: dict):
        """Handle a received message."""
        msg_type = msg.get("type")

        if msg_type == "auth_success":
            self.authenticated = True
            self.user_id = msg.get("user_id")
            self.username = msg.get("username")

        elif msg_type == "register_result":
            if msg.get("success"):
                # Registration successful - notify via callback
                self.register_success = True
                self.registered_user_id = msg.get("user_id")
                if self.on_register_result:
                    self.on_register_result(True, "Registration successful! Please log in.")
            else:
                self.register_success = False
                error_msg = msg.get("message", "Registration failed")
                if self.on_register_result:
                    self.on_register_result(False, error_msg)
                elif self.on_error:
                    self.on_error(error_msg)

        elif msg_type == "login_result":
            if msg.get("success"):
                self.authenticated = True
                self.token = msg.get("token")
                self.user_id = msg.get("user_id")
                self.username = msg.get("username")
            else:
                error_msg = msg.get("message", "Login failed")
                if self.on_error:
                    self.on_error(error_msg)

        elif msg_type == "game_state":
            if self.on_game_state:
                self.on_game_state(msg.get("data"))

        elif msg_type == "match_found":
            if self.on_match_found:
                self.on_match_found(msg)

        elif msg_type == "action_result":
            if self.on_action_result:
                self.on_action_result(msg)

        elif msg_type == "friends_list":
            if self.on_friends_list:
                self.on_friends_list(msg.get("friends", []))

        elif msg_type == "friend_request_received":
            if self.on_friend_request:
                self.on_friend_request(msg)

        elif msg_type == "friend_request_result":
            if self.on_friend_request_result:
                self.on_friend_request_result(msg)

        elif msg_type == "friend_status_update":
            if self.on_friend_status:
                self.on_friend_status(msg)

        elif msg_type in ["auth_failed", "match_error"]:
            if self.on_error:
                self.on_error(msg.get("error", "Unknown error"))

    # ==================== API Methods ====================

    def register(self, username: str, password: str):
        """Register a new account."""
        self.send({
            "type": "register",
            "username": username,
            "password": password
        })

    def login(self, username: str, password: str):
        """Login to an existing account."""
        self.send({
            "type": "login",
            "username": username,
            "password": password
        })

    def auth_with_token(self, token: str):
        """Authenticate with an existing token."""
        self.token = token
        self.send({
            "type": "auth",
            "token": token
        })

    def find_match(self):
        """Start matchmaking."""
        self.send({"type": "find_match"})

    def cancel_match(self):
        """Cancel matchmaking."""
        self.send({"type": "cancel_match"})

    def get_decks(self):
        """Request user's decks."""
        self.send({"type": "get_decks"})

    def save_deck(self, name: str, cards: list, is_active: bool = False):
        """Save a deck."""
        self.send({
            "type": "save_deck",
            "name": name,
            "cards": cards,
            "is_active": is_active
        })

    def set_active_deck(self, deck_id: int):
        """Set active deck."""
        self.send({
            "type": "set_active_deck",
            "deck_id": deck_id
        })

    def get_stats(self):
        """Get user statistics."""
        self.send({"type": "get_stats"})

    def get_cards(self):
        """Get available cards for deck building."""
        self.send({"type": "get_cards"})

    # ==================== Game Actions ====================

    def draw_card(self, card_id: str):
        """Draw a card from deck."""
        self.send({
            "type": "game_action",
            "action": {
                "action": "draw_card",
                "card_id": card_id
            }
        })

    def place_card(self, card_id: str, location: str, zone: str = "middle_zone"):
        """Place a card on the battlefield in a specific zone."""
        self.send({
            "type": "game_action",
            "action": {
                "action": "place_card",
                "card_id": card_id,
                "location": location,
                "zone": zone
            }
        })

    def move_card(self, from_location: str, to_location: str, card_index: int):
        """Move a card between locations."""
        self.send({
            "type": "game_action",
            "action": {
                "action": "move_card",
                "from_location": from_location,
                "to_location": to_location,
                "card_index": card_index
            }
        })

    def end_turn(self):
        """End your turn."""
        self.send({
            "type": "game_action",
            "action": {"action": "end_turn"}
        })

    # ==================== Friend Actions ====================

    def get_friends(self):
        """Get friends list."""
        self.send({"type": "get_friends"})

    def send_friend_request(self, username: str):
        """Send a friend request to a user by username."""
        self.send({
            "type": "send_friend_request",
            "username": username
        })

    def accept_friend_request(self, request_id: int):
        """Accept a friend request."""
        self.send({
            "type": "accept_friend_request",
            "request_id": request_id
        })

    def decline_friend_request(self, request_id: int):
        """Decline a friend request."""
        self.send({
            "type": "decline_friend_request",
            "request_id": request_id
        })

    def remove_friend(self, friend_id: int):
        """Remove a friend."""
        self.send({
            "type": "remove_friend",
            "friend_id": friend_id
        })

    def get_pending_requests(self):
        """Get pending friend requests."""
        self.send({"type": "get_pending_requests"})
