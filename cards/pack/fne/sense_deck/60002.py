from . import *


def GetAbilities() -> Sequence['Ability']:

    def acute_tactility(effect: 'Effect', message: 'Message2') -> None:
        Faces.ReadyAll([effect.GetInitiator().GetIdentity()], effect)

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
            acute_tactility,
            conditions=[defeated_by_you],
        ).SetCostFunc(CostFunc.Discard("This")),
        AbilityFactory.WhenSchemeWouldRemoveThreat(
            AbilityType.Interrupt,
            "AttachedScheme",
            acute_tactility,
            conditions=[YourIdentityWouldRemoveLastThreat],
        ).SetCostFunc(CostFunc.Discard("This")),
    ]
