from importlib import import_module
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, call, patch

from engine import Engine  # noqa: F401 - establishes the project's import order
from cards.database import CardsDB
from engine.lib.version import Ver
from game.card.factory import CardFactory
from game.card.face.attribute.has_teamup import HasTeamUp
from game.effect.effect_checker import EffectChecker
from game.operate.worlds import Worlds
from game.world.world import World


ROOT = Path(__file__).resolve().parents[1]


def _make_status_effect(ability, status):
    role = MagicMock()
    role.IsStunned.return_value = status == "stunned"
    role.IsConfused.return_value = status == "confused"
    effect = MagicMock()
    effect.ability = ability
    effect.bind_message = None
    effect.context = SimpleNamespace(
        all_legal_targets=[],
        target_range=None,
    )
    effect.initiator.GetRoleCharacter.return_value = role
    effect.world.rule.v18_timing = False
    effect.world.rule.v16_confuse_stun = True
    return effect


class TestFearNoEvilContent(unittest.TestCase):

    def test_all_non_hero_player_cards_are_registered(self):
        cards = json.loads(
            (ROOT / "data" / "cards.json").read_text(encoding="utf-8")
        )["fne"]
        expected_ids = {
            *[f"600{i:02d}" for i in range(19, 32)],
            "60038",
            *[f"600{i:02d}" for i in range(48, 60)],
        }

        papers = {
            card["card_id"]: card
            for card in cards
            if card["card_id"] in expected_ids
        }
        self.assertEqual(set(papers), expected_ids)
        self.assertNotIn("Hero", {card.get("type") for card in papers.values()})
        self.assertNotIn("AlterEgo", {card.get("type") for card in papers.values()})

    def test_reprints_reuse_rules_without_hiding_available_fne_scans(self):
        cards = {
            card["card_id"]: card
            for card in json.loads(
                (ROOT / "data" / "cards.json").read_text(encoding="utf-8")
            )["fne"]
        }

        # Cerebro has no 60025 image, so this one intentionally uses the
        # original Chance Encounter printing and scan.
        self.assertEqual(cards["60025"], {
            "card_id": "60025",
            "full_link": "26034",
        })
        self.assertEqual(cards["60051"]["ability_link"], "32014")
        self.assertEqual(cards["60056"]["ability_link"], "40059")
        self.assertEqual(cards["60051"]["card_id"], "60051")
        self.assertEqual(cards["60056"]["card_id"], "60056")

    def test_every_new_script_imports_and_builds_abilities(self):
        scripted_ids = [
            *[f"600{i:02d}" for i in range(19, 25)],
            *[f"600{i:02d}" for i in range(26, 32)],
            "60038",
            *[f"600{i:02d}" for i in range(48, 51)],
            *[f"600{i:02d}" for i in range(52, 56)],
        ]

        for card_id in scripted_ids:
            with self.subTest(card_id=card_id):
                abilities = import_module(
                    f"cards.pack.fne.{card_id}"
                ).GetAbilities()
                self.assertTrue(abilities)

    def test_all_fne_player_cards_initialize_through_the_card_factory(self):
        Ver.Initialize()
        CardsDB.Initialize()
        world = MagicMock()
        world.GetPlayerNumIcon.return_value = 1

        for card_id in [
            *[f"600{i:02d}" for i in range(19, 32)],
            "60038",
            *[f"600{i:02d}" for i in range(48, 60)],
        ]:
            with self.subTest(card_id=card_id):
                paper = CardsDB.FindCardPaper(card_id)
                face = CardFactory.CreateFace(paper, world)
                self.assertEqual(face.paper.card_id, card_id)

    def test_team_up_cards_use_team_up_as_the_first_selector(self):
        for card_id in ["60031", "60055"]:
            with self.subTest(card_id=card_id):
                play_ability = next(
                    ability
                    for ability in import_module(
                        f"cards.pack.fne.{card_id}"
                    ).GetAbilities()
                    if ability.is_play
                )
                self.assertEqual(
                    play_ability.selectors[0].target_text,
                    "TeamUp",
                )

    def test_team_up_selector_accepts_dance_with_the_devil_upgrade(self):
        helper = import_module("game.selector.selector_target_helper")
        Ver.Initialize()
        CardsDB.Initialize()
        world = MagicMock()
        world.GetPlayerNumIcon.return_value = 1
        upgrade = CardFactory.CreateFace(
            CardsDB.FindCardPaper("60031"),
            world,
        )
        team_up_units = [MagicMock(), MagicMock()]
        effect = SimpleNamespace(this=upgrade)

        with patch.object(
            upgrade,
            "GetTeamUpUnits",
            return_value=team_up_units,
        ):
            targets = helper.get_TeamUp(effect)

        self.assertEqual(targets, team_up_units)
        self.assertTrue(helper.HasTeamUp.IsType(upgrade))

    def test_team_up_matches_an_identity_and_an_ally(self):
        daredevil_identity = MagicMock()
        daredevil_identity.IsName.side_effect = lambda name: name == "Daredevil"
        daredevil_identity.IsSubName.return_value = False
        echo_ally = MagicMock()
        echo_ally.IsName.side_effect = lambda name: name == "Echo"
        echo_ally.IsSubName.return_value = False
        team_up_card = SimpleNamespace(
            team_up=[["Daredevil"], ["Echo"]],
            card=SimpleNamespace(game_area=MagicMock()),
        )

        with patch.object(
            Worlds,
            "GetOnFieldFriendlyCharacters",
            return_value=[daredevil_identity, echo_ally],
        ):
            targets = HasTeamUp.GetTeamUpUnits(team_up_card)

        self.assertCountEqual(targets, [daredevil_identity, echo_ally])

    def test_status_cards_do_not_bypass_team_up_play_restrictions(self):
        ability = import_module("cards.pack.fne.60055").GetAbilities()[0]
        selector = ability.selectors[0]

        for status in ["stunned", "confused"]:
            for team_up_count in [0, 1]:
                with self.subTest(status=status, team_up_count=team_up_count):
                    effect = _make_status_effect(ability, status)

                    with patch.object(
                        selector,
                        "GetAllLegalTargets",
                        return_value=[MagicMock() for _ in range(team_up_count)],
                    ):
                        self.assertFalse(
                            EffectChecker(effect).UpdateLegalTargets()
                        )

    def test_status_cancelled_team_up_card_is_playable_when_both_are_present(self):
        ability = import_module("cards.pack.fne.60055").GetAbilities()[0]
        selector = ability.selectors[0]

        for status in ["stunned", "confused"]:
            with self.subTest(status=status):
                effect = _make_status_effect(ability, status)

                with patch.object(
                    selector,
                    "GetAllLegalTargets",
                    return_value=[MagicMock(), MagicMock()],
                ):
                    self.assertTrue(EffectChecker(effect).UpdateLegalTargets())

                self.assertEqual(effect.context.all_legal_targets, [])
                self.assertEqual(effect.context.target_range, (0, 0))

    def test_status_cards_still_waive_ordinary_target_requirements(self):
        ability = import_module("cards.pack.fne.60023").GetAbilities()[-1]
        effect = _make_status_effect(ability, "confused")

        with patch.object(
            ability.selectors[0],
            "GetAllLegalTargets",
        ) as get_targets:
            self.assertTrue(EffectChecker(effect).UpdateLegalTargets())

        get_targets.assert_not_called()
        self.assertEqual(effect.context.target_range, (0, 0))

    def test_innate_reflexes_attaches_to_its_owners_identity(self):
        play_ability = import_module(
            "cards.pack.fne.60038"
        ).GetAbilities()[0]

        self.assertEqual(
            play_ability.selectors[0].target_text,
            "YourIdentity",
        )

    def test_stealth_training_response_is_not_thwart_labeled(self):
        response = import_module(
            "cards.pack.fne.60028"
        ).GetAbilities()[1]

        self.assertEqual(response.labels, [])


class TestStartingTiming(unittest.TestCase):

    @patch("game.operate.faces.Faces.MoveAllTo")
    def test_only_starting_cards_still_in_the_deck_are_offered(self, move_all_to):
        player = MagicMock()
        player_deck = player.player_deck
        hand = player.hand_cards

        starting = MagicMock(name="starting")
        starting.kind = "starting"
        starting.name = "Innate Reflexes"
        starting.printed_starting = 1
        starting.card.area = player_deck

        setup_moved = MagicMock(name="setup_moved")
        setup_moved.kind = "starting"
        setup_moved.name = "Future Starting Card"
        setup_moved.printed_starting = 1
        setup_moved.card.area = object()

        ordinary = MagicMock(name="ordinary")
        ordinary.kind = "ordinary"

        player.player_deck.GetAll.return_value = [
            starting,
            setup_moved,
            ordinary,
        ]
        player.AskChooseOneText.return_value = True
        world = SimpleNamespace(const_players=[player])
        effect = MagicMock()

        with patch(
            "game.world.world.HasStarting.IsType",
            side_effect=lambda face: face.kind == "starting",
        ):
            World.ResolveStartingCardChoices(world, effect)

        player.AskChooseOneText.assert_called_once()
        move_all_to.assert_called_once_with([starting], hand, effect)

    def test_starting_resolution_is_after_setup_and_before_opening_draw(self):
        source = inspect.getsource(World.Initialize)

        self.assertLess(
            source.index("ResolveTeamUpAllyRemovalChoices"),
            source.index("ResolveStartingCardChoices"),
        )
        self.assertLess(
            source.index("ResolveStartingCardChoices"),
            source.index('DrawUp("Max"'),
        )


class TestFearNoEvilMechanics(unittest.TestCase):

    def test_blindspot_triggers_after_non_basic_thwarts(self):
        module = import_module("cards.pack.fne.60019")
        ability = module.GetAbilities()[0]
        finder = ability.selectors[0].selector_filter.finder
        self.assertIs(finder.with_attach, module.Upgrade)
        blindspot = MagicMock()
        card = MagicMock()
        blindspot.card = card
        effect = MagicMock(this=blindspot)
        message = MagicMock(trigger=blindspot)
        message.trigger.card = card
        message.IsBasicThwart.return_value = False

        basic_thwart_condition = ability.const_condition[1]
        self.assertTrue(basic_thwart_condition(effect, message))

        with patch.object(module.Faces, "GiveStatus") as give_status:
            effect.targets = [MagicMock()]
            ability.operation(effect, message)

        give_status.assert_called_once_with(
            effect.targets,
            "Confused",
            effect,
        )

    def test_cloak_finds_and_puts_dagger_into_play(self):
        module = import_module("cards.pack.fne.60020")
        ability = module.GetAbilities()[0]
        player = MagicMock()
        effect = MagicMock()
        effect.GetInitiator.return_value = player

        self.assertEqual(ability.cost_fn(effect, []).y, 2)
        self.assertEqual(len(ability.cost_funcs), 1)

        with patch.object(module.Find, "FindAndPutIntoPlay") as find_dagger:
            ability.operation(effect, MagicMock())

        find_dagger.assert_called_once_with(
            effect,
            player,
            name="Dagger",
            card_type=module.Ally,
        )

    def test_ghost_rider_uses_the_correct_cost_and_confuses_attacked_enemy(self):
        module = import_module("cards.pack.fne.60022")
        minion_ability, villain_ability = module.GetAbilities()

        self.assertEqual(minion_ability.cost_fn(MagicMock(), []).y, 1)
        self.assertEqual(villain_ability.cost_fn(MagicMock(), []).y, 2)

        message = MagicMock()
        message.attacked_targets = [MagicMock()]
        effect = MagicMock()
        with patch.object(module.Faces, "GiveStatus") as give_status:
            minion_ability.operation(effect, message)

        give_status.assert_called_once_with(
            message.attacked_targets,
            "Confused",
            effect,
        )

    def test_know_your_enemy_resolves_two_separate_threat_removals(self):
        module = import_module("cards.pack.fne.60023")
        ability = module.GetAbilities()[-1]
        event = MagicMock()
        effect = MagicMock()
        effect.this.CastTo.return_value = event
        effect.targets = [MagicMock(name="first_scheme")]
        effect.targets2 = [MagicMock(name="second_scheme")]

        ability.operation(effect, MagicMock())

        self.assertEqual(event.RemoveThreatFromSchemes.call_args_list, [
            call(effect.targets, 1, effect),
            call(effect.targets2, 1, effect),
        ])

    def test_de_escalation_removes_one_chosen_acceleration_token(self):
        module = import_module("cards.pack.fne.60024")
        ability = module.GetAbilities()[0]
        effect = MagicMock()
        token_face = MagicMock()

        with patch.object(
            module.Worlds,
            "GetAccelerationTokenFaces",
            return_value=[token_face],
        ), patch.object(
            module.Filter,
            "One",
            return_value=token_face,
        ), patch.object(module.Faces, "RemoveTokensOn") as remove_tokens:
            ability.operation(effect, MagicMock())

        remove_tokens.assert_called_once_with(
            [token_face],
            1,
            "acceleration_token",
            effect,
        )

    def test_legal_trouble_applies_minus_two_scheme_to_attached_minion(self):
        module = import_module("cards.pack.fne.60026")
        marker = MagicMock()
        with patch.object(
            module.AbilityFactory,
            "GiveKeywordToAttached",
            return_value=[marker],
        ) as give_keyword:
            abilities = module.GetAbilities()

        self.assertIn(marker, abilities)
        give_keyword.assert_called_once_with(module.Minion, scheme=-2)

    def test_move_in_shadow_removes_threat_after_a_card_is_played(self):
        module = import_module("cards.pack.fne.60027")
        ability = module.GetAbilities()[-1]
        upgrade = MagicMock()
        effect = MagicMock()
        effect.this.CastTo.return_value = upgrade
        effect.targets = [MagicMock()]

        ability.operation(effect, MagicMock())

        upgrade.RemoveThreatFromSchemes.assert_called_once_with(
            effect.targets,
            1,
            effect,
        )

    def test_stealth_training_stuns_its_selected_enemy(self):
        module = import_module("cards.pack.fne.60028")
        ability = module.GetAbilities()[-1]
        effect = MagicMock()
        effect.targets = [MagicMock()]

        with patch.object(module.Faces, "GiveStatus") as give_status:
            ability.operation(effect, MagicMock())

        give_status.assert_called_once_with(
            effect.targets,
            "Stunned",
            effect,
        )

    def test_stick_builds_both_basic_power_choices(self):
        module = import_module("cards.pack.fne.60029")
        ability = module.GetAbilities()[0]
        finder = inspect.getclosurevars(
            ability.const_condition[0]
        ).nonlocals["which_unit"]
        self.assertIs(finder.card_type, module.Friend)
        support = MagicMock()
        player = MagicMock()
        effect = MagicMock()
        effect.this.CastTo.return_value = support
        effect.GetInitiator.return_value = player
        message = MagicMock()

        ability.operation(effect, message)

        args = player.ChooseAbilities.call_args.args
        self.assertIs(args[0], effect)
        increase, reduce = args[1:]
        self.assertEqual(len(increase.cost_funcs), 1)
        self.assertFalse(reduce.NeedCost())

        choice_effect = MagicMock()
        choice_effect.targets = []
        with patch.object(module.Faces, "ReadyAll") as ready_all:
            reduce.operation(choice_effect, MagicMock())
        message.GainValue.assert_called_once_with(-1, effect)
        ready_all.assert_called_once_with([support], effect)

    def test_contingency_planning_filters_and_tucks_attachable_upgrades(self):
        module = import_module("cards.pack.fne.60030")
        ability = module.GetAbilities()[-1]
        check_fn = ability.selectors[0].selector_filter.finder.check_effect_fns[0]
        effect = MagicMock()

        attachable = MagicMock()
        attachable.CastTo.return_value = attachable
        attachable.ability.Find.return_value = [SimpleNamespace(
            selectors=[SimpleNamespace(
                selector_filter=SimpleNamespace(
                    finder=SimpleNamespace(card_type=module.Minion),
                ),
                target_text=None,
            )],
        )]
        identity_only = MagicMock()
        identity_only.CastTo.return_value = identity_only
        identity_only.ability.Find.return_value = [SimpleNamespace(
            selectors=[SimpleNamespace(
                selector_filter=SimpleNamespace(
                    finder=SimpleNamespace(card_type=module.Identity),
                ),
                target_text="YourIdentity",
            )],
        )]

        self.assertTrue(check_fn(effect, attachable))
        self.assertFalse(check_fn(effect, identity_only))

        upgrade = MagicMock()
        effect.this.CastTo.return_value = upgrade
        effect.targets = [attachable]
        ability.operation(effect, MagicMock())
        upgrade.TuckCardUnderHere.assert_called_once_with(
            effect.targets,
            effect,
        )

    def test_dance_with_the_devil_attaches_then_damages_attached_enemy(self):
        module = import_module("cards.pack.fne.60031")
        play_ability, action_ability = module.GetAbilities()
        upgrade = MagicMock()
        enemy = MagicMock()
        effect = MagicMock()
        effect.this.CastTo.return_value = upgrade
        effect.targets2 = [enemy]

        with patch.object(module.Filter, "One", return_value=enemy):
            play_ability.operation(effect, MagicMock())
        upgrade.AttachTo2.assert_called_once_with(enemy, effect)

        effect.targets = [enemy]
        action_ability.operation(effect, MagicMock())
        upgrade.DealDamage.assert_called_once_with([enemy], 3, effect)

    def test_innate_reflexes_grants_one_defense_to_the_attached_hero(self):
        module = import_module("cards.pack.fne.60038")
        marker = MagicMock()
        with patch.object(
            module.AbilityFactory,
            "GiveKeywordToAttached",
            return_value=[marker],
        ) as give_keyword:
            abilities = module.GetAbilities()

        self.assertIn(marker, abilities)
        give_keyword.assert_called_once_with(module.Hero, defense=1)

    def test_ally_scaled_cost_counts_controlled_allies(self):
        army_ability = import_module("cards.pack.fne.60048").GetAbilities()[0]
        harm_ability = import_module("cards.pack.fne.60050").GetAbilities()[0]
        player = MagicMock()
        player.GetControlAllies.return_value = [MagicMock(), MagicMock()]
        effect = MagicMock()
        effect.GetInitiator.return_value = player
        message = MagicMock()

        army_ability.operation(effect, message)
        harm_ability.operation(effect, message)

        self.assertEqual(message.UpdateCost.call_args_list, [
            call(2, effect),
            call(2, effect),
        ])

    def test_army_of_one_readies_your_hero(self):
        module = import_module("cards.pack.fne.60048")
        ability = module.GetAbilities()[-1]
        effect = MagicMock()
        effect.targets = [MagicMock()]

        with patch.object(module.Faces, "ReadyAll") as ready_all:
            ability.operation(effect, MagicMock())

        ready_all.assert_called_once_with(effect.targets, effect)

    def test_get_their_attention_removes_three_threat(self):
        module = import_module("cards.pack.fne.60049")
        ability = module.GetAbilities()[0]
        event = MagicMock()
        effect = MagicMock()
        effect.this.CastTo.return_value = event
        effect.targets = [MagicMock()]

        ability.operation(effect, MagicMock())

        event.RemoveThreatFromSchemes.assert_called_once_with(
            effect.targets,
            3,
            effect,
        )

    def test_in_harms_way_uses_current_defense_for_both_effects(self):
        module = import_module("cards.pack.fne.60050")
        ability = module.GetAbilities()[-1]
        event = MagicMock()
        hero = MagicMock(defense=4)
        identity = MagicMock()
        identity.CastTo.return_value = hero
        player = MagicMock()
        player.GetIdentity.return_value = identity
        effect = MagicMock()
        effect.this.CastTo.return_value = event
        effect.GetInitiator.return_value = player
        effect.targets = [MagicMock(name="enemy")]
        effect.targets2 = [MagicMock(name="scheme")]

        ability.operation(effect, MagicMock())

        event.DealDamage.assert_called_once_with(effect.targets, 4, effect)
        event.RemoveThreatFromSchemes.assert_called_once_with(
            effect.targets2,
            4,
            effect,
        )

    def test_in_harms_way_is_playable_when_either_half_has_a_target(self):
        ability = import_module("cards.pack.fne.60050").GetAbilities()[-1]
        enemy_selector, scheme_selector = ability.selectors

        self.assertTrue(enemy_selector.is_optional)
        self.assertTrue(scheme_selector.is_optional)

        for enemy_targets, scheme_targets in [
            ([MagicMock(name="enemy")], []),
            ([], [MagicMock(name="scheme")]),
        ]:
            with self.subTest(
                has_enemy=bool(enemy_targets),
                has_scheme=bool(scheme_targets),
            ):
                effect = MagicMock()
                effect.ability = ability
                effect.bind_message = None
                effect.context = SimpleNamespace(
                    all_legal_targets=[],
                    target_range=None,
                )
                effect.world.rule.v16_confuse_stun = False

                with patch.object(
                    enemy_selector,
                    "GetAllLegalTargets",
                    return_value=enemy_targets,
                ), patch.object(
                    scheme_selector,
                    "GetAllLegalTargets",
                    return_value=scheme_targets,
                ):
                    self.assertTrue(
                        EffectChecker(effect).UpdateLegalTargets()
                    )

    def test_confused_cancels_all_of_in_harms_way(self):
        ability = import_module("cards.pack.fne.60050").GetAbilities()[-1]
        effect = _make_status_effect(ability, "confused")

        self.assertEqual(ability.labels, ["attack", "thwart"])
        with patch.object(
            ability.selectors[0],
            "GetAllLegalTargets",
        ) as get_enemies, patch.object(
            ability.selectors[1],
            "GetAllLegalTargets",
        ) as get_schemes:
            self.assertTrue(EffectChecker(effect).UpdateLegalTargets())

        get_enemies.assert_not_called()
        get_schemes.assert_not_called()
        self.assertEqual(effect.context.all_legal_targets, [])
        self.assertEqual(effect.context.target_range, (0, 0))

    def test_dagger_only_reduces_consequential_damage_with_cloak_in_play(self):
        module = import_module("cards.pack.fne.60021")
        ability = module.GetAbilities()[-1]
        effect = MagicMock()
        message = MagicMock()
        cloak_condition = ability.const_condition[-1]

        with patch.object(
            module.Worlds,
            "FindCardOnField",
            return_value=MagicMock(),
        ):
            self.assertTrue(cloak_condition(effect, message))
            ability.operation(effect, message)
        message.ReduceDamage.assert_called_once_with(1, effect)

        message.reset_mock()
        with patch.object(
            module.Worlds,
            "FindCardOnField",
            return_value=None,
        ):
            self.assertFalse(cloak_condition(effect, message))
        message.ReduceDamage.assert_not_called()

    def test_dagger_suppresses_all_of_cloaks_acceleration_icons(self):
        module = import_module("cards.pack.fne.60021")
        marker = MagicMock()
        with patch.object(
            module.AbilityFactory,
            "GiveKeywordToInPlayWhenApplyThis",
            return_value=[marker],
        ) as give_keyword:
            abilities = module.GetAbilities()

        self.assertIn(marker, abilities)
        apply = give_keyword.call_args.kwargs["apply"]
        cloak = MagicMock()
        cloak.CastTo.return_value = cloak
        effect = MagicMock()
        apply(effect, cloak, 1)
        cloak.SetIgnoreAccelerationIcon.assert_called_once_with(1, effect)

    def test_stealth_training_requires_an_exact_defeat(self):
        ability = import_module("cards.pack.fne.60028").GetAbilities()[1]
        exact_condition = ability.const_condition[-1]
        effect = MagicMock()

        self.assertTrue(
            exact_condition(effect, SimpleNamespace(exact_defeat=True))
        )
        self.assertFalse(
            exact_condition(effect, SimpleNamespace(exact_defeat=False))
        )

    def test_best_offense_replaces_attack_and_thwart_everywhere(self):
        module = import_module("cards.pack.fne.60052")
        buff = module.BuffUseDefenseForAttackAndThwart()
        hero = MagicMock()
        hero.GetBuff.return_value = buff
        hero.GetKeyword.side_effect = lambda keyword: {
            "ATK": 2,
            "THW": 1,
            "DEF": 4,
        }[keyword]
        hero.CastTo.return_value = SimpleNamespace(defense=4)
        effect = MagicMock()

        attack = module.HasAttack.attack.fget
        thwart = module.HasThwart.thwart.fget
        self.assertIsNotNone(attack)
        self.assertIsNotNone(thwart)

        with patch.object(module.HasDefense, "IsType", return_value=True):
            self.assertEqual(attack(hero), 2)
            self.assertEqual(thwart(hero), 1)

            module.apply_the_best_offense(effect, hero, 1)
            self.assertEqual(attack(hero), 4)
            self.assertEqual(thwart(hero), 4)

            module.apply_the_best_offense(effect, hero, -1)
            self.assertEqual(attack(hero), 2)
            self.assertEqual(thwart(hero), 1)

        marker = MagicMock()
        with patch.object(
            module.AbilityFactory,
            "GiveKeywordToAttached",
            return_value=[marker],
        ) as give_keyword:
            abilities = module.GetAbilities()

        self.assertIn(marker, abilities)
        self.assertEqual(give_keyword.call_args.kwargs["defense"], 1)
        self.assertIs(
            give_keyword.call_args.kwargs["apply"],
            module.apply_the_best_offense,
        )

    def test_ronin_grants_defense_and_retaliate_only_without_allies(self):
        module = import_module("cards.pack.fne.60053")
        marker = MagicMock()
        with patch.object(
            module.AbilityFactory,
            "GiveKeywordToInPlayWhenApplyThis",
            return_value=[marker],
        ) as give_keyword:
            abilities = module.GetAbilities()

        self.assertIn(marker, abilities)
        kwargs = give_keyword.call_args.kwargs
        self.assertEqual(kwargs["control_by"], "You")
        self.assertEqual(kwargs["defense"], 1)
        self.assertEqual(kwargs["retaliate"], 1)

        player = MagicMock()
        effect = MagicMock()
        effect.GetInitiator.return_value = player
        player.GetControlAllies.return_value = []
        self.assertTrue(kwargs["condition"](effect))
        player.GetControlAllies.return_value = [MagicMock()]
        self.assertFalse(kwargs["condition"](effect))

    def test_stand_alone_requires_no_allies_and_readies_your_hero(self):
        module = import_module("cards.pack.fne.60054")
        ability = module.GetAbilities()[-1]
        player = MagicMock()
        effect = MagicMock()
        effect.GetInitiator.return_value = player
        condition = ability.const_condition[-1]

        player.GetControlAllies.return_value = []
        self.assertTrue(condition(effect, MagicMock()))
        player.GetControlAllies.return_value = [MagicMock()]
        self.assertFalse(condition(effect, MagicMock()))

        effect.targets = [MagicMock()]
        with patch.object(module.Faces, "ReadyAll") as ready_all:
            ability.operation(effect, MagicMock())
        ready_all.assert_called_once_with(effect.targets, effect)

    def test_see_no_evil_allows_the_same_choice_twice(self):
        module = import_module("cards.pack.fne.60055")
        ability = module.GetAbilities()[0]
        event = MagicMock()
        player = MagicMock()
        effect = MagicMock()
        effect.this.CastTo.return_value = event
        effect.GetInitiator.return_value = player

        ability.operation(effect, MagicMock())

        args = player.ChooseAbilities.call_args.args
        kwargs = player.ChooseAbilities.call_args.kwargs
        self.assertIs(args[0], effect)
        damage_choice, thwart_choice = args[1:]
        self.assertEqual(kwargs["repeat"], 2)
        self.assertFalse(kwargs.get("choose_x_different_options"))

        enemy = MagicMock()
        damage_effect = MagicMock()
        damage_effect.targets = [enemy]
        damage_choice.operation(damage_effect, MagicMock())
        event.DealDamage.assert_called_once_with([enemy], 3, effect)

        scheme = MagicMock()
        thwart_effect = MagicMock()
        thwart_effect.targets = [scheme]
        thwart_choice.operation(thwart_effect, MagicMock())
        event.RemoveThreatFromSchemes.assert_called_once_with(
            [scheme],
            3,
            effect,
        )


if __name__ == "__main__":
    unittest.main()
