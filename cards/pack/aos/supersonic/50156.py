from . import *

# * MACH-IV

def GetAbilities() -> Sequence['Ability']:

    return [
        *AbilityFactory.UnitCannotMakeBasicDefense(
            CardFinder(non_trait="AERIAL"),
            "This",
        ),
    ]

