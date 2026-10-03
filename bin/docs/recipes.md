# Recipe docs!

## Name
Each recipe is named on the format of `reciepename_version.bb` expressed as `${PN}_${PV}.bb`.

### Package Name
This is the name of the recipe, without the version of file extension. It can be accesed inside of a recipe as `${PN}`

### Package Version
This is usually configured as some sort of number, e.g. `1.2.4`, but can also bet set as `git` for recipe versions that are set differently. It can be accesed inside of a recipe as `${PV}`
