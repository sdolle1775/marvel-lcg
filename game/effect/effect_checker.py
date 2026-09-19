from core import *
from game.card.face import *
from game.ability import *
from game.message import *
from game.player import *
from engine.log import Log
from game.effect.effect_failure import EffectFailure

CATEGORY_NAME = "EFFECT"

class EffectChecker:
    def __init__(self, effect: 'Effect') -> None:
        from game.effect.effect_failure import FailureReason
        from game.effect.effect_target_cost import TargetCost
        self.effect = effect
        self.ability = effect.ability

        self.failures = FailureReason(effect)
        self.cost_for_different_target = TargetCost()

    def HasCostTargets(self) -> bool:
        for cost_func in self.effect.cost_func.GetAll():
            if not cost_func.HasTargets(self.effect):
                return False
        return True

    def UpdateLegalTargets(self, referential_effect: 'Effect|None'=None) -> bool:
        from game.operate.faces_counter import FacesCounter
        from game.selector.selector import Selector
        effect = self.effect
        ability = self.ability

        if isinstance(effect.bind_message, Message.WhenPlayerChooseAbility):
            for_second_target = effect.bind_message.for_second_target
        else:
            for_second_target = False

        if ability.flags.is_statistics:
            return True
        if ability.flags.is_delay_ability:
            return True
        if not ability.selectors:
            return True

        def get_all_legal_targets(selector: 'Selector', index: int, dont_update_target: bool) -> bool:
            all_legal_targets = list(selector.GetAllLegalTargets(effect, referential_effect))

            # Fix "29033" `divided_evenly`
            if index == 0:
                effect.context.all_legal_targets = all_legal_targets

            target_range = selector.GetTargetRange(effect, all_legal_targets)
            if target_range == None:
                # `failure_reason` is set in `GetTargetRange`
                # self.failure_reason = "target range error"
                return False
            if selector.selector_rule.select_rule == "DifferentType":
                if FacesCounter.GetDifferentTypesCount(all_legal_targets) < target_range[0]:
                    self.failures.Set(effect.initiator, EffectFailure.TypeCountNotEnough)
                    return False
            if selector.selector_rule.select_rule == "MustIncludeTraits":
                left_must_include_traits: List['CardFace.TRAITS'] = selector.selector_rule.target_must_include_traits[:]
                for target in all_legal_targets:
                    traits = target.FindHasTrait(*left_must_include_traits)
                    left_must_include_traits = [x for x in left_must_include_traits if x not in traits]
                    if not left_must_include_traits:
                        break
                if left_must_include_traits:
                    self.failures.Set(effect.initiator, EffectFailure.TypeCountNotEnough)
                    return False

            if dont_update_target:
                pass
            elif index == 0:
                effect.context.all_legal_targets = all_legal_targets
                effect.context.target_range = target_range
            else:
                effect.context.all_legal_targets = []
                effect.context.target_range = (0, 0)
            return True

        if effect.world.rule.v18_timing or effect.world.rule.v16_confuse_stun:
            # A stunned character can attempt to attack or use an attack ability even if it has no valid target for an attack.
            # This also applies to attack/thwart Specials: an undamaged
            # Vibranium Suit can remove stun before the next upgrade resolves.
            # We cannot use `is_like_xxx` here; basic powers handle their own targets.
            status_cancels_ability = (
                ability.is_label_attack and effect.initiator.GetRoleCharacter().IsStunned()
            ) or (
                # A confused character can attempt to thwart or use a thwart ability even if it has no valid target for a thwart
                ability.is_label_thwart and effect.initiator.GetRoleCharacter().IsConfused()
            )
            if status_cancels_ability and not for_second_target:
                # A status card can waive the labeled ability's target requirement,
                # but it cannot waive a Team-Up play restriction.
                for index, selector in enumerate(ability.selectors):
                    if selector and selector.target_text == "TeamUp" and \
                    (
                        selector.condition == None or \
                        selector.condition(effect)
                    ):
                        try:
                            if not get_all_legal_targets(selector, index, True):
                                return False
                        except Exception as exc:
                            info = Log.OnCrash(CATEGORY_NAME, exc, effect.GetDisplayName(), None)
                            effect.world.render.ErrorOccurred(info)
                            return False

                effect.context.all_legal_targets = []
                effect.context.target_range = (0, 0)
                return True

        has_target = False
        is_teamup = False

        for index, selector in enumerate(ability.selectors):
            if selector and \
            (
                selector.condition == None or \
                selector.condition(effect)
            ):
                has_this_target = False
                if not has_target or index == 0 or not selector.is_optional:
                    try:
                        dont_update_target = is_teamup or (not selector.is_optional and index != 0)
                        has_this_target = get_all_legal_targets(selector, index, dont_update_target)
                    except Exception as exc:
                        info = Log.OnCrash(CATEGORY_NAME, exc, effect.GetDisplayName(), None)
                        effect.world.render.ErrorOccurred(info)
                        has_target = False
                        break

                    if not selector.is_optional and not has_this_target:
                        has_target = False
                        break

                    # TeamUp must can select TeamUp characters and its targets
                    if selector.target_text == "TeamUp":
                        is_teamup = True
                        if has_this_target == False:
                            has_target = False
                            break
                        else:
                            if len(ability.selectors) > 1:
                                continue
                has_target |= has_this_target

        return has_target

    def UpdatePayResources(self, player: 'Player') -> bool:
        from game.message import Message
        from game.effect.effect_target_cost import TargetCost
        effect = self.effect
        ability = self.ability

        assert ability.NeedCost()
        if player.world.rule.disable_pay:
            effect.context.ignore_resource_cost = True
        else:
            effect.context.ignore_resource_cost = False

        self.effect.this.card.ui.cost.Reset("All")

        self.cost_for_different_target = TargetCost()
        if not effect.context.ignore_resource_cost:
            def process_target(target: 'CardFace|None'):
                if target:
                    targets = [target]
                else:
                    targets = []

                calc_message = Message.WhenCalculateEffectCost(player, effect, targets)
                calc_message.Send()
                self.cost_for_different_target.AddTarget(target, calc_message.cost)

                paying_message = Message.CheckPlayerCanPayCost(player, effect, calc_message.cost, targets)
                paying_message.Send()
                for the_effects in paying_message.can_pay_effects:
                    cost_effect, res, check_effect = the_effects
                    self.cost_for_different_target.AddPayment(target, cost_effect, res, check_effect)
                pass

            # Upgrade costs can depend on the attached card (Iron Man) or
            # its play area (Pawn Shop Showdown). Price each destination.
            if effect.context.all_legal_targets and (
                (ability.is_play and Upgrade.IsType(effect.this)) or
                "09039" in [x.paper.card_id for x in effect.context.all_legal_targets]
            ):
                for target in effect.context.all_legal_targets:
                    process_target(target)
            else:
                self.cost_for_different_target.SetNoneTargetOnly()
                process_target(None)

        return True

    ################################################################################
    #
    def CheckBeforeActive(self, player: 'Player') -> bool:
        from game.element.resources import Resources
        effect = self.effect

        def check_target() -> bool:
            if self.ability.selectors != []:
                if not self.ability.selectors[0]:
                    return True
                if not self.ability.selectors[0].AfterSelectTargets(effect, effect.targets, effect.context.target_range):
                    return False
            return True

        def check_pay():
            res_text = ""
            need_cost = ""
            if not self.cost_for_different_target.IsEmpty() and not effect.context.ignore_resource_cost:
                target = effect.targets[0] if effect.targets != [] else None
                need_cost = self.cost_for_different_target.GetCost(target)
                paid_effects = effect.context.paid_this_res_effects
                effect.context.this_effect_need_cost = need_cost

                effect.context.paid_this_cost = need_cost
                payment = self.cost_for_different_target.GetPayment(target)

                # Mr. Hollywood can only supply a resource after the card's
                # resource cost has already been met by the other payments.
                if any(paid_effect.this.IsName("Mr. Hollywood") for paid_effect in paid_effects):
                    other_resources = Resources("0")
                    for paid_effect in paid_effects:
                        if paid_effect.this.IsName("Mr. Hollywood"):
                            continue
                        for pay_info in payment.payments:
                            if paid_effect in pay_info:
                                other_resources += Resources.FromText(pay_info[paid_effect])
                                break
                    if not other_resources.IsMatchCost(need_cost):
                        return False

                effect.context.paid_this_resources = player.SpendResource(effect, paid_effects, payment)
                player.res_pool.Reset()
                return effect.context.paid_this_resources.IsMatchCost(need_cost)
            else:
                effect.context.paid_this_resources = Resources("0")
                return True
            self.failures.Set(player, f"pay cost, need {need_cost}, but only have {res_text}")
            return False

        if not check_target():
            self.failures.Set(player, EffectFailure.CheckTarget)
            return False

        if not check_pay():
            self.failures.Set(player, EffectFailure.CheckPay)
            return False

        return True

    def CheckNotOutOfPlay(self) -> bool:
        from game.card.face.card_type import Obligation
        from game.card.face.base import Villain

        this = self.effect.this

        if Obligation.IsType(this):
            if this.card.area.flags.is_processing:
                return False
        if Villain.IsType(this): # Fix "27074"
            if this.IsInPlay() and this.IsThisFaceUp(): # Fix "16080b"
                return True

        if this.card.area.flags.is_status_area and this.IsFaceUp():
            return True

        if self.ability.is_ignore_out_of_play:
            return True

        if self.ability.can_work_also_in_hand:
            if this.IsLikeInHand():
                return True

        # Fix "21032", this must be infront of `IsInPlay`
        if self.ability.can_work_only_in_hand:
            if not this.IsLikeInHand():
                return False
            else:
                return True

        # If a minion with WhenRevealed, it will past this check from here
        if this.IsInPlay(is_same_face=True) and this.IsFaceUp():
            return True

        if this.card.area.flags.is_processing and \
            this.IsFaceUp():
            return True

        if self.ability.is_play:
            return True

        if self.ability.flags.is_when_reveal and \
            this.CanResolveWhenRevealed():
            return True
        if self.ability.flags.is_boost and \
            this.card.area.flags.is_boost_area and \
            this.IsFaceUp():
            return True
        return False

    # def CheckBindFaceIsNotDefeating(self) -> bool:
    #     this = self.this

    #     # if not self.effect.ability.type.is_nonkeyword:
    #     #     return True

    #     face = this.bind_face
    #     if face:
    #         # Fix "27104"
    #         # You can remove threat from Light at the End when you defeat a 
    #         # Sinister Six villain, even if that villain had Taunting Presence attached.
    #         # Fix "16064"
    #         if face.card.state.is_defeating:
    #             return True
    #     return True

    def CheckCondition(self, message: 'Message2', asked_player: 'Player|None') -> bool:
        this = self.effect.this

        # Player card abilities cannot resolve during game setup,
        # unless prefaced by a "Setup" timing trigger.
        # Fix "01019b", "50067a", "20001b"
        if not self.effect.world.is_game_started and \
            not isinstance(message, Message.WhenPlayerChooseAbility) and \
            not self.effect.is_forced and \
            not self.ability.flags.is_setup and \
            PlayerCard.IsType(this):
            return False

        # Fix there are more than 3 allies and defeat "50081"
        # if this.card.state.is_defeating:
        #     return False

        if not self.CheckNotOutOfPlay():
            self.failures.Set(asked_player, EffectFailure.OutOfPlay)
            return False

        # Fix "27153", "39071"
        if this.card.area.flags.is_revealing and \
            self.effect.ability.flags.is_nonkeyword and \
            not self.effect.ability.IsFunction("AttachToWhenEnterPlay") and \
            not self.effect.ability.IsFunction("CheckAllyLimit"):
            return False

        # if not self.CheckBindFaceIsNotDefeating():
        #     self.failures.Set(asked_player, EffectFailure.BindFaceIsDefeating)
        #     return False

        if self.ability.is_play:
            if asked_player:
                if this.card.can_state.is_like_in_hand is True:
                    pass
                elif this.card.area == asked_player.hand_cards:
                    pass
                elif this.GetOwner() != asked_player:
                    self.failures.SetText(asked_player, f"{asked_player} doesn't have this card")
                    return False

        if message.send_resolve_message:
            if not self.ability.flags.is_statistics:
                check_message = Message.CheckEffectCondition(self.effect, this)
                check_message.Send()
                if not check_message.effect_valid:
                    self.failures.SetText(asked_player, str([x.this for x in check_message.cause_by]))
                    return False

        for condition in self.ability.conditions:
            if not self.effect.is_forced and self.effect.initiator != asked_player:
                self.failures.SetText(asked_player, f"asking {asked_player}, but initiator is {self.effect.initiator}")
                return False
            try:
                if not condition(self.effect, message):
                    self.failures.SetText(asked_player, GetFuncName(condition))
                    return False
            except Exception as exc:
                info = Log.OnCrash(CATEGORY_NAME, exc, self.effect.GetDisplayName(), condition)
                self.effect.world.render.ErrorOccurred(info)
                return False

        if isinstance(message, Message.WhenPlayerChooseAbility):
            by_effect = message.by_effect
        else:
            by_effect = self.effect

        if not self.UpdateLegalTargets(by_effect):
            self.failures.Set(asked_player, EffectFailure.UpdateLegalTargets)
            return False

        if not self.HasCostTargets():
            self.failures.Set(asked_player, EffectFailure.NoCostTarget)
            return False

        if self.ability.NeedCost():
            if not asked_player:
                self.failures.Set(asked_player, EffectFailure.HasCostButNoAskPlayer)
                assert False, f"{self=}"
            self.UpdatePayResources(asked_player)

        if self.ability.is_label_defense:
            # from game.message.message_type import AttackerMessageInternal
            if isinstance(message, AttackerMessageInternal):
                if message.has_resolves_defense_labeled_ability != None and \
                    message.has_resolves_defense_labeled_ability != asked_player:
                    self.failures.Set(asked_player, EffectFailure.AlreadyResolvesDefense)
                    return False

        self.failures.Set(asked_player, EffectFailure.OK)
        return True
