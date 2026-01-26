"""Resource manager for downloading and managing game assets."""

import os
import sys
import json
import requests
from pathlib import Path


class ResourceManager:
    """Handles downloading and verifying game resources from the server."""

    # Resource structure to download
    RESOURCES = {
        "Songs": [
            "CastleSong.mp3"
        ],
        "Units": [],  # Will be filled dynamically based on card IDs
        "CardsBorders": []
    }

    def __init__(self, resource_dir: str = "resources", server_host: str = "localhost", server_port: int = 8766):
        """Initialize resource manager.
        
        Args:
            resource_dir: Directory where resources should be stored
            server_host: Server hostname/IP
            server_port: Server HTTP port for resources
        """
        self.resource_dir = Path(resource_dir)
        self.server_host = server_host
        self.server_port = server_port
        self.base_url = f"http://{server_host}:{server_port}"
        self.resource_dir.mkdir(parents=True, exist_ok=True)

    def check_and_download_resources(self) -> bool:
        """Check if resources exist, download missing ones.
        
        Returns:
            True if all resources are available, False otherwise
        """
        print("Checking game resources...")
        
        # Try to get resource list from server
        try:
            response = requests.get(f"{self.base_url}/resources/list", timeout=5)
            if response.status_code == 200:
                available_resources = response.json()
                return self._download_missing_resources(available_resources)
        except requests.exceptions.ConnectionError:
            print("Warning: Could not connect to resource server")
            print("Checking for local resources instead...")
            return self._check_local_resources()
        except Exception as e:
            print(f"Error checking resources: {e}")
            return self._check_local_resources()

    def _download_missing_resources(self, available_resources: dict) -> bool:
        """Download resources that are missing locally.
        
        Args:
            available_resources: Dict of available resources from server
            
        Returns:
            True if all resources were successfully downloaded/verified
        """
        all_present = True
        
        for category, files in available_resources.items():
            category_path = self.resource_dir / category
            category_path.mkdir(parents=True, exist_ok=True)
            
            for filename in files:
                filepath = category_path / filename
                
                if not filepath.exists():
                    print(f"Downloading {category}/{filename}...")
                    if not self._download_file(category, filename, filepath):
                        print(f"Warning: Could not download {category}/{filename}")
                        all_present = False
                else:
                    print(f"✓ {category}/{filename}")
        
        return all_present

    def _download_file(self, category: str, filename: str, filepath: Path) -> bool:
        """Download a single file from server.
        
        Args:
            category: Resource category (Songs, Units, etc.)
            filename: Filename to download
            filepath: Local path to save to
            
        Returns:
            True if download was successful
        """
        try:
            url = f"{self.base_url}/resources/{category}/{filename}"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                return True
            else:
                print(f"Server returned {response.status_code} for {url}")
                return False
                
        except requests.exceptions.Timeout:
            print(f"Timeout downloading {filename}")
            return False
        except Exception as e:
            print(f"Error downloading {filename}: {e}")
            return False

    def _check_local_resources(self) -> bool:
        """Check if critical resources exist locally.
        
        Returns:
            True if critical resources are present
        """
        critical_files = [
            self.resource_dir / "Songs" / "CastleSong.mp3",
        ]
        
        all_present = True
        for filepath in critical_files:
            if filepath.exists():
                print(f"✓ {filepath.relative_to(self.resource_dir.parent)}")
            else:
                print(f"✗ Missing: {filepath.relative_to(self.resource_dir.parent)}")
                all_present = False
        
        return all_present

    def verify_resource(self, relative_path: str) -> bool:
        """Verify a specific resource exists.
        
        Args:
            relative_path: Path relative to resources dir (e.g., "Units/1.png")
            
        Returns:
            True if resource exists
        """
        filepath = self.resource_dir / relative_path
        return filepath.exists()


def ensure_resources(server_host: str = "localhost", server_port: int = 8766) -> bool:
    """Convenience function to ensure resources are available.
    
    Args:
        server_host: Server hostname/IP
        server_port: Server HTTP port
        
    Returns:
        True if resources are available
    """
    manager = ResourceManager(server_host=server_host, server_port=server_port)
    success = manager.check_and_download_resources()
    
    if not success:
        print("\nWarning: Some resources could not be verified.")
        print("Game may not display graphics correctly.")
    
    return success
