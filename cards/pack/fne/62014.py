from . import *

# * Valkyrie: Brunnhilde

def GetAbilities() -> Sequence['Ability']:

    def valkyrie(effect: 'Effect', message: 'Message.WhenUnitWouldBeDefeated') -> None:
        this = effect.this.CastTo(Ally)
        Unused(this)

        message.SetBeInstead(effect)
        message.trigger.CastTo(Unit2).SetHealth(1, effect)

    return [
        AbilityFactory.WhenUnitWouldBeDefeated(
            AbilityType.Interrupt,
            Ally,
            valkyrie,
            conditions=[
                lambda effect, message: message.trigger != effect.this
            ]
        ).SetCostFunc(CostFunc.Discard("This")),
    ]