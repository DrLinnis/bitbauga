from pathlib import Path

class Recipe:
    def __init__(self, recipe_path: Path):
        name_format = recipe_path.name.split('.')[0]
        name_split = name_format.split('_')
        assert(len(name_split) == 2)

        self.recipe_path = recipe_path
        self.name = name_split[0]
        self.version = name_split[1]
