from . import *


def GetAbilities() -> Sequence['Ability']:
    return DisasterEnvironmentAbilities(
        "B",
        lambda character: character.HasTrait("MYSTIC"),
    )
