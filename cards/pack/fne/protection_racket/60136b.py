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
                # Form changes reuse the entry event to refresh card effects.
                lambda effect, message: not message.pre_message.is_flip,
                lambda effect, message: IsInThisPlayArea(message.trigger, effect),
            ],
        ),
        *ProtectionRacketLossAbilities(),
    ]
