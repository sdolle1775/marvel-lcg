from . import *


def GetAbilities() -> Sequence['Ability']:
    def entered(effect: 'Effect', message: 'Message.AfterCardEnterPlay') -> None:
        effect.this.DealDamage([message.trigger], 1, effect)
        PlaceThreatHere(effect, 1)

    return [
        AbilityFactory.AfterCardEnterPlay(
            AbilityType.ForcedResponse,
            Unit2,
            entered,
            conditions=[
                lambda effect, message: IsInThisPlayArea(message.trigger, effect),
            ],
        ),
        *ProtectionRacketLossAbilities(),
    ]
