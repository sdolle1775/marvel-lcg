from . import *


def GetAbilities() -> Sequence['Ability']:
    def attack(effect: 'Effect', message: 'Message.WhenUnitWouldAttack') -> None:
        message.DealAdditionalDamage(4, effect)

    return [
        AbilityFactory.WhenUnitWouldAttack(
            AbilityType.Interrupt,
            Friend,
            attack,
        ).SetCostFunc(
            CostFunc.Counter("This", 1, 'synergy'),
        ).AnyPlayerCanDoThis(),
    ]
