"""WebSocket Game Server for WarMasterMind multiplayer."""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from websockets.server import serve
from websockets.exceptions import ConnectionClosed
from database import Database
from game_manager import GameManager, Player
import cards_database as db


class GameSession:
    """Represents an active game session between two players."""

    def __init__(self, match_id: int, attacker_id: int, defender_id: int,
                 attacker_deck: list, defender_deck: list):
        self.match_id = match_id
        self.attacker_id = attacker_id
        self.defender_id = defender_id

        # Initialize game manager with player decks
        self.game_manager = GameManager()
        self.game_manager.player_decks[Player.ATTACKER] = attacker_deck.copy()
        self.game_manager.player_decks[Player.DEFENDER] = defender_deck.copy()

        # Setup starting hands (Avatar for both)
        self._setup_starting_hands()

        # WebSocket connections
        self.connections: dict[int, any] = {}  # user_id -> websocket

        # Game state
        self.is_active = True
        self.winner: str | None = None  # "attacker" or "defender" when game ends

        # Combat phase state (for Hearthstone-style blocking with zones)
        # Each entry is (location, zone) tuple
        self.pending_combat_zones: list[tuple[str, str]] = []  # [(location, zone), ...]
        self.combat_assignments: dict[str, dict[str, dict]] = {}  # location -> zone -> {attacker_idx: [blocker_indices]}
        self.awaiting_blocker_selection: tuple[str, str] | None = None  # (location, zone) awaiting selection

    def _setup_starting_hands(self):
        """Setup starting hands for both players."""
        for player in [Player.ATTACKER, Player.DEFENDER]:
            avatar_info = db.get_card_info("Avatar")
            if avatar_info:
                self.game_manager.add_card_to_hand("Avatar", avatar_info, player)

    def get_player_role(self, user_id: int) -> Player | None:
        """Get the role (ATTACKER/DEFENDER) for a user."""
        if user_id == self.attacker_id:
            return Player.ATTACKER
        elif user_id == self.defender_id:
            return Player.DEFENDER
        return None

    def get_game_state_for_player(self, user_id: int) -> dict:
        """Get the game state visible to a specific player (fog of war applied)."""
        try:
            player = self.get_player_role(user_id)
            if not player:
                return {}

            gm = self.game_manager
            player_key = "attacker" if player == Player.ATTACKER else "defender"
            enemy_key = "defender" if player == Player.ATTACKER else "attacker"

            # Build battlefield state with fog of war (3-zone structure)
            battlefield = {}
            for location in gm.LOCATIONS:
                loc_data = gm.battlefield_cards[location]

                # Build zone data for this location
                zones = {}
                has_presence = False
                has_scout = False

                for zone_name in ["attacker_zone", "middle_zone", "defender_zone"]:
                    zone_data = loc_data[zone_name]
                    own_cards = zone_data[player_key]
                    enemy_cards = zone_data[enemy_key]

                    if own_cards:
                        has_presence = True

                    # Check for Scout subtype in own cards
                    for c in own_cards:
                        card_info = c.get("card_info", [])
                        if len(card_info) > db.IDX_SUBTYPE:
                            subtype = card_info[db.IDX_SUBTYPE] or ""
                            if "Scout" in subtype:
                                has_scout = True

                    zones[zone_name] = {
                        "own_cards": [self._serialize_card(c) for c in own_cards],
                        "enemy_cards": None,  # Set below based on visibility
                        "enemy_count": len(enemy_cards),
                        "first_placer": zone_data.get("first_placer") if zone_name == "middle_zone" else None
                    }

                can_see = has_presence or has_scout

                # Update enemy visibility based on can_see
                for zone_name in ["attacker_zone", "middle_zone", "defender_zone"]:
                    zone_data = loc_data[zone_name]
                    enemy_cards = zone_data[enemy_key]
                    if can_see:
                        zones[zone_name]["enemy_cards"] = [self._serialize_card(c) for c in enemy_cards]

                # Convert controller enum to string
                controller = gm.location_control.get(location)
                controller_str = None
                if controller == Player.ATTACKER:
                    controller_str = "attacker"
                elif controller == Player.DEFENDER:
                    controller_str = "defender"

                # Get capture info for all capturable locations (always visible)
                raw_capture_info = gm.get_location_capture_info(location)
                capture_info = None
                if raw_capture_info:
                    capture_info = dict(raw_capture_info)
                    # Convert controller enum to string
                    if capture_info.get("controller") == Player.ATTACKER:
                        capture_info["controller"] = "attacker"
                    elif capture_info.get("controller") == Player.DEFENDER:
                        capture_info["controller"] = "defender"
                    else:
                        capture_info["controller"] = None

                battlefield[location] = {
                    "zones": zones,
                    "can_see": can_see,
                    "controller": controller_str,
                    "capture_info": capture_info
                }

            # Get hand
            hand = gm.get_hand(player)

            # Get reinforcements
            reinforcements = gm.get_hand_reinforcements(player)

            # Get deck count (not the actual cards)
            deck_count = len(gm.get_deck(player))

            # Combat phase info (zone-based)
            combat_state = None
            if self.awaiting_blocker_selection:
                loc, zone = self.awaiting_blocker_selection
                zone_data = gm.battlefield_cards[loc][zone]

                # Determine who assigns blockers based on zone rules
                blocker_side = gm.get_blocker_side(loc, zone)

                # Is it this player's turn to assign?
                is_your_combat = (player_key == blocker_side)

                # Get cards in the zone
                atk_cards = zone_data["attacker"]
                def_cards = zone_data["defender"]

                # In zone-based combat:
                # - The "blocker_side" player assigns blockers
                # - The other side's cards are the "attackers" in combat
                if blocker_side == "attacker":
                    # Attacker assigns blockers, so defender's cards attack
                    attackers = [self._serialize_card(c) for c in def_cards]
                    your_blockers = [self._serialize_card(c) for c in atk_cards] if is_your_combat else []
                else:
                    # Defender assigns blockers, so attacker's cards attack
                    attackers = [self._serialize_card(c) for c in atk_cards]
                    your_blockers = [self._serialize_card(c) for c in def_cards] if is_your_combat else []

                combat_state = {
                    "phase": "assign_blockers",
                    "location": loc,
                    "zone": zone,
                    "blocker_side": blocker_side,
                    "is_your_turn_to_assign": is_your_combat,
                    "attackers": attackers,
                    "your_blockers": your_blockers,
                }

            return {
                "turn": gm.current_turn,
                "current_player": "attacker" if gm.current_player == Player.ATTACKER else "defender",
                "your_role": player_key,
                "is_your_turn": gm.current_player == player,
                "battlefield": battlefield,
                "hand": [self._serialize_card(c) for c in hand],
                "reinforcements": [
                    {"card_id": r["card_id"], "turns_remaining": r["turns_remaining"]}
                    for r in reinforcements
                ],
                "deck_count": deck_count,
                "can_draw": gm.can_draw_card(player),
                "can_move": gm.can_move_card(player),
                "deck_cards": [c for c in gm.get_deck(player)],  # Card IDs only for draw menu
                "combat_state": combat_state,
                "winner": self.winner,  # None if game ongoing, "attacker"/"defender" if game ended
            }
        except Exception as e:
            print(f"Error in get_game_state_for_player: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _serialize_card(self, card: dict) -> dict:
        """Serialize a card for network transmission."""
        card_info = card.get("card_info", [])
        gm = self.game_manager

        # Check if card can move (not placed this turn, hasn't moved this turn)
        turn_placed = card.get("turn_placed", 0)
        has_moved = card.get("has_moved_this_turn", False)
        can_move = (turn_placed < gm.current_turn) and not has_moved

        return {
            "card_id": card.get("card_id"),
            "name": card_info[db.IDX_NAME] if len(card_info) > db.IDX_NAME else "",
            "attack": card_info[db.IDX_ATTACK] if len(card_info) > db.IDX_ATTACK else 0,
            "health": card_info[db.IDX_HEALTH] if len(card_info) > db.IDX_HEALTH else 0,
            "cost": card_info[db.IDX_COST] if len(card_info) > db.IDX_COST else 0,
            "subtype": card_info[db.IDX_SUBTYPE] if len(card_info) > db.IDX_SUBTYPE else "",
            "special": card_info[db.IDX_SPECIAL] if len(card_info) > db.IDX_SPECIAL else "",
            "current_health": card.get("current_health"),
            "is_tapped": card.get("is_tapped", False),
            "turn_placed": turn_placed,
            "has_moved_this_turn": has_moved,
            "can_move": can_move,  # Computed: can card move this turn?
        }

    async def broadcast_state(self):
        """Send updated game state to all connected players."""
        for user_id, ws in self.connections.items():
            try:
                state = self.get_game_state_for_player(user_id)
                await ws.send(json.dumps({
                    "type": "game_state",
                    "data": state
                }))
            except ConnectionClosed:
                pass
            except Exception as e:
                print(f"Error broadcasting state to user {user_id}: {e}")
                import traceback
                traceback.print_exc()

    async def handle_action(self, user_id: int, action: dict) -> dict:
        """Handle a player action and return result."""
        player = self.get_player_role(user_id)
        if not player:
            return {"success": False, "error": "Not in this game"}

        gm = self.game_manager
        action_type = action.get("action")

        # Handle combat assignment (special case - doesn't require it to be your turn)
        if action_type == "combat_assignments":
            return await self._handle_combat_assignments(user_id, player, action)

        # Check if we're in combat phase
        if self.awaiting_blocker_selection:
            return {"success": False, "error": "Waiting for blocker assignment"}

        # Check if it's player's turn
        if gm.current_player != player:
            return {"success": False, "error": "Not your turn"}

        result = {"success": False}

        if action_type == "draw_card":
            card_id = action.get("card_id")
            if gm.draw_card_from_deck(card_id, player):
                result = {"success": True, "action": "draw_card", "card_id": card_id}

        elif action_type == "place_card":
            card_id = action.get("card_id")
            location = action.get("location")
            zone = action.get("zone", "middle_zone")  # Default to middle zone
            card_info = db.get_card_info(card_id)
            if card_info and gm.place_card_on_battlefield(location, card_id, card_info, player, zone):
                gm.remove_card_from_hand(card_id, player)
                result = {"success": True, "action": "place_card", "card_id": card_id, "location": location, "zone": zone}

        elif action_type == "move_card":
            from_loc = action.get("from_location")
            to_loc = action.get("to_location")
            card_index = action.get("card_index")
            if gm.move_card(from_loc, to_loc, card_index, player):
                result = {"success": True, "action": "move_card"}

        elif action_type == "end_turn":
            prev_turn = gm.current_turn
            gm.end_turn()

            result = {"success": True, "action": "end_turn"}

            # Check if turn advanced (both passed)
            if gm.current_turn > prev_turn:
                # Check for combat zones at all locations
                self.pending_combat_zones = []
                for loc in gm.LOCATIONS:
                    combat_zones = gm.get_combat_zones_at_location(loc)
                    for zone_info in combat_zones:
                        self.pending_combat_zones.append((loc, zone_info["zone"]))

                if self.pending_combat_zones:
                    # Enter combat phase
                    self.combat_assignments = {}

                    # Start with first combat zone
                    first_loc, first_zone = self.pending_combat_zones[0]
                    self.awaiting_blocker_selection = (first_loc, first_zone)
                    result["combat_phase"] = True
                    result["combat_location"] = first_loc
                    result["combat_zone"] = first_zone
                else:
                    # No combat, check win condition
                    winner = gm.check_win_condition()
                    if winner:
                        self.winner = "attacker" if winner == Player.ATTACKER else "defender"
                        result["winner"] = self.winner
                        self.is_active = False

        # Broadcast updated state to all players
        await self.broadcast_state()

        return result

    async def _handle_combat_assignments(self, user_id: int, player: Player, action: dict) -> dict:
        """Handle blocker assignments from the blocking player (zone-based)."""
        print(f"[COMBAT] _handle_combat_assignments called by user {user_id}")
        print(f"[COMBAT] awaiting_blocker_selection: {self.awaiting_blocker_selection}")
        print(f"[COMBAT] player role: {player}")

        if not self.awaiting_blocker_selection:
            return {"success": False, "error": "Not in combat phase"}

        location, zone = self.awaiting_blocker_selection
        gm = self.game_manager

        # Determine who should assign blockers based on zone rules
        blocker_side = gm.get_blocker_side(location, zone)
        player_key = "attacker" if player == Player.ATTACKER else "defender"

        # Only the blocker_side player can assign blockers
        if player_key != blocker_side:
            print(f"[COMBAT] Rejected - player is {player_key}, blocker_side is {blocker_side}")
            return {"success": False, "error": f"Only {blocker_side} can assign blockers in {zone}"}

        assignments = action.get("assignments", {})
        print(f"[COMBAT] Raw assignments: {assignments}")

        # Convert string keys to int (JSON serialization issue)
        assignments = {int(k): v for k, v in assignments.items()}
        print(f"[COMBAT] Converted assignments: {assignments}")

        # Store assignments
        if location not in self.combat_assignments:
            self.combat_assignments[location] = {}
        self.combat_assignments[location][zone] = assignments

        # Log battlefield state before combat
        zone_data = gm.battlefield_cards[location][zone]
        atk_cards = zone_data["attacker"]
        def_cards = zone_data["defender"]
        print(f"[COMBAT] Before combat at {location}/{zone}:")
        atk_info = [(c['card_id'], c.get('current_health', '?')) for c in atk_cards]
        def_info = [(c['card_id'], c.get('current_health', '?')) for c in def_cards]
        print(f"[COMBAT]   Attackers: {atk_info}")
        print(f"[COMBAT]   Defenders: {def_info}")

        # Determine attacker_side for combat resolution
        # In zone-based combat, the side that is NOT the blocker is the attacker
        attacker_side = "defender" if blocker_side == "attacker" else "attacker"

        # Resolve combat at this zone
        combat_result = gm.resolve_combat_with_assignments(location, assignments, attacker_side, zone)

        print(f"[COMBAT] After combat:")
        print(f"[COMBAT]   Attacker casualties: {combat_result.attacker_casualties}")
        print(f"[COMBAT]   Defender casualties: {combat_result.defender_casualties}")
        print(f"[COMBAT]   Attacks: {combat_result.attacks}")

        # Move to next combat zone or finish combat phase
        self.pending_combat_zones.remove((location, zone))

        result = {
            "success": True,
            "action": "combat_resolved",
            "location": location,
            "zone": zone,
            "combat": {
                "location": combat_result.location,
                "zone": combat_result.zone,
                "attacks": combat_result.attacks,
                "attacker_casualties": combat_result.attacker_casualties,
                "defender_casualties": combat_result.defender_casualties,
            }
        }

        if self.pending_combat_zones:
            # More combat to resolve
            next_loc, next_zone = self.pending_combat_zones[0]
            self.awaiting_blocker_selection = (next_loc, next_zone)
            result["next_combat_location"] = next_loc
            result["next_combat_zone"] = next_zone
        else:
            # All combat resolved
            self.awaiting_blocker_selection = None
            self.combat_assignments = {}

            # Check win condition
            winner = gm.check_win_condition()
            if winner:
                self.winner = "attacker" if winner == Player.ATTACKER else "defender"
                result["winner"] = self.winner
                self.is_active = False

        # Broadcast updated state
        await self.broadcast_state()

        return result


class GameServer:
    """Main game server handling connections and matchmaking."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.database = Database()

        # Active connections: token -> (user_id, websocket)
        self.connections: dict[str, tuple[int, any]] = {}

        # Active game sessions: match_id -> GameSession
        self.games: dict[int, GameSession] = {}

        # User to game mapping: user_id -> match_id
        self.user_games: dict[int, int] = {}

        # Waiting for match: user_id -> websocket
        self.waiting_players: dict[int, any] = {}

    async def handle_connection(self, websocket):
        """Handle a new WebSocket connection."""
        token = None
        user_id = None

        try:
            async for message in websocket:
                data = json.loads(message)
                msg_type = data.get("type")

                # Handle authentication
                if msg_type == "auth":
                    token = data.get("token")
                    user_info = self.database.validate_token(token)

                    if user_info:
                        user_id = user_info["user_id"]
                        self.connections[token] = (user_id, websocket)

                        await websocket.send(json.dumps({
                            "type": "auth_success",
                            "user_id": user_id,
                            "username": user_info["username"]
                        }))

                        # Check if user was in a game
                        if user_id in self.user_games:
                            match_id = self.user_games[user_id]
                            if match_id in self.games:
                                game = self.games[match_id]
                                game.connections[user_id] = websocket
                                await websocket.send(json.dumps({
                                    "type": "game_rejoined",
                                    "match_id": match_id
                                }))
                                await game.broadcast_state()
                    else:
                        await websocket.send(json.dumps({
                            "type": "auth_failed",
                            "error": "Invalid or expired token"
                        }))

                elif msg_type == "register":
                    username = data.get("username")
                    password = data.get("password")
                    result = self.database.register_user(username, password)
                    await websocket.send(json.dumps({
                        "type": "register_result",
                        **result
                    }))

                elif msg_type == "login":
                    username = data.get("username")
                    password = data.get("password")
                    result = self.database.login_user(username, password)
                    await websocket.send(json.dumps({
                        "type": "login_result",
                        **result
                    }))

                    if result.get("success"):
                        token = result["token"]
                        user_id = result["user_id"]
                        self.connections[token] = (user_id, websocket)

                # Authenticated actions
                elif user_id:
                    if msg_type == "find_match":
                        await self._handle_find_match(user_id, websocket)

                    elif msg_type == "cancel_match":
                        await self._handle_cancel_match(user_id)

                    elif msg_type == "game_action":
                        if user_id in self.user_games:
                            match_id = self.user_games[user_id]
                            if match_id in self.games:
                                game = self.games[match_id]
                                result = await game.handle_action(user_id, data.get("action", {}))
                                await websocket.send(json.dumps({
                                    "type": "action_result",
                                    **result
                                }))

                    elif msg_type == "get_decks":
                        decks = self.database.get_user_decks(user_id)
                        await websocket.send(json.dumps({
                            "type": "decks",
                            "decks": decks
                        }))

                    elif msg_type == "save_deck":
                        deck_id = self.database.save_deck(
                            user_id,
                            data.get("name", "New Deck"),
                            data.get("cards", []),
                            data.get("is_active", False)
                        )
                        await websocket.send(json.dumps({
                            "type": "deck_saved",
                            "deck_id": deck_id
                        }))

                    elif msg_type == "set_active_deck":
                        success = self.database.set_active_deck(user_id, data.get("deck_id"))
                        await websocket.send(json.dumps({
                            "type": "deck_activated",
                            "success": success
                        }))

                    elif msg_type == "get_stats":
                        stats = self.database.get_user_stats(user_id)
                        await websocket.send(json.dumps({
                            "type": "stats",
                            "stats": stats
                        }))

                    elif msg_type == "get_cards":
                        # Send available cards (for deck building)
                        cards = {}
                        for card_id, card_info in db.CARDS_DATA.items():
                            if card_id != "Avatar":
                                cards[card_id] = {
                                    "name": card_info[db.IDX_NAME],
                                    "type": card_info[db.IDX_TYPE],
                                    "subtype": card_info[db.IDX_SUBTYPE],
                                    "species": card_info[db.IDX_SPECIES],
                                    "attack": card_info[db.IDX_ATTACK],
                                    "health": card_info[db.IDX_HEALTH],
                                    "cost": card_info[db.IDX_COST],
                                    "special": card_info[db.IDX_SPECIAL] if len(card_info) > db.IDX_SPECIAL else "",
                                }
                        await websocket.send(json.dumps({
                            "type": "cards",
                            "cards": cards
                        }))

                    # ==================== FRIEND ACTIONS ====================

                    elif msg_type == "get_friends":
                        friends = self.database.get_friends(user_id)
                        await websocket.send(json.dumps({
                            "type": "friends_list",
                            "friends": friends
                        }))

                    elif msg_type == "send_friend_request":
                        target_username = data.get("username")
                        result = self.database.send_friend_request(user_id, target_username)
                        await websocket.send(json.dumps({
                            "type": "friend_request_result",
                            **result
                        }))

                        # Notify target user if they're online
                        if result.get("success") and result.get("to_user_id"):
                            await self._notify_friend_request(
                                result["to_user_id"],
                                user_id,
                                self.database.get_user_stats(user_id)["username"]
                            )

                    elif msg_type == "accept_friend_request":
                        request_id = data.get("request_id")
                        result = self.database.accept_friend_request(request_id, user_id)
                        await websocket.send(json.dumps({
                            "type": "friend_request_result",
                            "action": "accept",
                            **result
                        }))

                        # Notify the other user if online
                        if result.get("success") and result.get("friend_id"):
                            await self._notify_friend_accepted(
                                result["friend_id"],
                                user_id,
                                self.database.get_user_stats(user_id)["username"]
                            )

                    elif msg_type == "decline_friend_request":
                        request_id = data.get("request_id")
                        result = self.database.decline_friend_request(request_id, user_id)
                        await websocket.send(json.dumps({
                            "type": "friend_request_result",
                            "action": "decline",
                            **result
                        }))

                    elif msg_type == "remove_friend":
                        friend_id = data.get("friend_id")
                        result = self.database.remove_friend(user_id, friend_id)
                        await websocket.send(json.dumps({
                            "type": "friend_request_result",
                            "action": "remove",
                            **result
                        }))

                    elif msg_type == "get_pending_requests":
                        pending = self.database.get_pending_requests(user_id)
                        sent = self.database.get_sent_requests(user_id)
                        await websocket.send(json.dumps({
                            "type": "pending_requests",
                            "incoming": pending,
                            "outgoing": sent
                        }))

        except ConnectionClosed:
            pass
        finally:
            # Cleanup on disconnect
            if token and token in self.connections:
                del self.connections[token]
            if user_id:
                if user_id in self.waiting_players:
                    del self.waiting_players[user_id]
                    self.database.leave_lobby(user_id)

    async def _handle_find_match(self, user_id: int, websocket):
        """Handle matchmaking request."""
        # Check if already in a game
        if user_id in self.user_games:
            await websocket.send(json.dumps({
                "type": "match_error",
                "error": "Already in a game"
            }))
            return

        # Add to lobby
        self.database.join_lobby(user_id)
        self.waiting_players[user_id] = websocket

        # Try to find opponent
        opponent = self.database.find_opponent(user_id)

        if opponent and opponent["user_id"] in self.waiting_players:
            # Match found!
            opponent_id = opponent["user_id"]
            opponent_ws = self.waiting_players[opponent_id]

            # Remove both from lobby
            self.database.leave_lobby(user_id)
            self.database.leave_lobby(opponent_id)
            del self.waiting_players[user_id]
            del self.waiting_players[opponent_id]

            # Get decks
            attacker_deck = self.database.get_active_deck(user_id) or ["Footman", "Footman", "Archer", "Eagle", "Knight"]
            defender_deck = self.database.get_active_deck(opponent_id) or ["Footman", "Footman", "Knight", "War_Hound", "Guardian"]

            print(f"[MATCH] Creating match: attacker={user_id} deck={attacker_deck}")
            print(f"[MATCH] Creating match: defender={opponent_id} deck={defender_deck}")

            # Create match
            match_id = self.database.create_match(user_id, opponent_id)
            print(f"[MATCH] Match ID: {match_id}")

            # Create game session
            try:
                game = GameSession(match_id, user_id, opponent_id, attacker_deck, defender_deck)
                print(f"[MATCH] GameSession created successfully")
            except Exception as e:
                print(f"[MATCH] Error creating GameSession: {e}")
                import traceback
                traceback.print_exc()
                return
            game.connections[user_id] = websocket
            game.connections[opponent_id] = opponent_ws

            self.games[match_id] = game
            self.user_games[user_id] = match_id
            self.user_games[opponent_id] = match_id

            # Notify both players
            await websocket.send(json.dumps({
                "type": "match_found",
                "match_id": match_id,
                "role": "attacker",
                "opponent": opponent["username"]
            }))

            await opponent_ws.send(json.dumps({
                "type": "match_found",
                "match_id": match_id,
                "role": "defender",
                "opponent": self.database.get_user_stats(user_id)["username"]
            }))

            # Send initial game state
            print(f"[MATCH] Broadcasting initial game state...")
            try:
                await game.broadcast_state()
                print(f"[MATCH] Initial game state broadcast complete")
            except Exception as e:
                print(f"[MATCH] Error broadcasting initial state: {e}")
                import traceback
                traceback.print_exc()

        else:
            # No opponent found, waiting
            await websocket.send(json.dumps({
                "type": "waiting_for_match"
            }))

    async def _handle_cancel_match(self, user_id: int):
        """Cancel matchmaking."""
        if user_id in self.waiting_players:
            del self.waiting_players[user_id]
            self.database.leave_lobby(user_id)

    def _get_websocket_for_user(self, user_id: int):
        """Get the websocket connection for a user if they're online."""
        for token, (uid, ws) in self.connections.items():
            if uid == user_id:
                return ws
        return None

    async def _notify_friend_request(self, to_user_id: int, from_user_id: int, from_username: str):
        """Notify a user that they received a friend request."""
        ws = self._get_websocket_for_user(to_user_id)
        if ws:
            try:
                await ws.send(json.dumps({
                    "type": "friend_request_received",
                    "from_user_id": from_user_id,
                    "from_username": from_username
                }))
            except:
                pass

    async def _notify_friend_accepted(self, to_user_id: int, friend_id: int, friend_username: str):
        """Notify a user that their friend request was accepted."""
        ws = self._get_websocket_for_user(to_user_id)
        if ws:
            try:
                await ws.send(json.dumps({
                    "type": "friend_status_update",
                    "action": "accepted",
                    "friend_id": friend_id,
                    "friend_username": friend_username
                }))
            except:
                pass

    async def _broadcast_online_status(self, user_id: int, is_online: bool, username: str):
        """Broadcast online status to friends."""
        friends = self.database.get_friends(user_id)
        for friend in friends:
            ws = self._get_websocket_for_user(friend["friend_id"])
            if ws:
                try:
                    await ws.send(json.dumps({
                        "type": "friend_status_update",
                        "action": "online_status",
                        "friend_id": user_id,
                        "friend_username": username,
                        "is_online": is_online
                    }))
                except:
                    pass

    async def start(self):
        """Start the game server."""
        print(f"Starting WarMasterMind server on {self.host}:{self.port}")
        async with serve(self.handle_connection, self.host, self.port):
            print(f"Server running! Players can connect to ws://{self.host}:{self.port}")
            await asyncio.Future()  # Run forever


def main():
    """Entry point for the server."""
    import argparse
    parser = argparse.ArgumentParser(description="WarMasterMind Game Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    args = parser.parse_args()

    server = GameServer(args.host, args.port)
    asyncio.run(server.start())


if __name__ == "__main__":
    main()
