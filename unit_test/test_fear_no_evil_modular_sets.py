from importlib import import_module
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from engine import Engine  # noqa: F401 - establishes the project's import order
from cards.database import CardsDB
from core.utility.types import Types
from engine.lib.version import Ver
from game.card.factory import CardFactory


ROOT = Path(__file__).resolve().parents[1]
MODULAR_SET_ORDER = [
    "disasters",
    "cops",
    "drive",
    "the_owl",
    "tombstone",
    "tracksuit_mafia",
]
REMAINING_CARD_IDS = (
    [str(card_id) for card_id in range(60177, 60182)]
    + [str(card_id) for card_id in range(60186, 60191)]
    + [str(card_id) for card_id in range(60195, 60205)]
)


def find_condition(ability, name):
    return next(condition for condition in ability.conditions if condition.__name__ == name)


class TestFearNoEvilModularSetRegistration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Ver.Initialize()
        CardsDB.Initialize()

    def test_all_twenty_unique_cards_initialize_through_card_factory(self):
        world = MagicMock()
        world.GetPlayerNumIcon.return_value = 1

        for card_id in REMAINING_CARD_IDS:
            with self.subTest(card_id=card_id):
                paper = CardsDB.FindCardPaper(card_id)
                face = CardFactory.CreateFace(paper, world)
                self.assertEqual(face.paper.card_id, card_id)
                self.assertTrue(face.ability.abilities)

    def test_all_six_modular_sets_are_registered_in_printed_order(self):
        sets_info = json.loads(
            (ROOT / "data" / "sets_info.json").read_text(encoding="utf-8")
        )["60. Fear No Evil"]

        self.assertEqual(sets_info["encounters"], MODULAR_SET_ORDER)
        self.assertEqual(sets_info["max_id"], "60210")

    def test_encounter_files_have_the_printed_cards_and_copy_counts(self):
        expected = {
            "disasters": [str(card_id) for card_id in range(60177, 60182)],
            "drive": [str(card_id) for card_id in range(60186, 60191)],
            "tombstone": [str(card_id) for card_id in range(60195, 60200)],
            "tracksuit_mafia": [
                "60200",
                "60201",
                "60202",
                "60203",
                "60203",
                "60203",
                "60204",
            ],
        }

        for slug, cards in expected.items():
            with self.subTest(slug=slug):
                encounter = json.loads(
                    (ROOT / "data" / "encounter_sets" / f"{slug}.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(encounter["encounters"], cards)

    def test_printed_stats_traits_and_keywords_match_the_scans(self):
        papers = {
            paper["card_id"]: paper
            for paper in json.loads(
                (ROOT / "data" / "cards.json").read_text(encoding="utf-8")
            )["fne"]
        }

        for card_id in ("60177", "60178", "60179"):
            self.assertEqual(papers[card_id]["desc"]["Uses"], "2,civilian")
            self.assertEqual(papers[card_id]["desc"]["Crisis"], "1")
            self.assertEqual(papers[card_id]["traits"], ["DISASTER"])
        self.assertEqual(
            papers["60180"]["desc"],
            {"StartingThreat": "1*", "Hinder": "2*", "Hazard": "1", "Boost": "2"},
        )
        self.assertEqual(papers["60181"]["desc"]["Peril"], "1")

        self.assertEqual(papers["60186"]["desc"]["ATK+"], "1")
        self.assertEqual(papers["60187"]["desc"]["SCH+"], "1")
        self.assertEqual(papers["60187"]["desc"]["THW+"], "1")
        self.assertEqual(papers["60189"]["desc"]["Acceleration"], "1")
        self.assertEqual(papers["60189"]["desc"]["StartingThreat"], "2*")

        self.assertEqual(papers["60195"]["desc"]["SCH+"], "2")
        self.assertEqual(papers["60196"]["desc"]["ATK+"], "2")
        self.assertEqual(papers["60197"]["desc"]["Villainous"], "1")
        self.assertEqual(papers["60198"]["desc"]["Boost"], "0")
        self.assertEqual(papers["60199"]["desc"]["StartingThreat"], "3*")

        self.assertEqual(papers["60200"]["desc"]["Teamwork"], "TRACKSUIT")
        self.assertEqual(papers["60201"]["desc"]["Villainous"], "1")
        self.assertEqual(papers["60202"]["desc"]["Retaliate"], "2")
        self.assertEqual(papers["60202"]["desc"]["Vulnerable"], "1")
        self.assertEqual(papers["60203"]["desc"]["Vulnerable"], "1")
        self.assertEqual(papers["60204"]["desc"]["StartingThreat"], "3*")

    def test_disasters_icons_initialize_on_runtime_faces(self):
        world = MagicMock()
        world.GetPlayerNumIcon.return_value = 1

        for card_id in ("60177", "60178", "60179"):
            with self.subTest(card_id=card_id):
                environment = CardFactory.CreateFace(
                    CardsDB.FindCardPaper(card_id),
                    world,
                )
                self.assertEqual(environment.printed_crisis, 1)

        collapsing_bridge = CardFactory.CreateFace(
            CardsDB.FindCardPaper("60180"),
            world,
        )
        self.assertEqual(collapsing_bridge.printed_hazard, 1)
        self.assertEqual(collapsing_bridge.printed_crisis, 0)

    def test_cards_and_set_info_checksums_are_current(self):
        for filename in ("cards.json", "sets_info.json"):
            with self.subTest(filename=filename):
                data = json.loads(
                    (ROOT / "data" / filename).read_text(encoding="utf-8")
                )
                stored = data.pop("checksum")
                self.assertEqual(stored, Types.DictChecksum(data))


class TestDisastersMechanics(unittest.TestCase):

    def test_each_rescue_action_offers_its_printed_resource_or_exhaust_cost(self):
        cases = {
            "60177": ("g", "HasTrait"),
            "60178": ("y", "HasTrait"),
            "60179": ("r", "IsTough"),
        }

        for card_id, (resource, bonus_method) in cases.items():
            with self.subTest(card_id=card_id):
                module = import_module(f"cards.pack.fne.disasters.{card_id}")
                ability = module.GetAbilities()[0]
                environment = MagicMock()
                player = MagicMock()
                effect = MagicMock()
                effect.this.CastTo.return_value = environment
                effect.GetInitiator.return_value = player

                ability.operation(effect, MagicMock())
                pay, exhaust = player.ChooseAbilities.call_args.args[1:]
                cost = pay.GetCost(MagicMock(), [])
                self.assertEqual(getattr(cost, resource), 2)
                self.assertEqual(cost.val, 2)
                self.assertEqual(len(exhaust.cost_funcs), 1)

                character = MagicMock()
                character.HasTrait.return_value = True
                character.IsTough.return_value = True
                cost_result = SimpleNamespace(return_exhausted_cards=[character])
                choice_effect = SimpleNamespace(
                    targets=[],
                    cost_func=SimpleNamespace(Get=MagicMock(return_value=cost_result)),
                    GetPaidResources=MagicMock(),
                )
                with (
                    patch.object(module.Unit2, "IsType", return_value=True),
                    patch.object(module.Faces, "RemoveCountersOn") as remove,
                ):
                    exhaust.operation(choice_effect, MagicMock())

                remove.assert_called_once_with(
                    [environment],
                    2,
                    "civilian",
                    effect,
                )
                if bonus_method == "HasTrait":
                    character.HasTrait.assert_called_once()
                else:
                    character.IsTough.assert_called_once()

    def test_exhausting_a_nonmatching_character_only_removes_one_civilian(self):
        module = import_module("cards.pack.fne.disasters.60177")
        ability = module.GetAbilities()[0]
        environment = MagicMock()
        player = MagicMock()
        effect = MagicMock()
        effect.this.CastTo.return_value = environment
        effect.GetInitiator.return_value = player
        ability.operation(effect, MagicMock())
        exhaust = player.ChooseAbilities.call_args.args[2]
        character = MagicMock()
        character.HasTrait.return_value = False
        choice_effect = SimpleNamespace(
            targets=[],
            cost_func=SimpleNamespace(
                Get=MagicMock(
                    return_value=SimpleNamespace(return_exhausted_cards=[character])
                )
            ),
            GetPaidResources=MagicMock(),
        )

        with patch.object(module.Faces, "RemoveCountersOn") as remove:
            exhaust.operation(choice_effect, MagicMock())

        remove.assert_called_once_with([environment], 1, "civilian", effect)

    def test_collapsing_bridge_replaces_one_threat_after_any_removal(self):
        module = import_module("cards.pack.fne.disasters.60180")
        ability = module.GetAbilities()[0]
        bridge = MagicMock()
        effect = MagicMock()
        effect.this.CastTo.return_value = bridge

        ability.operation(effect, SimpleNamespace(value=4))

        bridge.PlaceThreatOnSchemes.assert_called_once_with([bridge], 1, effect)

    def test_bystanders_places_a_counter_without_searching_when_possible(self):
        module = import_module("cards.pack.fne.disasters.60181")
        ability = module.GetAbilities()[0]
        environment = MagicMock()
        player = MagicMock()
        player.AskChooseFace.return_value = environment
        message = SimpleNamespace(GetToPlayer=MagicMock(return_value=player))

        with (
            patch.object(module.Worlds, "FindCardsOnField", return_value=[environment]),
            patch.object(module.Faces, "PlaceCountersOn", return_value=1) as place,
            patch.object(module.Search, "EncounterCard") as search,
        ):
            ability.operation(MagicMock(), message)

        place.assert_called_once()
        search.assert_not_called()

    def test_bystanders_searches_and_reveals_when_no_counter_can_be_placed(self):
        module = import_module("cards.pack.fne.disasters.60181")
        ability = module.GetAbilities()[0]
        found = MagicMock()
        player = MagicMock()
        message = SimpleNamespace(GetToPlayer=MagicMock(return_value=player))
        effect = MagicMock()

        with (
            patch.object(module.Worlds, "FindCardsOnField", return_value=[]),
            patch.object(module.Search, "EncounterCard", return_value=found) as search,
        ):
            ability.operation(effect, message)

        self.assertTrue(search.call_args.kwargs["include_discard_pile"])
        self.assertEqual(search.call_args.kwargs["trait"], "DISASTER")
        found.Reveal.assert_called_once_with(player, effect)

    def test_bystanders_handles_an_empty_search_and_boost_has_no_search_fallback(self):
        module = import_module("cards.pack.fne.disasters.60181")
        reveal_ability, boost_ability = module.GetAbilities()
        player = MagicMock()
        message = SimpleNamespace(GetToPlayer=MagicMock(return_value=player))

        with (
            patch.object(module.Worlds, "FindCardsOnField", return_value=[]),
            patch.object(module.Search, "EncounterCard", return_value=None) as search,
        ):
            reveal_ability.operation(MagicMock(), message)
            boost_ability.operation(MagicMock(), message)

        search.assert_called_once()


class TestDriveMechanics(unittest.TestCase):

    def test_vehicle_attachments_forward_printed_target_priority_and_exclusion(self):
        package = import_module("cards.pack.fne.drive")
        cases = {
            "60186": (4, "highest_atk"),
            "60187": (3, "highest_sch"),
            "60188": (6, "fewest_remaining_hp"),
        }

        for card_id, (threshold, priority) in cases.items():
            with self.subTest(card_id=card_id):
                module = import_module(f"cards.pack.fne.drive.{card_id}")
                with patch.object(
                    module,
                    "VehicleAttachmentAbilities",
                    return_value=[],
                ) as helper:
                    module.GetAbilities()
                self.assertEqual(helper.call_args.args, (threshold,))
                self.assertTrue(helper.call_args.kwargs[priority])

        with (
            patch.object(
                package.AbilityFactory,
                "AttachToFaceWhenPutIntoPlay",
                return_value=MagicMock(),
            ) as attach,
            patch.object(
                package.AbilityFactory,
                "WhenUnitWouldTakeDamage",
                return_value=MagicMock(),
            ),
        ):
            package.VehicleAttachmentAbilities(4, highest_atk=True)

        finder = attach.call_args.args[0]
        self.assertIs(finder.card_type, package.Enemy)
        self.assertTrue(attach.call_args.kwargs["highest_atk"])
        check_no_vehicle = finder.check_effect_fns[0]
        with patch.object(package, "HasVehicleAttachment", side_effect=[False, True]):
            self.assertTrue(check_no_vehicle(MagicMock(), MagicMock()))
            self.assertFalse(check_no_vehicle(MagicMock(), MagicMock()))

    def test_vehicle_stores_all_damage_and_discards_at_its_threshold(self):
        module = import_module("cards.pack.fne.drive.60186")
        ability = module.GetAbilities()[1]
        attachment = MagicMock()
        attachment.GetCounters.return_value = 4
        effect = MagicMock()
        effect.this.CastTo.return_value = attachment
        message = MagicMock()
        message.will_take_damage = 4

        with (
            patch.object(module.Faces, "PlaceCountersOn") as place,
            patch.object(module.Faces, "DiscardAll") as discard,
        ):
            ability.operation(effect, message)

        message.SetBeInstead.assert_called_once_with(effect)
        place.assert_called_once_with([attachment], 4, "damage", effect)
        discard.assert_called_once_with([attachment], effect)

    def test_vehicle_remains_below_its_damage_threshold(self):
        module = import_module("cards.pack.fne.drive.60188")
        ability = module.GetAbilities()[1]
        attachment = MagicMock()
        attachment.GetCounters.return_value = 5
        effect = MagicMock()
        effect.this.CastTo.return_value = attachment
        message = MagicMock(will_take_damage=2)

        with patch.object(module.Faces, "DiscardAll") as discard:
            ability.operation(effect, message)

        discard.assert_not_called()

    def test_traffic_jam_redirects_vehicle_scheme_and_thwart_without_recursing(self):
        module = import_module("cards.pack.fne.drive.60189")
        place_ability, remove_ability = module.GetAbilities()
        traffic = MagicMock()
        actor = MagicMock()
        effect = MagicMock()
        effect.this = MagicMock()
        effect.this.CastTo.return_value = traffic
        place_message = MagicMock()
        place_message.trigger = MagicMock()
        place_message.sch_message = SimpleNamespace(trigger=actor)
        place_message.value = 3
        remove_message = MagicMock()
        remove_message.trigger = MagicMock()
        remove_message.by_face = actor
        remove_message.value = 2

        place_condition = find_condition(place_ability, "vehicle_places_threat")
        remove_condition = find_condition(remove_ability, "vehicle_removes_threat")
        with (
            patch.object(module, "HasVehicleAttachment", return_value=True),
            patch.object(module.Unit2, "IsType", return_value=True),
        ):
            self.assertTrue(place_condition(effect, place_message))
            self.assertTrue(remove_condition(effect, remove_message))
            place_ability.operation(effect, place_message)
            remove_ability.operation(effect, remove_message)

        place_message.SetBeInstead.assert_called_once_with(effect)
        traffic.PlaceThreatOnSchemes.assert_called_once_with([traffic], 3, effect)
        remove_message.SetBeInstead.assert_called_once_with(effect)
        traffic.RemoveThreatFromSchemes.assert_called_once_with([traffic], 2, effect)

        place_message.trigger = effect.this
        remove_message.trigger = effect.this
        with (
            patch.object(module, "HasVehicleAttachment", return_value=True),
            patch.object(module.Unit2, "IsType", return_value=True),
        ):
            self.assertFalse(place_condition(effect, place_message))
            self.assertFalse(remove_condition(effect, remove_message))

    def test_traffic_jam_ignores_characters_without_a_vehicle(self):
        module = import_module("cards.pack.fne.drive.60189")
        place_ability = module.GetAbilities()[0]
        condition = find_condition(place_ability, "vehicle_places_threat")
        effect = SimpleNamespace(this=MagicMock())
        message = SimpleNamespace(
            trigger=MagicMock(),
            sch_message=SimpleNamespace(trigger=MagicMock()),
            by_effect=SimpleNamespace(this=MagicMock()),
        )

        with patch.object(module, "HasVehicleAttachment", return_value=False):
            self.assertFalse(condition(effect, message))

    def test_carjacking_reveals_if_payment_is_refused_and_attaches_if_paid(self):
        module = import_module("cards.pack.fne.drive.60190")
        ability = module.GetAbilities()[0]
        player = MagicMock()
        identity = MagicMock()
        player.GetIdentity.return_value = identity
        vehicle = MagicMock()
        effect = MagicMock()
        message = SimpleNamespace(GetToPlayer=MagicMock(return_value=player))

        with (
            patch.object(module.Worlds, "DiscardEncounterCardsUntil", return_value=vehicle),
            patch.object(module, "HasVehicleAttachment", return_value=False),
        ):
            ability.operation(effect, message)

        attach, reveal = player.ChooseAbilities.call_args.args[1:]
        cost = attach.GetCost(MagicMock(), [])
        self.assertEqual(cost.val, 3)
        self.assertTrue(cost.rule.same_type)
        choice_effect = SimpleNamespace(
            targets=[],
            GetPaidResources=MagicMock(),
        )
        attach.operation(choice_effect, MagicMock())
        vehicle.AttachTo2.assert_called_once_with(identity, effect)
        reveal.operation(choice_effect, MagicMock())
        vehicle.Reveal.assert_called_once_with(player, effect)

    def test_carjacking_reveals_with_an_existing_vehicle_and_handles_no_match(self):
        module = import_module("cards.pack.fne.drive.60190")
        ability = module.GetAbilities()[0]
        player = MagicMock()
        identity = MagicMock()
        player.GetIdentity.return_value = identity
        message = SimpleNamespace(GetToPlayer=MagicMock(return_value=player))
        vehicle = MagicMock()

        with (
            patch.object(module.Worlds, "DiscardEncounterCardsUntil", return_value=vehicle),
            patch.object(module, "HasVehicleAttachment", return_value=True),
        ):
            ability.operation(MagicMock(), message)
        vehicle.Reveal.assert_called_once()
        player.ChooseAbilities.assert_not_called()

        player.reset_mock()
        with patch.object(module.Worlds, "DiscardEncounterCardsUntil", return_value=None):
            ability.operation(MagicMock(), message)
        player.ChooseAbilities.assert_not_called()


class TestTombstoneMechanics(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Ver.Initialize()
        CardsDB.Initialize()

    def test_attachments_choose_every_tied_highest_base_hp_minion_and_gain_surge_without_one(self):
        package = import_module("cards.pack.fne.tombstone")
        attach_marker = MagicMock()
        with (
            patch.object(
                package.AbilityFactory,
                "AttachToFaceWhenPutIntoPlay",
                return_value=attach_marker,
            ) as attach,
            patch.object(package.AbilityFactory, "AfterUnitSchemeEnd", return_value=MagicMock()),
        ):
            package.TombstoneAttachmentAbilities("Scheme")

        finder = attach.call_args.args[0]
        self.assertTrue(attach.call_args.kwargs["if_cannot_gain_surge"])
        highest = finder.check_effect_fns[0]
        first = MagicMock(base_health=5)
        tied = MagicMock(base_health=5)
        lower = MagicMock(base_health=4)
        effect = MagicMock()
        with patch.object(package.Worlds, "GetOnFieldMinions", return_value=[first, tied, lower]):
            self.assertTrue(highest(effect, first))
            self.assertTrue(highest(effect, tied))
            self.assertFalse(highest(effect, lower))
        with patch.object(package.Worlds, "GetOnFieldMinions", return_value=[]):
            self.assertFalse(highest(effect, first))

        with patch.object(package.Faces, "GiveStatus") as give_status:
            attach.call_args.kwargs["when_attach_operation"](first, effect)
        give_status.assert_called_once_with([first], "Tough", effect)

    def test_cold_and_hard_discard_even_when_the_status_cannot_be_applied(self):
        cases = {
            "60195": ("Confused", "GetFirstPlayer"),
            "60196": ("Stunned", None),
        }
        for card_id, (status, first_player_call) in cases.items():
            with self.subTest(card_id=card_id):
                module = import_module(f"cards.pack.fne.tombstone.{card_id}")
                ability = module.GetAbilities()[1]
                attachment = MagicMock()
                identity = MagicMock()
                effect = MagicMock()
                effect.this.CastTo.return_value = attachment
                message = MagicMock()
                message.attacked_targets = [identity]
                with (
                    patch.object(module.Faces, "GiveStatus", return_value=0) as give,
                    patch.object(module.Faces, "DiscardAll") as discard,
                    patch.object(
                        module.Worlds,
                        "GetFirstPlayer",
                        return_value=SimpleNamespace(
                            GetIdentity=MagicMock(return_value=identity)
                        ),
                    ) as get_first_player,
                ):
                    ability.operation(effect, message)

                give.assert_called_once_with([identity], status, effect)
                discard.assert_called_once_with([attachment], effect)
                if first_player_call:
                    get_first_player.assert_called_once_with(effect)

    def test_beetle_attachment_eligibility_excludes_incompatible_printed_targets(self):
        world = MagicMock()
        world.GetPlayerNumIcon.return_value = 1
        beetle = CardFactory.CreateFace(CardsDB.FindCardPaper("60197"), world)
        cold = CardFactory.CreateFace(CardsDB.FindCardPaper("60195"), world)
        identity_only = CardFactory.CreateFace(CardsDB.FindCardPaper("60080"), world)
        villain_only = CardFactory.CreateFace(CardsDB.FindCardPaper("60070"), world)
        sports_car = CardFactory.CreateFace(CardsDB.FindCardPaper("60186"), world)
        effect = MagicMock()

        self.assertTrue(cold._CanAttachByPrintedRuleTo(beetle, effect))
        self.assertFalse(identity_only._CanAttachByPrintedRuleTo(beetle, effect))
        self.assertFalse(villain_only._CanAttachByPrintedRuleTo(beetle, effect))
        drive = import_module("cards.pack.fne.drive")
        with patch.object(drive, "HasVehicleAttachment", side_effect=[False, True]):
            self.assertTrue(sports_car._CanAttachByPrintedRuleTo(beetle, effect))
            self.assertFalse(sports_car._CanAttachByPrintedRuleTo(beetle, effect))

    def test_beetle_searches_both_piles_attaches_a_legal_result_and_handles_empty_search(self):
        module = import_module("cards.pack.fne.tombstone.60197")
        ability = module.GetAbilities()[0]
        beetle = MagicMock()
        attachment = MagicMock()
        player = MagicMock()
        effect = MagicMock()
        effect.this.CastTo.return_value = beetle
        message = SimpleNamespace(GetToPlayer=MagicMock(return_value=player))

        with patch.object(module.Search, "EncounterCard", return_value=attachment) as search:
            ability.operation(effect, message)

        self.assertTrue(search.call_args.kwargs["include_discard_pile"])
        self.assertIs(search.call_args.kwargs["card_type"], module.Attachment)
        attachment.AttachTo2.assert_called_once_with(beetle, effect)

        attachment.reset_mock()
        with patch.object(module.Search, "EncounterCard", return_value=None):
            ability.operation(effect, message)
        attachment.AttachTo2.assert_not_called()

    def test_tombstone_boost_gives_the_villain_tough_if_possible(self):
        module = import_module("cards.pack.fne.tombstone.60198")
        ability = module.GetAbilities()[0]
        villain = MagicMock()
        effect = MagicMock()
        with (
            patch.object(module.Worlds, "FindVillain", return_value=villain),
            patch.object(module.Faces, "GiveStatus", return_value=0) as give,
        ):
            ability.operation(effect, MagicMock())
        give.assert_called_once_with([villain], "Tough", effect)

    def test_hit_list_counts_only_allies_defeated_by_its_indirect_damage(self):
        module = import_module("cards.pack.fne.tombstone.60199")
        ability = module.GetAbilities()[0]
        scheme = MagicMock()
        identity = MagicMock()
        ally = MagicMock()
        hero = MagicMock()
        effect = MagicMock()
        effect.this.CastTo.return_value = scheme

        class Defeated:
            def __init__(self, target):
                self.target = target

        identity.TakeIndirectDamage.return_value = [
            Defeated(ally),
            Defeated(ally),
            Defeated(hero),
            MagicMock(),
        ]
        with (
            patch.object(
                module.Worlds,
                "GetFirstPlayer",
                return_value=SimpleNamespace(GetIdentity=MagicMock(return_value=identity)),
            ),
            patch.object(module.Worlds, "GetPlayerNumIcon", return_value=2),
            patch.object(module.Message, "AfterUnitDefeatedUnit", Defeated),
            patch.object(module.Ally, "IsType", side_effect=lambda face: face is ally),
        ):
            ability.operation(effect, MagicMock())

        identity.TakeIndirectDamage.assert_called_once_with(scheme, 3, effect)
        scheme.RemoveThreatFromSchemes.assert_called_once_with([scheme], 4, effect)

    def test_hit_list_removes_no_threat_when_no_ally_is_defeated(self):
        module = import_module("cards.pack.fne.tombstone.60199")
        ability = module.GetAbilities()[0]
        scheme = MagicMock()
        identity = MagicMock()
        identity.TakeIndirectDamage.return_value = [MagicMock()]
        effect = MagicMock()
        effect.this.CastTo.return_value = scheme
        with patch.object(
            module.Worlds,
            "GetFirstPlayer",
            return_value=SimpleNamespace(GetIdentity=MagicMock(return_value=identity)),
        ):
            ability.operation(effect, MagicMock())
        scheme.RemoveThreatFromSchemes.assert_not_called()


class TestTracksuitMafiaMechanics(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Ver.Initialize()
        CardsDB.Initialize()

    def test_ivan_accumulates_acceleration_tokens_on_reveal_and_after_scheming(self):
        module = import_module("cards.pack.fne.tracksuit_mafia.60200")
        minion = MagicMock()
        effect = MagicMock()
        effect.this.CastTo.return_value = minion
        for ability in module.GetAbilities():
            ability.operation(effect, MagicMock())
        self.assertEqual(minion.PlaceAccelerationToken.call_count, 2)
        minion.PlaceAccelerationToken.assert_called_with(1, effect)

    def test_the_clown_gains_one_facedown_boost_after_scheming(self):
        module = import_module("cards.pack.fne.tracksuit_mafia.60201")
        effect = MagicMock()
        with patch.object(module.Faces, "GiveFacedownBoostCards") as give:
            module.GetAbilities()[0].operation(effect, MagicMock())
        give.assert_called_once_with([effect.this], 1, effect)

    def test_tracksuit_defeat_alternatives_tuck_or_apply_the_printed_fallback(self):
        mafioso = import_module("cards.pack.fne.tracksuit_mafia.60202")
        bro = import_module("cards.pack.fne.tracksuit_mafia.60203")
        scheme = MagicMock()
        minion = MagicMock()
        killer = MagicMock()
        effect = MagicMock()
        effect.this.CastTo.return_value = minion
        message = SimpleNamespace(killer=killer)

        with patch.object(mafioso, "FindTracksuitMafia", return_value=scheme):
            mafioso.GetAbilities()[0].operation(effect, message)
        scheme.TuckCardUnderHere.assert_called_once_with(minion, effect)

        with (
            patch.object(mafioso, "FindTracksuitMafia", return_value=None),
            patch.object(mafioso.Unit2, "IsType", return_value=True),
            patch.object(mafioso.Faces, "GiveStatus", side_effect=[0, 0]) as give,
        ):
            mafioso.GetAbilities()[0].operation(effect, message)
        self.assertEqual(
            give.call_args_list,
            [
                unittest.mock.call([killer], "Stunned", effect),
                unittest.mock.call([killer], "Confused", effect),
            ],
        )

        with patch.object(bro, "FindTracksuitMafia", return_value=scheme):
            bro.GetAbilities()[0].operation(effect, message)
        scheme.TuckCardUnderHere.assert_called_with(minion, effect)
        with (
            patch.object(bro, "FindTracksuitMafia", return_value=None),
            patch.object(bro.Faces, "ShuffleAllTo") as shuffle,
        ):
            bro.GetAbilities()[0].operation(effect, message)
        shuffle.assert_called_once_with([minion], "EncounterDeck", effect)

    def test_mafioso_does_nothing_without_a_character_killer(self):
        module = import_module("cards.pack.fne.tracksuit_mafia.60202")
        effect = MagicMock()
        message = SimpleNamespace(killer=None)
        with (
            patch.object(module, "FindTracksuitMafia", return_value=None),
            patch.object(module.Faces, "GiveStatus") as give,
        ):
            module.GetAbilities()[0].operation(effect, message)
        give.assert_not_called()

    def test_side_scheme_tucks_the_first_discarded_tracksuit_and_handles_no_match(self):
        module = import_module("cards.pack.fne.tracksuit_mafia.60204")
        ability = module.GetAbilities()[0]
        scheme = MagicMock()
        minion = MagicMock()
        effect = MagicMock()
        effect.this.CastTo.return_value = scheme
        with patch.object(
            module.Worlds,
            "DiscardEncounterCardsUntil",
            return_value=minion,
        ) as discard:
            ability.operation(effect, MagicMock())
        self.assertEqual(discard.call_args.kwargs["trait"], "TRACKSUIT")
        scheme.TuckCardUnderHere.assert_called_once_with(minion, effect)

        scheme.reset_mock()
        with patch.object(module.Worlds, "DiscardEncounterCardsUntil", return_value=None):
            ability.operation(effect, MagicMock())
        scheme.TuckCardUnderHere.assert_not_called()

    def test_side_scheme_only_responds_to_tracksuit_minions_from_encounter_deck(self):
        module = import_module("cards.pack.fne.tracksuit_mafia.60204")
        ability = module.GetAbilities()[1]
        world = MagicMock()
        world.GetPlayerNumIcon.return_value = 1
        tracksuit = CardFactory.CreateFace(CardsDB.FindCardPaper("60203"), world)
        non_tracksuit = CardFactory.CreateFace(CardsDB.FindCardPaper("60198"), world)
        effect = MagicMock()
        check_card = find_condition(ability, "check_which_card")
        origin_condition = ability.conditions[-1]

        message = SimpleNamespace(
            trigger=tracksuit,
            reveal_message=SimpleNamespace(
                IsFromEncounterDeck=MagicMock(return_value=True)
            ),
        )
        self.assertTrue(check_card(effect, message))
        self.assertTrue(origin_condition(effect, message))
        message.trigger = non_tracksuit
        self.assertFalse(check_card(effect, message))
        message.trigger = tracksuit
        message.reveal_message.IsFromEncounterDeck.return_value = False
        self.assertFalse(origin_condition(effect, message))

    def test_side_scheme_reveals_one_chosen_tucked_minion_without_recursive_trigger(self):
        module = import_module("cards.pack.fne.tracksuit_mafia.60204")
        ability = module.GetAbilities()[1]
        tucked = MagicMock()
        scheme = MagicMock()
        scheme.GetPlacedCardArea.return_value.GetAll.return_value = [tucked]
        player = MagicMock()
        player.AskChooseFace.return_value = tucked
        effect = MagicMock()
        effect.this.CastTo.return_value = scheme
        message = SimpleNamespace(
            GetToPlayer=MagicMock(return_value=player),
            reveal_message=SimpleNamespace(
                IsFromEncounterDeck=MagicMock(return_value=False)
            ),
        )

        with patch.object(module.TRACKSUIT_MINION, "Checks", return_value=[tucked]):
            ability.operation(effect, message)
        tucked.Reveal.assert_called_once_with(player, effect)
        self.assertFalse(ability.conditions[-1](effect, message))

        player.reset_mock()
        with patch.object(module.TRACKSUIT_MINION, "Checks", return_value=[]):
            ability.operation(effect, message)
        player.AskChooseFace.assert_not_called()

    def test_tucked_minions_are_discarded_when_the_side_scheme_leaves_play(self):
        component_module = import_module("game.card.face.component.attach")
        parent = MagicMock()
        scheme = MagicMock()
        parent.face = scheme
        component = component_module.PlacedCard(parent)
        tucked = MagicMock()
        component.GetDeck = MagicMock(
            return_value=SimpleNamespace(Get=MagicMock(return_value=[tucked]))
        )
        effect = MagicMock()

        with patch("game.operate.faces.Faces.DiscardAll") as discard:
            component.OnParentLeavePlay(effect)
        discard.assert_called_once()
        self.assertEqual(discard.call_args.args[0], [tucked])


if __name__ == "__main__":
    unittest.main()
