from . import *


class BuffPawnShopDiscount(Buff):
    def __init__(self) -> None:
        super().__init__()
        self.used = False

    @override
    def OnRoundEnd(self) -> None:
        super().OnRoundEnd()
        self.used = False


def GetAbilities() -> Sequence['Ability']:
    def targets_this_area(effect: 'Effect', targets: Sequence['CardFace']) -> bool:
        return any(IsInThisPlayArea(target, effect) for target in targets)

    discount = AbilityFactory.UpdateCostOfCardInternal(
        Upgrade,
        -1,
        "AnyPlayer",
        is_play=True,
        conditions=[
            lambda effect, message: not effect.this.GetBuff(BuffPawnShopDiscount).used,
            lambda effect, message: targets_this_area(effect, message.for_targets),
        ],
    )

    def played(effect: 'Effect', message: 'Message.WhenPlayerPlayCard') -> None:
        # Cost previews run repeatedly and cannot consume a once-per-round
        # limit. Record the actual play, including a zero-cost upgrade, before
        # its effects can play another card. Putting an upgrade into play
        # without playing it does not consume the discount.
        effect.this.GetBuff(BuffPawnShopDiscount).used = True

    def entered(effect: 'Effect', message: 'Message.AfterCardEnterPlay') -> None:
        PlaceThreatHere(effect, 1)

    return [
        discount,
        AbilityFactory.AfterCardEnterPlay(
            AbilityType.ForcedResponse,
            CardFinder(card_type=Attachment) | CardFinder(card_type=Upgrade),
            entered,
            conditions=[
                lambda effect, message: IsInThisPlayArea(message.trigger, effect),
            ],
        ),
        *ProtectionRacketLossAbilities(),
        AbilityFactory.WhenPlayerPlayCard(
            AbilityType.NonKeyword,
            "AnyPlayer",
            CardFinder(card_type=Upgrade),
            played,
            conditions=[
                lambda effect, message: targets_this_area(effect, message.played_effect.targets),
            ],
        ),
    ]
