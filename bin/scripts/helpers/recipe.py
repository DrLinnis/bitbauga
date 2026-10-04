import re

from pathlib import Path

def collapse_strings_and_nested_brackets(text: str) -> str:
    # ------------------------------------------------------------------
    # Step 1: Collapse single-quote or double-quote strings across lines.
    # Matches "..." or '...' including backslash-escaped characters/newlines (\.)
    # ------------------------------------------------------------------
    string_pattern = r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'

    def normalize_string(match: re.Match) -> str:
        s = match.group(0)
        # Remove trailing backslashes at line ends and reduce whitespace to single spaces
        s = re.sub(r'\\\n\s*', ' ', s)
        return re.sub(r'\s+', ' ', s)

    text = re.sub(string_pattern, normalize_string, text, flags=re.DOTALL)

    # ------------------------------------------------------------------
    # Step 2: Iteratively collapse innermost curly brackets { ... }
    # ------------------------------------------------------------------
    # Matches a { ... } block that contains NO nested { or } inside it
    innermost_bracket_pattern = r'\{[^{}]*\}'

    def normalize_bracket(match: re.Match) -> str:
        return re.sub(r'\s+', ' ', match.group(0))

    prev_text = None

    # Loop until no more un-collapsed inner brackets remain
    while text != prev_text:
        prev_text = text
        text = re.sub(innermost_bracket_pattern, normalize_bracket, text, flags=re.DOTALL)

    return text


class BitBaugaData:
    def __init__(self, file_content, filename):
        lines = collapse_strings_and_nested_brackets(file_content).split('\n')
        lines = [l.strip() for l in lines]
        lines = [l for l in lines if len(l) > 0]

        self.inherit = self.include \
                     = self.require \
                     = self.deps_runtime \
                     = self.deps_build = []

        for line in lines:
            words = line.split(' ')
            match words[0]:
                case "inherit":
                    self.inherit = words[1:]
                case "include":
                    self.include = words[1:]
                case "require":
                    self.require = words[1:]
                case "DEPENDS":
                    self.deps_build = words[1:]
                case "RDEPENDS":
                    self.deps_runtime = words[1:]
        self.name = filename
        self.helper_dependencies = self.inherit + self.include + self.require
        self.recipe_dependencies = self.deps_runtime + self.deps_build

    def __str__(self, verbose=False):
        result = "${PN} = " + self.name
        if self.helper_dependencies and verbose:
            result += "\n"
            result += f"inherit : {self.inherit}\n" if self.inherit else ""
            result += f"include : {self.include}\n" if self.include else ""
            result += f"require : {self.require}\n" if self.require else ""

        if self.recipe_dependencies and verbose:
            result += f"build dependencies : {self.deps_build}\n" if self.deps_build else ""
            result += f"runtime dependencies : {self.deps_runtime}\n" if self.deps_runtime else ""

        return result


class Recipe:
    def __init__(self, recipe_path: Path):
        name_format = recipe_path.name.split('.')[0]
        name_split = name_format.split('_')
        assert(len(name_split) == 2)

        self.bb_data = None
        self.recipe_path = recipe_path
        self.name = name_split[0]
        self.version = name_split[1]

    def __str__(self, verbose=False):
        result = self.name + "-" + self.version
        if self.bb_data:
            result += "\n"
            result += self.bb_data.__str__(verbose)
        return result

    def parse_recipe(self):
        self.bb_data = None

        with open(self.recipe_path, "r") as f:
            content = f.read()
            self.bb_data = BitBaugaData(content, self.name)

        assert(self.bb_data is not None)
        return self
