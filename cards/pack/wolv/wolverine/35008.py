from . import *

# Berserker Barrage

def GetAbilities() -> Sequence['Ability']:

    def berserker_barrage(effect: 'Effect', message: 'Message.WhenPlayerInTurn') -> None:
        this = effect.this.CastTo(Event)
        Unused(this)

        initiator = effect.GetInitiator()

        def repeat_this_ability():
            def repeat_this_ability_internal(targets: Sequence['CardFace']):
                initiator.GetIdentity().TakeDamage(this, 2, effect)
                action(targets, is_repeat=True)

            initiator.MayChooseOneAbility(
                effect,
                AbilityFactory.ForChoiceAbility(
                    "",
                    repeat_this_ability_internal,
                ).SetLabel('attack')
                .SetTarget(Enemy)
            )

        def action(targets: Sequence['CardFace'], *, is_repeat: bool=False):
            this.effect.RegisterTemp(
                AbilityFactory.AfterUnitDefeatedUnitInternal(
                    AbilityType.Temp0,
                    None,
                    targets,
                    lambda defeat_effect, defeat_message:
                        repeat_this_ability(),
                    conditions=[
                        lambda defeat_effect, defeat_message:
                            defeat_message.would_atk_message != None and \
                            defeat_message.would_atk_message.by_effect == effect and \
                            defeat_message.target in targets,
                    ]
                ),
                unregister_after_exec=True,
                until_turn_end=True,
                until_resolve_effect=effect,
            )
            this.DealDamage(targets, 4, effect,
                            property=AttackProperty(resolve_separately=is_repeat))

        action(effect.targets)

    return [
        AbilityFactory.WhenInYourPlayTurn(
            AbilityType.HeroAction,
            berserker_barrage
        ).SetPlay().SetLabel('attack')
        .SetTarget(Enemy)
    ]

