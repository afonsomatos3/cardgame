#!/usr/bin/env python3
"""
WarMasterMind Server Launcher

Run this script to start the multiplayer server.
Your friends can connect using the thin client.

Usage:
    python run_server.py
    python run_server.py --port 8765
    python run_server.py --host 0.0.0.0 --port 8765
"""

import sys
import socket
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from game_server import GameServer
import asyncio


def get_local_ip():
    """Get the local IP address for LAN play."""
    try:
        # Create a socket to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="WarMasterMind Game Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    args = parser.parse_args()

    local_ip = get_local_ip()

    print("=" * 60)
    print("       WarMasterMind Multiplayer Server")
    print("=" * 60)
    print()
    print(f"Server starting on port {args.port}...")
    print()
    print("Share this address with your friends:")
    print(f"  LAN:      ws://{local_ip}:{args.port}")
    print(f"  Local:    ws://localhost:{args.port}")
    print()
    print("For internet play, you need to:")
    print("  1. Port forward port {0} on your router".format(args.port))
    print("  2. Share your public IP (search 'what is my ip')")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    print()

    server = GameServer(args.host, args.port)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
