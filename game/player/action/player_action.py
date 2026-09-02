from typing import TypeAlias
from core import *
from build import Build
from engine.log import Log
from game.card.face import *
from game.card import *
from game.deck import *
from game.ability import *
from game.selector import *
from game.ability.factory import *
from game.message import *
from game.player import *
from game.element.resources import Resources
from game.element.cost import Cost
from game.effect.effect_target_cost import TargetCost

CATEGORY_NAME = "PLAYER"

CardFaceType: TypeAlias = 'CardFace'

class PlayerAction:
    def GetPlayer(self) -> 'Player':
        from game.player import Player
        return Cast(Player, self)

    ################################################################################
    # Encounter
    def DealEncounterCard(self, face: 'CardFace', by_effect: 'Effect', *,
                          by_surge: bool=False,
                          to_end_of_queue: bool=False):
        from game.message import Message
        # from game.ability.rule import GameRule
        from game.operate.faces import Faces
        player = self.GetPlayer()
        world = self.GetPlayer().world

        would_message = Message.WhenPlayerWouldBeDealtEncounterCard(player, by_effect, face)
        would_message.Send()

        if would_message.is_be_instead:
            return

        pos = None
        if world.rule.v16_reveal or to_end_of_queue:
            pos = "Bottom"
            if by_surge:
                pos = "Top"
            Faces.MoveAllToDeck([face], player.dealt_encounter_cards, pos, by_effect)
        else:
            Faces.MoveAllTo([face], player.dealt_encounter_cards, by_effect)

        message = Message.AfterPlayerDealEncounterCard(player, would_message)
        message.Send()

    # facedown
    def DealEncounterCards(self, size: int, by_effect: 'Effect', *,
                           by_surge: bool=False,
                           to_end_of_queue: bool=False) -> None:
        world = self.GetPlayer().world
        if world.is_game_over:
            return

        faces: List['CardFace'] = []
        def process(face: 'CardFace'):
            nonlocal faces
            faces.append(face)
            self.DealEncounterCard(
                face,
                by_effect,
                by_surge=by_surge,
                to_end_of_queue=to_end_of_queue,
            )
        from game.operate.worlds import Worlds
        Worlds.PopEncounterCards(size, process, True, by_effect)

    def RevealEncounterCards(self) -> None:
        from game.effect.rule import GameRule
        player = self.GetPlayer()
        last_face = None
        while player.dealt_encounter_cards.GetSize() > 0:
            face = player.dealt_encounter_cards.GetTop()
            if not face:
                break
            assert face != last_face, f"{face=} {last_face=}"
            """
            You need to discard them by
            target = message.trigger
            target.Discard(effect)
            """
            face.Reveal(player, GameRule(face))
            if player.world.is_game_over:
                break
            if player.is_eliminated:
                break
            last_face = face
            player.stat.RecordReveal(last_face)

        player.dealt_encounter_cards.DiscardAll(GameRule(player.GetIdentity()))

    ################################################################################
    # Assign
    def AssignDamage(self, targets: Sequence['Unit2'], source: 'CardFace', damage: int, by_effect: 'Effect', *, operation: Callable[['Message.AfterUnitTookDamage'], None]|None=None, from_atk_message: 'Message.WhenUnitWouldAttack|None'=None):
        from game.operate.faces_helper import FacesHelper
        player = self.GetPlayer()

        messages: List['Message.AfterUnitDefeatedUnit|Message.AfterUnitTookDamage'] = []

        def assign() -> Dict['Unit2', int]:
            effects = player.ChooseAbilities(
                by_effect,
                AbilityFactory.ForChoiceAbility(
                    f"Assign {damage} damage",
                    lambda targets:
                        None,
                ).SetTarget(
                    targets,
                    range=("Zero", damage),
                    repeat_rules="Health")
            )
            if effects == []:
                # Fix "01111" when no heroes and allies
                # assert value == 0
                return {}
            else:
                # If indirect damage dealt to a player cannot be assigned to any character that player controls, that damage is ignored.
                assign_targets = effects[0].targets
                return FacesHelper.ListToDict(assign_targets) # type: ignore

        units = assign()
        from game.element.damage_property import DamageProperty

        for unit in units:
            damage = units[unit]
            message = unit.TakeDamage(source, DamageProperty(damage, is_indirect_damage=True), by_effect, operation=operation, from_atk_message=from_atk_message)
            if message:
                messages.append(message)

        # self.GetIdentity().TakeIndirectDamage(effect.this, damage, effect)
        return messages

    def AssignHeal(self, targets: Sequence['Unit2'], value: int, by_effect: 'Effect'):
        player = self.GetPlayer()

        def assign(targets: Sequence['Unit2'], value: int, by_effect: 'Effect') -> Dict['Unit2', int]:
            if not Select.From(faces=targets, repeat_rules="Sustained").GetAllLegalTargets(by_effect):
                return {}
            effects = player.ChooseAbilities(
                by_effect,
                AbilityFactory.ForChoiceAbility(
                    "",
                    lambda targets:
                        None,
                ).SetTarget(
                    targets,
                    repeat_rules="Sustained",
                    range=("Zero", value))
            )
            if effects == []:
                assert value == 0
                return {}
            else:
                from game.operate.faces_helper import FacesHelper
                return FacesHelper.ListToDict(effects[0].targets) # type: ignore

        units = assign(targets, value, by_effect)
        for unit in units:
            value = units[unit]
            unit.HealHealth(value, by_effect)

    ################################################################################
    # Effect
    def ChooseEffects(self, effects: List['Effect'], message: 'Message2', *, forced: bool=False, priority: 'TimingPriority'=TimingPriority.Normal) -> 'Effect|None':
        from game.event.manager import EventManager
        # from game.object.object_manager import ObjectManager
        player = self.GetPlayer()
        while True:
            # Clean all resource effect
            # ~~Call this late for avoid being reset before process all the paying effect~~
            # Must call this before filter
            # ObjectManager.ResetPayingEffect()
            filtered_effects = EventManager.FilterAvailableEffects(message, effects, player, player.world, None)
            if filtered_effects == []:
                return None
            from game.message import Message
            Message.PlayerOnEvent_Text(player, message)
            effect, cheat = self.ChoiceAndSpellEffect(filtered_effects, message, priority, forced)
            if cheat:
                continue
            else:
                break
        return effect

    def ChooseAbilities(self, by_effect: 'Effect', *abilities: 'Ability|None', forced: bool=True, repeat: int=1, choose_x_different_options: int|None=None, for_second_target: bool=False) -> List['Effect']:
        all_abilities = list(abilities)
        chose_effects: List['Effect'] = []

        must_different = False
        if choose_x_different_options != None:
            must_different = True
            repeat = choose_x_different_options

        for i in range(repeat):
            effect = self.ChooseAbilitiesHelper(by_effect, *all_abilities, forced=forced, step=(i+1, repeat), for_second_target=for_second_target)
            if effect:
                chose_effects.append(effect)
                if must_different:
                    all_abilities.remove(effect.ability)
        return chose_effects

    # Only choose one
    def ChooseAbilitiesHelper(self, by_effect: 'Effect', *abilities: 'Ability|None', forced: bool=True, step: Tuple[int, int]=(1, 1), for_second_target: bool=False) -> 'Effect|None':
        priority = TimingPriority.Normal
        if not by_effect.is_rule:
            # Hack for "50014"
            type = by_effect.ability.flags
            if type.is_interrupt:
                priority = TimingPriority.Interrupt
            elif type.is_response:
                priority = TimingPriority.Response

        player = self.GetPlayer()
        player.world.object_manager.ResetChooseEffect()
        effects: List['Effect'] = []
        identity = player.GetIdentity()
        for ability in abilities:
            if ability == None:
                continue
            effect = Effect(identity, ability, world=by_effect.world)
            effects.append(effect)

            if "ForChoiceAbilityWithCost" in ability.func_names:
                forced = False

        message = Message.WhenPlayerChooseAbility(player, by_effect, step, for_second_target)
        message.Send()
        # Cannot set `forced=True`, see "39019"
        return self.ChooseEffects(effects, message, forced=forced, priority=priority)

    def MayChooseOneAbility(self, by_effect: 'Effect', *abilities: 'Ability') -> 'Effect|None':
        cancel_ability = AbilityFactory.ForChoiceAbility(
            "Cancel",
            lambda targets: None,
        )
        effects = self.ChooseAbilities(by_effect, *abilities, cancel_ability)
        if effects and effects[0].ability == cancel_ability:
            return None
        return effects[0]

    # effects[force_index] = fallthrough_effect
    def ChoiceAndSpellEffect(self, filtered_effects: List['Effect'], message: 'Message2', priority: 'TimingPriority', forced: bool|Literal["Forced_Action"]=False) -> Tuple['Effect|None', bool]:
        from engine import Engine
        game = Engine.game

        player = self.GetPlayer()

        assert filtered_effects != [], f"{filtered_effects=} {message=}"

        while True:
            fallthrough_effect: Effect|None = None
            need_choose = True

            backup_effects = filtered_effects[:]
            for find_effect in filtered_effects[:]:
                if find_effect.context.only_work_when_no_other_options:
                    filtered_effects.remove(find_effect)
            if filtered_effects == []:
                filtered_effects = backup_effects

            # find fallthrough_effect
            for find_effect in filtered_effects:
                if forced == True:
                    fallthrough_effect = find_effect
                    min_target_num = fallthrough_effect.context.target_range[0]
                    max_target_num = fallthrough_effect.context.target_range[1]
                    fallthrough_effect.context.targets_internal = fallthrough_effect.context.all_legal_targets[:min_target_num]
                    if not forced:
                        assert not fallthrough_effect.ability.NeedCost(), f"{fallthrough_effect.ability}"
                    if min_target_num == max_target_num:
                        if min_target_num <= 1:
                            if len(find_effect.context.all_legal_targets) <= find_effect.context.target_range[0]:
                                need_choose = False
                        # Assign
                        elif len([x for x in fallthrough_effect.targets if x == fallthrough_effect.targets[0]]) == len(fallthrough_effect.targets) and \
                            fallthrough_effect.context.all_legal_targets == fallthrough_effect.targets:
                            need_choose = False
                    break

            if len(filtered_effects) != 1:
                need_choose = True
            elif filtered_effects[0].ability.is_play and \
                not filtered_effects[0].ability.flags.is_delay_ability and \
                filtered_effects[0].this.IsLikeInHand() and \
                not filtered_effects[0].this.card.area.flags.is_processing:
                need_choose = True

            # Reproduce only the forced confirmations recorded by legacy
            # saves. New full-deck inspection does not affect need_choose.
            if fallthrough_effect and fallthrough_effect.ability.selectors:
                selector = fallthrough_effect.ability.selectors[0]
                if selector and selector.force_choose:
                    need_choose = True

            if fallthrough_effect == None:
                for find_effect in filtered_effects:
                    if find_effect.must_choose:
                        fallthrough_effect = find_effect
                        min_target_num = fallthrough_effect.context.target_range[0]
                        fallthrough_effect.context.targets_internal = fallthrough_effect.context.all_legal_targets[:min_target_num]
                        assert not fallthrough_effect.ability.NeedCost(), f"{fallthrough_effect.ability}"

            def choice_one_effect(effect_list: Sequence['Effect']) -> Tuple['Effect|None', bool]:
                if not need_choose:
                    if fallthrough_effect and fallthrough_effect.ability.selectors:
                        selector = fallthrough_effect.ability.selectors[0]
                        if selector and \
                            selector.selector_end.full_search_display_faces and \
                            not selector.force_choose:
                            player.GetController().PresentFullSearch(
                                [
                                    face.card.object_id
                                    for face in selector.selector_end.full_search_display_faces
                                ],
                                [
                                    face.card.object_id
                                    for face in fallthrough_effect.context.all_legal_targets
                                ],
                                fallthrough_effect.context.target_range,
                                "Search the full deck",
                            )
                    return fallthrough_effect, False
                    # if not fallthrough_effect or \
                    #     fallthrough_effect.is_forced or \
                    #     fallthrough_effect.ability.type.is_discard_pay:
                    #     return fallthrough_effect, False

                if fallthrough_effect and \
                    fallthrough_effect.IsName("Cancel") and \
                    len(effect_list) == 1:
                    return fallthrough_effect, False

                # Fix "44028"
                if player.is_eliminated or message.world.is_game_over:
                    return None, False
                if type(message) is Message.WhenPlayerChooseAbility:
                    bind_effect = message.by_effect
                else:
                    bind_effect = None

                from game.world.world import Phase
                set_undo = False
                if type(message) == Message.WhenPlayerInTurn:
                    set_undo = True
                elif message.world.phase.state == Phase.State.PlayerTurnEnd:
                    set_undo = True
                elif message.world.phase.state == Phase.State.EnemyActivation:
                    if type(message) == Message.WhenUnitBeingAttack:
                        set_undo = True
                    pass
                elif message.world.phase.state == Phase.State.RevealsEncounterCards:
                    if type(message) == Message.WhenPlayerRevealCard:
                        set_undo = True
                    pass
                elif message.world.phase.state == Phase.State.ResolveMulligans:
                    set_undo = True

                if set_undo:
                    game.controller_manager.undo.PushNewStep(game.controller_manager.replay.current_step_id)

                selected, is_cheating = player.GetController().ChoiceOne(effect_list, bind_effect, message, priority, forced)

                game.controller_manager.undo.UpdateLastStep()

                if message.world.is_game_over:
                    return None, False
                return selected, is_cheating

            effect, is_cheating = choice_one_effect(filtered_effects)

            if is_cheating:
                return None, True
            else:
                break

        if not effect and fallthrough_effect:
            effect = fallthrough_effect

        while True:
            if not effect:
                break
            if message.world.is_game_over:
                break
            if self.ResolveEffect(effect, message):
                break

            if effect != fallthrough_effect:
                if type(message) == Message.WhenPlayerInTurn:
                    game.controller_manager.replay.Pop()
                    if not Build.release:
                        game.controller_manager.skip.Clean()
                    message.world.render.PresentForceNoWait(is_update=False)
                    Log.Assert(CATEGORY_NAME, f"{effect} failed")
                    # engine.DebugBreak()
                    break
                elif fallthrough_effect != None:
                    effect = fallthrough_effect
                else:
                    effect = None
                    break
            else:
                # Is is in selecting target
                # game.controller_manager.replay.PopHistoryInputs()
                # game.controller_manager.replay.PopHistoryInputs()
                return None, False
        return effect, False

    ################################################################################
    # Ability
    def ResolveSpecialAbility(self, faces: Sequence['CardFace'], by_effect: 'Effect'):
        player = self.GetPlayer()
        for face in faces:
            face.ResolveSpecialAbility(player, by_effect, sequence=faces)

    def ResolveEffect(self, effect: 'Effect', message: 'Message2') -> bool:
        from game.card.face.base import ClassCard
        from game.operate.faces import Faces

        this = effect.this

        is_like_from_hand = this.IsLikeInHand()
        # Fix for https://itch.io/t/4493777/interaction-between-magik-mutant-protector-defensive-energy
        if effect.ability.is_play and not effect.ability.flags.is_delay_ability:
            from_area = this.card.area
            Faces.MoveAllToProcessingArea([this], effect)
        else:
            from_area = None

        player = self.GetPlayer()

        if effect.checker.CheckBeforeActive(player):
            # assert type(message) != Send.WhenPlayerPayingResources, f"{message=}"
            if effect.ability.is_play and not effect.ability.flags.is_delay_ability:
                assert from_area != None
                this = effect.this.CastTo(ClassCard)
                if this.Play(player, effect, message, effect.context.paid_this_resources, from_area, is_like_from_hand):
                    player.stat.RecordPlayedFace(this)
                    player.world.buff_manager.OnRecordPlayedFace(this)
            else:
                effect.ResolveSelf(message, effect)
            return True
        else:
            if effect.ability.is_play:
                Faces.DiscardAll([this], effect)

        # Fix "45017"
        if effect.ability.selectors and \
            effect.ability.selectors[0]:
            effect.ability.selectors[0].IfSelectTargetFailure(effect)

        # Error
        from game.test import Test
        if Test.IsInTesting():
            from core.lib.beep import Beep
            Beep.Warning()
            # We can't call this, save data will broken
            # game.controller_manager.replay.PopHistoryInputs()
            # game.controller_manager.replay.UpdateReplayStepId(+1)
            # DebugBreak()

        Log.Assert(CATEGORY_NAME, f"{effect} failed")
        if not Build.release:
            controller_manager = player.controller.manager
            if controller_manager.skip.SetIsSkipping(False):
                if player.world:
                    player.world.render.PresentForceNoWait()

        return False

    ################################################################################
    # Hand Size
    def GetCountHandSizeFaces(self):
        player = self.GetPlayer()
        count_faces: List['CardFace'] = []
        for face in player.hand_cards.Get():
            message = Message.CheckIfFaceCountHandSize(player, face)
            message.Send()
            if message.count_hand_size:
                count_faces.append(face)
        return count_faces

    ################################################################################
    # Hand Cards
    def DrawUp(self, size: int|Literal["Max"], by_effect: 'Effect') -> List['CardFace']:
        from game.message import Message
        from game.card.face.card_type import Obligation
        player = self.GetPlayer()

        if player.world.is_game_over:
            return []

        if player.is_eliminated:
            return []

        faces: List['CardFace'] = []

        if size == "Max":

            max_repeat_times = 10
            while True:
                assert max_repeat_times > 0
                max_repeat_times -= 1

                if player.is_eliminated:
                    return []
                if by_effect.world.is_game_over:
                    return []

                count_hand_cards = player.GetCountHandSizeFaces()
                size = player.hand_size - len(count_hand_cards)
                size -= len([x for x in faces if Obligation.IsType(x)]) # Fix "04163"
                if size > 0:
                    faces += player.DrawUp(size, by_effect)
                else:
                    break
        else:
            def draw_up(face: 'CardFace'):
                message = Message.WhenPlayerWouldDrawCard(player, face, by_effect)
                message.Send()
                if not message.is_be_instead:
                    face.card.MoveToArea(player.hand_cards, by_effect, ui_group=True)

            faces = self.PopPlayerDeckCards(
                size,
                draw_up,
                by_effect,
                continue_after_shuffle=True,
            )
            if len(faces) < size:
                player.Eliminate(by_effect)
            message = Message.AfterPlayerDrewCards(player, {x: player.player_deck for x in faces}, by_effect)
            message.Send()
        return faces

    # Add it to your hand
    def GainCard(self, faces: Sequence['CardFace']|Sequence['ClassCard']|'CardFace', by_effect: 'Effect') -> List['CardFace']:
        from game.operate.faces import Faces
        from game.card.face.card_face import CardFace
        from game.player import Player
        from game.effect.rule import GameRule
        player = self.GetPlayer()

        if isinstance(faces, CardFace):
            faces = [faces]

        for face in faces:
            if face.IsInPlay():
                Faces.DiscardAll(face.GetInventoryDeck().Get(), GameRule(face))
                Faces.DiscardAll(face.GetPlacedCardArea().Get(), GameRule(face))

            # Fix "04097"
            from game.card.face.base import ClassCard
            if type(face.card.GetOwner()) is not Player and ClassCard.IsType(face):
                face.card.SetOwner(player)

        moved_faces = Faces.MoveAllTo(faces, player.hand_cards, by_effect)
        Message.AfterPlayerGainCards_Text(player, moved_faces, by_effect)
        return moved_faces

    def DiscardRandomHandCards(self, size: int, by_effect: 'Effect', rule: Literal["", "IdentitySpecific"]="") -> List['CardFace']:
        from game.operate.faces import Faces
        faces = self.GetRandomHandCards(size, rule)
        Faces.DiscardAll(faces, by_effect)
        return faces

    def GetRandomHandCards(self, size: int, rule: Literal["", "IdentitySpecific"]="") -> List['CardFace']:
        from game.card.face.base import ClassCard
        player = self.GetPlayer()

        # Log.GameInfo(f'{self} random choice {size} cards')
        faces = player.hand_cards.Get()
        if rule == "IdentitySpecific":
            for face in faces[:]:
                if not ClassCard.IsType(face) or not face.IsClass("IdentitySpecific"):
                    faces.remove(face)

        if len(faces) > size:
            from game.operate.rand import Rand
            return Rand.RandomChoice2(faces, size, player.world)
        return player.hand_cards.Get()

    def DiscardAllHands(self, by_effect: 'Effect', finder: 'CardFinder|None'=None) -> int:
        from game.operate.faces import Faces
        player = self.GetPlayer()

        faces = player.hand_cards.FindCards(finder)

        return len(Faces.DiscardAll(faces, by_effect))

    def GetAllResourceHandCards(self, text: "Resources.RBY") -> List['CardFace']:
        from game.card.face.base import ClassCard
        player = self.GetPlayer()

        return [x for x in player.hand_cards.Get() if ClassCard.IsType(x) and x.printed_resource.HasColorPrinted(text)]

    ################################################################################
    # Play
    def PlayAnAlly(self, ally: 'Ally', paying_cost: bool) -> bool:
        from game.element.resources import Resources
        from game.effect.rule import GameRule
        from game.operate.faces import Faces

        player = self.GetPlayer()

        effects = ally.effect.Find(func_name="Play")
        for effect in effects:
            # effect = effect.Copy()
            effect.context.initiator = player
            message = Message.WhenPlayerLikeInTurn(player, GameRule(player.GetIdentity()))
            message.Send()
            effect.checker.UpdateLegalTargets()
            effect.context.targets_internal = effect.context.all_legal_targets[:effect.context.target_range[1]]
            effect.context.bind_message = message
            from_area = ally.card.area
            if paying_cost:
                ally.card.can_state.is_like_in_hand = True
                self.ChooseEffects([effect], message)
                ally.card.can_state.is_like_in_hand = None
                # def play_ally(targets: Sequence['CardFace'], res: 'Resources'):
                #     ally.Play(player, effect, message, res, from_area)

                # # Cannot use `ForChoiceAbility` because we need the cost in `pay_effect`
                # play_effect = player.ChooseAbilities(
                #     effect,
                #     AbilityFactory.ForChoiceAbilityWithCost(
                #         AbilityType.ChooseAbility,
                #         ally.printed_cost,
                #         play_ally
                #     )
                # )
                # return play_effect != None
            else:
                Faces.MoveAllToProcessingArea([ally], effect)
                return ally.Play(player, effect, message, Resources("0"), from_area, False)
            # self.ChooseEffects([effect], )
        return False

    def _RegisterLikeInTurnCostModifiers(
        self,
        face: 'HasCost',
        effects: Sequence['Effect'],
        *,
        ignore_resources_cost: bool,
        update_resources_cost: int,
    ) -> List['Effect']:
        temp_effects: List[Effect] = []
        if ignore_resources_cost:
            for check_effect in effects:
                temp_effects += face.effect.Registers(
                    AbilityFactory.IgnoreThisCostIf(
                        AbilityType.Temp0,
                    )
                )
        elif update_resources_cost != 0:
            for check_effect in effects:
                temp_effects += face.effect.RegisterTemp(
                    AbilityFactory.ReduceCostToPlayThis(
                        lambda effect: -1 * update_resources_cost,
                        which_effect=check_effect
                    ),
                    unregister_after_exec=False
                )
        return temp_effects

    def CanPlayEffectLikeInHand(
        self,
        play_effect: 'Effect',
        message: 'Message2',
        *,
        ignore_resources_cost: bool=False,
        update_resources_cost: int=0,
        excluded_payment_faces: Sequence['CardFace']|None=None,
    ) -> bool:
        from game.card.face.attribute.has_cost import HasCost
        from game.event.manager import EventManager
        from game.operate.effects import Effects

        player = self.GetPlayer()
        face = play_effect.this.CastTo(HasCost)
        previous_like_in_hand = face.card.can_state.is_like_in_hand
        previous_excluded = play_effect.context.excluded_payment_faces
        temp_effects = self._RegisterLikeInTurnCostModifiers(
            face,
            [play_effect],
            ignore_resources_cost=ignore_resources_cost,
            update_resources_cost=update_resources_cost,
        )

        face.card.can_state.is_like_in_hand = True
        play_effect.context.excluded_payment_faces = list(
            excluded_payment_faces or []
        )
        try:
            return bool(EventManager.FilterAvailableEffects(
                message,
                [play_effect],
                player,
                player.world,
                None,
            ))
        finally:
            play_effect.context.excluded_payment_faces = previous_excluded
            face.card.can_state.is_like_in_hand = previous_like_in_hand
            Effects.UnRegister(temp_effects)

    def PlayEffectLikeInHand(
        self,
        play_effect: 'Effect',
        message: 'Message2',
        *,
        ignore_resources_cost: bool=False,
        update_resources_cost: int=0,
    ) -> 'Effect|None':
        from game.card.face.attribute.has_cost import HasCost
        from game.operate.effects import Effects

        player = self.GetPlayer()
        face = play_effect.this.CastTo(HasCost)
        previous_like_in_hand = face.card.can_state.is_like_in_hand
        temp_effects = self._RegisterLikeInTurnCostModifiers(
            face,
            [play_effect],
            ignore_resources_cost=ignore_resources_cost,
            update_resources_cost=update_resources_cost,
        )

        face.card.can_state.is_like_in_hand = True
        try:
            return player.ChooseEffects(
                [play_effect],
                message,
                forced=False,
                priority=play_effect.ability.priority,
            )
        finally:
            face.card.can_state.is_like_in_hand = previous_like_in_hand
            Effects.UnRegister(temp_effects)

    def PlayOneCardLikeInTurn(self, faces: List['CardFace'],
                            by_effect: 'Effect',
                            *,
                            ignore_resources_cost: bool=False,
                            update_resources_cost: int=0,
                            forced: bool=False):
        from game.card.face.attribute.has_cost import HasCost
        from game.operate.effects import Effects
        from game.operate.faces import Faces
        player = self.GetPlayer()

        def can_play_with_cost_modifiers(face: 'CardFace') -> bool:
            if not HasCost.IsType(face):
                return face.CanPlayBy(player)

            temp_effects = self._RegisterLikeInTurnCostModifiers(
                face,
                face.GetTurnPlayEffects(),
                ignore_resources_cost=ignore_resources_cost,
                update_resources_cost=update_resources_cost,
            )
            try:
                return face.CanPlayBy(player)
            finally:
                Effects.UnRegister(temp_effects)

        faces = [x for x in faces if can_play_with_cost_modifiers(x)]
        face = player.AskChooseFace(
            faces,
            by_effect,
            forced=forced,
            peek=True,
            not_move=False,
        )

        if HasCost.IsType(face):
            player.PlayCardsLikeInTurn(
                [face],
                by_effect,
                ignore_resources_cost=ignore_resources_cost,
                update_resources_cost=update_resources_cost,
                forced=forced
            )

        if face:
            if face.card.area.flags.is_processing:
                Faces.DiscardAll([face], by_effect)

    def MakeBasicPowerLikeInTurn(self,
                                faces: Sequence['CardFace'],
                                by_effect: 'Effect',
                                which_powers: List["CardFace.BASIC_POWER"],
                                *,
                                when_use: Callable[['Unit2', 'Message.WhenUnitUseBasicPower'], Any]|None=None,
                                ):
        from game.card.face.base import Friend
        from game.operate.effects import Effects

        effects: List['Effect'] = []
        temp_effects: List[Effect] = []

        for face in faces:
            if Friend.IsType(face):
                effects += face.GetBasicPowerEffects(which_powers)
        player = self.GetPlayer()
        identity = player.GetIdentity()

        if when_use:
            when_use_effects = identity.effect.Registers(
                AbilityFactory.WhenUnitUseBasicPower(
                    AbilityType.Temp0,
                    faces,
                    lambda effect, message:
                        when_use(message.trigger, message),
                )
            )
            temp_effects += when_use_effects

        message = Message.WhenPlayerLikeInTurn(player, by_effect)
        message.Send()
        player.ChooseEffects(effects, message)

        Effects.UnRegister(temp_effects)


    def PlayCardsLikeInTurn(self,
                            faces: List['CardFace'],
                            by_effect: 'Effect',
                            *,
                            ignore_resources_cost: bool=False,
                            update_resources_cost: int=0,
                            give_piercing: bool=False,
                            forced: bool=True,
                            after_play: Callable[['HasCost'], Any]|None=None,
                            if_not_play_discard_it: bool=True
                            ) -> List['CardFace']:
        from game.card.face.attribute.has_cost import HasCost
        from game.operate.effects import Effects
        from game.operate.faces import Faces

        player = self.GetPlayer()
        identity = player.GetIdentity()

        def play_card(face: HasCost) -> 'Effect|None':
            effects = face.GetTurnPlayEffects()

            # Fix "30004"
            # assert len(effects) == 1, f"{effects=}"
            temp_effects = self._RegisterLikeInTurnCostModifiers(
                face,
                effects,
                ignore_resources_cost=ignore_resources_cost,
                update_resources_cost=update_resources_cost,
            )

            if give_piercing:
                for check_effect in effects:
                    temp_effects += identity.effect.Registers(
                        AbilityFactory.WhenUnitWouldAttack(
                            AbilityType.Temp0,
                            None,
                            lambda effect, message:
                                message.GainPiercing(effect),
                            by_effect=check_effect,
                        )
                    )

            message = Message.WhenPlayerLikeInTurn(player, by_effect)
            message.Send()

            forced_play = forced
            if forced_play and not ignore_resources_cost:
                forced_play = False

            face.card.can_state.is_like_in_hand = True
            played = player.ChooseEffects(effects, message, forced=forced_play)
            face.card.can_state.is_like_in_hand = None

            # After play
            Effects.UnRegister(temp_effects)
            if after_play:
                after_play(face)

            if not played and if_not_play_discard_it:
                if face.IsInProcessingArea():
                    Faces.DiscardAll([face], by_effect)

            return played

        played_faces: List['CardFace'] = []
        for face in faces:
            if HasCost.IsType(face):
                # face.card.can_state.is_like_in_hand = None
                if play_card(face):
                    played_faces.append(face)
        return played_faces

    ################################################################################
    # Deck
    def PopPlayerDeckCards(self,
                           size: int,
                           process: Callable[['CardFace'], None|bool],
                           by_effect: 'Effect',
                           *,
                           continue_after_shuffle: bool=False,
                        #    is_group_action: Literal[False, "Draw", "Discard", "Set"]=False
                           ) -> List['CardFace']:
        player = self.GetPlayer()
        if player.is_eliminated:
            return []

        faces = player.player_deck.PopInternal(
            size,
            process,
            by_effect,
            continue_after_shuffle=continue_after_shuffle,
        )
        return faces

    def DiscardDeckTopCards(self, size: int|Literal["1*"], by_effect: 'Effect') -> List['CardFace']:
        player = self.GetPlayer()
        if player.is_eliminated:
            return []

        from game.operate.worlds import Worlds
        size = Worlds.ConvertPerPlayerIconToInt(size, by_effect)

        faces = player.player_deck.DiscardCardsInternal(
            size,
            by_effect,
            continue_after_shuffle=False,
        )
        return faces

    def DiscardDeckTopCard(self, by_effect: 'Effect') -> 'CardFace':
        faces = self.DiscardDeckTopCards(1, by_effect)
        return faces[0]

    def DiscardDeckUntil(self,
                         by_effect: 'Effect',
                        #  finder: 'CardFinder|None'=None,
                         *,
                         name: str|None=None,
                         trait: "CardFace.TRAITS|None"=None,
                         card_type: 'Type[TF]|CardFace'=CardFaceType,
                         return_other_faces: List['CardFace']|None=None,
                         **kwargs: Unpack['CardFinder.KWArgs'],
                         ) -> 'TF|None':
        player = self.GetPlayer()
        if player.is_eliminated:
            return None

        face, other = player.player_deck.DiscardUntil(
            by_effect,
            name=name,
            trait=trait,
            card_type=card_type,
            **kwargs
        )
        if return_other_faces != None:
            return_other_faces.clear()
            return_other_faces.extend(other)
        return face

    ################################################################################
    # Resources
    # def GetCanPayEffects(self, message: 'Send.CheckPlayerCanPayingResources', for_effect: 'Effect') -> List['Effect']:
    #     from cards.pack import World
    #     effects: List['Effect'] = []
    #     for player in World().GetPlayers(for_effect):
    #         for face in player.hand_cards.Get():
    #             for effect in face.effects:
    #                 if effect.ability.when == Send.WhenPlayerPayingResources:
    #                     effects += effect.ToAvailableArray(message)
    #         for face in player.GetControlCards():
    #             for effect in face.effects:
    #                 if effect.ability.when == Send.WhenPlayerPayingResources:
    #                     effects += effect.ToAvailableArray(message)
    #     return effects

    def SpendResource(self, for_effect: 'Effect', paid_effects: Sequence['Effect'], payment: 'TargetCost.Payment') -> 'Resources':
        from game.message import Message

        player = self.GetPlayer()

        paid_faces: List['CardFace'] = []

        for paying_effect in paid_effects:
            paid = False
            for pay_info in payment.payments:
                if paying_effect in pay_info:
                    paid = True
                    expected_res = Resources.FromText(pay_info[paying_effect])
                    paying_effect.context.initiator = player
                    cost_check_effect = payment.cost_check[paying_effect]
                    message = Message.WhenPlayerPayingResources(player, paying_effect, for_effect, for_effect.targets, expected_res, cost_check_effect)
                    message.Send()
                    paid_faces.append(paying_effect.this)
                    break
            if not paid:
                assert False, f"{paying_effect=} {for_effect=}"

        # for paying_effect in paying_effects:
        #     paying_effect.UnRegisterSelf()

        spent_message = Message.AfterCardsBeSpendAsResource(paid_faces, for_effect, player)
        spent_message.Send()

        for_effect.world.DiscardResourcesArea()

        resource = player.res_pool.Get()
        player.res_pool.Reset()

        return resource

    def AskSpendResources(self, cost: 'Cost', by_effect: 'Effect') -> bool:
        paid_res = self.AskSpendResourcesInternal(cost, by_effect)
        return paid_res != None

    def AskSpendResourcesInternal(self, cost: 'Cost', by_effect: 'Effect') -> 'Resources|None':
        player = self.GetPlayer()

        effects = player.ChooseAbilities(
            by_effect,
            AbilityFactory.ForChoiceAbilityWithCost(
                cost,
            )
        )
        if effects:
            return effects[0].context.paid_this_resources
        return None

    # Will ignore "Requirement"
    def PayCardPrintCost(self, face: 'HasCost', by_effect: 'Effect') -> 'Resources|None':
        player = self.GetPlayer()

        player.world.object_manager.ResetChooseEffect()
        ability = AbilityFactory.ForChoiceAbilityWithCost(
            face.printed_cost,
        )

        message = Message.WhenPlayerChooseAbility(player, by_effect, (1, 1), False)
        message.Send()
        # Fix "01072"
        effect = self.ChooseEffects([Effect(face, ability, world=by_effect.world)], message)
        if effect:
            return effect.context.paid_this_resources
        return None

    # def HasEnoughResources(self, cost: 'Resources'):
    #     return self.GetHasResource().IsMatchCost(cost)

    # Return from top to bottom
    def LookAtDeck(self, deck: 'Deck|Literal["EncounterDeck"]', num: int|Literal["2*"], by_effect: 'Effect', *, from_top: bool=True) -> List['CardFace']:
        from game.operate.faces import Faces
        from game.operate.worlds import Worlds

        player = self.GetPlayer()

        num = Worlds.ConvertPerPlayerIconToInt(num, by_effect)

        if deck == "EncounterDeck":
            deck = Worlds.GetEncounterDeck(by_effect)

        faces = deck.Get(from_top)[:num]
        Faces.LookAt(faces, player, by_effect)

        # reversed_face = faces[::-1]
        return faces

    def SwapTheseCards(self, faces: Sequence['CardFace'], by_effect: 'Effect'):
        from game.operate.faces import Faces
        def action(targets: Sequence['CardFace']):
            Faces.SwapTwoCards(targets, by_effect)

        while True:
            effect = self.MayChooseOneAbility(
                by_effect,
                AbilityFactory.ForChoiceAbility(
                    "Select 2 cards to swap",
                    action
                ).SetTargetInternal(Select.From(faces=faces, range=(2, 2), by_search=True, not_shuffle=True, not_move=True))
            )
            if effect == None:
                break
            if effect.world.is_game_over:
                break
