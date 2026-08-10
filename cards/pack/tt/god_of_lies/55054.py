from . import *


def GetAbilities() -> Sequence['Ability']:
    def thwart(effect: 'Effect', message: 'Message.WhenUnitWouldThwart') -> None:
        message.RemoveAdditionalThreat(4, effect)

    return [
        AbilityFactory.WhenUnitWouldThwart(
            AbilityType.Interrupt,
            Friend,
            thwart,
            thwarted_scheme=None,
        ).SetCostFunc(
            CostFunc.Counter("This", 1, 'synergy'),
        ).AnyPlayerCanDoThis(),
    ]
