from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
import importlib
import unittest
from unittest.mock import MagicMock, patch

from engine import Engine  # noqa: F401 - establishes the project's import order
from engine.controller.controller import Controller
from engine.device.manager.base import DeviceManager
from engine.device.manager.web.client import ClientManager
from engine.device.web.server.server_base import GameServerBase
from game.operate.search import Search
from game.operate.search_internal import SearchInternal
from game.scene.scene import Scene
from game.selector.factory import Select
from game.selector.selector_end import SelectorEnd
from game.world.world_rule import WorldRule


class FakeDeck:
    def __init__(self, *, is_deck=True, is_discards=False):
        self.flags = SimpleNamespace(
            is_deck=is_deck,
            is_discards=is_discards,
        )
        self.faces = []
        self.Shuffle = MagicMock()

    def Get(self, from_top=False):
        return list(reversed(self.faces)) if from_top else list(self.faces)

    def GetSize(self):
        return len(self.faces)


def make_deck(card_count=3, *, object_id_start=1, **kwargs):
    deck = FakeDeck(**kwargs)
    deck.faces = [
        SimpleNamespace(
            name=f"Card {index + 1}",
            card=SimpleNamespace(
                area=deck,
                object_id=object_id_start + index,
            ),
        )
        for index in range(card_count)
    ]
    return deck


def make_effect(*, legacy=False, current_step_id=0):
    scene = SimpleNamespace(
        UseLegacyFullSearchPrompt=MagicMock(return_value=legacy),
    )
    replay = SimpleNamespace(current_step_id=current_step_id)
    world = SimpleNamespace(
        scene=scene,
        controller_manager=SimpleNamespace(replay=replay),
        rule=SimpleNamespace(v16_referential_ability=False),
    )
    return SimpleNamespace(world=world, initiator=SimpleNamespace())


class FakeSelector:
    def __init__(self, legal_faces, target_range=(1, 1)):
        self.legal_faces = list(legal_faces)
        if target_range == "All":
            target_range = (len(legal_faces), len(legal_faces))
        self.selector_range = SimpleNamespace(
            GetTargetMin=MagicMock(return_value=target_range[0]),
            GetTargetMax=MagicMock(return_value=target_range[1]),
        )
        self.GetAllLegalTargets = MagicMock(return_value=self.legal_faces)
        self.AfterSelectTargets = MagicMock(return_value=True)
        self.IfSelectTargetFailure = MagicMock()


class TestFullDeckSearchDisplay(unittest.TestCase):

    def test_setup_option_initializes_a_cookie_not_a_game_rule(self):
        rule = WorldRule()
        self.assertFalse(bool(rule.show_deck_during_full_search))

        # Keep parsing the old rule so existing saves remain compatible.
        rule.SetRule(["show_deck_during_full_search"], False, 1)
        self.assertTrue(bool(rule.show_deck_during_full_search))

        project_root = Path(__file__).resolve().parents[1]
        scene = (project_root / "public" / "scene.html").read_text(
            encoding="utf-8"
        )
        settings = (
            project_root / "public" / "js" / "marvel" / "settings.ts"
        ).read_text(encoding="utf-8")

        self.assertIn('id="show_deck_during_full_search"', scene)
        self.assertNotIn(
            "new_game.rules.push('show_deck_during_full_search')",
            scene,
        )
        self.assertIn("btn_show_deck_during_full_search_", scene)
        self.assertIn("class ClientPreferences", settings)
        self.assertIn("btn_show_deck_during_full_search", settings)

    def call_search(self, deck, *, legacy=False, **kwargs):
        with patch.object(
            SearchInternal,
            "SearchForCardsInternal",
            return_value=[],
        ) as search_internal:
            Search.SearchForCards(
                make_effect(legacy=legacy),
                SimpleNamespace(),
                faces=deck.Get(True),
                **kwargs,
            )
        return search_internal.call_args.kwargs

    def test_complete_specialized_deck_is_detected_unconditionally(self):
        deck = make_deck()

        kwargs = self.call_search(deck)

        self.assertEqual(kwargs["full_search_display_faces"], deck.Get(True))
        self.assertEqual(kwargs["full_search_decks"], [])
        self.assertFalse(kwargs["force_full_search_prompt"])

    def test_limited_or_non_shuffling_searches_have_no_full_search_metadata(self):
        deck = make_deck()

        for kwargs in [{"most_top": 2}, {"not_move": True}]:
            with self.subTest(kwargs=kwargs):
                call = self.call_search(deck, **kwargs)
                self.assertEqual(call["full_search_display_faces"], [])
                self.assertEqual(call["full_search_decks"], [])

    def test_select_all_search_has_metadata_without_becoming_a_choice(self):
        deck = make_deck()

        kwargs = self.call_search(deck, range="All")

        self.assertEqual(kwargs["full_search_display_faces"], deck.Get(True))
        self.assertFalse(kwargs["force_full_search_prompt"])

    def test_legacy_search_boundary_restores_old_prompt_and_shuffle_metadata(self):
        deck = make_deck()

        kwargs = self.call_search(deck, legacy=True)

        self.assertEqual(kwargs["full_search_display_faces"], deck.Get(True))
        self.assertEqual(kwargs["full_search_decks"], [deck])
        self.assertTrue(kwargs["force_full_search_prompt"])

    def test_multi_area_search_displays_discard_without_extra_shuffle_decks(self):
        encounter_deck = make_deck(object_id_start=1)
        encounter_discard = make_deck(
            is_discards=True,
            object_id_start=10,
        )
        set_aside = make_deck(is_deck=False, object_id_start=20)
        effect = make_effect()

        with patch.object(
            SearchInternal,
            "SearchForCardsInternal",
            return_value=[],
        ) as search_internal:
            Search.SearchForCards(
                effect,
                SimpleNamespace(),
                faces=(
                    encounter_deck.Get(True)
                    + encounter_discard.Get(True)
                    + set_aside.Get(True)
                ),
                range="All",
            )

        kwargs = search_internal.call_args.kwargs
        self.assertEqual(kwargs["full_search_decks"], [])
        self.assertEqual(
            kwargs["full_search_display_faces"],
            encounter_deck.Get(True) + encounter_discard.Get(True),
        )

    def test_partial_explicit_deck_is_not_a_full_search(self):
        deck = make_deck()
        with patch.object(
            SearchInternal,
            "SearchForCardsInternal",
            return_value=[],
        ) as search_internal:
            Search.SearchForCards(
                make_effect(),
                SimpleNamespace(),
                faces=deck.Get(True)[:2],
            )

        self.assertEqual(
            search_internal.call_args.kwargs["full_search_display_faces"],
            [],
        )

    def test_direct_selector_detects_full_search_without_forcing_a_choice(self):
        deck = make_deck()
        selector = Select.From(faces=deck.Get(True), by_search=True)

        selector.EnableFullSearchDisplay(make_effect(), deck.Get(True))

        self.assertFalse(selector.force_choose)
        self.assertEqual(selector.selector_end.full_search_decks, [])
        self.assertEqual(
            selector.selector_end.full_search_display_faces,
            deck.Get(True),
        )

    def test_direct_multi_area_selector_keeps_all_presentation_cards(self):
        deck = make_deck(object_id_start=1)
        discard = make_deck(is_discards=True, object_id_start=10)
        faces = deck.Get(True) + discard.Get(True)
        selector = Select.From(faces=faces, by_search=True)

        selector.EnableFullSearchDisplay(make_effect(), faces)

        self.assertFalse(selector.force_choose)
        self.assertEqual(selector.selector_end.full_search_decks, [])
        self.assertEqual(selector.selector_end.full_search_display_faces, faces)

    def test_direct_selector_refreshes_detected_cards_between_searches(self):
        deck = make_deck()
        selector = Select.From(faces=deck.Get(True), by_search=True)
        selector.EnableFullSearchDisplay(make_effect(), deck.Get(True))

        removed = deck.faces.pop()
        selector.EnableFullSearchDisplay(make_effect(), deck.Get(True))

        self.assertNotIn(
            removed,
            selector.selector_end.full_search_display_faces,
        )
        self.assertEqual(
            selector.selector_end.full_search_display_faces,
            deck.Get(True),
        )

    def test_direct_limited_or_non_shuffling_selectors_do_not_show_full_deck(self):
        deck = make_deck()
        selectors = [
            (Select.From(faces=deck.Get(True)[:2], by_search=True), deck.Get(True)[:2]),
            (Select.From(faces=deck.Get(True), by_search=True, not_move=True), deck.Get(True)),
            (Select.From(faces=deck.Get(True), by_search=True, not_shuffle=True), deck.Get(True)),
            (
                Select.From(
                    faces=deck.Get(True),
                    by_search=True,
                    display_in_target_order=True,
                ),
                deck.Get(True),
            ),
        ]

        for selector, faces in selectors:
            with self.subTest(selector_end=selector.selector_end):
                selector.EnableFullSearchDisplay(make_effect(), faces)
                self.assertEqual(
                    selector.selector_end.full_search_display_faces,
                    [],
                )
                self.assertFalse(selector.force_choose)

    def run_internal_search(
        self,
        legal_faces,
        *,
        all_faces=None,
        may=False,
        target_range=(1, 1),
        selected_faces=None,
        force_legacy=False,
        full_search_decks=(),
    ):
        all_faces = list(all_faces if all_faces is not None else legal_faces)
        selected_faces = list(
            legal_faces if selected_faces is None else selected_faces
        )
        finder = SimpleNamespace(
            Checks=MagicMock(return_value=list(legal_faces)),
        )
        controller = SimpleNamespace(PresentFullSearch=MagicMock())
        player = SimpleNamespace(
            GetController=MagicMock(return_value=controller),
            AskChooseSelect=MagicMock(return_value=selected_faces),
        )
        selector = FakeSelector(legal_faces, target_range)
        captured = {}

        def create_selector(**kwargs):
            captured.update(kwargs)
            return selector

        with patch(
            "game.operate.search_internal.Select.From",
            side_effect=create_selector,
        ):
            result = SearchInternal.SearchForCardsInternal(
                SimpleNamespace(),
                player,
                all_faces,
                process_choose=None,
                process_other=None,
                finder=finder,
                may=may,
                range=target_range,
                full_search_display_faces=all_faces,
                full_search_decks=full_search_decks,
                force_full_search_prompt=force_legacy,
            )
        return result, player, controller, selector, captured

    def test_zero_match_search_uses_inspection_channel_then_resolves_normally(self):
        deck = make_deck()
        result, player, controller, selector, captured = self.run_internal_search(
            [],
            all_faces=deck.Get(True),
        )

        self.assertEqual(result, [])
        player.AskChooseSelect.assert_not_called()
        controller.PresentFullSearch.assert_called_once_with(
            [face.card.object_id for face in deck.Get(True)],
            [],
            (1, 1),
            "Search the full deck",
        )
        selector.AfterSelectTargets.assert_called_once_with(
            unittest.mock.ANY,
            [],
            (1, 1),
        )
        self.assertFalse(captured["force_choose"])

    def test_one_mandatory_match_stays_automatic(self):
        deck = make_deck()
        match = deck.Get(True)[0]
        result, player, controller, _, captured = self.run_internal_search(
            [match],
            all_faces=deck.Get(True),
        )

        self.assertEqual(result, [match])
        player.AskChooseSelect.assert_not_called()
        controller.PresentFullSearch.assert_called_once()
        self.assertFalse(captured["force_choose"])

    def test_duplicate_matches_keep_the_original_deterministic_top_card(self):
        deck = make_deck()
        for face in deck.faces:
            face.name = "Duplicate"
        legal = deck.Get(True)[:2]

        result, player, controller, _, _ = self.run_internal_search(
            legal,
            all_faces=deck.Get(True),
        )

        self.assertEqual(result, [legal[0]])
        player.AskChooseSelect.assert_not_called()
        controller.PresentFullSearch.assert_called_once()

    def test_one_optional_match_remains_an_accept_or_decline_decision(self):
        deck = make_deck()
        match = deck.Get(True)[0]

        for selected in ([], [match]):
            with self.subTest(selected=selected):
                result, player, controller, _, captured = self.run_internal_search(
                    [match],
                    all_faces=deck.Get(True),
                    may=True,
                    selected_faces=selected,
                )
                self.assertEqual(result, selected)
                player.AskChooseSelect.assert_called_once()
                controller.PresentFullSearch.assert_not_called()
                self.assertEqual(captured["range"], (0, 1))
                self.assertEqual(
                    captured["full_search_display_faces"],
                    deck.Get(True),
                )
                self.assertFalse(captured["force_choose"])

    def test_multiple_matches_keep_the_original_choice(self):
        deck = make_deck()
        legal = deck.Get(True)[:2]
        result, player, _, _, captured = self.run_internal_search(
            legal,
            all_faces=deck.Get(True),
            selected_faces=[legal[1]],
        )

        self.assertEqual(result, [legal[1]])
        player.AskChooseSelect.assert_called_once()
        self.assertEqual(captured["full_search_display_faces"], deck.Get(True))
        self.assertFalse(captured["force_choose"])

    def test_select_all_uses_canonical_order_without_gameplay_input(self):
        deck = make_deck(card_count=4)
        canonical = deck.Get(True)
        result, player, controller, _, captured = self.run_internal_search(
            canonical,
            all_faces=canonical,
            target_range="All",
        )

        self.assertEqual(result, canonical)
        player.AskChooseSelect.assert_not_called()
        controller.PresentFullSearch.assert_called_once()
        self.assertFalse(captured["force_choose"])

    def test_legacy_search_still_forces_its_recorded_confirmation(self):
        deck = make_deck()
        clicked = list(reversed(deck.Get(True)))
        result, player, controller, _, captured = self.run_internal_search(
            deck.Get(True),
            all_faces=deck.Get(True),
            target_range=(len(clicked), len(clicked)),
            selected_faces=clicked,
            force_legacy=True,
            full_search_decks=[deck],
        )

        self.assertEqual(result, clicked)
        player.AskChooseSelect.assert_called_once()
        controller.PresentFullSearch.assert_not_called()
        self.assertTrue(captured["force_choose"])
        self.assertEqual(captured["full_search_decks"], [deck])

    def test_legacy_select_all_restores_canonical_order(self):
        deck = make_deck(card_count=4)
        canonical = deck.Get(True)
        result, _, _, _, _ = self.run_internal_search(
            canonical,
            all_faces=canonical,
            target_range="All",
            selected_faces=list(reversed(canonical)),
            force_legacy=True,
            full_search_decks=[deck],
        )

        self.assertEqual(result, canonical)

    def test_presentation_metadata_does_not_add_shuffle_calls(self):
        deck = make_deck()
        selector_end = SelectorEnd(
            peek=True,
            full_search_display_faces=deck.Get(True),
        )

        with patch.object(SelectorEnd, "DoMove", return_value=[]):
            selector_end.Process(SimpleNamespace(), [])

        deck.Shuffle.assert_not_called()

    def test_legacy_confirmation_keeps_its_historical_extra_shuffle(self):
        deck = make_deck()
        selector_end = SelectorEnd(
            peek=True,
            full_search_display_faces=deck.Get(True),
            full_search_decks=[deck],
            force_choose=True,
        )

        with patch.object(SelectorEnd, "DoMove", return_value=[]):
            selector_end.Process(SimpleNamespace(), [])

        deck.Shuffle.assert_called_once()

    def test_legacy_save_migration_records_and_retains_input_boundary(self):
        scene = Scene(
            rules=["show_deck_during_full_search"],
            inputs=[SimpleNamespace(), SimpleNamespace(), SimpleNamespace()],
        )

        scene.MigrateFullSearchDisplayRule()

        self.assertEqual(
            scene.metadata["legacy_full_search_prompt_end_step"],
            3,
        )
        self.assertTrue(scene.UseLegacyFullSearchPrompt(0))
        self.assertTrue(scene.UseLegacyFullSearchPrompt(2))
        self.assertFalse(scene.UseLegacyFullSearchPrompt(3))
        self.assertIn("show_deck_during_full_search", scene.rules)
        self.assertIn("legacy_full_search_prompt_end_step", asdict(scene)["metadata"])

    def test_new_scene_does_not_emit_legacy_compatibility_state(self):
        scene = Scene()
        scene.MigrateFullSearchDisplayRule()

        self.assertNotIn("legacy_full_search_prompt_end_step", scene.metadata)
        self.assertNotIn("show_deck_during_full_search", scene.rules)

    def test_controller_preference_only_gates_presentation(self):
        controller = Controller.__new__(Controller)
        controller.preferences = SimpleNamespace(
            show_deck_during_full_search=False,
        )
        controller.manager = SimpleNamespace(
            replay=SimpleNamespace(is_replay=False),
            skip=SimpleNamespace(is_skipping=False),
        )
        controller.input = SimpleNamespace(PresentFullSearch=MagicMock())

        controller.PresentFullSearch([1, 2], [2], (1, 1), "Search")
        controller.input.PresentFullSearch.assert_not_called()

        controller.SetShowDeckDuringFullSearch(True)
        controller.PresentFullSearch([1, 2], [2], (1, 1), "Search")
        controller.input.PresentFullSearch.assert_called_once_with(
            [1, 2], [2], (1, 1), "Search"
        )

        controller.input.PresentFullSearch.reset_mock()
        controller.manager.skip.is_skipping = True
        controller.PresentFullSearch([1], [1], (1, 1), "Search")
        controller.input.PresentFullSearch.assert_not_called()

        controller.manager.skip.is_skipping = False
        controller.manager.replay.is_replay = True
        controller.PresentFullSearch([1], [1], (1, 1), "Search")
        controller.input.PresentFullSearch.assert_not_called()

    def test_toggle_changes_only_automatic_search_presentation(self):
        def resolve(enabled):
            deck = make_deck()
            match = deck.Get(True)[0]
            input_device = SimpleNamespace(PresentFullSearch=MagicMock())
            controller = Controller.__new__(Controller)
            controller.preferences = SimpleNamespace(
                show_deck_during_full_search=enabled,
            )
            controller.manager = SimpleNamespace(
                replay=SimpleNamespace(
                    is_replay=False,
                    current_step_id=7,
                    history_inputs=[],
                ),
                skip=SimpleNamespace(is_skipping=False),
            )
            controller.input = input_device
            player = SimpleNamespace(
                GetController=MagicMock(return_value=controller),
                AskChooseSelect=MagicMock(),
            )
            selector = FakeSelector([match])
            with patch(
                "game.operate.search_internal.Select.From",
                return_value=selector,
            ):
                result = SearchInternal.SearchForCardsInternal(
                    SimpleNamespace(),
                    player,
                    deck.Get(True),
                    process_choose=None,
                    process_other=None,
                    finder=SimpleNamespace(
                        Checks=MagicMock(return_value=[match]),
                    ),
                    may=False,
                    full_search_display_faces=deck.Get(True),
                )
            return (
                [face.card.object_id for face in result],
                controller.manager.replay.current_step_id,
                list(controller.manager.replay.history_inputs),
                input_device.PresentFullSearch.call_count,
            )

        disabled = resolve(False)
        enabled = resolve(True)

        self.assertEqual(disabled[:3], enabled[:3])
        self.assertEqual(disabled[3], 0)
        self.assertEqual(enabled[3], 1)

    def test_presentation_ack_never_enters_gameplay_input_state(self):
        manager = DeviceManager()

        def acknowledge_during_wait(check, timeout):
            self.assertEqual(manager.asking_players, [])
            payload = manager.full_search_presentations[1]
            self.assertEqual(payload.card_ids, [4, 3, 2])
            self.assertEqual(payload.legal_target_ids, [3])
            self.assertEqual((payload.target_min, payload.target_max), (1, 1))
            manager.AcknowledgeFullSearchPresentation(
                1, payload.presentation_id + 1
            )
            self.assertIn(1, manager.full_search_presentations)
            manager.AcknowledgeFullSearchPresentation(
                1, payload.presentation_id
            )
            self.assertTrue(check())
            return True

        with patch.object(
            manager.notify.presentation,
            "Wait",
            side_effect=acknowledge_during_wait,
        ):
            manager.DoPresentFullSearch(
                1,
                [4, 3, 2],
                [3],
                (1, 1),
                "Search the full deck",
                lambda: False,
            )

        self.assertEqual(manager.asking_players, [])
        self.assertEqual(manager.full_search_presentations, {})
        self.assertEqual(manager.ask_options, {})

    def test_server_preferences_are_authoritative_and_isolated_per_player(self):
        controllers = [
            SimpleNamespace(
                preferences=SimpleNamespace(
                    show_deck_during_full_search=False,
                )
            )
            for _ in range(2)
        ]
        for controller in controllers:
            controller.SetShowDeckDuringFullSearch = MagicMock(
                side_effect=lambda enabled, c=controller: setattr(
                    c.preferences, "show_deck_during_full_search", enabled
                )
            )
        manager = SimpleNamespace(
            controllers=controllers,
            AcknowledgeFullSearchPresentation=MagicMock(),
        )
        server = GameServerBase.__new__(GameServerBase)
        server.device_manager = manager

        server.set_full_search_preference(0, True)

        self.assertTrue(controllers[0].preferences.show_deck_during_full_search)
        self.assertFalse(controllers[1].preferences.show_deck_during_full_search)
        manager.AcknowledgeFullSearchPresentation.assert_not_called()

        server.set_full_search_preference(0, False)
        manager.AcknowledgeFullSearchPresentation.assert_called_once_with(0)

    def test_hotseat_connection_covers_players_added_after_connect(self):
        manager = ClientManager()
        hotseat_socket = object()
        manager.Add(
            hotseat_socket,
            [0],
            "hot_seat&ui=202&notification=2",
        )

        # The connection was opened while only P1 existed, but it must also be
        # eligible for targeted P2/P3 presentation frames after a game load.
        self.assertEqual(
            manager.GetClients(1),
            manager.GetClients(0),
        )
        self.assertEqual(
            manager.GetClients(2),
            manager.GetClients(0),
        )

        single_player_manager = ClientManager()
        single_player_manager.Add(object(), [0], "p=0&ui=202")
        self.assertEqual(single_player_manager.GetClients(1), [])

    def test_face_the_past_searches_all_listed_areas(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "cards" / "pack" / "magneto" / "49022.py"
        ).read_text(encoding="utf-8")

        self.assertIn("include_encounter_deck=True", source)
        self.assertIn("include_encounter_discard_pile=True", source)
        self.assertIn("include_set_aside=True", source)
        self.assertIn('range="All"', source)

    def test_suit_up_supplies_complete_search_zones_to_its_selector(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "cards" / "pack" / "aoa" / "45017.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "search_faces = initiator.player_deck.Get() + initiator.discard_pile.Get()",
            source,
        )
        self.assertIn("Faces.LookAt(selectable_faces, initiator, effect)", source)
        self.assertIn(").SetTarget(search_faces,", source)
        self.assertIn("range=(_GetRequiredTargetCount, 2)", source)
        self.assertNotIn("check_again_fn=has_one_ally", source)

    def test_suit_up_requires_only_available_result_types(self):
        suit_up = importlib.import_module("cards.pack.aoa.45017")
        ally = SimpleNamespace(kind="ally")
        upgrade = SimpleNamespace(kind="upgrade")

        def required_count(targets):
            effect = SimpleNamespace(
                context=SimpleNamespace(all_legal_targets=targets)
            )
            with patch.object(
                suit_up.Ally,
                "IsType",
                side_effect=lambda target: target is ally,
            ), patch.object(
                suit_up.Upgrade,
                "IsType",
                side_effect=lambda target: target is upgrade,
            ):
                return suit_up._GetRequiredTargetCount(effect)

        self.assertEqual(required_count([]), 1)
        self.assertEqual(required_count([ally]), 1)
        self.assertEqual(required_count([upgrade]), 1)
        self.assertEqual(required_count([ally, upgrade]), 2)

    def test_suit_up_upgrade_is_independently_legal_if_it_targets_allies(self):
        suit_up = importlib.import_module("cards.pack.aoa.45017")

        def make_upgrade(target_type):
            selector = SimpleNamespace(
                target_text=None,
                selector_filter=SimpleNamespace(
                    finder=SimpleNamespace(card_type=target_type)
                ),
            )
            play_ability = SimpleNamespace(selectors=[selector])
            return SimpleNamespace(
                ability=SimpleNamespace(Find=MagicMock(return_value=[play_ability]))
            )

        self.assertTrue(suit_up._CanAttachToAnAlly(make_upgrade(suit_up.Ally)))
        self.assertTrue(suit_up._CanAttachToAnAlly(make_upgrade(suit_up.Friend)))
        self.assertFalse(suit_up._CanAttachToAnAlly(make_upgrade(suit_up.Identity)))

    def test_client_uses_local_preference_for_full_search_presentation(self):
        project_root = Path(__file__).resolve().parents[1]
        effect_source = (
            project_root / "public" / "js" / "marvel" / "effect.ts"
        ).read_text(encoding="utf-8")
        cards_source = (
            project_root / "public" / "js" / "marvel" / "cards.ts"
        ).read_text(encoding="utf-8")
        client_source = (
            project_root / "public" / "js" / "marvel" / "client.ts"
        ).read_text(encoding="utf-8")
        server_source = (
            project_root / "engine" / "device" / "web" / "server"
            / "server_sync.py"
        ).read_text(encoding="utf-8")

        self.assertIn("getFullSearchDisplayTargets()", effect_source)
        self.assertIn("ClientPreferences.showDeckDuringFullSearch", effect_source)
        self.assertIn("...Effect.getFullSearchDisplayTargets()", effect_source)
        self.assertIn("Effect.getFullSearchDisplayTargets().length", cards_source)
        self.assertIn("ClientPreferences.connectionSettings()", client_source)
        self.assertIn("get_full_search_presentation", server_source)
        self.assertIn("full_search_presentation_ack", server_source)
        self.assertIn("client_settings", server_source)

    def test_automatic_presentation_reuses_the_standard_search_ui(self):
        project_root = Path(__file__).resolve().parents[1]
        presentation_source = (
            project_root / "public" / "js" / "marvel"
            / "full_search_presentation.ts"
        ).read_text(encoding="utf-8")
        buttons_source = (
            project_root / "public" / "js" / "marvel" / "buttons.ts"
        ).read_text(encoding="utf-8")
        page_source = (
            project_root / "public" / "marvel.html"
        ).read_text(encoding="utf-8")
        presentation_css = (
            project_root / "public" / "css" / "marvel"
            / "full-search-presentation.css"
        ).read_text(encoding="utf-8")

        self.assertIn("Cards.getDiv(objectId)", presentation_source)
        self.assertIn(
            "Effect.select_effect_obj = new EffectDescriptor",
            presentation_source,
        )
        self.assertIn(
            "SelectStep.setTargets(true)",
            presentation_source,
        )
        self.assertIn("select_rule: ''", presentation_source)
        self.assertNotIn("classList.toggle(ClassName.select_card)", presentation_source)
        self.assertNotIn("playClickCardSound", presentation_source)
        self.assertIn("UI.prompt.setTempPromptText", presentation_source)
        self.assertIn("UI.btn_ok_div", presentation_source)
        self.assertIn(
            "FullSearchPresentation.dismissIfActive()",
            buttons_source,
        )
        self.assertIn("FullSearchPresentation.isActive()", buttons_source)
        self.assertNotIn("full-search-presentation-panel", page_source)
        self.assertNotIn("full-search-presentation-cards", page_source)
        self.assertNotIn("full-search-presentation-ok", page_source)
        self.assertNotIn("full-search-presentation-card", presentation_css)
        self.assertNotIn("background: rgba", presentation_css)
        self.assertIn(
            ".deck.clicked:has(.being-searching)",
            presentation_css,
        )
        self.assertIn("#prompt-box-container", presentation_css)
        self.assertIn("this.minimizeDecks()", presentation_source)

    def test_toggle_is_in_settings_and_solo_toolbar_controls_stay_visible(self):
        project_root = Path(__file__).resolve().parents[1]
        buttons_source = (
            project_root / "public" / "js" / "marvel" / "buttons.ts"
        ).read_text(encoding="utf-8")
        client_source = (
            project_root / "public" / "js" / "marvel" / "client.ts"
        ).read_text(encoding="utf-8")
        sidebar_source = (
            project_root / "public" / "css" / "marvel" / "side-bar.css"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "Button.full_search_button = "
            "Button.createButtonBase(parent_div_right",
            buttons_source,
        )
        self.assertNotIn(
            "Button.full_search_button = "
            "Button.createButtonBase(parent_div4",
            buttons_source,
        )
        multiplayer_branch = client_source.index(
            "if( Game.total_players > 1 )"
        )
        for control in (
            "playersPin",
            "hideNoActionCards",
            "allHandCards",
        ):
            visible_call = f"{control}.classList.remove('hide')"
            self.assertIn(visible_call, client_source)
            self.assertLess(client_source.index(visible_call), multiplayer_branch)
        self.assertIn(
            "#right-side-bar > #show-deck-during-full-search-btn",
            sidebar_source,
        )
        self.assertIn(
            "const playerId = Button.getFullSearchPreferencePlayerId()",
            buttons_source,
        )
        self.assertIn(
            "Game.forced_on_player < Game.total_players",
            buttons_source,
        )
        self.assertIn(
            "P${playerId + 1} ` : ''",
            buttons_source,
        )
        focus_player = buttons_source[
            buttons_source.index("static focusPlayer(num: number)"):
        ]
        self.assertLess(
            focus_player.index("UI.focusOnPlayer(num)"),
            focus_player.index("Button.updateFullSearchButton()"),
        )


if __name__ == "__main__":
    unittest.main()
