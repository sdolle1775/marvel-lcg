from . import *

# * Collector

def GetAbilities() -> Sequence['Ability']:

    def collector(effect: 'Effect', message: 'Message.WhenRoundEnd') -> None:
        this = effect.this.CastTo(EncounterVillain)
        Unused(this)

        face = this.card.back_faces[0].CastTo(Villain)
        face.effect.RegisterTemp(
            AbilityFactory.WhenCardEnterPlay(
                AbilityType.Temp0,
                "This",
                lambda effect, message:
                    face.SetHealth(face.printed_health, effect),
                include_face_changes=True,
            ),
            unregister_after_exec=True,
            until_turn_end=True
        )
        this.card.Flip(effect)


    return [
        *AbilityFactory.UnitCannotBeDefeatedWhile(
            AbilityType.NonKeyword,
            "This",
        ),
        AbilityFactory.WhenRoundEnd(
            AbilityType.ForcedInterrupt,
            None,
            collector
        ),
    ]

