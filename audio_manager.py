"""Audio manager for handling background music and sound effects."""

import pygame
import os


class AudioManager:
    """Manages background music and sound effects."""

    def __init__(self):
        """Initialize the audio manager."""
        self.initialized = False
        self.music_volume = 0.5
        self.sfx_volume = 0.7
        self.is_muted = False
        self.music_playing = False

        # Try to initialize pygame mixer
        try:
            pygame.mixer.init()
            self.initialized = True
        except pygame.error:
            print("Warning: Could not initialize audio system")

    def play_music(self, music_path: str = None, loop: int = -1):
        """Play background music.

        Args:
            music_path: Path to music file. If None, tries default paths.
            loop: Number of times to loop (-1 for infinite)
        """
        if not self.initialized:
            return

        # Default music paths to try
        if music_path is None:
            default_paths = [
                os.path.join("resources", "music", "background.mp3"),
                os.path.join("resources", "music", "background.ogg"),
                os.path.join("resources", "music", "background.wav"),
            ]
            for path in default_paths:
                if os.path.exists(path):
                    music_path = path
                    break

        if music_path is None or not os.path.exists(music_path):
            # No music file found - that's okay
            return

        try:
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.set_volume(0 if self.is_muted else self.music_volume)
            pygame.mixer.music.play(loop)
            self.music_playing = True
        except pygame.error as e:
            print(f"Warning: Could not play music: {e}")

    def stop_music(self):
        """Stop background music."""
        if not self.initialized:
            return

        try:
            pygame.mixer.music.stop()
            self.music_playing = False
        except pygame.error:
            pass

    def set_music_volume(self, volume: float):
        """Set music volume (0.0 to 1.0)."""
        self.music_volume = max(0.0, min(1.0, volume))
        if self.initialized and not self.is_muted:
            try:
                pygame.mixer.music.set_volume(self.music_volume)
            except pygame.error:
                pass

    def get_music_volume(self) -> float:
        """Get current music volume."""
        return self.music_volume

    def toggle_mute(self) -> bool:
        """Toggle mute state. Returns new mute state."""
        self.is_muted = not self.is_muted
        if self.initialized:
            try:
                pygame.mixer.music.set_volume(0 if self.is_muted else self.music_volume)
            except pygame.error:
                pass
        return self.is_muted

    def set_muted(self, muted: bool):
        """Set mute state."""
        self.is_muted = muted
        if self.initialized:
            try:
                pygame.mixer.music.set_volume(0 if self.is_muted else self.music_volume)
            except pygame.error:
                pass

    def is_music_muted(self) -> bool:
        """Check if music is muted."""
        return self.is_muted

    def play_sfx(self, sfx_name: str):
        """Play a sound effect.

        Args:
            sfx_name: Name of the sound effect (without extension)
        """
        if not self.initialized or self.is_muted:
            return

        # Try to find and play sound effect
        sfx_paths = [
            os.path.join("resources", "sfx", f"{sfx_name}.wav"),
            os.path.join("resources", "sfx", f"{sfx_name}.ogg"),
            os.path.join("resources", "sfx", f"{sfx_name}.mp3"),
        ]

        for path in sfx_paths:
            if os.path.exists(path):
                try:
                    sound = pygame.mixer.Sound(path)
                    sound.set_volume(self.sfx_volume)
                    sound.play()
                    return
                except pygame.error:
                    pass

    def cleanup(self):
        """Clean up audio resources."""
        if self.initialized:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            except pygame.error:
                pass
