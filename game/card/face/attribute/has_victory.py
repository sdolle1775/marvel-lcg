from . import *

class HasVictory(HasAttribute):
    @override
    def __init__(self, paper: 'Paper') -> None:
        self.printed_victory: int|None = None

        super().__init__(paper)

        self.RegisterAttribute("Victory", "printed_victory")
        # self.RegisterInfoDict('victory')

    @override
    def GetAbilities(self) -> List['Ability']:
        from game.card.face.base import Scheme2, Unit2
        from game.card.face.card_type import Attachment, Upgrade

        def is_direct_victory_trigger(
            effect: 'Effect',
            message: 'Message.WhenUnitBeDefeated|Message.WhenSchemeBeDefeated',
        ) -> bool:
            this = effect.this.CastTo(HasVictory)
            return (
                bool(effect.world.rule.v18_timing) and
                this.victory and
                this.IsThisFaceUp() and
                this is message.trigger
            )

        def is_attached_victory_trigger(
            effect: 'Effect',
            message: 'Message.WhenUnitBeDefeated|Message.WhenSchemeBeDefeated',
        ) -> bool:
            this = effect.this.CastTo(HasVictory)
            return (
                bool(effect.world.rule.v18_timing) and
                this.victory and
                this.IsThisFaceUp() and
                this.bind_face is message.trigger
            )

        if Attachment.IsType(self) or Upgrade.IsType(self):
            ability = Ability(
                AbilityType.ForcedInterrupt,
                Message.WhenUnitBeDefeated|Message.WhenSchemeBeDefeated,
                [is_attached_victory_trigger],
                lambda effect, message:
                    effect.this.CastTo(HasVictory).MoveToVictoryDisplay(),
            )
        elif Unit2.IsType(self) or Scheme2.IsType(self):
            def resolve_victory(effect: 'Effect', message: 'Message.WhenUnitBeDefeated|Message.WhenSchemeBeDefeated') -> None:
                # V1.8 gives Victory When Defeated timing, but the defeated
                # card stays in play until all of its defeat abilities resolve.
                # Record its destination for the defeat's leave-play step.
                message.add_to_victory_display = True

            ability = Ability(
                AbilityType.WhenDefeated,
                Message.WhenUnitBeDefeated|Message.WhenSchemeBeDefeated,
                [is_direct_victory_trigger],
                resolve_victory,
            )
            # Only records the destination; moving the defeated card still
            # waits for all defeat abilities. Ordering this flag has no effect.
            ability.resolve_automatically = True
        else:
            return super().GetAbilities()

        return [ability.SetName("Victory")] + super().GetAbilities()

    def MoveToVictoryDisplay(self) -> None:
        from game.card.face.base import Villain
        from game.effect.rule import GameRule
        from game.operate.faces import Faces

        do_move = True
        if Villain.IsType(self):
            next_villain = self.card.world.scenario.GetNextVillain(self)
            if next_villain and next_villain.IsName(self.name, check_all_face=True):
                do_move = False
        if do_move:
            Faces.AddToVictoryDisplay([self], GameRule(self))

    @override
    def GetInfoDict(self) -> Dict[str, int]:
        return {
            'victory': self.printed_victory if self.printed_victory != None else 0,
        } | super().GetInfoDict()

    @override
    def OnBeDefeated(self, would_defeated_message: 'Message.WhenSchemeWouldBeDefeated|Message.WhenUnitWouldBeDefeated', *, as_asset: bool, ignore_when_defeated: bool):
        if self.victory and self.IsThisFaceUp() and \
            not bool(self.card.world.rule.v18_timing):
            self.MoveToVictoryDisplay()
        return super().OnBeDefeated(would_defeated_message, as_asset=as_asset, ignore_when_defeated=ignore_when_defeated)

    # @override
    # def OnResetKeywords(self, by_effect: 'Effect'):
    #     from game.ability.rule import ResetKeyword
    #     if self.printed_victory != None:
    #         self.GainVictory(self.printed_victory, ResetKeyword(self))
    #     return super().OnResetKeywords(by_effect)

    # def GainVictory(self, diff: int, by_effect: 'Effect'):
    #     self.GainKeyword(diff, 'Victory', by_effect)

    @final
    @property
    def victory(self) -> bool:
        return self.printed_victory != None

