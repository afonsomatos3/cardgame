"""Database module for WarMasterMind multiplayer."""

import sqlite3
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from pathlib import Path


class Database:
    """SQLite database manager for user accounts and game data."""

    def __init__(self, db_path: str = None):
        # Use absolute path relative to this file's directory
        if db_path is None:
            db_path = Path(__file__).parent / "warmastermind.db"
        self.db_path = str(db_path)
        self.conn = None
        self._init_database()

    def _init_database(self):
        """Initialize database with tables."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()

        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                is_online INTEGER DEFAULT 0
            )
        ''')

        # Sessions table (for JWT-like tokens)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                is_valid INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # Decks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS decks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                cards TEXT NOT NULL,
                is_active INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # Matches table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attacker_id INTEGER NOT NULL,
                defender_id INTEGER NOT NULL,
                winner_id INTEGER,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                game_state TEXT,
                FOREIGN KEY (attacker_id) REFERENCES users(id),
                FOREIGN KEY (defender_id) REFERENCES users(id),
                FOREIGN KEY (winner_id) REFERENCES users(id)
            )
        ''')

        # Lobby/matchmaking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lobby (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # Friend requests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS friend_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                responded_at TIMESTAMP,
                FOREIGN KEY (from_user_id) REFERENCES users(id),
                FOREIGN KEY (to_user_id) REFERENCES users(id),
                UNIQUE(from_user_id, to_user_id)
            )
        ''')

        # Friends table (bidirectional friendship)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS friends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                friend_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (friend_id) REFERENCES users(id),
                UNIQUE(user_id, friend_id)
            )
        ''')

        self.conn.commit()

    def _hash_password(self, password: str, salt: str) -> str:
        """Hash password with salt using SHA-256."""
        return hashlib.sha256((password + salt).encode()).hexdigest()

    def _generate_salt(self) -> str:
        """Generate a random salt."""
        return secrets.token_hex(32)

    def _generate_token(self) -> str:
        """Generate a session token."""
        return secrets.token_urlsafe(64)

    # ==================== USER MANAGEMENT ====================

    def register_user(self, username: str, password: str) -> dict:
        """Register a new user.

        Returns:
            dict with 'success' bool and 'message' or 'user_id'
        """
        if len(username) < 3 or len(username) > 20:
            return {"success": False, "message": "Username must be 3-20 characters"}

        if len(password) < 6:
            return {"success": False, "message": "Password must be at least 6 characters"}

        # Check if username exists
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username.lower(),))
        if cursor.fetchone():
            return {"success": False, "message": "Username already exists"}

        # Create user
        salt = self._generate_salt()
        password_hash = self._hash_password(password, salt)

        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
                (username.lower(), password_hash, salt)
            )
            self.conn.commit()
            user_id = cursor.lastrowid

            # Create default deck for new user
            default_deck = ["Footman", "Footman", "Archer", "Eagle", "Knight"]
            self.save_deck(user_id, "Default Deck", default_deck, is_active=True)

            return {"success": True, "user_id": user_id}
        except sqlite3.Error as e:
            return {"success": False, "message": str(e)}

    def login_user(self, username: str, password: str) -> dict:
        """Login a user.

        Returns:
            dict with 'success', and if successful: 'user_id', 'token'
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, password_hash, salt FROM users WHERE username = ?",
            (username.lower(),)
        )
        row = cursor.fetchone()

        if not row:
            return {"success": False, "message": "Invalid username or password"}

        # Verify password
        password_hash = self._hash_password(password, row["salt"])
        if password_hash != row["password_hash"]:
            return {"success": False, "message": "Invalid username or password"}

        user_id = row["id"]

        # Create session token
        token = self._generate_token()
        expires_at = datetime.now() + timedelta(days=7)

        cursor.execute(
            "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires_at)
        )

        # Update last login and online status
        cursor.execute(
            "UPDATE users SET last_login = ?, is_online = 1 WHERE id = ?",
            (datetime.now(), user_id)
        )
        self.conn.commit()

        return {
            "success": True,
            "user_id": user_id,
            "username": username.lower(),
            "token": token
        }

    def validate_token(self, token: str) -> dict | None:
        """Validate a session token.

        Returns:
            dict with user info if valid, None otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT s.user_id, u.username, s.expires_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.is_valid = 1
        ''', (token,))
        row = cursor.fetchone()

        if not row:
            return None

        # Check expiration
        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.now() > expires_at:
            # Invalidate expired token
            cursor.execute("UPDATE sessions SET is_valid = 0 WHERE token = ?", (token,))
            self.conn.commit()
            return None

        return {
            "user_id": row["user_id"],
            "username": row["username"]
        }

    def logout_user(self, token: str) -> bool:
        """Logout user by invalidating token."""
        cursor = self.conn.cursor()

        # Get user_id before invalidating
        cursor.execute("SELECT user_id FROM sessions WHERE token = ?", (token,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE users SET is_online = 0 WHERE id = ?", (row["user_id"],))

        cursor.execute("UPDATE sessions SET is_valid = 0 WHERE token = ?", (token,))
        self.conn.commit()
        return True

    def get_user_stats(self, user_id: int) -> dict | None:
        """Get user statistics."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT username, wins, losses, created_at FROM users WHERE id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "username": row["username"],
                "wins": row["wins"],
                "losses": row["losses"],
                "created_at": row["created_at"]
            }
        return None

    # ==================== DECK MANAGEMENT ====================

    def save_deck(self, user_id: int, name: str, cards: list, is_active: bool = False) -> int:
        """Save a deck for a user."""
        cursor = self.conn.cursor()

        # If setting as active, deactivate others
        if is_active:
            cursor.execute(
                "UPDATE decks SET is_active = 0 WHERE user_id = ?",
                (user_id,)
            )

        cursor.execute(
            "INSERT INTO decks (user_id, name, cards, is_active) VALUES (?, ?, ?, ?)",
            (user_id, name, json.dumps(cards), 1 if is_active else 0)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_user_decks(self, user_id: int) -> list:
        """Get all decks for a user."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, name, cards, is_active FROM decks WHERE user_id = ?",
            (user_id,)
        )
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "cards": json.loads(row["cards"]),
                "is_active": bool(row["is_active"])
            }
            for row in cursor.fetchall()
        ]

    def get_active_deck(self, user_id: int) -> list | None:
        """Get the active deck for a user."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT cards FROM decks WHERE user_id = ? AND is_active = 1",
            (user_id,)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row["cards"])
        return None

    def set_active_deck(self, user_id: int, deck_id: int) -> bool:
        """Set a deck as active."""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE decks SET is_active = 0 WHERE user_id = ?", (user_id,))
        cursor.execute(
            "UPDATE decks SET is_active = 1 WHERE id = ? AND user_id = ?",
            (deck_id, user_id)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    # ==================== MATCH MANAGEMENT ====================

    def create_match(self, attacker_id: int, defender_id: int) -> int:
        """Create a new match."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO matches (attacker_id, defender_id) VALUES (?, ?)",
            (attacker_id, defender_id)
        )
        self.conn.commit()
        return cursor.lastrowid

    def end_match(self, match_id: int, winner_id: int):
        """End a match and update stats."""
        cursor = self.conn.cursor()

        # Get match info
        cursor.execute(
            "SELECT attacker_id, defender_id FROM matches WHERE id = ?",
            (match_id,)
        )
        row = cursor.fetchone()
        if not row:
            return

        # Update match
        cursor.execute(
            "UPDATE matches SET winner_id = ?, ended_at = ? WHERE id = ?",
            (winner_id, datetime.now(), match_id)
        )

        # Update winner stats
        cursor.execute("UPDATE users SET wins = wins + 1 WHERE id = ?", (winner_id,))

        # Update loser stats
        loser_id = row["defender_id"] if winner_id == row["attacker_id"] else row["attacker_id"]
        cursor.execute("UPDATE users SET losses = losses + 1 WHERE id = ?", (loser_id,))

        self.conn.commit()

    def save_game_state(self, match_id: int, game_state: dict):
        """Save current game state for a match."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE matches SET game_state = ? WHERE id = ?",
            (json.dumps(game_state), match_id)
        )
        self.conn.commit()

    # ==================== LOBBY MANAGEMENT ====================

    def join_lobby(self, user_id: int) -> bool:
        """Add user to matchmaking lobby."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO lobby (user_id, joined_at) VALUES (?, ?)",
                (user_id, datetime.now())
            )
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False

    def leave_lobby(self, user_id: int):
        """Remove user from lobby."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM lobby WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def get_lobby_users(self) -> list:
        """Get all users in lobby."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT l.user_id, u.username
            FROM lobby l
            JOIN users u ON l.user_id = u.id
            ORDER BY l.joined_at
        ''')
        return [{"user_id": row["user_id"], "username": row["username"]}
                for row in cursor.fetchall()]

    def find_opponent(self, user_id: int) -> dict | None:
        """Find an opponent in the lobby (excluding self)."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT l.user_id, u.username
            FROM lobby l
            JOIN users u ON l.user_id = u.id
            WHERE l.user_id != ?
            ORDER BY l.joined_at
            LIMIT 1
        ''', (user_id,))
        row = cursor.fetchone()
        if row:
            return {"user_id": row["user_id"], "username": row["username"]}
        return None

    # ==================== FRIEND MANAGEMENT ====================

    def get_user_by_username(self, username: str) -> dict | None:
        """Get user info by username."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, username, is_online FROM users WHERE username = ?",
            (username.lower(),)
        )
        row = cursor.fetchone()
        if row:
            return {
                "user_id": row["id"],
                "username": row["username"],
                "is_online": bool(row["is_online"])
            }
        return None

    def send_friend_request(self, from_user_id: int, to_username: str) -> dict:
        """Send a friend request to a user.

        Returns:
            dict with 'success' bool and 'message'
        """
        # Find target user
        target = self.get_user_by_username(to_username)
        if not target:
            return {"success": False, "message": "User not found"}

        to_user_id = target["user_id"]

        if from_user_id == to_user_id:
            return {"success": False, "message": "Cannot add yourself as a friend"}

        # Check if already friends
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM friends WHERE user_id = ? AND friend_id = ?",
            (from_user_id, to_user_id)
        )
        if cursor.fetchone():
            return {"success": False, "message": "Already friends with this user"}

        # Check if request already exists
        cursor.execute(
            "SELECT id, status FROM friend_requests WHERE from_user_id = ? AND to_user_id = ?",
            (from_user_id, to_user_id)
        )
        existing = cursor.fetchone()
        if existing:
            if existing["status"] == "pending":
                return {"success": False, "message": "Friend request already sent"}
            # Update existing declined request
            cursor.execute(
                "UPDATE friend_requests SET status = 'pending', created_at = ?, responded_at = NULL WHERE id = ?",
                (datetime.now(), existing["id"])
            )
            self.conn.commit()
            return {"success": True, "message": "Friend request sent", "to_user_id": to_user_id}

        # Check if they already sent us a request
        cursor.execute(
            "SELECT id FROM friend_requests WHERE from_user_id = ? AND to_user_id = ? AND status = 'pending'",
            (to_user_id, from_user_id)
        )
        if cursor.fetchone():
            return {"success": False, "message": "This user already sent you a friend request"}

        # Create new request
        try:
            cursor.execute(
                "INSERT INTO friend_requests (from_user_id, to_user_id) VALUES (?, ?)",
                (from_user_id, to_user_id)
            )
            self.conn.commit()
            return {"success": True, "message": "Friend request sent", "to_user_id": to_user_id, "request_id": cursor.lastrowid}
        except sqlite3.Error as e:
            return {"success": False, "message": str(e)}

    def get_pending_requests(self, user_id: int) -> list:
        """Get pending friend requests for a user."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT fr.id, fr.from_user_id, u.username, fr.created_at
            FROM friend_requests fr
            JOIN users u ON fr.from_user_id = u.id
            WHERE fr.to_user_id = ? AND fr.status = 'pending'
            ORDER BY fr.created_at DESC
        ''', (user_id,))
        return [
            {
                "request_id": row["id"],
                "from_user_id": row["from_user_id"],
                "from_username": row["username"],
                "created_at": row["created_at"]
            }
            for row in cursor.fetchall()
        ]

    def get_sent_requests(self, user_id: int) -> list:
        """Get sent friend requests from a user."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT fr.id, fr.to_user_id, u.username, fr.status, fr.created_at
            FROM friend_requests fr
            JOIN users u ON fr.to_user_id = u.id
            WHERE fr.from_user_id = ?
            ORDER BY fr.created_at DESC
        ''', (user_id,))
        return [
            {
                "request_id": row["id"],
                "to_user_id": row["to_user_id"],
                "to_username": row["username"],
                "status": row["status"],
                "created_at": row["created_at"]
            }
            for row in cursor.fetchall()
        ]

    def accept_friend_request(self, request_id: int, user_id: int) -> dict:
        """Accept a friend request.

        Returns:
            dict with 'success' bool and 'message'
        """
        cursor = self.conn.cursor()

        # Get request
        cursor.execute(
            "SELECT from_user_id, to_user_id FROM friend_requests WHERE id = ? AND status = 'pending'",
            (request_id,)
        )
        row = cursor.fetchone()
        if not row:
            return {"success": False, "message": "Friend request not found"}

        if row["to_user_id"] != user_id:
            return {"success": False, "message": "This request is not for you"}

        from_user_id = row["from_user_id"]

        # Update request status
        cursor.execute(
            "UPDATE friend_requests SET status = 'accepted', responded_at = ? WHERE id = ?",
            (datetime.now(), request_id)
        )

        # Create friendship (bidirectional)
        try:
            cursor.execute(
                "INSERT INTO friends (user_id, friend_id) VALUES (?, ?)",
                (user_id, from_user_id)
            )
            cursor.execute(
                "INSERT INTO friends (user_id, friend_id) VALUES (?, ?)",
                (from_user_id, user_id)
            )
            self.conn.commit()
            return {"success": True, "message": "Friend request accepted", "friend_id": from_user_id}
        except sqlite3.Error as e:
            self.conn.rollback()
            return {"success": False, "message": str(e)}

    def decline_friend_request(self, request_id: int, user_id: int) -> dict:
        """Decline a friend request.

        Returns:
            dict with 'success' bool and 'message'
        """
        cursor = self.conn.cursor()

        # Get request
        cursor.execute(
            "SELECT to_user_id FROM friend_requests WHERE id = ? AND status = 'pending'",
            (request_id,)
        )
        row = cursor.fetchone()
        if not row:
            return {"success": False, "message": "Friend request not found"}

        if row["to_user_id"] != user_id:
            return {"success": False, "message": "This request is not for you"}

        # Update request status
        cursor.execute(
            "UPDATE friend_requests SET status = 'declined', responded_at = ? WHERE id = ?",
            (datetime.now(), request_id)
        )
        self.conn.commit()
        return {"success": True, "message": "Friend request declined"}

    def get_friends(self, user_id: int) -> list:
        """Get friends list for a user."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT f.friend_id, u.username, u.is_online, u.wins, u.losses
            FROM friends f
            JOIN users u ON f.friend_id = u.id
            WHERE f.user_id = ?
            ORDER BY u.is_online DESC, u.username
        ''', (user_id,))
        return [
            {
                "friend_id": row["friend_id"],
                "username": row["username"],
                "is_online": bool(row["is_online"]),
                "wins": row["wins"],
                "losses": row["losses"]
            }
            for row in cursor.fetchall()
        ]

    def remove_friend(self, user_id: int, friend_id: int) -> dict:
        """Remove a friend.

        Returns:
            dict with 'success' bool and 'message'
        """
        cursor = self.conn.cursor()

        # Check if friends
        cursor.execute(
            "SELECT id FROM friends WHERE user_id = ? AND friend_id = ?",
            (user_id, friend_id)
        )
        if not cursor.fetchone():
            return {"success": False, "message": "Not friends with this user"}

        # Remove friendship (bidirectional)
        cursor.execute(
            "DELETE FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)",
            (user_id, friend_id, friend_id, user_id)
        )
        self.conn.commit()
        return {"success": True, "message": "Friend removed"}

    def are_friends(self, user_id: int, other_user_id: int) -> bool:
        """Check if two users are friends."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM friends WHERE user_id = ? AND friend_id = ?",
            (user_id, other_user_id)
        )
        return cursor.fetchone() is not None

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
