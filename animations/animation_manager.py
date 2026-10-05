from pathlib import Path
from PySide6.QtGui import QPixmap

class AnimationManager:
    def __init__(self, base_path):
        self.base = Path(base_path)
        self.animations = {}

    def load(self, name):
        folder = self.base / name
        frames = sorted(folder.glob("*.png"))
        self.animations[name] = [QPixmap(str(f)) for f in frames]

    def get(self, name):
        return self.animations.get(name, [])