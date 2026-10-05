# Devtool docs

This is the tool for working with the recipes and meta-layers.

## Devtool function: List

All recipes are stored in the format of `meta-layer/recipe-category/recipe-name/recipe-name_version.bb`.

### List: Layers

Item set as `layers` show all of the meta-layers available in your repo. See [meta-layers](meta-layers.md)

### List: Recipes

Item set as `recipes` list all of the recipes available in your repo, without the versioning. See [recipes](recipes.md)

### List: Categories

Item set as `catagories` list all of the recipe catagories used in your repo.

## Devtool function: Inspect

All recipes can be inspected to figure out their dependencies, source content, and realized definition