from game.card.face.base import *
from game.card.face import *
from game.deck import *
from game.ability import *
from game.message import *

# Rename Character
class Unit2(CanHealth, CanRetaliate, CanStatus, CanPlaceCounter, CanPlaceToken):

    @override
    def OnWouldEnterPlay(self, into_area: 'Deck') -> bool:
        from game.effect.rule import ResetKeyword
        self.ResetHealth(ResetKeyword(self))
        return super().OnWouldEnterPlay(into_area)

    @override
    def OnAfterCardEnterPlay(self, message: 'Message.AfterCardEnterPlay') -> None:
        super().OnAfterCardEnterPlay(message)
        self.CheckHealthAfterActivation()

    @override
    def OnAfterCardFaceActivated(self, message: 'Message.AfterCardFaceActivated') -> None:
        super().OnAfterCardFaceActivated(message)
        self.CheckHealthAfterActivation()

    def CheckHealthAfterActivation(self) -> None:
        from game.effect.rule import GameRule
        if self.health <= 0 and self.IsInPlay() and not self.card.state.is_discarding: # Fix for "34009"
            # "12011"
            self.Death(None, GameRule(self))

    @override
    # def OnWouldDefeated(self, by_effect: 'Effect', message: 'Send.WhenUnitWouldThwart|Send.WhenUnitWouldAttack|None') -> 'Send.WhenUnitWouldBeDefeated|None':
    def OnWouldDefeated(self, killer: 'CardFace|None', by_effect: 'Effect', being_message: 'Message.WhenSchemeBeingThwart|Message.WhenUnitBeingAttack|None') -> 'Message.WhenSchemeWouldBeDefeated|Message.WhenUnitWouldBeDefeated|None':
        assert isinstance(being_message, Message.WhenUnitBeingAttack|None)
        would_message = Message.WhenUnitWouldBeDefeated(self.card.face.CastTo(Unit2), by_effect, killer, being_message)
        would_message.Send()
        return would_message

    @override
    def OnBeDefeated(self, would_defeated_message: 'Message.WhenSchemeWouldBeDefeated|Message.WhenUnitWouldBeDefeated', *, as_asset: bool, ignore_when_defeated: bool):
        from game.card.face.base import Villain
        from game.card.face.card_type import Identity
        from game.operate.faces import Faces
        from game.effect.rule import GameRule

        being_message = would_defeated_message.being_message
        by_effect = GameRule(self, being_message)
        killer = would_defeated_message.killer

        assert isinstance(would_defeated_message, Message.WhenUnitWouldBeDefeated)

        # Fix for "40199", "50131b"
        if self.bind_face and as_asset:
            Faces.DiscardAll([self], by_effect)
            return

        if being_message != None:
            assert type(being_message) is Message.WhenUnitBeingAttack

        defeated_message = Message.WhenUnitBeDefeated(self, would_defeated_message, ignore_when_defeated)
        defeated_message.Send()
        if defeated_message.add_to_victory_display and self.IsInPlay():
            self.CastTo(HasVictory).MoveToVictoryDisplay()

        super().OnBeDefeated(would_defeated_message, as_asset=as_asset, ignore_when_defeated=ignore_when_defeated)

        # Fix for "40199", "32066"
        if self.card.area.flags.is_in_play and \
            (not self.card.area.flags.is_upgrades or self.paper.card_id != "40199") and \
            not Villain.IsType(self) and \
            not Identity.IsType(self):
            Faces.DiscardAll([self], by_effect)
        after_defeated_message = Message.AfterUnitBeDefeated(self, killer, being_message, would_defeated_message)
        after_defeated_message.Send()

    ################################################################################
    #
    def CanBeAttackBy(self, effect: 'Effect') -> bool:
        from game.card.face.base import Enemy
        if Enemy.IsType(self):
            check_message = Message.CheckIfUnitCanBeAttackBy(self, effect)
            check_message.Send()
            return check_message.can_be_attack
        else:
            return True # Fix "32037"

    ################################################################################
    #
    @final
    def Death(self, killer: 'CardFace|None', by_effect: 'Effect', atk_message: 'Message.WhenUnitWouldAttackUnit|None'=None, *, ignore_when_defeated: bool=False) -> bool:
        from game.card.face.card_type import Event
        if Event.IsType(killer):
            killer = killer.GetControlByPlayer().GetIdentity()
        return self.Defeated(killer, by_effect, atk_message.being_atk_message if atk_message else None, ignore_when_defeated=ignore_when_defeated)

    ################################################################################
    #
    def GainForThisActive(self,
                            by_effect: 'Effect',
                            active_message: 'CanGainValueMessage',
                            *,
                            attack: int|None=None,
                            defense: int|None=None,
                            scheme: int|None=None,
                            thwart: int|None=None,
                            recover: int|None=None,
                            attack_consequential_damage: int|None=None,
                            thwart_consequential_damage: int|None=None,
                            ignore_flip: bool=True,
                            render_ui: bool=True):
        return self.TemporaryGain(
            by_effect,
            active_message,
            attack=attack,
            defense=defense,
            scheme=scheme,
            thwart=thwart,
            recover=recover,
            attack_consequential_damage=attack_consequential_damage,
            thwart_consequential_damage=thwart_consequential_damage,
            ignore_flip=ignore_flip,
            render_ui=render_ui
        )
    # def GainAttackForThisActive(self,
    #                             value: int,
    #                             by_effect: 'Effect',
    #                             end_message: 'Send.WhenUnitWouldAttack|Send.WhenUnitWouldScheme|Send.WhenUnitWouldThwart|Send.WhenUnitWouldAttackUnit|Send.WhenUnitWouldRecovery|Send.WhenUnitWouldAttack|Send.WhenUnitWouldDefend',
    #                             ignore_flip: bool=True,
    #                             *,
    #                             render_ui: bool=False):

    #     return self.TemporaryGain(
    #         by_effect,
    #         end_message,
    #         attack=value,
    #         ignore_flip=ignore_flip,
    #         render_ui=render_ui
    #     )

    # def GainDefenseForThisActive(self,
    #                             value: int,
    #                             by_effect: 'Effect',
    #                             end_message: 'Send.WhenUnitWouldAttack',
    #                             ignore_flip: bool=True,
    #                             *,
    #                             render_ui: bool=False):

    #     return self.TemporaryGain(
    #         by_effect,
    #         end_message,
    #         defense=value,
    #         ignore_flip=ignore_flip,
    #         render_ui=render_ui
    #     )

    # def GainSchemeForThisActive(self,
    #                             value: int,
    #                             by_effect: 'Effect',
    #                             end_message: 'Send.WhenUnitWouldAttack|Send.WhenUnitWouldScheme',
    #                             ignore_flip: bool=True,
    #                             *,
    #                             render_ui: bool=False):

    #     return self.TemporaryGain(
    #         by_effect,
    #         end_message,
    #         scheme=value,
    #         ignore_flip=ignore_flip,
    #         render_ui=render_ui
    #     )

    # def GainThwartForThisActive(self,
    #                             value: int,
    #                             by_effect: 'Effect',
    #                             end_message: 'Send.WhenUnitWouldAttack|Send.WhenUnitWouldThwart',
    #                             ignore_flip: bool=True,
    #                             *,
    #                             render_ui: bool=False):

    #     return self.TemporaryGain(
    #         by_effect,
    #         end_message,
    #         thwart=value,
    #         ignore_flip=ignore_flip,
    #         render_ui=render_ui
    #     )

    # def GainForThisActive(self,
    #                       process_fn: Callable[[bool], None],
    #                       by_effect: 'Effect',
    #                       end_message: 'Send.WhenUnitWouldAttack|Send.WhenUnitWouldSchemes'):
    #     return self.TemporaryGain(
    #         process_fn,
    #         by_effect,
    #         Send.AfterUnitAttacked|Send.AfterUnitSchemed,
    #         lambda effect, message:
    #             isinstance(message, Send.AfterUnitAttacked) and \
    #             end_message == message.atk_message or \
    #             isinstance(message, Send.AfterUnitSchemed) and \
    #             end_message == message.sch_message
    #     )

