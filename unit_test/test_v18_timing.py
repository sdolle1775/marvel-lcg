from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from engine import Engine  # noqa: F401 - establishes the project's import order
from engine.lib.version import Ver
from game.ability import AbilityType, TimingPriority
from game.card.face.attribute.can_status import CanStatus
from game.card.face.attribute.has_vulnerable import HasVulnerable
from game.event.manager import EventManager
from game.event.timing import TriggeredCandidate
from game.message import Message
from game.rule.gameplay import GetGamePlayRules
from game.scene.scene import Scene
from game.world.world_rule import WorldRule


class FakeEffect:

    def __init__(self, object_id, name, ability):
        self.object_id = object_id
        self.name = name
        self.ability = ability
        self.context = SimpleNamespace(bind_message=None)
        self.this = SimpleNamespace(
            card=SimpleNamespace(object_id=1000 + object_id),
            paper=SimpleNamespace(card_id="card"),
            name="Test Card",
        )

    def Render(self, by_effect, player_id):
        message_name = (
            self.context.bind_message.name
            if self.context.bind_message != None
            else "unbound"
        )
        return SimpleNamespace(
            id=self.object_id,
            name=f"{self.name}_{message_name}",
            choice_id="",
        )

    def GetReplayText(self):
        return (
            f"e{self.object_id} {self.name} "
            f"c{self.this.card.object_id} card"
        )

    def GetDisplayName(self, *, remove_space=False):
        return self.name.replace(" ", "_") if remove_space else self.name


class TestV18RuleAndMigration(unittest.TestCase):

    def test_v18_timing_defaults_on_and_is_independent_of_v16(self):
        rules = WorldRule()

        self.assertTrue(bool(rules.v18_timing))
        self.assertFalse(bool(rules.v16_all))

        rules.SetRule(["v16_all", "no_v18_timing"], False, 1)

        self.assertTrue(bool(rules.v16_all))
        self.assertTrue(bool(rules.v16_reveal))
        self.assertFalse(bool(rules.v18_timing))

    def test_old_saves_without_a_timing_token_migrate_to_legacy(self):
        scene = Scene(version="1.2.0.2")

        scene.UpdateVersion()

        self.assertIn("no_v18_timing", scene.rules)

    def test_explicit_old_save_selection_is_preserved(self):
        scene = Scene(version="1.2.0.2", rules=["v18_timing"])

        scene.UpdateVersion()

        self.assertIn("v18_timing", scene.rules)
        self.assertNotIn("no_v18_timing", scene.rules)

    def test_new_saves_use_the_default_without_a_legacy_token(self):
        scene = Scene(version="1.3.0")

        scene.UpdateVersion()

        self.assertNotIn("no_v18_timing", scene.rules)
        self.assertTrue(Ver(scene.version).IsV18Timing())

    def test_scene_ui_serializes_an_explicit_legacy_selection(self):
        scene_html = (
            Path(__file__).resolve().parents[1] / "public" / "scene.html"
        ).read_text(encoding="utf-8")

        self.assertIn('"v18_timing": "Use Rules Reference v1.8', scene_html)
        self.assertIn("new_game.rules.push('no_v18_timing')", scene_html)
        self.assertIn("'v18_timing'", scene_html)


class TestTimingOccurrence(unittest.TestCase):

    @staticmethod
    def make_world(*, v18=True):
        world = MagicMock()
        world.rule.v18_timing = v18
        world.is_game_over = False
        world.GetFirstPlayer.return_value = MagicMock(player_id=0)
        world.const_players = []
        return world

    def test_attack_and_basic_power_messages_are_collected_together(self):
        world = self.make_world()
        manager = EventManager(world)
        world.event_manager = manager
        manager.BroadcastTimingWindow = MagicMock()
        occurrence = manager.BeginTimingOccurrence()
        attack = object.__new__(Message.AfterUnitAttackUnit)
        basic = object.__new__(Message.AfterUnitUseBasicPower)

        self.assertTrue(manager.TryQueueTimingMessage(attack))
        self.assertTrue(manager.TryQueueTimingMessage(basic))
        manager.EndTimingOccurrence(occurrence)

        manager.BroadcastTimingWindow.assert_called_once_with([attack, basic])

    def test_every_core_after_condition_is_eligible_for_grouping(self):
        world = self.make_world()
        manager = EventManager(world)
        world.event_manager = manager
        occurrence = manager.BeginTimingOccurrence()
        grouped_types = (
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
        messages = [object.__new__(message_type) for message_type in grouped_types]

        for message in messages:
            self.assertTrue(manager.TryQueueTimingMessage(message), type(message))

        manager.BroadcastTimingWindow = MagicMock()
        manager.EndTimingOccurrence(occurrence)
        manager.BroadcastTimingWindow.assert_called_once_with(messages)

    def test_nested_occurrences_resolve_separately_from_the_parent(self):
        world = self.make_world()
        manager = EventManager(world)
        world.event_manager = manager
        manager.BroadcastTimingWindow = MagicMock()
        outer = manager.BeginTimingOccurrence()
        outer_message = object.__new__(Message.AfterUnitAttackUnit)
        inner = manager.BeginTimingOccurrence()
        inner_message = object.__new__(Message.AfterUnitTookDamage)

        self.assertTrue(manager.TryQueueTimingMessage(inner_message))
        manager.EndTimingOccurrence(inner)
        self.assertTrue(manager.TryQueueTimingMessage(outer_message))
        manager.EndTimingOccurrence(outer)

        self.assertEqual(
            manager.BroadcastTimingWindow.call_args_list,
            [
                unittest.mock.call([inner_message]),
                unittest.mock.call([outer_message]),
            ],
        )

    def test_child_response_occurrence_cannot_leak_into_suspended_parent(self):
        world = self.make_world()
        manager = EventManager(world)
        world.event_manager = manager
        outer = manager.BeginTimingOccurrence()
        outer_message = object.__new__(Message.AfterUnitAttackUnit)
        inner = manager.BeginTimingOccurrence()
        inner_message = object.__new__(Message.AfterUnitTookDamage)
        response_message = object.__new__(Message.AfterFaceDealDamage)
        windows = []

        def broadcast(messages):
            windows.append(messages)
            if messages == [inner_message]:
                self.assertEqual(manager.timing_occurrences, [])
                response_occurrence = manager.BeginTimingOccurrence()
                self.assertTrue(manager.TryQueueTimingMessage(response_message))
                manager.EndTimingOccurrence(response_occurrence)

        manager.BroadcastTimingWindow = MagicMock(side_effect=broadcast)
        self.assertTrue(manager.TryQueueTimingMessage(inner_message))
        manager.EndTimingOccurrence(inner)
        self.assertEqual(manager.timing_occurrences, [outer])
        self.assertTrue(manager.TryQueueTimingMessage(outer_message))
        manager.EndTimingOccurrence(outer)

        self.assertEqual(
            windows,
            [[inner_message], [response_message], [outer_message]],
        )
        self.assertEqual(manager.timing_occurrences, [])
        self.assertEqual(manager.resolving_timing_occurrences, [])

    def test_scoped_occurrence_aborts_and_restores_depth_on_exception(self):
        world = self.make_world()
        manager = EventManager(world)
        world.event_manager = manager
        occurrence = None

        with self.assertRaisesRegex(RuntimeError, "test failure"):
            with manager.TimingOccurrenceScope() as occurrence:
                self.assertIsNotNone(occurrence)
                raise RuntimeError("test failure")

        self.assertEqual(occurrence.state, "aborted")
        self.assertEqual(manager.timing_occurrences, [])

    def test_stale_or_out_of_order_close_aborts_without_asserting(self):
        world = self.make_world()
        manager = EventManager(world)
        world.event_manager = manager
        outer = manager.BeginTimingOccurrence()
        inner = manager.BeginTimingOccurrence()

        manager.EndTimingOccurrence(outer)

        self.assertEqual(outer.state, "aborted")
        self.assertEqual(inner.state, "aborted")
        self.assertEqual(manager.timing_occurrences, [])

        manager.EndTimingOccurrence(outer)
        self.assertEqual(outer.state, "aborted")

    def test_legacy_mode_does_not_open_a_grouped_occurrence(self):
        world = self.make_world(v18=False)
        manager = EventManager(world)

        self.assertIsNone(manager.BeginTimingOccurrence())
        self.assertEqual(manager.timing_occurrences, [])

    def test_legacy_mode_broadcasts_attack_then_basic_power_separately(self):
        world = self.make_world(v18=False)
        manager = EventManager(world)
        world.event_manager = manager
        manager.BroadcastMessage = MagicMock()
        attack = object.__new__(Message.AfterUnitAttackUnit)
        attack.world = world
        basic = object.__new__(Message.AfterUnitUseBasicPower)
        basic.world = world

        attack.Send()
        basic.Send()

        self.assertEqual(
            [call.args[0] for call in manager.BroadcastMessage.call_args_list],
            [attack, basic],
        )

    def test_immediate_message_broadcast_marks_nested_gameplay(self):
        world = self.make_world()
        manager = EventManager(world)
        world.event_manager = manager
        message = SimpleNamespace()
        attack = object.__new__(Message.WhenUnitWouldTakeDamage)
        attack.world = world

        def broadcast(sent_message):
            self.assertIs(sent_message, attack)
            self.assertEqual(manager.broadcasting_messages, [attack])

        manager.BroadcastMessage = MagicMock(side_effect=broadcast)

        attack.Send()

        self.assertEqual(manager.broadcasting_messages, [])

    def test_message_exception_aborts_only_occurrences_opened_by_that_message(self):
        world = self.make_world()
        manager = EventManager(world)
        world.event_manager = manager
        parent = manager.BeginTimingOccurrence()
        message = object.__new__(Message.WhenUnitWouldTakeDamage)
        message.world = world
        leaked = None

        def broadcast(sent_message):
            nonlocal leaked
            leaked = manager.BeginTimingOccurrence()
            raise RuntimeError("message failure")

        manager.BroadcastMessage = MagicMock(side_effect=broadcast)
        with patch("engine.log.Log.OnCrash", return_value="test error"):
            message.Send()

        self.assertEqual(leaked.state, "aborted")
        self.assertEqual(manager.timing_occurrences, [parent])
        self.assertEqual(manager.broadcasting_messages, [])
        world.render.ErrorOccurred.assert_called_once()
        manager.AbortTimingOccurrence(parent)

    def test_when_defeated_and_completed_move_to_forced_interrupt_only_in_v18(self):
        world = self.make_world()
        manager = EventManager(world)

        for ability_type in (AbilityType.WhenDefeated, AbilityType.WhenCompleted):
            with self.subTest(ability_type=ability_type):
                effect = SimpleNamespace(
                    ability=SimpleNamespace(
                        type=ability_type,
                        priority=TimingPriority.Boost,
                    ),
                )
                self.assertEqual(
                    manager.GetEffectivePriority(effect),
                    TimingPriority.ForcedInterrupt,
                )
                world.rule.v18_timing = False
                self.assertEqual(
                    manager.GetEffectivePriority(effect),
                    TimingPriority.Boost,
                )
                world.rule.v18_timing = True

    def test_local_constant_modifiers_resolve_as_rules_without_player_choice(self):
        world = self.make_world()
        manager = EventManager(world)
        world.event_manager = manager
        ability = SimpleNamespace(
            type=AbilityType.NonKeyword,
            priority=TimingPriority.Constant,
            when=Message.WhenCardEnterPlay,
            flags=SimpleNamespace(
                is_statistics=False,
                is_temp=False,
            ),
        )
        health = SimpleNamespace(
            ability=ability,
            is_nonkeyword=True,
            is_rule=False,
            is_forced=True,
        )
        defense = SimpleNamespace(
            ability=ability,
            is_nonkeyword=True,
            is_rule=False,
            is_forced=True,
        )
        face = MagicMock()
        face.effect.local_effects = [health, defense]
        message = object.__new__(Message.WhenCardEnterPlay)
        message.world = world
        message.related_faces = {face}
        manager.ProcessRuleEffect = MagicMock(return_value=False)
        manager.ProcessForcedEffect = MagicMock(return_value=False)

        manager.BroadcastMessage(message)

        manager.ProcessRuleEffect.assert_called_once_with(
            message,
            [health, defense],
            TimingPriority.Constant,
            None,
        )
        manager.ProcessForcedEffect.assert_not_called()

    def test_defensive_conditioning_modifiers_are_constant_abilities(self):
        abilities = import_module("cards.pack.cw.56046").GetAbilities()[1:]

        self.assertEqual(len(abilities), 2)
        self.assertTrue(all(ability.flags.is_nonkeyword for ability in abilities))
        self.assertTrue(all(
            ability.priority == TimingPriority.Constant
            for ability in abilities
        ))
        self.assertTrue(all(
            ability.when == Message.WhenCardEnterPlay | Message.WhenCardFaceActivated
            for ability in abilities
        ))

    def test_framework_effects_are_automatic_and_keep_their_v18_priorities(self):
        world = self.make_world()
        manager = EventManager(world)

        expected = (
            (
                AbilityType.DelayAbility,
                TimingPriority.Constant,
                "Rule",
            ),
            (
                AbilityType.Temp1,
                TimingPriority.Constant,
                "Rule",
            ),
            (
                AbilityType.Consequential,
                TimingPriority.Consequential,
                "Rule",
            ),
        )
        for ability_type, priority, category in expected:
            with self.subTest(ability_type=ability_type):
                effect = SimpleNamespace(
                    ability=SimpleNamespace(
                        type=ability_type,
                        flags=ability_type.flags,
                        priority=ability_type.flags.GetPriority(),
                    ),
                    is_nonkeyword=False,
                    is_rule=False,
                    is_forced=True,
                )

                self.assertEqual(manager.GetEffectivePriority(effect), priority)
                self.assertEqual(
                    manager.GetEffectCategory(
                        effect,
                        Message.AfterUnitUseBasicPower,
                    ),
                    category,
                )

        world.rule.v18_timing = False
        legacy_expected = (
            (
                AbilityType.DelayAbility,
                TimingPriority.Rule,
                "Forced",
            ),
            (
                AbilityType.Temp1,
                TimingPriority.Normal,
                "Rule",
            ),
            (
                AbilityType.Consequential,
                TimingPriority.Consequential,
                "Forced",
            ),
        )
        for ability_type, priority, category in legacy_expected:
            with self.subTest(legacy_ability_type=ability_type):
                effect = SimpleNamespace(
                    ability=SimpleNamespace(
                        type=ability_type,
                        flags=ability_type.flags,
                        priority=ability_type.flags.GetPriority(),
                    ),
                    is_nonkeyword=False,
                    is_rule=False,
                    is_forced=True,
                )

                self.assertEqual(manager.GetEffectivePriority(effect), priority)
                self.assertEqual(
                    manager.GetEffectCategory(
                        effect,
                        Message.AfterUnitUseBasicPower,
                    ),
                    category,
                )

    def test_first_player_selects_the_order_of_forced_candidates(self):
        world = self.make_world()
        first_player = world.GetFirstPlayer.return_value
        manager = EventManager(world)
        world.event_manager = manager
        message = SimpleNamespace(world=world)
        first_effect = MagicMock()
        first_effect.IsPlayerInitiator.return_value = False
        second_effect = MagicMock()
        second_effect.IsPlayerInitiator.return_value = False
        first = SimpleNamespace(
            key=(1, 101),
            effect=MagicMock(),
            message=message,
            TryPrepare=MagicMock(return_value=first_effect),
        )
        second = SimpleNamespace(
            key=(2, 102),
            effect=MagicMock(),
            message=message,
            TryPrepare=MagicMock(return_value=second_effect),
        )

        def build(messages, category, priority, asked_player, processed):
            if category != "Forced" or priority != TimingPriority.ForcedResponse:
                return []
            return [candidate for candidate in (first, second) if candidate.key not in processed]

        manager._BuildTimingCandidates = MagicMock(side_effect=build)
        manager._ChooseTimingCandidate = MagicMock(return_value=(second, False))
        manager.ProcessEffect = MagicMock(return_value=True)

        manager.BroadcastTimingWindow([message])

        manager._ChooseTimingCandidate.assert_called_once_with(
            first_player,
            [first, second],
            TimingPriority.ForcedResponse,
            forced=True,
            select_only=True,
        )
        self.assertEqual(
            [call.args[0] for call in manager.ProcessEffect.call_args_list],
            [second.TryPrepare.return_value, first.TryPrepare.return_value],
        )

    def test_same_face_forced_abilities_are_ordered_in_normal_v18_windows(self):
        world = self.make_world()
        first_player = world.GetFirstPlayer.return_value
        manager = EventManager(world)
        face = MagicMock()
        flags = SimpleNamespace(
            is_resource=False,
            is_discard_pay=False,
            is_check_pay=False,
            is_delay_ability=False,
        )

        def make_effect(object_id):
            effect = MagicMock()
            effect.object_id = object_id
            effect.this = face
            effect.card = face.card
            effect.ability = SimpleNamespace(
                flags=flags,
                priority=TimingPriority.ForcedInterrupt,
                type=AbilityType.ForcedInterrupt,
            )
            effect.is_forced = True
            effect.IsPlayerInitiator.return_value = False
            effect.context.targets_internal = []
            effect.context.all_legal_targets = []
            effect.Render.return_value = SimpleNamespace(
                id=object_id,
                name=f"Forced {object_id}",
                choice_id="",
            )
            return effect

        first = make_effect(1)
        second = make_effect(2)
        message = SimpleNamespace(
            object_id=300,
            name="WhenUnitBeDefeated",
            world=world,
        )

        def choose(player, candidates, priority, **kwargs):
            self.assertIs(player, first_player)
            return (
                next(candidate for candidate in candidates if candidate.effect is second),
                False,
            )

        manager._ChooseTimingCandidate = MagicMock(side_effect=choose)
        manager.ProcessEffect = MagicMock(return_value=True)

        with patch.object(
            EventManager,
            "FilterAvailableEffects",
            side_effect=lambda message, effects, asked_player, world, undo: effects,
        ):
            manager.ProcessForcedEffect(
                message,
                [first, second],
                TimingPriority.ForcedInterrupt,
                None,
            )

        manager._ChooseTimingCandidate.assert_called_once()
        self.assertEqual(
            [call.args[0] for call in manager.ProcessEffect.call_args_list],
            [second, first],
        )

    def test_grouped_priority_ladder_resolves_in_rules_order(self):
        world = self.make_world()
        manager = EventManager(world)
        world.event_manager = manager
        message = SimpleNamespace(world=world)
        priorities = (
            TimingPriority.Rule,
            TimingPriority.Constant,
            TimingPriority.Status,
            TimingPriority.ForcedInterrupt,
            TimingPriority.Interrupt,
            TimingPriority.Boost,
            TimingPriority.ForcedResponse,
            TimingPriority.Response,
            TimingPriority.Consequential,
        )
        effects = {
            priority: SimpleNamespace(
                name=priority.name,
                IsPlayerInitiator=MagicMock(return_value=False),
                context=SimpleNamespace(all_legal_targets=[]),
            )
            for priority in priorities
        }
        candidates = {
            priority: SimpleNamespace(
                key=(index + 1, 500 + index),
                effect=effects[priority],
                message=message,
                TryPrepare=MagicMock(return_value=effects[priority]),
            )
            for index, priority in enumerate(priorities)
        }

        def build(messages, category, priority, asked_player, processed):
            if category != "Forced" or priority not in candidates:
                return []
            candidate = candidates[priority]
            return [] if candidate.key in processed else [candidate]

        resolved = []
        manager._BuildTimingCandidates = MagicMock(side_effect=build)
        manager.ProcessEffect = MagicMock(
            side_effect=lambda effect, message, priority: resolved.append(priority) or True
        )

        manager.BroadcastTimingWindow([message])

        self.assertEqual(resolved, list(priorities))

    def test_optional_opportunities_begin_with_first_player(self):
        world = self.make_world()
        first = MagicMock(player_id=1)
        second = MagicMock(player_id=0)
        world.const_players = [first, second]
        world.GetFirstPlayer.return_value = first
        manager = EventManager(world)
        world.event_manager = manager
        message = SimpleNamespace(world=world)
        effects = {
            first: SimpleNamespace(name="first"),
            second: SimpleNamespace(name="second"),
        }
        candidates = {
            player: SimpleNamespace(
                key=(600 + player.player_id, 700 + player.player_id),
                effect=effects[player],
                message=message,
            )
            for player in (first, second)
        }

        def build(messages, category, priority, asked_player, processed):
            if category != "Optional" or priority != TimingPriority.Response:
                return []
            candidate = candidates[asked_player]
            return [] if candidate.key in processed else [candidate]

        order = []
        first.ResolveEffect.side_effect = lambda effect, message: order.append("first") or True
        second.ResolveEffect.side_effect = lambda effect, message: order.append("second") or True
        manager._BuildTimingCandidates = MagicMock(side_effect=build)
        manager._ChooseTimingCandidate = MagicMock(
            side_effect=lambda player, candidates, priority, **kwargs: (
                candidates[0],
                False,
            )
        )

        with patch.object(Message, "PlayerOnEvent_Text"):
            manager.BroadcastTimingWindow([message])

        self.assertEqual(order, ["first", "second"])

    def test_optional_opportunities_rotate_to_the_actual_first_player(self):
        world = self.make_world()
        first = MagicMock(player_id=1)
        second = MagicMock(player_id=0)
        world.const_players = [second, first]
        world.GetFirstPlayer.return_value = first
        manager = EventManager(world)
        world.event_manager = manager
        message = SimpleNamespace(world=world)
        candidates = {
            first: SimpleNamespace(
                key=(710, 810), effect=SimpleNamespace(name="first"), message=message,
            ),
            second: SimpleNamespace(
                key=(711, 811), effect=SimpleNamespace(name="second"), message=message,
            ),
        }

        def build(messages, category, priority, asked_player, processed):
            if category != "Optional" or priority != TimingPriority.Response:
                return []
            candidate = candidates[asked_player]
            return [] if candidate.key in processed else [candidate]

        order = []
        first.ResolveEffect.side_effect = lambda effect, message: order.append("first") or True
        second.ResolveEffect.side_effect = lambda effect, message: order.append("second") or True
        manager._BuildTimingCandidates = MagicMock(side_effect=build)
        manager._ChooseTimingCandidate = MagicMock(
            side_effect=lambda player, choices, priority, **kwargs: (
                choices[0],
                False,
            )
        )

        with patch.object(Message, "PlayerOnEvent_Text"):
            manager.BroadcastTimingWindow([message])

        self.assertEqual(order, ["first", "second"])

    def test_single_message_response_window_uses_round_robin_dispatcher(self):
        world = self.make_world()
        manager = EventManager(world)
        message = SimpleNamespace(world=world)
        effect = SimpleNamespace()
        manager.ProcessOptionalTimingPriority = MagicMock(return_value=False)

        manager.ProcessOptionalEffect(
            message,
            [effect],
            [],
            TimingPriority.Response,
        )

        manager.ProcessOptionalTimingPriority.assert_called_once_with(
            [message],
            TimingPriority.Response,
            set(),
        )

    def test_eliminated_players_get_no_optional_opportunity(self):
        world = self.make_world()
        eliminated = MagicMock(player_id=0, is_eliminated=True)
        active = MagicMock(player_id=1, is_eliminated=False)
        world.const_players = [eliminated, active]
        world.GetFirstPlayer.return_value = eliminated
        manager = EventManager(world)
        world.event_manager = manager
        message = SimpleNamespace(world=world)
        candidate = SimpleNamespace(
            key=(720, 820),
            effect=SimpleNamespace(name="active"),
            message=message,
        )

        def build(messages, category, priority, asked_player, processed):
            self.assertIs(asked_player, active)
            return [] if candidate.key in processed else [candidate]

        active.ResolveEffect.return_value = True
        manager._BuildTimingCandidates = MagicMock(side_effect=build)
        manager._ChooseTimingCandidate = MagicMock(
            side_effect=lambda player, choices, priority, **kwargs: (
                choices[0],
                False,
            )
        )

        with patch.object(Message, "PlayerOnEvent_Text"):
            manager.ProcessOptionalTimingPriority(
                [message],
                TimingPriority.Response,
                set(),
            )

        eliminated.ResolveEffect.assert_not_called()
        active.ResolveEffect.assert_called_once_with(candidate.effect, message)

    def test_all_eliminated_players_end_optional_window_without_first_player(self):
        world = self.make_world()
        eliminated = MagicMock(player_id=0, is_eliminated=True)
        world.const_players = [eliminated]
        world.GetFirstPlayer.side_effect = AssertionError(
            "there is no active first player"
        )
        manager = EventManager(world)
        manager._BuildTimingCandidates = MagicMock()

        result = manager.ProcessOptionalTimingPriority(
            [SimpleNamespace(world=world)],
            TimingPriority.Response,
            set(),
        )

        self.assertFalse(result)
        world.GetFirstPlayer.assert_not_called()
        manager._BuildTimingCandidates.assert_not_called()

    def test_candidate_legality_is_recalculated_after_each_response(self):
        world = self.make_world()
        player = MagicMock(player_id=0)
        world.const_players = [player]
        world.GetFirstPlayer.return_value = player
        manager = EventManager(world)
        world.event_manager = manager
        message = SimpleNamespace(world=world)
        nova = SimpleNamespace(name="Nova")
        jarnbjorn = SimpleNamespace(name="Jarnbjorn")
        nova_candidate = SimpleNamespace(
            key=(801, 901), effect=nova, message=message,
        )
        jarnbjorn_candidate = SimpleNamespace(
            key=(802, 902), effect=jarnbjorn, message=message,
        )
        state = {"jarnbjorn_payable": False}

        def build(messages, category, priority, asked_player, processed):
            if category != "Optional" or priority != TimingPriority.Response:
                return []
            result = []
            if nova_candidate.key not in processed:
                result.append(nova_candidate)
            if state["jarnbjorn_payable"] and jarnbjorn_candidate.key not in processed:
                result.append(jarnbjorn_candidate)
            return result

        resolved = []
        def resolve(effect, message):
            resolved.append(effect.name)
            if effect is nova:
                state["jarnbjorn_payable"] = True
            return True

        player.ResolveEffect.side_effect = resolve
        manager._BuildTimingCandidates = MagicMock(side_effect=build)
        manager._ChooseTimingCandidate = MagicMock(
            side_effect=lambda player, candidates, priority, **kwargs: (
                candidates[0],
                False,
            )
        )

        with patch.object(Message, "PlayerOnEvent_Text"):
            manager.BroadcastTimingWindow([message])

        self.assertEqual(resolved, ["Nova", "Jarnbjorn"])

    def test_later_player_can_make_earlier_players_response_legal(self):
        world = self.make_world()
        first = MagicMock(player_id=0)
        second = MagicMock(player_id=1)
        world.const_players = [first, second]
        world.GetFirstPlayer.return_value = first
        manager = EventManager(world)
        world.event_manager = manager
        message = SimpleNamespace(world=world)
        first_effect = SimpleNamespace(name="First player response")
        second_effect = SimpleNamespace(name="Second player response")
        first_candidate = SimpleNamespace(
            key=(820, 920), effect=first_effect, message=message,
        )
        second_candidate = SimpleNamespace(
            key=(821, 921), effect=second_effect, message=message,
        )
        state = {"first_is_legal": False}

        def build(messages, category, priority, asked_player, processed):
            if category != "Optional" or priority != TimingPriority.Response:
                return []
            if asked_player is first:
                if state["first_is_legal"] and first_candidate.key not in processed:
                    return [first_candidate]
                return []
            if second_candidate.key not in processed:
                return [second_candidate]
            return []

        order = []
        first.ResolveEffect.side_effect = (
            lambda effect, message: order.append(effect.name) or True
        )

        def resolve_second(effect, message):
            order.append(effect.name)
            state["first_is_legal"] = True
            return True

        second.ResolveEffect.side_effect = resolve_second
        manager._BuildTimingCandidates = MagicMock(side_effect=build)
        manager._ChooseTimingCandidate = MagicMock(
            side_effect=lambda player, candidates, priority, **kwargs: (
                candidates[0],
                False,
            )
        )

        with patch.object(Message, "PlayerOnEvent_Text"):
            manager.BroadcastTimingWindow([message])

        self.assertEqual(
            order,
            ["Second player response", "First player response"],
        )

    def test_passed_optional_response_is_reoffered_after_another_response(self):
        world = self.make_world()
        first = MagicMock(player_id=0)
        second = MagicMock(player_id=1)
        world.const_players = [first, second]
        world.GetFirstPlayer.return_value = first
        manager = EventManager(world)
        world.event_manager = manager
        message = SimpleNamespace(world=world)
        first_candidate = SimpleNamespace(
            key=(830, 930), effect=SimpleNamespace(name="Passed"), message=message,
        )
        second_candidate = SimpleNamespace(
            key=(831, 931), effect=SimpleNamespace(name="Resolved"), message=message,
        )

        def build(messages, category, priority, asked_player, processed):
            if category != "Optional" or priority != TimingPriority.Response:
                return []
            candidate = first_candidate if asked_player is first else second_candidate
            return [] if candidate.key in processed else [candidate]

        choices = []

        first_opportunities = 0

        def choose(player, candidates, priority, **kwargs):
            nonlocal first_opportunities
            choices.append((player.player_id, candidates[0].key))
            if player is first:
                first_opportunities += 1
                if first_opportunities == 1:
                    return None, False
            return candidates[0], False

        first.ResolveEffect.return_value = True
        second.ResolveEffect.return_value = True
        manager._BuildTimingCandidates = MagicMock(side_effect=build)
        manager._ChooseTimingCandidate = MagicMock(side_effect=choose)

        with patch.object(Message, "PlayerOnEvent_Text"):
            manager.BroadcastTimingWindow([message])

        self.assertEqual(
            choices,
            [
                (0, first_candidate.key),
                (1, second_candidate.key),
                (0, first_candidate.key),
            ],
        )
        first.ResolveEffect.assert_called_once_with(
            first_candidate.effect,
            message,
        )
        second.ResolveEffect.assert_called_once_with(
            second_candidate.effect,
            message,
        )

    def test_defeated_character_own_damage_response_is_inactive(self):
        world = self.make_world()
        manager = EventManager(world)
        face = MagicMock()
        face.IsInPlay.return_value = False
        effect = SimpleNamespace(
            this=face,
            ability=SimpleNamespace(
                when=Message.AfterUnitTookDamage,
                type=AbilityType.Response,
                priority=TimingPriority.Response,
                flags=SimpleNamespace(is_statistics=False),
            ),
            is_nonkeyword=False,
            is_rule=False,
            is_forced=False,
        )
        face.effect.local_effects = [effect]
        message = object.__new__(Message.AfterUnitTookDamage)
        message.related_faces = {face}
        message.private_trigger = face

        with patch("game.card.face.base.Unit2.IsType", return_value=True):
            self.assertEqual(
                manager._FindLocalTimingEffects(
                    message,
                    "Optional",
                    TimingPriority.Response,
                ),
                [],
            )


class TestNovaJarnbjornTiming(unittest.TestCase):

    def setUp(self):
        self.world = MagicMock()
        self.world.rule.v18_timing = True
        self.world.is_game_over = False
        self.player = MagicMock(player_id=0)
        self.world.GetFirstPlayer.return_value = self.player
        self.world.const_players = [self.player]
        self.manager = EventManager(self.world)
        self.world.event_manager = self.manager

        self.nova_ability = import_module(
            "cards.pack.nova.nova.28001a"
        ).GetAbilities()[0]
        self.jarnbjorn_ability = import_module(
            "cards.pack.thor.06019"
        ).GetAbilities()[0]
        self.nova = FakeEffect(10, "Nova", self.nova_ability)
        self.jarnbjorn = FakeEffect(11, "Jarnbjorn", self.jarnbjorn_ability)

        self.attack = object.__new__(Message.AfterUnitAttackUnit)
        self.attack.object_id = 201
        self.attack.world = self.world
        self.attack.related_faces = set()
        self.basic = object.__new__(Message.AfterUnitUseBasicPower)
        self.basic.object_id = 202
        self.basic.world = self.world
        self.basic.related_faces = set()

        self.manager.AddEffectsList(
            "Optional",
            Message.AfterUnitAttackUnit,
            TimingPriority.Response,
            self.jarnbjorn,
        )
        self.manager.AddEffectsList(
            "Optional",
            Message.AfterUnitUseBasicPower,
            TimingPriority.Response,
            self.nova,
        )

    def build_candidates(self, state, processed=set()):
        def available(message, effects, asked_player, world, undo_handle):
            effect = effects[0]
            effect.context.bind_message = message
            if effect is self.nova:
                return [effect] if state["helmet_exhausted"] else []
            if effect is self.jarnbjorn:
                return [effect] if state["wild_resource"] else []
            return []

        with patch.object(
            EventManager,
            "FilterAvailableEffects",
            side_effect=available,
        ):
            return self.manager._BuildTimingCandidates(
                [self.attack, self.basic],
                "Optional",
                TimingPriority.Response,
                self.player,
                set(processed),
            )

    def test_printed_responses_share_the_response_priority(self):
        self.assertEqual(self.nova_ability.priority, TimingPriority.Response)
        self.assertEqual(self.jarnbjorn_ability.priority, TimingPriority.Response)
        self.assertIs(
            self.nova_ability.when,
            Message.AfterUnitUseBasicPower,
        )
        self.assertIs(
            self.jarnbjorn_ability.when,
            Message.AfterUnitAttackUnit,
        )

    def test_nova_can_ready_helmet_before_jarnbjorn_is_rechecked(self):
        state = {"helmet_exhausted": True, "wild_resource": False}

        candidates = self.build_candidates(state)
        self.assertEqual([candidate.effect for candidate in candidates], [self.nova])

        resolved_nova = candidates[0]
        state["helmet_exhausted"] = False
        state["wild_resource"] = True
        candidates = self.build_candidates(state, {resolved_nova.key})

        self.assertEqual(
            [candidate.effect for candidate in candidates],
            [self.jarnbjorn],
        )

    def test_both_initially_payable_responses_are_distinct_choices(self):
        state = {"helmet_exhausted": True, "wild_resource": True}

        candidates = self.build_candidates(state)

        self.assertEqual(
            {candidate.effect for candidate in candidates},
            {self.nova, self.jarnbjorn},
        )
        self.assertEqual(
            len({candidate.choice_id for candidate in candidates}),
            2,
        )

    def test_one_effect_bound_to_two_conditions_keeps_each_origin(self):
        ability = SimpleNamespace(
            type=AbilityType.Response,
            priority=TimingPriority.Response,
            when=Message.AfterUnitAttackUnit | Message.AfterUnitUseBasicPower,
        )
        shared = FakeEffect(12, "Shared Response", ability)
        self.manager.AddEffectsList(
            "Optional",
            Message.AfterUnitAttackUnit,
            TimingPriority.Response,
            shared,
        )
        self.manager.AddEffectsList(
            "Optional",
            Message.AfterUnitUseBasicPower,
            TimingPriority.Response,
            shared,
        )

        def available(message, effects, asked_player, world, undo_handle):
            effects[0].context.bind_message = message
            return list(effects)

        with patch.object(
            EventManager,
            "FilterAvailableEffects",
            side_effect=available,
        ):
            candidates = self.manager._BuildTimingCandidates(
                [self.attack, self.basic],
                "Optional",
                TimingPriority.Response,
                self.player,
                set(),
            )

        shared_candidates = [
            candidate for candidate in candidates if candidate.effect is shared
        ]
        self.assertEqual(len(shared_candidates), 2)
        self.assertEqual(
            {candidate.message for candidate in shared_candidates},
            {self.attack, self.basic},
        )
        self.assertEqual(
            len({candidate.choice_id for candidate in shared_candidates}),
            2,
        )
        self.assertTrue(
            all("AfterUnit" in candidate.descriptor.name for candidate in shared_candidates)
        )


class TestV18KeywordPriority(unittest.TestCase):

    def test_retaliate_is_a_forced_response_candidate(self):
        ability = next(
            ability
            for ability in GetGamePlayRules()
            if ability.name == "Retaliate"
        )

        self.assertEqual(ability.type, AbilityType.ForcedResponse)
        self.assertEqual(ability.priority, TimingPriority.ForcedResponse)
        self.assertIs(ability.when, Message.AfterUnitAttackUnit)

    def test_vulnerable_is_a_forced_interrupt_candidate(self):
        ability = next(
            ability
            for ability in GetGamePlayRules()
            if ability.name == "Vulnerable"
        )

        self.assertEqual(ability.type, AbilityType.ForcedInterrupt)
        self.assertEqual(ability.priority, TimingPriority.ForcedInterrupt)
        self.assertIs(ability.when, Message.WhenStatusWouldCardPlaceOn)

    def test_vulnerable_only_triggers_before_stun_or_confuse_placement(self):
        ability = next(
            ability
            for ability in GetGamePlayRules()
            if ability.name == "Vulnerable"
        )
        trigger = MagicMock()
        trigger.IsVulnerable.return_value = True
        effect = MagicMock()
        effect.world.rule.v18_timing = True

        with patch.object(HasVulnerable, "IsType", return_value=True):
            self.assertTrue(all(
                condition(
                    effect,
                    SimpleNamespace(trigger=trigger, status_name="Stunned"),
                )
                for condition in ability.conditions
            ))
            self.assertFalse(all(
                condition(
                    effect,
                    SimpleNamespace(trigger=trigger, status_name="Tough"),
                )
                for condition in ability.conditions
            ))

    def test_status_is_not_placed_after_interrupt_removes_recipient(self):
        unit = MagicMock()
        unit.card.IsOnField.side_effect = [True, False]
        unit.CanbeStunned.return_value = True
        would_message = MagicMock(is_be_instead=False)
        effect = MagicMock()

        with patch.object(
            Message,
            "WhenStatusWouldCardPlaceOn",
            return_value=would_message,
        ):
            placed = CanStatus.GainStatus(unit, "Stunned", effect)

        self.assertFalse(placed)
        would_message.Send.assert_called_once_with()
        unit.components.status.GiveStatusCard.assert_not_called()


class TestTriggeredCandidateReplayIdentity(unittest.TestCase):

    @staticmethod
    def make_candidate(
        effect_id=30,
        *,
        message_index=2,
        message_name="AfterUnitAttackUnit",
        ability_slot=0,
        display_name="Response",
    ):
        effect = FakeEffect(
            effect_id,
            display_name,
            SimpleNamespace(type=AbilityType.Response),
        )
        message = SimpleNamespace(
            object_id=400 + effect_id,
            name=message_name,
            world=SimpleNamespace(),
        )
        return TriggeredCandidate(
            effect,
            message,
            message_index,
            None,
            SimpleNamespace(name=display_name),
            ability_slot,
        )

    def test_trigger_condition_is_part_of_replay_identity(self):
        candidate = self.make_candidate()

        self.assertEqual(
            candidate.GetReplayText(),
            "timing2 t2 AfterUnitAttackUnit a0 Response c1030 card",
        )
        self.assertEqual(
            TriggeredCandidate.ConvertReplayId(
                candidate.GetReplayText(),
                [candidate],
            ),
            candidate.choice_id,
        )

    def test_unnamed_internal_effect_never_uses_ordinary_replay_text(self):
        candidate = self.make_candidate(display_name="")
        candidate.effect.GetReplayText = MagicMock(side_effect=AssertionError)

        self.assertTrue(candidate.GetDisplayName())
        self.assertEqual(
            candidate.GetReplayText(),
            "timing2 t2 AfterUnitAttackUnit a0 Response c1030 card",
        )
        self.assertIsNone(candidate.GetLegacyReplayText())
        candidate.effect.GetReplayText.assert_called_once_with()

    def test_v2_replay_survives_changed_runtime_effect_and_card_ids(self):
        recorded = self.make_candidate(effect_id=40, ability_slot=3)
        restored = self.make_candidate(effect_id=41, ability_slot=3)

        self.assertEqual(
            TriggeredCandidate.ConvertReplayId(
                recorded.GetReplayText(),
                [restored],
            ),
            restored.choice_id,
        )

    def test_v2_replay_reprompts_when_duplicate_copies_are_ambiguous(self):
        recorded = self.make_candidate(effect_id=50)
        first = self.make_candidate(effect_id=51)
        second = self.make_candidate(effect_id=52)

        self.assertIsNone(
            TriggeredCandidate.ConvertReplayId(
                recorded.GetReplayText(),
                [first, second],
            )
        )

    def test_current_named_timing_replay_format_remains_supported(self):
        candidate = self.make_candidate(effect_id=60)
        legacy_replay = candidate.GetLegacyReplayText()

        self.assertIsNotNone(legacy_replay)
        self.assertEqual(
            TriggeredCandidate.ConvertReplayId(legacy_replay, [candidate]),
            candidate.choice_id,
        )

    def test_malformed_timing_replay_reprompts(self):
        candidate = self.make_candidate()

        self.assertIsNone(
            TriggeredCandidate.ConvertReplayId("timing2 malformed", [candidate])
        )

    def test_stale_candidate_try_prepare_returns_none(self):
        candidate = self.make_candidate()

        with patch.object(EventManager, "FilterAvailableEffects", return_value=[]):
            self.assertIsNone(candidate.TryPrepare())

    def test_candidate_chooser_does_not_require_a_named_effect(self):
        world = TestTimingOccurrence.make_world()
        manager = EventManager(world)
        player = MagicMock(player_id=0)
        candidate = self.make_candidate(display_name="")
        candidate.message.world = world
        candidate.effect.GetReplayText = MagicMock(side_effect=AssertionError)
        player.GetController.return_value.ChoiceOne.return_value = (None, False)

        selected, retry = manager._ChooseTimingCandidate(
            player,
            [candidate],
            TimingPriority.ForcedResponse,
            forced=True,
            select_only=False,
        )

        self.assertIsNone(selected)
        self.assertFalse(retry)
        candidate.effect.GetReplayText.assert_not_called()

    def test_select_only_chooser_clears_stale_failure_reasons(self):
        world = TestTimingOccurrence.make_world()
        manager = EventManager(world)
        player = MagicMock(player_id=1)
        candidate = self.make_candidate()
        candidate.message.world = world
        candidate.descriptor = SimpleNamespace(
            name="Call for Backup: When Defeated",
            failure_reason="no process",
            all_legal_targets=[10],
            target_num_range=[1, 1],
            target_payment={0: object()},
        )
        controller = player.GetController.return_value
        controller.ChoiceOne.return_value = (None, False)

        selected, retry = manager._ChooseTimingCandidate(
            player,
            [candidate],
            TimingPriority.ForcedInterrupt,
            forced=True,
            select_only=True,
        )

        self.assertIsNone(selected)
        self.assertFalse(retry)
        override = controller.ChoiceOne.call_args.args[5]
        descriptor = override.descriptors[0]
        self.assertEqual(descriptor.failure_reason, "")
        self.assertEqual(descriptor.all_legal_targets, [])
        self.assertEqual(descriptor.target_num_range, [0, 0])
        self.assertEqual(descriptor.target_payment, {})
        self.assertEqual(candidate.descriptor.failure_reason, "no process")

    def test_duplicate_display_names_include_trigger_origin_and_ability_slot(self):
        world = TestTimingOccurrence.make_world()
        manager = EventManager(world)
        first = self.make_candidate(
            effect_id=70,
            message_name="AfterUnitAttackUnit",
            ability_slot=0,
            display_name="Forced Response",
        )
        second = self.make_candidate(
            effect_id=71,
            message_name="AfterUnitAttackUnit",
            ability_slot=1,
            display_name="Forced Response",
        )
        first.message.attacked = SimpleNamespace(name="Rhino")
        second.message.attacked = SimpleNamespace(name="Rhino")

        manager._FinalizeTimingCandidateLabels([first, second])

        self.assertNotEqual(first.descriptor.name, second.descriptor.name)
        self.assertIn("Test_Card:_Forced_Response", first.descriptor.name)
        self.assertIn("after_attack_on_Rhino", first.descriptor.name)
        self.assertIn("option_2", second.descriptor.name)


if __name__ == "__main__":
    unittest.main()
