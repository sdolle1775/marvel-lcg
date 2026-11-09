from cards.pack import *


def DisasterEnvironmentAbilities(
    resource: 'Resources.RBYG',
    bonus_condition: Callable[['CardFace'], bool],
) -> List['Ability']:
    resource_name = {
        "B": "[mental]",
        "G": "[wild]",
        "Y": "[energy]",
        "R": "[physical]",
    }[resource]

    def remove_civilians(effect: 'Effect', message: 'Message.WhenPlayerInTurn') -> None:
        Unused(message)
        this = effect.this.CastTo(Environment)
        player = effect.GetInitiator()

        def remove(value: int) -> None:
            Faces.RemoveCountersOn([this], value, "civilian", effect)

        def exhaust_character(targets: Sequence['CardFace']) -> None:
            character = targets[0]
            remove(2 if bonus_condition(character) else 1)

        player.ChooseAbilities(
            effect,
            AbilityFactory.ForChoiceAbilityWithCost(
                Cost(resource * 2),
                f"Spend 2 {resource_name} resources → remove 1 civilian counter",
                lambda targets, resources: remove(1),
            ),
            AbilityFactory.ForChoiceAbility(
                "Exhaust a hero or ally you control → remove civilian counters",
                exhaust_character,
                targets_is_exhaust_cost=True,
            ).SetCostFunc(CostFunc.Exhaust("YouControlUnit")),
        )

    return [
        AbilityFactory.WhenInYourPlayTurn(
            AbilityType.HeroAction,
            remove_civilians,
            conditions=[
                lambda effect, message:
                    effect.this.GetCounters("civilian") > 0,
            ],
        ).SetName("Rescue civilians").AnyPlayerCanDoThis(),
    ]
