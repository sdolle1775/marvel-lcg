from . import *


def GetAbilities() -> Sequence['Ability']:

    def enhanced_olfaction(effect: 'Effect', message: 'Message2') -> None:
        Worlds.UpdateNextCardPlayCost(
            effect.GetInitiator(),
            -2,
            effect,
            in_this="Phase",
        )

    def defeated_by_you(effect: 'Effect', message: 'Message.WhenUnitWouldBeDefeated') -> bool:
        return (
            not message.is_be_instead
            and Condition.CheckWhichCard("YourIdentity", message.killer, effect)
        )

    return [
        AbilityFactory.CanPlayThisUpgradeCard(
            CardFinder(card_type=Enemy|Scheme2),
        ),
        # Interrupt before defeat discards the enemy and its attached upgrades.
        AbilityFactory.WhenUnitWouldBeDefeated(
            AbilityType.Interrupt,
            "AttachedEnemy",
            enhanced_olfaction,
            conditions=[defeated_by_you],
        ).SetCostFunc(CostFunc.Discard("This")),
        AbilityFactory.WhenSchemeWouldRemoveThreat(
            AbilityType.Interrupt,
            "AttachedScheme",
            enhanced_olfaction,
            conditions=[YourIdentityWouldRemoveLastThreat],
        ).SetCostFunc(CostFunc.Discard("This")),
    ]
