from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from engine import Engine  # noqa: F401 - establishes the project's import order
from engine.lib.version import Ver
from cards.database import CardsDB
from game.ability import AbilityType, TimingPriority
from game.card.card import Card
from game.card.factory import CardFactory
from game.card.face.attribute.can_attack import (
    _ShouldResolvePiercing,
    _TakeIndirectAttackDamage,
)
from game.card.face.attribute.can_retaliate import CanRetaliate
from game.card.face.attribute.has_villainous import HasVillainous
from game.event.manager import EventManager
from game.message import Message
from game.rule.gameplay import GetGamePlayRules


class TestV18KeywordAbilityDefinitions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Ver.Initialize()
        CardsDB.Initialize()

    @staticmethod
    def keyword_ability(card_id, name):
        world = MagicMock()
        world.GetPlayerNumIcon.return_value = 1
        face = CardFactory.CreateFace(CardsDB.FindCardPaper(card_id), world)
        ability = next(
            ability
            for ability in face.ability.abilities
            if ability.name == name
        )
        return face, ability

    def test_reveal_keywords_are_when_revealed_abilities(self):
        for card_id, name, printed_attribute in (
            ("01121", "Surge", "printed_surge"),
            ("04056", "Incite", "printed_incite"),
        ):
            with self.subTest(keyword=name):
                face, ability = self.keyword_ability(card_id, name)

                self.assertGreater(getattr(face, printed_attribute), 0)
                self.assertEqual(ability.type, AbilityType.WhenRevealed)
                self.assertEqual(ability.priority, TimingPriority.Boost)
                self.assertIs(ability.when, Message.WhenCardRevealed)
                self.assertTrue(ability.v18_timing_keyword)

    def test_response_keywords_have_printed_v18_priorities(self):
        expected = (
            (
                "01167",
                "Quickstrike",
                AbilityType.ForcedResponseHero,
                Message.AfterMinionEngagePlayer,
            ),
            (
                "32159",
                "Teamwork",
                AbilityType.ForcedResponse,
                Message.AfterCardEnterPlay,
            ),
            (
                "01076",
                "Toughness",
                AbilityType.ForcedResponse,
                Message.AfterCardEnterPlay,
            ),
            (
                "03009",
                "Restricted",
                AbilityType.ForcedResponse,
                Message.AfterCardEnterPlay,
            ),
        )
        for card_id, name, ability_type, event in expected:
            with self.subTest(keyword=name):
                _, ability = self.keyword_ability(card_id, name)

                self.assertEqual(ability.type, ability_type)
                self.assertEqual(ability.priority, TimingPriority.ForcedResponse)
                self.assertTrue(isinstance(object.__new__(event), ability.when))

        quickstrike = self.keyword_ability("01167", "Quickstrike")[1]
        self.assertTrue(quickstrike.type.flags.is_hero_type)

        restricted = self.keyword_ability("03009", "Restricted")[1]
        self.assertTrue(isinstance(
            object.__new__(Message.AfterCardControlChanged),
            restricted.when,
        ))

    def test_interrupt_keywords_have_printed_v18_priorities(self):
        expected = (
            ("11041", "Villainous", Message.WhenUnitUseBasicPower),
            ("33005", "Temporary", Message.WhenRoundEnd),
        )
        for card_id, name, event in expected:
            with self.subTest(keyword=name):
                _, ability = self.keyword_ability(card_id, name)

                self.assertEqual(ability.type, AbilityType.ForcedInterrupt)
                self.assertEqual(ability.priority, TimingPriority.ForcedInterrupt)
                self.assertIs(ability.when, event)

    def test_victory_uses_when_defeated_with_effective_interrupt_priority(self):
        _, ability = self.keyword_ability("16178a", "Victory")
        world = MagicMock()
        world.rule.v18_timing = True
        manager = EventManager(world)
        effect = SimpleNamespace(ability=ability)

        self.assertEqual(ability.type, AbilityType.WhenDefeated)
        self.assertTrue(isinstance(
            object.__new__(Message.WhenSchemeBeDefeated),
            ability.when,
        ))
        self.assertEqual(
            manager.GetEffectivePriority(effect),
            TimingPriority.ForcedInterrupt,
        )

    def test_victory_attachment_is_a_forced_interrupt_on_bound_defeat(self):
        _, ability = self.keyword_ability("32170", "Victory")

        self.assertEqual(ability.type, AbilityType.ForcedInterrupt)
        self.assertEqual(ability.priority, TimingPriority.ForcedInterrupt)
        self.assertTrue(isinstance(
            object.__new__(Message.WhenUnitBeDefeated),
            ability.when,
        ))
        self.assertTrue(isinstance(
            object.__new__(Message.WhenSchemeBeDefeated),
            ability.when,
        ))

    def test_hero_only_forced_interrupt_and_response_types_are_form_scoped(self):
        self.assertTrue(AbilityType.ForcedInterruptHero.flags.is_hero_type)
        self.assertTrue(AbilityType.ForcedResponseHero.flags.is_hero_type)
        self.assertEqual(
            AbilityType.ForcedResponseHero.flags.GetPriority(),
            TimingPriority.ForcedResponse,
        )


class TestV18RevealKeywordTiming(unittest.TestCase):

    @staticmethod
    def can_cancel_when_revealed(*, v18, keyword_only):
        reveal = object.__new__(Message.WhenPlayerRevealCard)
        reveal.world = SimpleNamespace(rule=SimpleNamespace(v18_timing=v18))
        reveal.private_trigger = MagicMock()
        reveal.by_effect = MagicMock()
        reveal.cannot_be_cancel = False
        reveal.cancel_all_effects = False
        reveal.cancel_when_revealed = False
        ability = SimpleNamespace(v18_timing_keyword=keyword_only)
        reveal.trigger.effect.Find.return_value = [SimpleNamespace(ability=ability)]
        check = MagicMock(can_be_cancel=True)

        with patch.object(
            Message,
            "CheckIfEffectCanBeCancelBy",
            return_value=check,
        ):
            result = Message.WhenPlayerRevealCard.CanBeCancel(
                reveal,
                "WhenRevealed",
                MagicMock(),
            )

        check.Send.assert_called_once_with()
        return result

    def test_surge_and_incite_can_be_canceled_as_when_revealed_in_v18(self):
        self.assertTrue(self.can_cancel_when_revealed(
            v18=True,
            keyword_only=True,
        ))

    def test_legacy_mode_does_not_treat_keyword_shims_as_printed_abilities(self):
        self.assertFalse(self.can_cancel_when_revealed(
            v18=False,
            keyword_only=True,
        ))
        self.assertTrue(self.can_cancel_when_revealed(
            v18=False,
            keyword_only=False,
        ))

    def test_reveal_occurrence_delays_enter_play_and_engagement_responses(self):
        world = MagicMock()
        world.rule.v18_timing = True
        world.is_game_over = False
        manager = EventManager(world)
        world.event_manager = manager
        occurrence = manager.BeginTimingOccurrence(
            delay_reveal_responses=True,
        )
        messages = [
            object.__new__(Message.AfterCardEnterPlay),
            object.__new__(Message.AfterCardPutIntoPlay),
            object.__new__(Message.AfterMinionEngagePlayer),
            object.__new__(Message.AfterCardRevealed),
            object.__new__(Message.AfterCardRevealedEnd),
        ]

        for message in messages:
            self.assertTrue(manager.TryQueueTimingMessage(message), type(message))

        manager.BroadcastTimingWindow = MagicMock()
        manager.EndTimingOccurrence(occurrence)
        manager.BroadcastTimingWindow.assert_called_once_with(messages)

    def test_normal_occurrence_does_not_delay_reveal_only_responses(self):
        world = MagicMock()
        world.rule.v18_timing = True
        world.is_game_over = False
        manager = EventManager(world)
        occurrence = manager.BeginTimingOccurrence()

        self.assertFalse(manager.TryQueueTimingMessage(
            object.__new__(Message.AfterMinionEngagePlayer),
        ))

        manager.BroadcastTimingWindow = MagicMock()
        manager.EndTimingOccurrence(occurrence)
        manager.BroadcastTimingWindow.assert_not_called()

    def test_keyword_when_revealed_operations_record_their_resolution(self):
        for card_id, name, method_name in (
            ("01121", "Surge", "ResolveSurge"),
            ("04056", "Incite", "ResolveIncite"),
        ):
            with self.subTest(keyword=name):
                _, ability = TestV18KeywordAbilityDefinitions.keyword_ability(
                    card_id,
                    name,
                )
                keyword_face = MagicMock()
                resolved = object()
                getattr(keyword_face, method_name).return_value = resolved
                effect = MagicMock()
                effect.this.CastTo.return_value = keyword_face
                message = MagicMock()

                ability.operation(effect, message)

                if name == "Surge":
                    keyword_face.ResolveSurge.assert_called_once_with(
                        message.GetToPlayer.return_value,
                    )
                else:
                    keyword_face.ResolveIncite.assert_called_once_with()
                message.reveal_message.AddResolved.assert_called_once_with(resolved)


class TestV18OtherKeywordResolution(unittest.TestCase):

    def test_restricted_rechecks_after_control_changes_in_v18(self):
        _, ability = TestV18KeywordAbilityDefinitions.keyword_ability(
            "03009",
            "Restricted",
        )
        restricted_face = MagicMock(restricted=1)
        effect = MagicMock()
        effect.world.rule.v18_timing = True
        effect.this.CastTo.return_value = restricted_face
        effect.this.IsInPlay.return_value = True
        message = object.__new__(Message.AfterCardControlChanged)
        message.private_trigger = effect.this
        message.to_controller = MagicMock()

        with patch(
            "game.card.face.attribute.has_restricted.Player.IsType",
            return_value=True,
        ):
            self.assertTrue(all(
                condition(effect, message)
                for condition in ability.conditions
            ))
            ability.operation(effect, message)

        restricted_face.CheckRestrictedLimit.assert_called_once_with([])

        effect.world.rule.v18_timing = False
        self.assertFalse(all(
            condition(effect, message)
            for condition in ability.conditions
        ))

    def test_in_play_control_transfer_emits_a_control_changed_message(self):
        old_controller = MagicMock()
        new_controller = MagicMock()
        face = MagicMock()
        by_effect = MagicMock()
        from_area = MagicMock()
        into_area = MagicMock()
        from_area.flags = SimpleNamespace(is_in_play=True, is_deck=False)
        into_area.flags = SimpleNamespace(is_in_play=True, is_in_hand=False)
        card = MagicMock()
        card.area = from_area
        card.GetController.side_effect = [old_controller, new_controller]
        into_area.Insert.side_effect = (
            lambda index, moved_card, target: setattr(card, "area", into_area)
        )
        move = SimpleNamespace(
            trigger=face,
            into_area=into_area,
            by_effect=by_effect,
            from_area=from_area,
        )
        control_changed = MagicMock()

        with patch.object(
            Message,
            "AfterCardControlChanged",
            return_value=control_changed,
        ) as make_control_changed:
            self.assertTrue(Card.MoveToAreaInternal(card, move))

        make_control_changed.assert_called_once_with(
            face,
            old_controller,
            new_controller,
            by_effect,
        )
        control_changed.Send.assert_called_once_with()

    def test_villainous_interrupt_deals_exactly_one_boost_card(self):
        _, ability = TestV18KeywordAbilityDefinitions.keyword_ability(
            "11041",
            "Villainous",
        )
        minion = MagicMock()
        effect = MagicMock()
        effect.this.CastTo.return_value = minion
        message = MagicMock()

        ability.operation(effect, message)

        minion.GiveFacedownBoostCardsInternal.assert_called_once_with(
            1,
            effect,
            message.would_message,
        )

    def test_villainous_legacy_stat_hook_is_disabled_in_v18(self):
        minion = MagicMock()
        minion.card.world.rule.v18_timing = True

        self.assertEqual(HasVillainous.GetBoostCardNum(minion, MagicMock()), 0)

        minion.card.world.rule.v18_timing = False
        minion.IsVillainous.return_value = True
        self.assertEqual(HasVillainous.GetBoostCardNum(minion, MagicMock()), 1)

    def test_quickstrike_and_teamwork_operations_use_the_triggering_minion(self):
        for card_id, name, method_name in (
            ("01167", "Quickstrike", "ResolveQuickstrike"),
            ("32159", "Teamwork", "ResolveTeamwork"),
        ):
            with self.subTest(keyword=name):
                _, ability = TestV18KeywordAbilityDefinitions.keyword_ability(
                    card_id,
                    name,
                )
                minion = MagicMock()
                effect = MagicMock()
                effect.this.CastTo.return_value = minion
                message = MagicMock()

                ability.operation(effect, message)

                if name == "Quickstrike":
                    minion.ResolveQuickstrike.assert_called_once_with(
                        message.engaged_player,
                    )
                else:
                    minion.ResolveTeamwork.assert_called_once_with()

    def test_quickstrike_hero_qualifier_checks_the_engaged_player(self):
        _, ability = TestV18KeywordAbilityDefinitions.keyword_ability(
            "01167",
            "Quickstrike",
        )
        quickstrike_face = MagicMock()
        quickstrike_face.IsQuickstrike.return_value = True
        effect = MagicMock()
        effect.world.rule.v18_timing = True
        effect.this.CastTo.return_value = quickstrike_face
        effect.this.IsInPlay.return_value = True
        effect.GetInitiator.return_value.IsHero.return_value = False
        engaged_player = MagicMock()
        engaged_player.IsHero.return_value = True
        message = object.__new__(Message.AfterMinionEngagePlayer)
        message.private_trigger = effect.this
        message.player = engaged_player

        with patch("game.card.face.base.Unit2.IsType", return_value=True):
            self.assertTrue(all(
                condition(effect, message)
                for condition in ability.conditions
            ))

            engaged_player.IsHero.return_value = False
            self.assertFalse(all(
                condition(effect, message)
                for condition in ability.conditions
            ))

    def test_temporary_restricted_and_victory_operations_use_forced_paths(self):
        temporary = TestV18KeywordAbilityDefinitions.keyword_ability(
            "33005",
            "Temporary",
        )[1]
        restricted = TestV18KeywordAbilityDefinitions.keyword_ability(
            "03009",
            "Restricted",
        )[1]
        victory = TestV18KeywordAbilityDefinitions.keyword_ability(
            "16178a",
            "Victory",
        )[1]
        effect = MagicMock()

        with patch("game.operate.faces.Faces.DiscardAll") as discard:
            temporary.operation(effect, MagicMock())
        discard.assert_called_once_with([effect.this], effect)

        restricted_face = MagicMock()
        effect.this.CastTo.return_value = restricted_face
        restricted.operation(effect, MagicMock())
        restricted_face.CheckRestrictedLimit.assert_called_once_with([])

        victory_face = MagicMock()
        effect.this.CastTo.return_value = victory_face
        defeat = SimpleNamespace(add_to_victory_display=False)
        victory.operation(effect, defeat)
        self.assertTrue(defeat.add_to_victory_display)
        victory_face.MoveToVictoryDisplay.assert_not_called()

    def test_piercing_does_not_discard_tough_when_attack_deals_no_damage(self):
        attack = MagicMock()
        attack.IsPiercing.return_value = True

        self.assertFalse(_ShouldResolvePiercing(0, attack))
        self.assertTrue(_ShouldResolvePiercing(1, attack))

    @patch("game.card.face.attribute.can_attack.Message.WhenDamageIsZero_Text")
    def test_zero_damage_indirect_attack_emits_attack_presentation(self, zero_damage_text):
        target = MagicMock()
        attacker = MagicMock()
        effect = MagicMock()
        attack_message = MagicMock()
        timing_occurrence = MagicMock()
        target.TakeIndirectDamage.return_value = []

        result = _TakeIndirectAttackDamage(
            target,
            attacker,
            0,
            effect,
            attack_message,
            timing_occurrence,
        )

        zero_damage_text.assert_called_once_with(target, attacker, True)
        target.TakeIndirectDamage.assert_called_once_with(
            attacker,
            0,
            effect,
            from_atk_message=attack_message,
            timing_occurrence=timing_occurrence,
        )
        self.assertEqual(result, [])

    def test_ranged_attack_ignores_retaliate(self):
        defender = MagicMock(retaliate=2)
        defender.IsDefeated.return_value = False
        attacker = MagicMock()
        attacker.IsDefeated.return_value = False
        attack = MagicMock(attacker=attacker)
        attack.IsRanged.return_value = True
        ignored = MagicMock()

        with patch.object(
            Message,
            "AfterIgnoreKeywordOnCard",
            return_value=ignored,
        ):
            result = CanRetaliate.ResolveRetaliate(defender, attack)

        attacker.TakeDamage.assert_not_called()
        ignored.Send.assert_called_once_with()
        self.assertIsNone(result)

    def test_ranged_attack_does_not_open_a_retaliate_response(self):
        ability = next(
            ability
            for ability in GetGamePlayRules()
            if ability.name == "Retaliate"
        )
        defender = MagicMock(retaliate=2)
        defender.IsInPlay.return_value = True
        attacker = MagicMock()
        attacker.IsDefeated.return_value = False
        attack = MagicMock()
        attack.IsRanged.return_value = True
        attack.IsIgnoreRetaliate.return_value = False
        message = SimpleNamespace(
            attacked=defender,
            attacker=attacker,
            would_atk_unit_message=attack,
        )
        effect = MagicMock()
        effect.world.rule.v18_timing = True

        with patch.object(CanRetaliate, "IsType", return_value=True):
            self.assertFalse(all(
                condition(effect, message)
                for condition in ability.conditions
            ))
            attack.IsRanged.return_value = False
            self.assertTrue(all(
                condition(effect, message)
                for condition in ability.conditions
            ))


if __name__ == "__main__":
    unittest.main()
