from typing import Final, TypeAlias
from core import *
from game.ability import *
from game.message import *
from game.player import *
from game.card.face import *
from engine.job import JobManager
from engine.log import DebugLog, Log
from game.world import *
from game.event.counter import EventCounter
from engine.config import ConfigVariables
from game.message.message_type import CardStateUpdatedMessage
from engine.controller.module.undo import UndoModule

FastUndoHandle = UndoModule.UndoHandle|None

FILE_BASED_FAST_UNDO    = ConfigVariables.Bool('file_based_fast_undo', False)
CACHE_BASED_FAST_UNDO   = ConfigVariables.Bool('cache_based_fast_undo', False)

class EventManager:

    CATEGORY: TypeAlias = Literal["Statistics", "Rule", "Paying", "Forced", "Optional"]
    CATEGORY_LIST: List['EventManager.CATEGORY'] = ["Statistics", "Rule", "Paying", "Forced", "Optional"]

    def __init__(self, world: 'World') -> None:
        self.effects: Dict[EventManager.CATEGORY, Dict[Type['Message2'], Dict['TimingPriority', List['Effect']]]] = {
            "Statistics": {},
            "Rule": {},
            "Paying": {},
            "Forced": {},
            "Optional": {},
        }

        self.registered_message_type: Dict[Type['Message2'], int] = {}

        self.event_size = EventCounter()
        # self.last_message: Message2|None = None
        # self.process_message: Message2|None = None
        self.world: Final = world
        self.new_effect_created: bool = False

        self.debug_log = DebugLog("NoSendResolve")
        self.debug_log_both = DebugLog("Both")
        self.debug_log_only_local = DebugLog("Only Local")
        self.debug_log_only_global = DebugLog("Only Global")

        self.stack_message: List['CardStateUpdatedMessage'] = []
        self.timing_occurrences: List['TimingOccurrence'] = []
        self.resolving_timing_occurrences: List['TimingOccurrence'] = []
        self.broadcasting_messages: List['Message2'] = []

    def BeginTimingOccurrence(
        self,
        *,
        delay_reveal_responses: bool=False,
    ) -> 'TimingOccurrence|None':
        if not bool(self.world.rule.v18_timing):
            return None
        from game.event.timing import TimingOccurrence

        occurrence = TimingOccurrence(
            self.world,
            delay_reveal_responses=delay_reveal_responses,
        )
        self.timing_occurrences.append(occurrence)
        return occurrence

    def EndTimingOccurrence(self, occurrence: 'TimingOccurrence|None') -> None:
        if occurrence == None:
            return
        if occurrence not in self.timing_occurrences:
            from engine.log import Log

            if occurrence.state == "collecting":
                occurrence.Abort()
            Log.Warn(
                "MESSAGE",
                f"Ignored stale timing occurrence close (state={occurrence.state})",
            )
            return
        if self.timing_occurrences[-1] is not occurrence:
            self.AbortTimingOccurrence(
                occurrence,
                reason="timing occurrences closed out of order",
            )
            return
        self.timing_occurrences.pop()

        # A child window must finish before its parent can collect any more
        # conditions. Temporarily hide every collecting parent while the
        # child resolves so gameplay initiated by a response opens its own
        # occurrence instead of leaking messages into the parent.
        parents = self.timing_occurrences[:]
        self.timing_occurrences.clear()
        self.resolving_timing_occurrences.append(occurrence)
        try:
            occurrence.Resolve()
        finally:
            if self.timing_occurrences:
                from engine.log import Log

                leaked = self.timing_occurrences[:]
                for check_occurrence in reversed(leaked):
                    check_occurrence.Abort()
                self.timing_occurrences.clear()
                Log.Warn(
                    "MESSAGE",
                    f"Aborted {len(leaked)} leaked timing occurrence(s) "
                    f"while resolving {occurrence.messages[0].name if occurrence.messages else 'empty occurrence'}",
                )
            assert self.resolving_timing_occurrences[-1] is occurrence
            self.resolving_timing_occurrences.pop()
            self.timing_occurrences.extend(parents)

    def AbortTimingOccurrence(
        self,
        occurrence: 'TimingOccurrence|None',
        *,
        reason: str="",
    ) -> None:
        if occurrence == None:
            return
        if occurrence not in self.timing_occurrences:
            return
        index = self.timing_occurrences.index(occurrence)
        aborted = self.timing_occurrences[index:]
        del self.timing_occurrences[index:]
        for check_occurrence in reversed(aborted):
            check_occurrence.Abort()
        if reason:
            from engine.log import Log

            Log.Warn(
                "MESSAGE",
                f"Aborted {len(aborted)} timing occurrence(s): {reason}",
            )

    def RestoreTimingOccurrenceDepth(self, depth: int, *, reason: str) -> None:
        if len(self.timing_occurrences) <= depth:
            return
        occurrence = self.timing_occurrences[depth]
        self.AbortTimingOccurrence(occurrence, reason=reason)

    def TimingOccurrenceScope(
        self,
        *,
        delay_reveal_responses: bool=False,
    ):
        from contextlib import contextmanager

        @contextmanager
        def scope():
            occurrence = self.BeginTimingOccurrence(
                delay_reveal_responses=delay_reveal_responses,
            )
            try:
                yield occurrence
            except Exception:
                self.AbortTimingOccurrence(
                    occurrence,
                    reason="exception escaped timing occurrence scope",
                )
                raise
            else:
                self.EndTimingOccurrence(occurrence)

        return scope()

    def TryQueueTimingMessage(self, message: 'Message2') -> bool:
        if not self.timing_occurrences:
            return False
        from game.message import Message

        grouped_types: Tuple[Type['Message2'], ...] = (
            Message.AfterAllyTakeConsequentialDamage,
            Message.AfterEnemyActivationEnd,
            Message.AfterFaceDealDamage,
            Message.AfterMainSchemeCompleted,
            Message.AfterSchemeBeDefeated,
            Message.AfterSchemePlaceThreat,
            Message.AfterSchemeRemoveThreat,
            Message.AfterUnitAttackEnd,
            Message.AfterUnitAttackUnit,
            Message.AfterUnitBeDefeated,
            Message.AfterUnitDefeatedUnit,
            Message.AfterUnitDefeatedScheme,
            Message.AfterUnitDefendEnd,
            Message.AfterUnitHealHealth,
            Message.AfterUnitRecovery,
            Message.AfterUnitSchemeEnd,
            Message.AfterUnitThwartEnd,
            Message.AfterUnitThwartScheme,
            Message.AfterUnitTookDamage,
            Message.AfterUnitUseBasicPower,
        )
        occurrence = self.timing_occurrences[-1]
        if occurrence.state != "collecting":
            return False
        if occurrence.delay_reveal_responses:
            # Rules Reference v1.8 defers responses to every step of an
            # encounter-card reveal until the complete reveal process ends.
            grouped_types += (
                Message.AfterCardEnterPlay,
                Message.AfterCardPutIntoPlay,
                Message.AfterMinionEngagePlayer,
                Message.AfterCardRevealed,
                Message.AfterCardRevealedEnd,
            )
        if not isinstance(message, grouped_types):
            return False
        occurrence.Add(message)
        return True

    def GetEffectCategory(self, effect: 'Effect', event: Type['Message2']) ->  Literal["Forced", "Rule", "Paying", "Optional", "Statistics"]:
        from game.ability import AbilityType
        from game.message import Message
        if effect.ability.flags.is_statistics:
            return "Statistics"
        if effect.is_nonkeyword:
            return "Rule"
        # Delayed effects and consequential damage are mandatory framework
        # effects, not Forced abilities. They resolve automatically at their
        # designated timing priorities and must never create an ordering
        # prompt intended for printed Forced triggers.
        if bool(self.world.rule.v18_timing) and effect.ability.type in (
            AbilityType.DelayAbility,
            AbilityType.Consequential,
        ):
            return "Rule"
        if event is Message.WhenPlayerPayingResources:
            return "Paying"
        if effect.is_rule:
            return "Rule"
        if effect.ability.flags.is_temp:
            return "Rule"
        if effect.is_forced:
            return "Forced"
        return "Optional"

    def AddEffectsList(self, category: 'EventManager.CATEGORY', event: Type['Message2'], priority: 'TimingPriority', add_effect: 'Effect') -> None:
        found_dict = self.effects[category]
        if event not in found_dict:
            found_dict[event] = {}
        if priority not in found_dict[event]:
            found_dict[event][priority] = []
        found_dict[event][priority].append(add_effect)

    def FindEffectsList(self, category: 'EventManager.CATEGORY', event: Type['Message2'], priority: 'TimingPriority') -> List['Effect']:
        found_dict = self.effects[category]
        if event not in found_dict:
            return []
        if priority not in found_dict[event]:
            return []
        return found_dict[event][priority]

    def GetEffectivePriority(self, effect: 'Effect') -> 'TimingPriority':
        """Return the selected ruleset's priority without mutating abilities."""
        from game.ability import AbilityType, TimingPriority

        if bool(self.world.rule.v18_timing) and effect.ability.type in (
            AbilityType.WhenDefeated,
            AbilityType.WhenCompleted,
        ):
            return TimingPriority.ForcedInterrupt
        if bool(self.world.rule.v18_timing) and effect.ability.type in (
            AbilityType.DelayAbility,
            AbilityType.Temp1,
        ):
            return TimingPriority.Constant
        return effect.ability.priority

    def FindTimingEffects(
        self,
        category: 'EventManager.CATEGORY',
        event: Type['Message2'],
        priority: 'TimingPriority',
    ) -> List['Effect']:
        """Find effects by effective rather than registration-time priority."""
        if not bool(self.world.rule.v18_timing):
            return self.FindEffectsList(category, event, priority)
        event_effects = self.effects[category].get(event, {})
        return [
            effect
            for effects in event_effects.values()
            for effect in effects
            if self.GetEffectivePriority(effect) == priority
        ]

    def HasRegisteredEvent(self, event: Type['Message2']) -> int:
        if event in self.registered_message_type:
            return self.registered_message_type[event]
        return 0

    def RegisterEffect(self, effect: 'Effect'):
        effect.is_unregister = False

        self.new_effect_created = True

        # if effect.ability.type.ability_type == AbilityType.CheckResource:
        #     pass

        if effect.is_local:
            events = Types.UnionTypeExtract(effect.ability.when)
            for event in events:
                category = self.GetEffectCategory(effect, event)
                assert category in ["Forced", "Paying", "Rule", "Optional"]
        else:
            events = Types.UnionTypeExtract(effect.ability.when)
            for event in events:
                if event in self.registered_message_type:
                    self.registered_message_type[event] += 1
                else:
                    self.registered_message_type[event] = 1

                self.event_size.Add(event)
                category = self.GetEffectCategory(effect, event)
                assert category != "Paying"
                self.AddEffectsList(category, event, effect.ability.priority, effect)

    def UnRegisterEffect(self, effect: 'Effect'):
        effect.is_unregister = True
        # TODO:
        # if effect.is_local:
        #     return
        events = Types.UnionTypeExtract(effect.ability.when)
        for event in events:
            self.registered_message_type[event] -= 1
            category = self.GetEffectCategory(effect, event)
            effects_list = self.FindEffectsList(category, event, effect.ability.priority)
            if effect.is_local:
                assert effect not in effects_list
            else:
                effects_list.remove(effect)

    ################################################################################
    #
    def RegisterPlayRule(self):
        from game.rule.gameplay import GetGamePlayRules
        from game.rule.statistics import GetStatisticsRule
        from game.rule.achievement import GetPlayAchievement
        # from game.rule.challenges import GetChallengeRules
        from game.card.factory import CardFactory
        from game.effect.rule import GameRule
        world = self.world
        insert = CardFactory.GenerateCard('rule_a,rule_b', world.area_insert, world).face.CastTo(Insert)
        world.insert = insert
        for ability in GetGamePlayRules():
            insert.effect.Registers(ability)
        from engine import Engine
        if Engine.statistics.CanRegisterAbility():
            for ability in GetStatisticsRule():
                insert.effect.Registers(ability)
            for ability in GetPlayAchievement():
                insert.effect.Registers(ability)
        # insert.PutIntoPlay(None, effect)
        effect = GameRule(insert)
        for challenge in world.scene.campaign.challenges:
            challenge = CardFactory.GenerateCard(challenge, world.area_insert, world).face
            challenge.PutIntoPlay("FirstPlayer", effect)

    ################################################################################
    #
    def ProcessEffect(self, effect: 'Effect', message: 'Message2', priority: 'TimingPriority') -> bool:
        from game.player import Player
        from game.message.sender.sender import TriggerNonePlayerMessage

        # self.process_message = message

        processed = False
        if effect.ability.selectors:
            owner = effect.this.GetOwner()
            player = None
            if isinstance(owner, Player):
                player = owner
            elif isinstance(message, TriggerNonePlayerMessage):
                # and not effect.is_forced:
                player = message.to_player
            if player:
                # if effect.is_forced:
                #     faces = player.AskChooseSelect2(
                #         effect.all_legal_targets,
                #         effect.target_range,
                #         effect,
                #         peek=False,
                #         not_move=True,
                #         not_shuffle=True,
                #     )
                #     effect.targets = faces
                # else:
                    cheat = True
                    while cheat:
                        selected, cheat = player.ChoiceAndSpellEffect([effect], message, priority, forced=True)
                    processed = selected != None
            else:
                assert effect.is_forced, f"{effect=}"
                assert effect.context.target_range[0] == effect.context.target_range[1], f"{effect.context.target_range=}"
                assert len(effect.context.all_legal_targets) == effect.context.target_range[1], f"{effect.context.all_legal_targets=}"
                effect.context.targets_internal = effect.context.all_legal_targets[:]
        if not processed:
            processed = effect.ResolveSelf(message, effect)
        return processed

    ################################################################################
    #
    def ProcessRuleEffect(self, message: 'Message2', rule_effects: List['Effect'], priority: 'TimingPriority', undo_handle: 'FastUndoHandle') -> 'GAME_OVER':
        # Rule and Temp
        for effect in rule_effects:

            if EventManager.FilterAvailableEffects(message, [effect], None, self.world, undo_handle):
                self.ProcessEffect(effect, message, priority)

            if self.world.is_game_over:
                break

        return self.world.is_game_over

    def ProcessPayingEffect(self, message: 'Message.WhenPlayerPayingResources', resources_effect: 'Effect', priority: 'TimingPriority') -> 'GAME_OVER':
        # Resources
        resources_effects = EventManager.FilterAvailableEffects(message, [resources_effect], message.to_player, self.world, None)
        assert len(resources_effects) == 1
        self.ProcessEffect(resources_effects[0], message, priority)

        return self.world.is_game_over

    def ProcessOptionalTimingPriority(
        self,
        messages: Sequence['Message2'],
        priority: 'TimingPriority',
        processed: Set[Tuple[int, int]],
    ) -> 'GAME_OVER':
        """Resolve one v1.8 optional priority in player order."""
        from game.message import Message

        players = [
            player
            for player in self.world.const_players
            if getattr(player, "is_eliminated", False) is not True
        ]
        if not players:
            return self.world.is_game_over

        first_player = self.world.GetFirstPlayer()
        if first_player in players:
            first_index = players.index(first_player)
            players = players[first_index:] + players[:first_index]

        player_index = 0
        consecutive_passes = 0
        while not self.world.is_game_over:
            active_players = [
                player
                for player in players
                if getattr(player, "is_eliminated", False) is not True
            ]
            if not active_players or consecutive_passes >= len(active_players):
                break

            player = players[player_index]
            player_index = (player_index + 1) % len(players)
            if player not in active_players:
                continue

            candidates = self._BuildTimingCandidates(
                messages,
                "Optional",
                priority,
                player,
                processed,
            )
            if not candidates:
                consecutive_passes += 1
                continue

            Message.PlayerOnEvent_Text(player, candidates[0].message)
            candidate, retry_choice = self._ChooseTimingCandidate(
                player,
                candidates,
                priority,
                forced=False,
                select_only=False,
            )
            if retry_choice:
                player_index = (player_index - 1) % len(players)
                continue
            if candidate == None:
                consecutive_passes += 1
            elif player.ResolveEffect(candidate.effect, candidate.message):
                processed.add(candidate.key)
                consecutive_passes = 0
            else:
                from engine.log import Log

                Log.Warn(
                    "MESSAGE",
                    f"Timing response failed after selection: "
                    f"{candidate.GetDiagnosticText()}",
                )
                consecutive_passes += 1

        return self.world.is_game_over

    def ProcessOptionalEffect(self, message: 'Message2', optional_effects: List['Effect'], local_optional_effects: List['Effect'], priority: 'TimingPriority') -> 'GAME_OVER':
        from game.message import Message
        from game.effect.effect_failure import EffectFailure
        from game.ability import TimingPriority
        # from game.object.object_manager import ObjectManager

        if bool(self.world.rule.v18_timing) and priority in (
            TimingPriority.Interrupt,
            TimingPriority.Response,
        ):
            return self.ProcessOptionalTimingPriority(
                [message],
                priority,
                set(),
            )

        is_play_turn = type(message) == Message.WhenPlayerInTurn

        players = self.world.const_players[:]

        def process_player(player: 'Player'):
            processed_effects: List['Effect'] = []
            nonlocal optional_effects

            while True:
                if is_play_turn:
                    self.new_effect_created = False
                if self.world.is_game_over:
                    break

                # Clean all resource effect
                # ObjectManager.EmptyPayingEffect()
                # ObjectManager.ResetPayingEffect()

                def fast_undo():
                    controller_manager = self.world.controller_manager
                    if controller_manager.undo.DoNotCheckFastUndo():
                        Log.DebugSilent("MESSAGE", f"{'-'*30}")
                        Log.DebugSilent("MESSAGE", f"{len(self.world.object_manager.message_dict)=}")
                        Log.DebugSilent("MESSAGE", f"{'-'*30}")
                        return optional_effects

                    step_id = controller_manager.replay.current_step_id

                    # We only check "Optional" when not skipping
                    from game.scene.replay import CommandDescriptor
                    is_puzzle = message.world.scene.is_puzzle
                    found_effects: List['Effect'] = optional_effects[:]
                    operation, read_ok = controller_manager.replay.GetReplayOperation(is_puzzle, check_crc=False)
                    replay_id = None
                    fast_undo_result = ""
                    if read_ok:
                        if operation:
                            from colorama import Fore
                            replay_id = f"{Fore.BLUE}{operation.effect.id}{Fore.RESET}"
                            if operation.effect.id.startswith(":"):
                                fast_undo_result = f"Skip debug command {replay_id}"
                            elif operation.effect.id != '':
                                effect_ids = CommandDescriptor.FindNewEffectIdInternal(operation.effect.id, optional_effects)
                                if effect_ids:
                                    found_effects.clear()
                                    for effect_id in effect_ids:
                                        for effect in optional_effects:
                                            if effect.object_id == effect_id:
                                                found_effects.append(effect)
                                                break
                                    assert found_effects
                                    fast_undo_result = f"{replay_id}, {len(optional_effects)} -> {len(found_effects)}"
                                else:
                                    fast_undo_result = f"{replay_id}, {len(optional_effects)} ->"
                            else:
                                # In this case, we have to check all optional effect
                                # to find is user cancel this effect in this event or others
                                fast_undo_result = f"{replay_id}, {len(optional_effects)} -> Input Cancel"
                    Log.DebugSilent("FAST_UNDO", f'{step_id}, {fast_undo_result}')
                    return found_effects

                if not FILE_BASED_FAST_UNDO.value:
                    filtered_effects = EventManager.FilterAvailableEffects(message, optional_effects, player, self.world, None)
                else:
                    fast_undo_effects = fast_undo()
                    if not fast_undo_effects:
                        return
                    filtered_effects = EventManager.FilterAvailableEffects(message, fast_undo_effects, player, self.world, None)

                for effect in filtered_effects[:]:
                    if effect in processed_effects:
                        filtered_effects.remove(effect)
                        effect.failures.Set(player, EffectFailure.AlreadyProcessed)

                if filtered_effects == []:
                    break
                else:
                    from game.message import Message
                    Message.PlayerOnEvent_Text(player, message)

                    filtered_effects = sorted(filtered_effects, key=lambda e: e.object_id)

                    forced = "Forced_Action" if any(effect.ability.flags.is_forced_action for effect in filtered_effects) else False
                    effect, is_cheating = player.ChoiceAndSpellEffect(filtered_effects, message, priority, forced)

                    if not is_cheating and not effect:
                        break
                    if is_cheating or self.new_effect_created:
                        if is_play_turn:
                            self.new_effect_created = False

                        if type(message) in self.effects["Optional"] and \
                            priority in self.effects["Optional"][type(message)]:

                            optional_effects = [
                                x for x in self.effects["Optional"][type(message)][priority]
                                if self.GetEffectivePriority(x) == priority
                            ] + local_optional_effects
                            optional_effects = Types.RemoveDuplicates(optional_effects)

                        if is_cheating:
                            assert effect == None, f"{effect=}"

                    if not is_play_turn and effect:
                        # Fix for "05005" and "05001a"
                        if not Event.IsType(effect.this):
                            processed_effects.append(effect)
                        pass

        JobManager.Simultaneous(process_player, players)

        return self.world.is_game_over

    def ProcessForcedEffect(self, message: 'Message2', forced_effects: List['Effect'], priority: 'TimingPriority', undo_handle: 'FastUndoHandle') -> 'GAME_OVER':
        from game.message.sender.sender import CanBeInstead
        from game.effect.rule import Ties
        from game.ability.ability import TimingPriority
        from game.message import Message

        # The order of `forced_effects` is by the id, which means when this card be created
        # And we didn't make them same to the hand card order

        # if isinstance(message, Send.CheckPlayerCanPayCost):
        #     pass

        # Forced
        while True:
            forced_effects = EventManager.FilterAvailableEffects(message, forced_effects, None, self.world, undo_handle)

            if forced_effects == []:
                break
            if self.world.is_game_over:
                break
            if isinstance(message, CanBeInstead) and message.is_be_instead:
                break

            def check_is_resources(forced_effect: 'Effect'):
                assert not forced_effect.ability.flags.is_resource
                assert not forced_effect.ability.flags.is_discard_pay
                return forced_effect.ability.flags.is_check_pay

            first_effect = forced_effects[0]

            if self.GetEffectivePriority(first_effect) != TimingPriority.Status and \
                not isinstance(message, Message.WhenGameBeginSetup) and \
                not check_is_resources(first_effect) and \
                not first_effect.ability.flags.is_delay_ability:
                first_player = self.world.GetFirstPlayer()
                if bool(self.world.rule.v18_timing) and len(forced_effects) > 1:
                    from game.event.timing import TriggeredCandidate

                    candidates: List[TriggeredCandidate] = []
                    for effect in forced_effects:
                        descriptor = effect.Render(None, first_player.player_id)
                        candidate = TriggeredCandidate(
                            effect,
                            message,
                            0,
                            None,
                            descriptor,
                            self._GetTimingAbilitySlot(effect),
                        )
                        descriptor.choice_id = candidate.choice_id
                        candidates.append(candidate)
                    self._FinalizeTimingCandidateLabels(candidates)
                    candidate = self._GetAutomaticTimingCandidate(candidates)
                    if candidate == None:
                        candidate, retry_choice = self._ChooseTimingCandidate(
                            first_player,
                            candidates,
                            priority,
                            forced=True,
                            select_only=True,
                        )
                        if retry_choice:
                            continue
                        if candidate == None:
                            break
                    effect = candidate.effect
                else:
                    faces = [x.this for x in forced_effects if not x.ability.flags.is_delay_ability]
                    is_on_the_same_card = all(x.card == faces[0].card for x in faces)
                    if is_on_the_same_card:
                        face = faces[0]
                    else:
                        face = first_player.AskChooseFace(faces, Ties("Forced abilities would initiate at the same moment", world=self.world), forced=True)
                        if face == None:
                            face = faces[0]
                    assert face
                    effect = forced_effects[faces.index(face)]
            else:
                effect = first_effect

            forced_effects.remove(effect)

            # Clean
            effect.context.targets_internal = []

            if effect.IsPlayerInitiator() and len(effect.context.all_legal_targets) > 0:
                initiator = effect.GetInitiator()
                _, is_cheating = initiator.ChoiceAndSpellEffect([effect], message, priority, True)
                if is_cheating:
                    forced_effects.append(effect)
            else:
                self.ProcessEffect(effect, message, priority)


        if self.world.is_game_over:
            return True
        if isinstance(message, CanBeInstead) and message.is_be_instead:
            return True
        return False

    ################################################################################
    #
    @staticmethod
    def SimpleCheckEffects(message: 'Message2', effects: Sequence['Effect'], asked_player: 'Player|None', world: 'World', undo_handle: 'FastUndoHandle') -> List['Effect']:
        from game.card.face.base import Unit2
        from game.card.face.base import Scheme2
        from game.card.face.card_type import Upgrade
        from game.card.face.card_type import Minion
        from game.card.face.card_type import Support
        from game.card.face.card_type import Attachment
        from game.card.face.card_type import Environment
        from game.card.face.card_type import Resource
        from game.card.face.card_type import Event
        from game.card.face.card_type import Obligation
        from game.effect.effect import EffectFailure
        from game.message import Message
        from game.message import TriggerPlayerMessage

        if CACHE_BASED_FAST_UNDO.value and undo_handle:
            check_effects_list = undo_handle.GetAvailableEffects(effects)
            step_id = undo_handle.step_id
            if check_effects_list != None:
                if check_effects_list and \
                    len(effects) != len(check_effects_list):
                    Log.DebugSilent("UNDO_HANDLE", f"{step_id} {message}: {len(effects)} -> {len(check_effects_list)}")
                effects = check_effects_list

        effects_list: List['Effect'] = []
        for effect in effects:
            if effect.is_unregister:
                continue

            assert isinstance(message, effect.ability.when), f"{message=} {effect.ability.when=}"

            if effect.this.is_treat_as_if_blank and \
                not effect.ability.ignore.treat_as_if_blank and \
                not isinstance(message, Message.WhenCardTreatAsIfBlank):
                effect.failures.Set(asked_player, EffectFailure.TreatAsBlank)
                continue
            if effect.this.card.area.flags.is_removed and \
                not effect.ability.ignore.be_removed and \
                type(message) is not Message.WhenPlayerLikeInTurn:
                # not effect.this.IsName("rule") and \
                effect.failures.Set(asked_player, EffectFailure.IsRemoved)
                continue
            # if effect.this.card.IsAsOtherCard():
            #     effect.AddFailureReason(asked_player, 'as other card')
            #     continue

            def check_initiator() -> Tuple[bool, str]:
                this = effect.this
                current_player = world.GetCurrentPlayer()
                check_player = None

                if effect.ability.flags.is_resource or effect.ability.flags.is_discard_pay:
                    check_player = message.CastTo(Message.WhenPlayerPayingResources).GetToPlayer()
                elif effect.ability.any_player_can_trigger_this_when:
                    if isinstance(message, TriggerPlayerMessage):
                        check_player = message.to_player
                    else:
                        check_player = current_player
                elif isinstance(message, Message.WhenPlayerPayingResources):
                    if Event.IsType(message.for_effect.this) and message.for_effect.this.alliance:
                        check_player = message.to_player
                    else:
                        # Fix "50014"
                        check_player = message.to_player # this.GetControlByOrOwner()
                elif isinstance(message, Message.WhenCardBeSpendAsResource):
                    # Fix "28019"
                    check_player = message.to_player
                elif effect.ability.is_choose:
                    return True, ""
                elif Obligation.IsType(this):
                    if this.card.area.flags.is_obligations_area:
                        check_player = this.GetGaveToPlayer()
                    else:
                        check_player = current_player
                elif Attachment.IsType(this) and \
                    not Identity.IsType(this.bind_face):
                    # Fix "21179"
                    check_player = current_player
                elif Minion.IsType(this):
                    # Fix "27131"
                    check_player = current_player
                elif Scheme2.IsType(this):
                    # Fix "27081"
                    check_player = current_player
                elif Environment.IsType(this):
                    # Fix "27077a"
                    check_player = current_player
                elif effect.ability.is_play and \
                    this.card.can_state.is_like_in_hand is True and \
                    asked_player is not None:
                    # Effects such as Echo's Photographic Reflexes can let a
                    # player play a card they do not own as though it were in
                    # their hand. In that explicit temporary state, the
                    # player evaluating the play is its initiator; using the
                    # tucked card's owner here rejects the play before its
                    # normal costs and targets can be checked.
                    check_player = asked_player
                elif effect.ability.flags.is_play_turn_option or \
                    effect.ability.flags.is_basic_power or \
                    effect.ability.flags.is_interrupt or \
                    effect.ability.flags.is_response or \
                    effect.ability.flags.is_resource or \
                    effect.ability.flags.is_action or \
                    effect.ability.flags.is_ask or \
                    effect.ability.is_play or \
                    effect.ability.flags.is_discard_pay:
                    if this.IsInPlay():
                        check_player = this.GetControlByOrOwner()
                    else:
                        check_player = this.card.area.GetOwner()
                elif Event.IsType(this):
                    assert False, f"{effect}"
                elif Resource.IsType(this):
                    assert False, f"{effect}"
                elif Support.IsType(this):
                    assert False, f"{effect}"
                elif Upgrade.IsType(this):
                    assert False, f"{effect}"
                    # return this.GetController() == asked_player
                    # Fix Spider-Tracer "01007"
                    # if isinstance(this.GetController(), Scenario):
                    #     # TODO: bug, if a card become an "Ultron Facedown DRONE",
                    #     # it's "this.card.area.owner" will not update
                    #     effect.initiator = this.GetOwner()
                    # else:
                    #     effect.initiator = this.GetController()
                elif Unit2.IsType(this):
                    assert False, f"{effect}"
                    # Fix "20016"
                    # return current_player == asked_player


                elif this.card.area.flags.is_processing:
                    assert False, f"{effect}"
                    # return True
                    # effect.initiator = this.GetOwner()
                else:
                    if asked_player == None:
                        return True, ""
                    else:
                        assert False, f"{this=}"
                    # return this.GetController() == asked_player
                    # this_owner = this.GetOwner()
                    # if isinstance(this_owner, Scenario):
                    #     effect.initiator = this_owner
                    # else:
                    #     effect.initiator = this.GetController()

                return check_player == asked_player, f"{check_player}"

            # Need initiator
            # if not effect.HasCostTargets():
            #     effect.failure_reason = "no cost target (simple check)"
            #     continue

            if not effect.is_forced:
                ok, error = check_initiator()
                if not ok:
                    # if effect.this.card.object_id == 128:
                    #     check_initiator()
                    #     pass
                    effect.failures.SetText(asked_player, f"initiator error, check: {error}, ask: {asked_player}")
                    continue

            effects_list.append(effect)

        return effects_list

    @staticmethod
    # Will also setup `all_legal_targets`
    def FilterAvailableEffects(message: 'Message2', effects: Sequence['Effect'], asked_player: 'Player|None', world: 'World', undo_handle: 'FastUndoHandle') -> List['Effect']:
        from game.message.sender.sender import CanBeInstead
        from game.message import Message
        from game.player import Player

        if isinstance(message, CanBeInstead) and message.is_be_instead:
            return []

        checked_effects = EventManager.SimpleCheckEffects(message, effects, asked_player, world, undo_handle)

        for effect in checked_effects:
            effect.this.card.ui.unavailable.Reset()

        def check():

            effects_list: List['Effect'] = []
            for effect in checked_effects:
                # init initiator
                effect.context.bind_message = message
                # if effect.ability.any_player_can_do_this and asked_player:
                #     effect.initiator = asked_player
                if asked_player != None:
                    effect.context.initiator = asked_player
                elif effect.this.card.area.flags.is_obligations_area:
                    # Obligations remain encounter-owned after they are given to
                    # a player. Their forced abilities still belong to the
                    # player whose obligation area contains the card.
                    effect.context.initiator = effect.this.GetGaveToPlayer()
                else:
                    effect.context.initiator = effect.this.GetControlByOrOwner()

                effect.context.ask_player = asked_player
                effect.context.ResetBeforeCondition()
                if asked_player == None and isinstance(effect.initiator, Player):
                    effect.context.ask_player = effect.initiator
                else:
                    effect.context.ask_player = asked_player
                if not effect.checker.CheckCondition(message, effect.context.ask_player):
                    if effect.ability.when is Message.WhenPlayerChooseAbility:
                        if effect.ability.selectors and \
                            effect.ability.selectors[0]:
                            effect.ability.selectors[0].IfSelectTargetFailure(effect)
                    continue

                effects_list.append(effect)
            return effects_list

        effects_list = check()

        if CACHE_BASED_FAST_UNDO.value and undo_handle:
            controller_manager = message.world.controller_manager
            controller_manager.undo.PushFastUndo(message, effects_list)
        return effects_list

    ################################################################################
    # Rules Reference v1.8 grouped timing windows
    def _FindLocalTimingEffects(
        self,
        message: 'Message2',
        category: 'EventManager.CATEGORY',
        priority: 'TimingPriority',
    ) -> List['Effect']:
        local_effects: List['Effect'] = []
        for face in message.related_faces:
            for effect in face.effect.local_effects:
                if not isinstance(message, effect.ability.when):
                    continue
                # Damage responses controlled by the character that took the
                # damage cease to be active once that character has left play.
                # The message itself remains in the occurrence so responses on
                # other cards can still observe the defeated target.
                if isinstance(message, Message.AfterUnitTookDamage) and \
                    effect.this is message.trigger and \
                    not effect.this.IsInPlay():
                    continue
                if self.GetEffectCategory(effect, type(message)) != category:
                    continue
                if self.GetEffectivePriority(effect) != priority:
                    continue
                local_effects.append(effect)
        return local_effects

    @staticmethod
    def _GetTimingAbilitySlot(effect: 'Effect') -> int:
        """Return the deterministic position of an ability on its face."""
        try:
            return effect.this.effect.GetAll().index(effect)
        except (AttributeError, ValueError):
            # Registered effects should be face-owned. Keep an internal
            # fallback for temporary test/rule effects instead of making
            # timing-choice rendering fatal.
            return 0

    @staticmethod
    def _FinalizeTimingCandidateLabels(
        candidates: Sequence['TriggeredCandidate'],
    ) -> None:
        base_names: Dict[str, int] = {}
        for candidate in candidates:
            candidate.descriptor.name = candidate.GetDisplayName()
            base_names[candidate.descriptor.name] = (
                base_names.get(candidate.descriptor.name, 0) + 1
            )

        used_names: Dict[str, int] = {}
        for candidate in candidates:
            base_name = candidate.descriptor.name
            if base_names[base_name] > 1:
                base_name += f"_-_{candidate.GetTriggerLabel()}"
            occurrence = used_names.get(base_name, 0) + 1
            used_names[base_name] = occurrence
            if occurrence > 1:
                base_name += f"_(option_{occurrence})"
            candidate.descriptor.name = base_name

    def _BuildTimingCandidates(
        self,
        messages: Sequence['Message2'],
        category: 'EventManager.CATEGORY',
        priority: 'TimingPriority',
        asked_player: 'Player|None',
        processed: Set[Tuple[int, int]],
    ) -> List['TriggeredCandidate']:
        from game.event.timing import TriggeredCandidate

        candidates: List[TriggeredCandidate] = []
        bind_player = asked_player or self.world.GetFirstPlayer()
        for message_index, message in enumerate(messages):
            effects = self.FindTimingEffects(category, type(message), priority)[:]
            effects += self._FindLocalTimingEffects(message, category, priority)
            effects = sorted(Types.RemoveDuplicates(effects), key=lambda x: x.object_id)
            for effect in effects:
                key = (effect.object_id, message.object_id)
                if key in processed:
                    continue
                available = EventManager.FilterAvailableEffects(
                    message,
                    [effect],
                    asked_player,
                    self.world,
                    None,
                )
                if not available:
                    continue
                descriptor = effect.Render(None, bind_player.player_id)
                candidate = TriggeredCandidate(
                    effect,
                    message,
                    message_index,
                    asked_player,
                    descriptor,
                    self._GetTimingAbilitySlot(effect),
                )
                descriptor.choice_id = candidate.choice_id
                candidates.append(candidate)

        self._FinalizeTimingCandidateLabels(candidates)
        return candidates

    def _ChooseTimingCandidate(
        self,
        player: 'Player',
        candidates: Sequence['TriggeredCandidate'],
        priority: 'TimingPriority',
        *,
        forced: bool,
        select_only: bool,
    ) -> Tuple['TriggeredCandidate|None', bool]:
        from engine.controller.controller import ChoiceOneOverride
        from game.event.timing import TriggeredCandidate

        descriptors = [copy(candidate.descriptor) for candidate in candidates]
        if select_only:
            for descriptor in descriptors:
                descriptor.all_legal_targets = []
                descriptor.target_num_range = [0, 0]
                descriptor.target_payment = {}
                # These candidates already passed FilterAvailableEffects.
                # The first player is only choosing their resolution order,
                # and may differ from the player who controls each effect.
                # Do not let that player's unchecked "no process" sentinel
                # disable every button in the ordering prompt.
                descriptor.failure_reason = ""

        override = ChoiceOneOverride(
            descriptors=descriptors,
            replay_texts=[candidate.GetReplayText() for candidate in candidates],
            prepare=lambda index: candidates[index].TryPrepare(),
            convert_replay_id=lambda replay_text: TriggeredCandidate.ConvertReplayId(
                replay_text,
                candidates,
            ),
            select_only=select_only,
        )
        effects = [candidate.effect for candidate in candidates]
        selected, is_cheating = player.GetController().ChoiceOne(
            effects,
            None,
            candidates[0].message,
            priority,
            forced,
            override,
        )
        if is_cheating:
            return None, True
        if selected == None or override.selected_index == None:
            return None, False
        return candidates[override.selected_index], False

    def _GetAutomaticTimingCandidate(
        self,
        candidates: Sequence['TriggeredCandidate'],
    ) -> 'TriggeredCandidate|None':
        from game.event.timing import TriggeredCandidate

        automatic = next((candidate for candidate in candidates
                          if getattr(candidate.effect.ability, "resolve_automatically", False) is True), None)
        if automatic == None:
            return None

        # Older saves contain an ordering choice for this window. Let the
        # normal replay reader consume it so subsequent inputs stay aligned.
        operation, _ = self.world.controller_manager.replay.GetReplayOperation(
            self.world.scene.is_puzzle, check_crc=False,
        )
        if operation and TriggeredCandidate.ConvertReplayId(operation.effect.id, candidates) != None:
            return None
        return automatic

    def BroadcastTimingWindow(self, messages: Sequence['Message2']) -> None:
        """Resolve simultaneous conditions in one v1.8 timing window."""
        from game.ability import TimingPriority
        from game.card.face.card_type import Event
        from game.event.timing import TriggeredCandidate
        from game.message import Message
        from game.player import Player

        messages = [message for message in messages if not self.world.is_game_over]
        if not messages:
            return
        if not bool(self.world.rule.v18_timing):
            for message in messages:
                self.BroadcastMessage(message)
            return

        processed: Set[Tuple[int, int]] = set()
        for priority in list(TimingPriority):
            for category in ("Statistics", "Rule"):
                while True:
                    candidates = self._BuildTimingCandidates(
                        messages,
                        category,
                        priority,
                        None,
                        processed,
                    )
                    if not candidates or self.world.is_game_over:
                        break
                    candidate = candidates[0]
                    effect = candidate.TryPrepare()
                    if effect == None:
                        from engine.log import Log

                        Log.Warn(
                            "MESSAGE",
                            f"Skipped stale timing rule candidate: {candidate.GetDiagnosticText()}",
                        )
                        processed.add(candidate.key)
                        continue
                    if self.ProcessEffect(effect, candidate.message, priority):
                        processed.add(candidate.key)
                    else:
                        processed.add(candidate.key)

            while not self.world.is_game_over:
                candidates = self._BuildTimingCandidates(
                    messages,
                    "Forced",
                    priority,
                    None,
                    processed,
                )
                if not candidates:
                    break
                if len(candidates) == 1:
                    candidate = candidates[0]
                    effect = candidate.TryPrepare()
                    if effect == None:
                        continue
                else:
                    candidate = self._GetAutomaticTimingCandidate(candidates)
                    if candidate == None:
                        candidate, retry_choice = self._ChooseTimingCandidate(
                            self.world.GetFirstPlayer(),
                            candidates,
                            priority,
                            forced=True,
                            select_only=True,
                        )
                        if retry_choice:
                            continue
                        if candidate == None:
                            return
                    effect = candidate.TryPrepare()
                    if effect == None:
                        from engine.log import Log

                        Log.Warn(
                            "MESSAGE",
                            f"Selected timing candidate became stale: "
                            f"{candidate.GetDiagnosticText()}",
                        )
                        continue
                resolved = False
                if effect.IsPlayerInitiator() and effect.context.all_legal_targets:
                    initiator = effect.GetInitiator()
                    assert isinstance(initiator, Player)
                    selected, is_cheating = initiator.ChoiceAndSpellEffect(
                        [effect],
                        candidate.message,
                        priority,
                        forced=True,
                    )
                    if is_cheating:
                        continue
                    resolved = selected != None
                else:
                    resolved = self.ProcessEffect(
                        effect,
                        candidate.message,
                        priority,
                    )
                if not resolved:
                    return
                processed.add(candidate.key)

            # An ability resolution resets consecutive passes, so an earlier
            # player may reconsider after a later response changes the state.
            if self.ProcessOptionalTimingPriority(messages, priority, processed):
                return

        if self.stack_message:
            self.BroadcastStackMessage()

    ################################################################################
    #
    def StackMessage(self, message: 'CardStateUpdatedMessage'):
        self.stack_message.append(message)

    def BroadcastStackMessage(self):
        if self.stack_message:
            # process_faces: List['CardFace'] = []
            messages = self.stack_message[:]
            self.stack_message.clear()

            for message in messages:
                # if not isinstance(message, Message.WhenCardKeywordUpdated) or \
                #     message.updated_face not in process_faces:
                self.BroadcastMessage(message)
                # process_faces.append(message.updated_face)

    def BroadcastMessage(self, message: 'Message2'):
        from game.ability.ability import TimingPriority
        from game.message import Message
        # from game.message import Message, TriggerMessage, AttackerNoneMessage, TargetsMessage, DefenderNoneMessage
        from game.message.message_type import NoSendResolve

        if self.world.is_game_over:
            from game.message.sender.sender import CanBeInstead
            if isinstance(message, CanBeInstead):
                message.SilentInstead()
            return

        # Under v1.8, Surge and Incite are When Revealed abilities. Another
        # When Revealed ability can make one of those keyword candidates legal
        # while this same message is resolving (for example, Assault or
        # Gang-Up granting Surge in alter-ego form). Use the recalculating
        # timing window so newly legal mandatory candidates are discovered
        # before reveal resolution continues.
        if bool(self.world.rule.v18_timing) and isinstance(
            message,
            Message.WhenCardRevealed,
        ):
            self.BroadcastTimingWindow([message])
            return

        # self.last_message = message

        is_playing_res = isinstance(message, Message.WhenPlayerPayingResources)

        def find_local_effects():
            if isinstance(message, Message.WhenPlayerPayingResources):
                return [message.by_effect]

            local_effects: List['Effect'] = []
            for face in message.related_faces:
                for check_effect in face.effect.local_effects:
                    if isinstance(message, check_effect.ability.when):
                        local_effects.append(check_effect)
            return local_effects

        local_effects = find_local_effects()
        has_registered_event = self.HasRegisteredEvent(type(message))

        if not has_registered_event and not local_effects:
            return

        if CACHE_BASED_FAST_UNDO.value:
            controller_manager = message.world.controller_manager
            undo_handle = controller_manager.undo.GetFastUndoHandle(message)
            if undo_handle:
                if not undo_handle.card_ids:
                    return
                step_id = undo_handle.step_id
                Log.DebugSilent("UNDO_HANDLE", f"{step_id} {message}: {undo_handle.card_ids}")
        else:
            undo_handle = None

        if isinstance(message, NoSendResolve):
            priorities: List[TimingPriority] = [TimingPriority.Rule, TimingPriority.Constant, TimingPriority.ForcedInterrupt]

            if has_registered_event or local_effects:
                check_in_play_and_hand = False
                check_face_up_or_hand = True
                check_only_in_play = True
                checked = False

                catogories: List['EventManager.CATEGORY'] = ["Rule", "Forced"]

                if has_registered_event:
                    if isinstance(message, (
                        Message.CheckPlayerCanPayCost)):
                        check_in_play_and_hand = True
                        checked = True
                        priorities = [TimingPriority.Constant]
                        catogories = ["Forced"]
                    elif isinstance(message, (
                        Message.CheckIfAttackMessageHasKeyword)):
                        checked = True
                        priorities = [TimingPriority.Constant]
                        catogories = ["Rule"]
                    elif isinstance(message, (
                        Message.WhenRecalculateAttackDamage)):
                        checked = True
                        priorities = [TimingPriority.Constant, TimingPriority.ForcedInterrupt]
                        catogories = ["Rule", "Forced"]
                    # elif isinstance(message, (
                    #     Message.CheckEffectGeneratedResources)):
                    #     check_only_in_play_and_hand = True
                    #     priorities = [TimingPriority.Constant]
                    #     catogories = ["Rule", "Forced"]

                    # elif isinstance(message, (
                    #     Message.CheckEffectCondition)):
                    #     priorities = [TimingPriority.Rule, TimingPriority.Constant]
                    #     catogories = ["Rule", "Forced"]
                    elif isinstance(message, (
                        Message.WhenCalculateEffectCost)):
                        checked = True
                        priorities = [TimingPriority.Rule, TimingPriority.Constant]
                        catogories = ["Rule"]
                    elif isinstance(message, (
                        Message.CheckIfAllyCountLimit)):
                        checked = True
                        priorities = [TimingPriority.Constant]
                        catogories = ["Rule"]
                    elif isinstance(message, (
                        Message.CheckIfFaceIsLikeInHand)):
                        checked = True
                        priorities = [TimingPriority.Constant]
                        catogories = ["Rule"]
                    elif isinstance(message, (
                        Message.CheckIfUnitCanBeAttackBy,
                        Message.CheckIfSchemeCanBeThwartBy,
                        Message.CheckIfEffectIsIgnoreKeyWord)):
                        checked = True
                        priorities = [TimingPriority.Constant]
                        catogories = ["Rule"]
                    # else:
                    #     priorities = [TimingPriority.Rule, TimingPriority.Constant, TimingPriority.ForcedInterrupt]
                    #     catogories = ["Rule", "Forced"]

                for priority in priorities:

                    if has_registered_event:
                        for category in catogories:

                            found_global_effects = self.FindTimingEffects(category, type(message), priority)

                            def check_is_in_hand(face: 'CardFace'):
                                if isinstance(message, Message.CheckIfFaceIsLikeInHand):
                                    return face.card.IsInHand()
                                return face.IsLikeInHand()

                            if found_global_effects:
                                if check_in_play_and_hand:
                                    found_global_effects = [x for x in found_global_effects if x.this.IsInPlay() or check_is_in_hand(x.this)]
                                elif check_face_up_or_hand:
                                    found_global_effects = [x for x in found_global_effects if x.this.IsFaceUp() or check_is_in_hand(x.this)]
                                elif check_only_in_play:
                                    found_global_effects = [x for x in found_global_effects if x.this.IsInPlay(is_same_face=True)]

                                if found_global_effects and not checked:
                                    name = message.name
                                    text = f"{priority}, {category}"
                                    self.debug_log.AddLog(name, text)

                                self.ProcessRuleEffect(message, found_global_effects, priority, undo_handle)

                    if local_effects:
                        found_local_effects: List['Effect'] = []

                        for check_effect in local_effects:
                            if self.GetEffectivePriority(check_effect) == priority:
                                found_local_effects.append(check_effect)

                        if found_local_effects:
                            self.ProcessRuleEffect(message, found_local_effects, priority, undo_handle)

            return

        if local_effects and has_registered_event:
            self.debug_log_both.AddLog(message.name, f"{has_registered_event} / {len(local_effects)}")
        if local_effects and not has_registered_event:
            self.debug_log_only_local.AddLog(message.name, f"{len(local_effects)}")
        if not local_effects and has_registered_event:
            self.debug_log_only_global.AddLog(message.name, f"{has_registered_event}")

        for priority in list(TimingPriority):

            check_effects: Dict['EventManager.CATEGORY', List[Effect]] = {}

            local_effect_priority_statistics: List['Effect'] = []
            local_effect_priority_rule: List['Effect'] = []
            local_effect_priority_paying: List['Effect'] = []
            local_effect_priority_forced: List['Effect'] = []
            local_effect_priority_optional: List['Effect'] = []

            size = 0
            if has_registered_event:
                for category in EventManager.CATEGORY_LIST:
                    found_effects = self.FindTimingEffects(category, type(message), priority)
                    # check_effects[catogory] = get_only_in_play_effects(found_effects)
                    check_effects[category] = found_effects[:]
                    size += len(check_effects[category])
            if local_effects:
                for check_effect in local_effects:
                    if self.GetEffectivePriority(check_effect) == priority:
                        category = self.GetEffectCategory(
                            check_effect,
                            type(message),
                        )
                        if category == "Statistics":
                            local_effect_priority_statistics.append(check_effect)
                        elif category == "Rule":
                            local_effect_priority_rule.append(check_effect)
                        elif category == "Paying":
                            local_effect_priority_paying.append(check_effect)
                        elif category == "Forced":
                            local_effect_priority_forced.append(check_effect)
                        else:
                            assert category == "Optional"
                            local_effect_priority_optional.append(check_effect)
                        size += 1

            if size == 0:
                continue

            if "Statistics" in check_effects and check_effects["Statistics"]:
                if self.ProcessRuleEffect(message, check_effects["Statistics"], priority, undo_handle):
                    return
            if local_effect_priority_statistics:
                if self.ProcessRuleEffect(
                    message,
                    local_effect_priority_statistics,
                    priority,
                    undo_handle,
                ):
                    return

            if "Rule" in check_effects and check_effects["Rule"]:
                if self.ProcessRuleEffect(message, check_effects["Rule"], priority, undo_handle):
                    return
            if local_effect_priority_rule:
                if self.ProcessRuleEffect(
                    message,
                    local_effect_priority_rule,
                    priority,
                    undo_handle,
                ):
                    return

            if local_effect_priority_paying:
                assert is_playing_res
                if self.ProcessPayingEffect(message, message.by_effect, priority):
                    return

            if local_effect_priority_forced and not is_playing_res or \
                "Forced" in check_effects and check_effects["Forced"]:
                forced_effects = local_effect_priority_forced
                if "Forced" in check_effects:
                    forced_effects += check_effects["Forced"]
                if forced_effects:
                    if self.ProcessForcedEffect(message, forced_effects, priority, undo_handle):
                        return

            if  local_effect_priority_optional or \
                "Optional" in check_effects and check_effects["Optional"]:
                optional_effects = local_effect_priority_optional
                if "Optional" in check_effects:
                    optional_effects += check_effects["Optional"]

                if optional_effects:
                    if self.ProcessOptionalEffect(message, optional_effects, local_effect_priority_optional, priority):
                        return
            pass

        return

