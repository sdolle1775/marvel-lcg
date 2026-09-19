from importlib import import_module
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from engine import Engine  # noqa: F401 - establishes the project's import order
from cards.database import CardsDB
from engine.lib.version import Ver
from game.card.card import Card
from game.card.face.card_type import Ally, Hero
from game.card.factory import CardFactory
from game.scene.replay.operation import CommandDescriptor
from game.test.headless import HeadlessDeviceManager
from game.test.v18_timing_harness import (
    TimingFixture,
    build_fixture_scene,
    run_scene_with_devices,
)


ROOT = Path(__file__).resolve().parents[1]


class TestDaredevilRegistration(unittest.TestCase):

    def test_hero_has_two_printed_thwart(self):
        Ver.Initialize()
        CardsDB.Initialize()
        world = MagicMock()
        world.GetPlayerNumIcon.return_value = 1

        hero = CardFactory.CreateFace(
            CardsDB.FindCardPaper("60001a"),
            world,
        )

        self.assertEqual(hero.printed_thwart, 2)

    def test_starter_contains_the_complete_identity_and_nemesis_sets(self):
        starter = json.loads(
            (ROOT / "deck" / "starter" / "daredevil.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(starter["hero"], ["60001a,60001b"])
        self.assertEqual(len(starter["hero_deck"]), 15)
        self.assertEqual(
            starter["set_aside"],
            ["60002", "60003", "60004", "60005", "60006"],
        )
        self.assertEqual(starter["obligations"], ["60032"])
        self.assertEqual(
            starter["nemesis_set"],
            ["60033", "60034", "60035", "60036", "60036"],
        )
        self.assertEqual(len(starter["player_deck"]), 25)

    def test_every_daredevil_card_initializes_through_the_card_factory(self):
        Ver.Initialize()
        CardsDB.Initialize()
        world = MagicMock()
        world.GetPlayerNumIcon.return_value = 1
        card_ids = [
            "60001a",
            "60001b",
            *[f"600{i:02d}" for i in range(2, 19)],
            *[f"600{i:02d}" for i in range(32, 37)],
        ]

        for card_id in card_ids:
            with self.subTest(card_id=card_id):
                paper = CardsDB.FindCardPaper(card_id)
                face = CardFactory.CreateFace(paper, world)
                self.assertEqual(face.paper.card_id, card_id)


class TestSenseDeck(unittest.TestCase):

    @staticmethod
    def controlled_face(face_type, player):
        face = object.__new__(face_type)
        face.card = MagicMock()
        face.card.state.is_swapping_end = False
        face.card.GetController.return_value = player
        face.consider_as = SimpleNamespace(card_types=[])
        return face

    def test_attack_and_thwart_senses_require_daredevils_identity(self):
        player = MagicMock()
        hero = self.controlled_face(Hero, player)
        ally = self.controlled_face(Ally, player)
        effect = SimpleNamespace(
            this=SimpleNamespace(
                card=SimpleNamespace(
                    area=SimpleNamespace(
                        flags=SimpleNamespace(is_obligations_area=False),
                    ),
                ),
            ),
            initiator=MagicMock(),
        )
        effect.initiator.IsScenario.return_value = False

        cases = (
            ("60005", 1),
            ("60006", 0),
        )
        with patch("game.selector.Select.GetYou", return_value=player):
            for card_id, actor_condition_index in cases:
                with self.subTest(card_id=card_id):
                    module = import_module(
                        f"cards.pack.fne.sense_deck.{card_id}"
                    )
                    ability = module.GetAbilities()[1]
                    actor_condition = ability.conditions[actor_condition_index]

                    self.assertTrue(
                        actor_condition(
                            effect,
                            SimpleNamespace(trigger=hero),
                        )
                    )
                    self.assertFalse(
                        actor_condition(
                            effect,
                            SimpleNamespace(trigger=ally),
                        )
                    )

    def test_setup_creates_one_shuffled_faceup_deck(self):
        module = import_module("cards.pack.fne")
        player = MagicMock()
        deck = player.additional_deck
        senses = [MagicMock() for _ in range(5)]
        player.set_aside_deck.Get.return_value = senses
        effect = MagicMock()
        effect.GetInitiator.return_value = player

        with patch.object(
            module.CardFinder,
            "Checks",
            return_value=senses,
        ), patch.object(
            module.Faces,
            "MoveAllTo",
        ) as move_all, patch.object(
            module.Faces,
            "FlipAllTo",
        ) as flip_all, patch.object(
            module.Message,
            "WhenDeckCreated_Text",
        ):
            module.SetupSenseDeck(effect, MagicMock())

        self.assertTrue(deck.face_up_override)
        move_all.assert_called_once_with(senses, deck, effect)
        deck.Shuffle.assert_called_once_with(effect)
        flip_all.assert_called_once_with(deck.Get(), True, effect)

    def test_identity_action_plays_only_the_top_sense_and_pays_its_cost(self):
        module = import_module("cards.pack.fne")
        player = MagicMock()
        sense = MagicMock()
        target = MagicMock()
        player.additional_deck.GetTop.return_value = sense
        player.AskChooseFace.return_value = sense
        effect = MagicMock()

        with patch.object(
            module,
            "GetSenseAttachmentTargets",
            return_value=[target],
        ):
            module.ChooseAndPlaySenseUpgrade(player, effect, top_only=True)

        player.AskChooseFace.assert_called_once_with(
            [sense],
            effect,
            forced=True,
            peek=True,
            not_move=True,
        )
        player.PlayCardsLikeInTurn.assert_called_once_with(
            [sense],
            effect,
            ignore_resources_cost=False,
            forced=False,
            if_not_play_discard_it=False,
        )

    def test_sense_leaving_play_is_redirected_to_the_bottom(self):
        module = import_module("cards.pack.fne")
        ability = module.SenseDeckRuleAbilities()[0]
        player = MagicMock()
        deck = player.additional_deck
        effect = MagicMock()
        effect.GetInitiator.return_value = player
        message = MagicMock()
        message.trigger.GetOwnerPlayer.return_value = player

        ability.operation(effect, message)

        message.ChangeToBottomOfDeck.assert_called_once_with(deck, effect)

    def test_card_move_uses_a_replacement_effects_requested_index(self):
        card = MagicMock()
        replacement_message = MagicMock(index=0)
        card.CheckIfCanMove.return_value = replacement_message
        into_area = MagicMock()
        effect = MagicMock()

        Card.MoveToArea(card, into_area, effect)

        card.MoveToAreaInternal.assert_called_once_with(
            replacement_message,
            callback=None,
            target_game_area=None,
            index=0,
        )

    def test_card_discard_uses_a_replacement_effects_requested_index(self):
        card = MagicMock()
        replacement_message = MagicMock(index=0)
        card.CheckIfCanDiscard.return_value = (
            replacement_message,
            MagicMock(),
        )
        effect = MagicMock()

        Card.Discard(card, effect)

        move_call = card.MoveToAreaInternal.call_args
        self.assertIs(move_call.args[0], replacement_message)
        self.assertTrue(callable(move_call.kwargs["callback"]))
        self.assertEqual(move_call.kwargs["index"], 0)

    def test_free_sense_search_keeps_the_deck_order(self):
        module = import_module("cards.pack.fne")
        player = MagicMock()
        sense = MagicMock()
        player.AskChooseFace.return_value = sense
        effect = MagicMock()

        with patch.object(
            module,
            "GetPlayableSenseCards",
            return_value=[sense],
        ):
            module.ChooseAndPlaySenseUpgrade(
                player,
                effect,
                ignore_resources_cost=True,
            )

        player.AskChooseFace.assert_called_once_with(
            [sense],
            effect,
            forced=False,
            peek=True,
            not_move=True,
        )
        player.PlayCardsLikeInTurn.assert_called_once_with(
            [sense],
            effect,
            ignore_resources_cost=True,
            forced=True,
            if_not_play_discard_it=False,
        )

    def test_scheme_senses_require_your_identity_to_remove_last_threat(self):
        player = MagicMock()
        hero = self.controlled_face(Hero, player)
        ally = self.controlled_face(Ally, player)
        scheme = MagicMock()
        scheme.CastTo.return_value = SimpleNamespace(threat=2)
        message = SimpleNamespace(
            trigger=scheme,
            by_face=hero,
            value=2,
            is_be_instead=False,
            cannot_be_removed=False,
        )
        effect = SimpleNamespace(
            this=SimpleNamespace(
                card=SimpleNamespace(
                    area=SimpleNamespace(
                        flags=SimpleNamespace(is_obligations_area=False),
                    ),
                ),
            ),
            initiator=MagicMock(),
        )
        effect.initiator.IsScenario.return_value = False

        with patch("game.selector.Select.GetYou", return_value=player):
            for card_id in ("60002", "60003"):
                with self.subTest(card_id=card_id):
                    module = import_module(f"cards.pack.fne.sense_deck.{card_id}")
                    ability = module.GetAbilities()[2]
                    last_threat_by_you = ability.conditions[-1]

                    self.assertIs(
                        ability.when,
                        module.Message.WhenSchemeWouldRemoveThreat,
                    )
                    self.assertTrue(last_threat_by_you(effect, message))

                    message.by_face = ally
                    self.assertFalse(last_threat_by_you(effect, message))
                    message.by_face = hero

                    message.value = 1
                    self.assertFalse(last_threat_by_you(effect, message))
                    message.value = 3
                    self.assertTrue(last_threat_by_you(effect, message))
                    message.value = 2

                    for flag in ("is_be_instead", "cannot_be_removed"):
                        setattr(message, flag, True)
                        self.assertFalse(last_threat_by_you(effect, message))
                        setattr(message, flag, False)
                    scheme.CastTo.return_value = SimpleNamespace(threat=0)
                    self.assertFalse(last_threat_by_you(effect, message))
                    scheme.CastTo.return_value = SimpleNamespace(threat=2)

    def test_enhanced_olfaction_applies_its_next_card_discount(self):
        module = import_module("cards.pack.fne.sense_deck.60003")
        ability = module.GetAbilities()[2]
        player = MagicMock()
        effect = MagicMock()
        effect.GetInitiator.return_value = player

        with patch.object(module.Worlds, "UpdateNextCardPlayCost") as update:
            ability.operation(effect, MagicMock())

        update.assert_called_once_with(
            player,
            -2,
            effect,
            in_this="Phase",
        )

    def test_enemy_senses_require_your_identity_to_defeat_the_enemy(self):
        player = MagicMock()
        hero = self.controlled_face(Hero, player)
        ally = self.controlled_face(Ally, player)
        effect = MagicMock()
        effect.GetInitiator.return_value = player
        effect.this = SimpleNamespace(
            card=SimpleNamespace(
                area=SimpleNamespace(
                    flags=SimpleNamespace(is_obligations_area=False),
                ),
            ),
        )
        effect.initiator.IsScenario.return_value = False
        message = SimpleNamespace(
            is_be_instead=False,
            killer=hero,
        )

        with patch("game.selector.Select.GetYou", return_value=player):
            for card_id in ("60002", "60003"):
                with self.subTest(card_id=card_id):
                    module = import_module(f"cards.pack.fne.sense_deck.{card_id}")
                    with patch.object(
                        module.AbilityFactory,
                        "WhenUnitWouldBeDefeated",
                    ) as factory:
                        module.GetAbilities()
                    defeated_by_you = factory.call_args.kwargs["conditions"][0]

                    self.assertTrue(defeated_by_you(effect, message))

                    message.killer = ally
                    self.assertFalse(defeated_by_you(effect, message))
                    message.killer = self.controlled_face(Hero, MagicMock())
                    self.assertFalse(defeated_by_you(effect, message))
                    message.killer = None
                    self.assertFalse(defeated_by_you(effect, message))
                    message.killer = hero

                    message.is_be_instead = True
                    self.assertFalse(defeated_by_you(effect, message))
                    message.is_be_instead = False

    def test_deft_focus_reduces_a_sense_played_as_if_from_hand(self):
        fixture = TimingFixture(
            "deft_focus_sense_deck.json",
            "Deft Focus discounts a Sense card",
            "rhino",
            ("daredevil",),
            780078,
            (
                'Puzzle.ClearHand()',
                'Puzzle.CreateHandCards("16024", "01088")',
            ),
            ("16024", "01088"),
        )
        stage = 0
        discounted_cost = None
        played_sense_id = None

        def choice(option, resources=()):
            target_minimum = int(
                (option.get("target_num_range") or [0])[0]
            )
            targets = [
                str(
                    target.get("id", target)
                    if isinstance(target, dict)
                    else target
                )
                for target in option.get("all_legal_targets", [])[:target_minimum]
            ]
            return CommandDescriptor(
                str(option.get("choice_id") or option["id"]),
                targets,
                list(resources),
            )

        def choose(prompt):
            nonlocal stage, discounted_cost, played_sense_id
            player = Engine.game.world.const_players[0]

            if prompt.event_name == "WhenPlayerInTurn" and stage == 0:
                option = next(
                    option
                    for option in prompt.options
                    if option.get("name") == "Change_Form"
                )
                stage = 1
                return choice(option)

            if prompt.event_name == "WhenPlayerInTurn" and stage == 1:
                deft_focus = player.hand_cards.FindCard(name="Deft Focus")
                option = next(
                    option
                    for option in prompt.options
                    if option.get("name") == "Play"
                    and option.get("bind_id") == deft_focus.card.object_id
                )
                payments = next(iter(option["target_payment"].values()))[
                    "payment"
                ]
                payment_effect = str(next(iter(payments[0])))
                stage = 2
                return choice(option, [payment_effect])

            if prompt.event_name == "WhenPlayerInTurn" and stage == 2:
                deft_focus = Engine.game.world.FindCardsOnField(
                    name="Deft Focus"
                )[0]
                option = next(
                    option
                    for option in prompt.options
                    if option.get("bind_id") == deft_focus.card.object_id
                )
                stage = 3
                return choice(option)

            if prompt.event_name == "WhenPlayerInTurn" and stage == 3:
                played_sense_id = player.additional_deck.GetTop().paper.card_id
                option = next(
                    option
                    for option in prompt.options
                    if option.get("name") == "Superhuman_Senses"
                )
                stage = 4
                return choice(option)

            if prompt.event_name == "WhenPlayerLikeInTurn" and stage == 4:
                option = next(
                    option
                    for option in prompt.options
                    if option.get("name") == "Play"
                )
                discounted_cost = next(
                    iter(option["target_payment"].values())
                )["cost"]
                stage = 5
                return choice(option)

            if prompt.event_name == "WhenPlayerInTurn" and stage == 5:
                stage = 6
                return None

            return HeadlessDeviceManager._DefaultChoice(prompt)

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = run_scene_with_devices(
            build_fixture_scene(fixture),
            devices,
        )
        player = game.world.const_players[0]

        self.assertEqual(stage, 6)
        self.assertEqual(discounted_cost, "0")
        self.assertEqual(player.hand_cards.Get(), [])
        self.assertEqual(len(player.additional_deck.Get()), 4)
        self.assertTrue(
            game.world.FindCardsOnField(name="Deft Focus")[0].card.IsExhaust()
        )
        self.assertTrue(
            any(
                face.paper.card_id == played_sense_id
                for face in game.world.FindCardsOnField()
            )
        )


class TestDaredevilCards(unittest.TestCase):

    def test_nelson_and_murdock_accepts_any_attorney_defeating_the_scheme(self):
        module = import_module("cards.pack.fne.daredevil.60015")
        ability = module.GetAbilities()[0]
        attorney = MagicMock()
        effect = MagicMock()
        message = SimpleNamespace(
            killer=attorney,
            defeating_player=MagicMock(),
        )

        with patch.object(module.CardFinder, "Check", return_value=True):
            self.assertTrue(ability.conditions[-1](effect, message))

        self.assertNotEqual(message.defeating_player, effect.GetInitiator())

    def test_cross_examination_counts_attached_upgrades(self):
        module = import_module("cards.pack.fne.daredevil.60008")
        ability = module.GetAbilities()[0]
        enemy = MagicMock()
        enemy.GetAttachedUpgrades.return_value = [MagicMock(), MagicMock()]
        event = MagicMock()
        player = MagicMock()
        player.AskChooseOneText.return_value = 2
        effect = MagicMock()
        effect.targets = [enemy]
        effect.this.CastTo.return_value = event
        effect.GetInitiator.return_value = player

        ability.operation(effect, MagicMock())

        args = event.DealDamage.call_args.args
        self.assertEqual(args[:3], ([enemy], 5, effect))
        self.assertIsInstance(event.DealDamage.call_args.kwargs["property"], module.AttackProperty)
        player.AskChooseOneText.assert_called_once_with(
            [0, 1, 2],
            [
                "Deal 0 additional damage",
                "Deal 1 additional damage",
                "Deal 2 additional damage",
            ],
        )

    def test_deadliest_man_alive_adds_one_boost_card_to_bullseyes_attack(self):
        module = import_module("cards.pack.fne.daredevil_nemesis.60034")
        ability = module.GetAbilities()[0]
        effect = MagicMock()
        message = MagicMock()

        ability.operation(effect, message)

        message.GiveAdditionalBoostCardForThisActivation.assert_called_once_with(
            1,
            effect,
        )


if __name__ == "__main__":
    unittest.main()
