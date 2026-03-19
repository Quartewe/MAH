from pathlib import Path

path = Path("assets\resource\image\fight\weapon\weapon_shoot.png").relative_to(Path("assets\resource\image"))

print(path)
