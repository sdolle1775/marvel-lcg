from __future__ import annotations

import re
from pathlib import Path
import unittest

from engine import Engine  # noqa: F401 - establishes the project's import order
from cards.database import CardsDB
from engine.job import JobManager
from engine.lib import Ver
from game.card.face.card_type import Hero
from game.scene.replay.operation import CommandDescriptor
from game.test.headless import HeadlessDeviceManager
from game.test.v18_timing_harness import (
    FIXTURES,
    OUTPUT_DIRECTORY,
    TimingFixture,
    build_fixture_scene,
    run_file_to_prompt,
    run_file_with_devices,
    run_scene_with_devices,
    validate_file,
)


class TestV18TimingPlayableCheckpoints(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Ver.Initialize()
        CardsDB.Initialize()

    def test_checkpoint_matrix_is_complete_and_serializer_valid(self):
        expected = [
            "01_nova_jarnbjorn_unlock.json",
            "02_nova_jarnbjorn_both_legal.json",
            "03_defensive_conditioning_constants.json",
            "04_unuscione_forced_order.json",
            "05_cancel_surge_and_incite.json",
            "06_nested_reveal_attack_defense.json",
            "07_keyword_priority_lab.json",
            "08_status_timing_lab.json",
            "09_retaliate_and_ranged.json",
            "10_martyr_consequential_damage.json",
            "11_thor_overkill_window.json",
            "12_indirect_divided_damage.json",
            "13_thwart_and_scheme_defeat.json",
            "14_recovery_response_window.json",
            "15_scheme_lifecycle.json",
            "16_multiplayer_priority.json",
        ]
        actual = sorted(path.name for path in OUTPUT_DIRECTORY.glob("*.json"))
        self.assertEqual(actual, expected)

        for filename in expected:
            with self.subTest(filename=filename):
                scene = validate_file(OUTPUT_DIRECTORY / filename)
                self.assertIn("v18_timing", scene.rules)
                self.assertNotIn("no_v18_timing", scene.rules)

    def test_every_declared_fixture_card_is_a_real_registered_card(self):
        for fixture in FIXTURES:
            for card_id in fixture.card_ids:
                with self.subTest(fixture=fixture.filename, card_id=card_id):
                    paper = CardsDB.FindCardPaper(card_id)
                    self.assertEqual(paper.card_id, card_id)
                    self.assertTrue(paper.name)

    def test_fixture_scenes_reach_a_real_player_action_with_injected_cards(self):
        quoted_card_id = re.compile(r'"([0-9]{5}[ab]?)"')
        for fixture in FIXTURES:
            with self.subTest(filename=fixture.filename):
                game, devices = run_file_to_prompt(
                    OUTPUT_DIRECTORY / fixture.filename,
                )
                self.assertEqual(
                    devices.stopped_prompt.event_name,
                    "WhenPlayerInTurn",
                )
                self.assertEqual(
                    len(game.world.const_players),
                    len(fixture.heroes),
                )
                self.assertEqual(game.world.event_manager.timing_occurrences, [])

                hand_ids = [
                    face.paper.card_id
                    for player in game.world.const_players
                    for face in player.hand_cards.Get()
                ]
                encounter_ids = [
                    face.paper.card_id
                    for face in game.world.scenario.encounter_deck.Get()
                ]
                for command in fixture.commands:
                    ids = quoted_card_id.findall(command)
                    if "CreateHandCards" in command:
                        for card_id in ids:
                            self.assertIn(card_id, hand_ids)
                    elif "CreateEncounterDeck" in command:
                        for card_id in ids:
                            self.assertIn(card_id, encounter_ids)

    @staticmethod
    def _payment_effect_ids(option: dict) -> list[str]:
        effects: list[str] = []
        for payment in option.get("target_payment", {}).values():
            for payment_entry in payment.get("payment", []):
                effects.extend(str(effect_id) for effect_id in payment_entry)
        return effects

    @staticmethod
    def _nova_option(options: tuple[dict, ...]) -> dict:
        return next(
            option
            for option in options
            if not option.get("target_payment")
            and option.get("all_legal_targets")
        )

    @staticmethod
    def _jarnbjorn_option(options: tuple[dict, ...]) -> dict:
        return next(option for option in options if option.get("target_payment"))

    @staticmethod
    def _choice(option: dict, targets: list[int] | None = None, resources: list[str] | None = None):
        if targets is None:
            minimum = int(option.get("target_num_range", [0, 0])[0])
            targets = list(option.get("all_legal_targets", []))[:minimum]
        return CommandDescriptor(
            str(option.get("choice_id") or option["id"]),
            [str(target) for target in targets],
            resources or [],
        )

    @staticmethod
    def _debug(command: str) -> CommandDescriptor:
        Engine.game.controller_manager.console.SetCommand(
            command,
            Engine.game.world,
        )
        return CommandDescriptor()

    def test_nova_unlock_checkpoint_starts_unpayable_then_reopens_jarnbjorn(self):
        path = OUTPUT_DIRECTORY / "01_nova_jarnbjorn_unlock.json"
        game, devices = run_file_to_prompt(path, event_name="")
        prompt = devices.stopped_prompt

        self.assertEqual(game.controller_manager.replay.current_step_id, 7)
        self.assertEqual(prompt.event_name, "AfterUnitAttackUnit")
        nova = self._nova_option(prompt.options)
        jarnbjorn = self._jarnbjorn_option(prompt.options)
        self.assertTrue(nova["all_legal_targets"])
        self.assertEqual(self._payment_effect_ids(jarnbjorn), [])

        chose_nova = False

        def choose_nova(next_prompt):
            nonlocal chose_nova
            if chose_nova:
                return None
            option = self._nova_option(next_prompt.options)
            chose_nova = True
            return CommandDescriptor(
                option["choice_id"],
                [str(option["all_legal_targets"][0])],
                [],
            )

        branch_devices = HeadlessDeviceManager(
            choice_provider=choose_nova,
        )
        branch_game = run_file_with_devices(path, branch_devices)
        reopened = self._jarnbjorn_option(branch_devices.stopped_prompt.options)

        self.assertGreater(len(self._payment_effect_ids(reopened)), 0)
        helmet = branch_game.world.FindCardsOnField(name="Supernova Helmet")[0]
        self.assertFalse(helmet.card.IsExhaust())
        self.assertEqual(branch_game.world.event_manager.timing_occurrences, [])

    def test_nova_both_legal_checkpoint_supports_both_first_choices(self):
        path = OUTPUT_DIRECTORY / "02_nova_jarnbjorn_both_legal.json"
        for first_choice in ("nova", "jarnbjorn"):
            with self.subTest(first_choice=first_choice):
                chose_response = False

                def choose_first(prompt):
                    nonlocal chose_response
                    if chose_response:
                        return None
                    chose_response = True
                    if first_choice == "nova":
                        option = self._nova_option(prompt.options)
                        return CommandDescriptor(
                            option["choice_id"],
                            [str(option["all_legal_targets"][0])],
                            [],
                        )

                    option = self._jarnbjorn_option(prompt.options)
                    payments = self._payment_effect_ids(option)
                    self.assertTrue(payments)
                    return CommandDescriptor(
                        option["choice_id"],
                        [str(option["all_legal_targets"][0])],
                        [payments[0]],
                    )

                devices = HeadlessDeviceManager(
                    choice_provider=choose_first,
                )
                game = run_file_with_devices(path, devices)
                remaining = devices.stopped_prompt.options
                if first_choice == "nova":
                    self.assertGreater(
                        len(self._payment_effect_ids(self._jarnbjorn_option(remaining))),
                        0,
                    )
                else:
                    self.assertTrue(self._nova_option(remaining)["all_legal_targets"])
                self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_defensive_conditioning_constants_apply_without_timing_choice(self):
        path = OUTPUT_DIRECTORY / "03_defensive_conditioning_constants.json"
        setup_step = 0

        def play_conditioning(prompt):
            nonlocal setup_step
            if prompt.event_name == "WhenPlayerInTurn" and setup_step == 0:
                setup_step = 1
                Engine.game.controller_manager.console.SetCommand(
                    'Puzzle.PutIntoPlay("Defensive Conditioning")',
                    Engine.game.world,
                )
                return CommandDescriptor()
            if prompt.event_name == "WhenPlayerInTurn" and setup_step == 1:
                setup_step = 2
                Engine.game.controller_manager.console.SetCommand(
                    'Puzzle.ChangeForm("Stephen Strange", "Hero")',
                    Engine.game.world,
                )
                return CommandDescriptor()
            return None

        devices = HeadlessDeviceManager(
            choice_provider=play_conditioning,
        )
        game = run_file_with_devices(path, devices)
        player = game.world.const_players[0]
        identity = player.GetIdentity()
        hero = next(
            face for face in identity.card.printed_faces if Hero.IsType(face)
        )

        self.assertEqual(identity.max_health, identity.printed_health + 3)
        self.assertEqual(hero.defense, hero.printed_defense + 1)
        self.assertTrue(game.world.FindCardsOnField(name="Defensive Conditioning"))
        self.assertFalse(any(
            prompt.ability_type == "Constant"
            for prompt in devices.prompts
        ))
        self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_unuscione_teamwork_and_toughness_are_forced_once_in_either_order(self):
        path = OUTPUT_DIRECTORY / "04_unuscione_forced_order.json"
        for first_name in ("Teamwork", "Toughness"):
            with self.subTest(first_name=first_name):
                commands = [
                    'Puzzle.PutIntoPlay("32159")',
                    'Puzzle.Reveal("32163")',
                ]
                command_index = 0
                chose_forced = False

                def choose(prompt):
                    nonlocal command_index, chose_forced
                    if prompt.event_name == "WhenPlayerInTurn" and command_index < len(commands):
                        command = commands[command_index]
                        command_index += 1
                        return self._debug(command)
                    if prompt.ability_type == "ForcedResponse" and not chose_forced:
                        names = {option["name"] for option in prompt.options}
                        self.assertEqual(
                            names,
                            {"Unuscione:_Teamwork", "Unuscione:_Toughness"},
                        )
                        chose_forced = True
                        return self._choice(next(
                            option for option in prompt.options
                            if option["name"].endswith(f":_{first_name}")
                        ))
                    return None

                devices = HeadlessDeviceManager(choice_provider=choose)
                game = run_file_with_devices(path, devices)
                unuscione = game.world.FindCardsOnField(name="Unuscione")[0]
                main_scheme = game.world.FindCardsOnField(name="The Break-In!")[0]

                self.assertTrue(chose_forced)
                self.assertTrue(unuscione.IsTough())
                self.assertEqual(main_scheme.threat, 2)
                self.assertEqual(sum(
                    prompt.ability_type == "ForcedResponse"
                    for prompt in devices.prompts
                ), 1)
                self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_cancelled_when_revealed_cancels_surge_and_incite(self):
        path = OUTPUT_DIRECTORY / "05_cancel_surge_and_incite.json"
        commands = [
            'Puzzle.ChangeForm("01001b", "Hero")',
            'Puzzle.Reveal("01191")',
            'Puzzle.Reveal("04069")',
        ]
        command_index = 0
        cancellations = 0

        def choose(prompt):
            nonlocal command_index, cancellations
            if prompt.event_name == "WhenPlayerInTurn" and command_index < len(commands):
                command = commands[command_index]
                command_index += 1
                return self._debug(command)
            if prompt.event_name == "WhenPlayerRevealCard":
                option = prompt.options[0]
                payments = self._payment_effect_ids(option)
                self.assertTrue(payments)
                cancellations += 1
                # The final alternative is one of the injected double-resource
                # cards, preserving the second Enhanced Spider-Sense.
                return self._choice(option, resources=payments[-1:])
            return None

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = run_file_with_devices(path, devices)
        hero = game.world.const_players[0].GetIdentity()
        main_scheme = game.world.FindCardsOnField(name="The Break-In!")[0]

        self.assertEqual(cancellations, 2)
        self.assertFalse(hero.IsExhaust())
        self.assertEqual(main_scheme.threat, 0)
        self.assertFalse(any(
            prompt.event_name == "WhenCardRevealed"
            and prompt.ability_type == "Boost"
            for prompt in devices.prompts
        ))
        self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_alter_ego_assault_and_gang_up_grant_then_resolve_surge(self):
        for card_id, card_name in (("01187", "Assault"), ("01189", "Gang-Up")):
            with self.subTest(card_name=card_name):
                fixture = TimingFixture(
                    "conditional_surge_when_revealed.json",
                    f"{card_name} grants Surge in alter-ego form",
                    "rhino",
                    ("echo",),
                    720000 + int(card_id),
                    (),
                    (card_id, "01188"),
                )
                scene = build_fixture_scene(fixture)
                commands = [
                    f'Puzzle.CreateEncounterDeck("{card_id}", "01188")',
                    f'Puzzle.Reveal("{card_id}")',
                ]
                command_index = 0

                def choose(prompt):
                    nonlocal command_index
                    if prompt.event_name == "WhenPlayerInTurn" and command_index < len(commands):
                        command = commands[command_index]
                        command_index += 1
                        return self._debug(command)
                    if prompt.event_name == "WhenPlayerInTurn":
                        return None
                    return HeadlessDeviceManager._DefaultChoice(prompt)

                devices = HeadlessDeviceManager(choice_provider=choose)
                game = run_scene_with_devices(scene, devices)
                player = game.world.const_players[0]

                self.assertTrue(player.IsAlterEgo())
                self.assertEqual(player.GetIdentity().health, player.GetIdentity().max_health)
                self.assertEqual(
                    [face.paper.card_id for face in player.dealt_encounter_cards.Get()],
                    ["01188"],
                )
                self.assertIn(
                    card_id,
                    [
                        face.paper.card_id
                        for face in game.world.scenario.encounter_discard_pile.Get()
                    ],
                )
                self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_nested_get_behind_me_attack_finishes_before_reveal_resumes(self):
        path = OUTPUT_DIRECTORY / "06_nested_reveal_attack_defense.json"
        commands = [
            'Puzzle.ChangeForm("01001b", "Hero")',
            'Puzzle.Reveal("01186")',
        ]
        command_index = 0
        played_interrupt = False

        def choose(prompt):
            nonlocal command_index, played_interrupt
            if prompt.event_name == "WhenPlayerInTurn" and command_index < len(commands):
                command = commands[command_index]
                command_index += 1
                return self._debug(command)
            if prompt.event_name == "WhenPlayerRevealCard" and not played_interrupt:
                option = prompt.options[0]
                payments = self._payment_effect_ids(option)
                played_interrupt = True
                return self._choice(option, resources=payments[-1:])
            if played_interrupt and prompt.event_name == "WhenUnitWouldAttack":
                return self._choice(prompt.options[0])
            if played_interrupt and prompt.event_name == "WhenUnitBeingAttack":
                return CommandDescriptor()  # leave the nested attack undefended
            return None

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = run_file_with_devices(path, devices)
        events = [prompt.event_name for prompt in devices.prompts]
        hero = game.world.const_players[0].GetIdentity()
        main_scheme = game.world.FindCardsOnField(name="The Break-In!")[0]

        self.assertLess(events.index("WhenPlayerRevealCard"), events.index("WhenUnitWouldAttack"))
        self.assertLess(events.index("WhenUnitWouldAttack"), events.index("WhenUnitBeingAttack"))
        self.assertLess(hero.health, hero.max_health)
        self.assertEqual(main_scheme.threat, 0)
        self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_tough_quickstrike_and_vulnerable_use_status_priority(self):
        path = OUTPUT_DIRECTORY / "08_status_timing_lab.json"
        commands = [
            'Puzzle.ChangeForm("01001b", "Hero")',
            'Puzzle.Tough("01001a")',
            'Puzzle.Reveal("60182")',
            'Puzzle.Stun("60182")',
        ]
        command_index = 0

        def choose(prompt):
            nonlocal command_index
            if prompt.event_name == "WhenPlayerInTurn" and command_index < len(commands):
                command = commands[command_index]
                command_index += 1
                return self._debug(command)
            if prompt.event_name == "WhenUnitBeingAttack":
                return CommandDescriptor()
            return None

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = run_file_with_devices(path, devices)
        hero = game.world.const_players[0].GetIdentity()

        self.assertEqual(hero.health, hero.max_health)
        self.assertFalse(hero.IsTough())
        self.assertEqual(game.world.FindCardsOnField(name="Cop"), [])
        self.assertFalse(any(
            face.name in ("Stunned", "Confused")
            for face in game.world.FindCardsOnField()
        ))
        self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_ranged_attack_ignores_retaliate_but_normal_attack_does_not(self):
        path = OUTPUT_DIRECTORY / "09_retaliate_and_ranged.json"
        commands = [
            'Puzzle.ChangeForm("01029b", "Hero")',
            'Puzzle.PutIntoPlay("04020")',
            'Puzzle.PutIntoPlay("01172")',
        ]
        command_index = 0
        attack_stage = 0

        def choose(prompt):
            nonlocal command_index, attack_stage
            if prompt.event_name == "WhenPlayerInTurn" and command_index < len(commands):
                command = commands[command_index]
                command_index += 1
                return self._debug(command)
            if prompt.event_name == "WhenPlayerInTurn" and attack_stage < 2:
                attacks = [option for option in prompt.options if option.get("name") == "Attack"]
                if attack_stage == 0:
                    option = next(option for option in attacks if option.get("bind_id") == 1)
                else:
                    option = next(option for option in attacks if option.get("bind_id") != 1)
                attack_stage += 1
                return self._choice(option, [option["all_legal_targets"][-1]])
            return None

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = run_file_with_devices(path, devices)
        iron_man = game.world.FindCardsOnField(name="Iron Man")[0]
        war_machine = next(
            face for face in game.world.FindCardsOnField(name="War Machine")
            if face.paper.card_id == "04020"
        )
        whiplash = game.world.FindCardsOnField(name="Whiplash")[0]

        self.assertEqual(attack_stage, 2)
        self.assertEqual(iron_man.health, iron_man.max_health - 1)
        self.assertEqual(war_machine.health, war_machine.max_health)
        self.assertFalse(war_machine.IsTough())
        self.assertEqual(whiplash.health, 1)
        self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_martyr_response_occurs_after_consequential_damage(self):
        path = OUTPUT_DIRECTORY / "10_martyr_consequential_damage.json"
        commands = [
            'Puzzle.PutIntoPlay("19012")',
            'Puzzle.PutIntoPlay("01167")',
            'Puzzle.Damage("01167", 2)',
        ]
        command_index = 0
        attacked = False
        responded = False

        def choose(prompt):
            nonlocal command_index, attacked, responded
            if prompt.event_name == "WhenPlayerInTurn" and command_index < len(commands):
                command = commands[command_index]
                command_index += 1
                return self._debug(command)
            if prompt.event_name == "WhenPlayerInTurn" and not attacked:
                martyr_id = Engine.game.world.FindCardsOnField(name="Martyr")[0].card.object_id
                option = next(
                    option for option in prompt.options
                    if option.get("name") == "Attack" and option.get("bind_id") == martyr_id
                )
                attacked = True
                return self._choice(option, [option["all_legal_targets"][-1]])
            if prompt.event_name == "AfterAllyTakeConsequentialDamage" and not responded:
                responded = True
                return self._choice(prompt.options[0])
            return None

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = run_file_with_devices(path, devices)
        martyr = game.world.FindCardsOnField(name="Martyr")[0]

        self.assertTrue(responded)
        self.assertEqual(martyr.health, martyr.max_health - 1)
        self.assertTrue(martyr.IsTough())
        self.assertEqual(game.world.FindCardsOnField(name="Vulture"), [])
        self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_thor_overkill_keeps_defeat_and_attack_responses_available(self):
        path = OUTPUT_DIRECTORY / "11_thor_overkill_window.json"
        response_orders = (
            ("Jarnbjorn", "Battle Fury", "Chase Them Down"),
            ("Battle Fury", "Chase Them Down", "Jarnbjorn"),
            ("Chase Them Down", "Jarnbjorn", "Battle Fury"),
        )

        for response_order in response_orders:
            with self.subTest(first_response=response_order[0]):
                commands = [
                    'Puzzle.ChangeFormFor(0, "Hero")',
                    'Puzzle.PutIntoPlay("06009")',
                    'Puzzle.PutIntoPlay("06019")',
                    'Puzzle.PutIntoPlay("06018")',
                    'Puzzle.PutIntoPlay("01167")',
                    'Puzzle.Exhaust("06001a")',
                    'Puzzle.SetThreat("01097b", 2)',
                ]
                command_index = 0
                played_hammer_throw = False
                response_ids: dict[str, int] = {}
                initial_candidates: set[str] = set()
                resolved_responses: list[str] = []

                def choose(prompt):
                    nonlocal command_index, played_hammer_throw
                    if prompt.event_name == "WhenPlayerInTurn" and command_index < len(commands):
                        command = commands[command_index]
                        command_index += 1
                        return self._debug(command)
                    if prompt.event_name == "WhenUnitWouldAttack":
                        return self._choice(prompt.options[0])
                    if prompt.event_name == "WhenUnitBeingAttack":
                        return CommandDescriptor()  # Vulture's Quickstrike is undefended.
                    if prompt.event_name == "AfterMinionEngagePlayer":
                        return CommandDescriptor()  # Keep the fixture hand deterministic.
                    if prompt.event_name == "WhenPlayerInTurn" and not played_hammer_throw:
                        hammer_throw = next(
                            face
                            for face in Engine.game.world.const_players[0].hand_cards.Get()
                            if face.paper.card_id == "06005"
                        )
                        option = next(
                            option for option in prompt.options
                            if option.get("bind_id") == hammer_throw.card.object_id
                        )
                        payments = self._payment_effect_ids(option)
                        played_hammer_throw = True
                        return self._choice(
                            option,
                            [option["all_legal_targets"][-1]],
                            payments[1:3],
                        )
                    if prompt.event_name == "WhenPlayerChooseAbility":
                        return self._choice(prompt.options[0])

                    if played_hammer_throw and not response_ids:
                        world = Engine.game.world
                        response_ids.update({
                            "Jarnbjorn": world.FindCardsOnField(name="Jarnbjorn")[0].card.object_id,
                            "Battle Fury": world.FindCardsOnField(name="Battle Fury")[0].card.object_id,
                            "Chase Them Down": next(
                                face.card.object_id
                                for face in world.const_players[0].hand_cards.Get()
                                if face.name == "Chase Them Down"
                            ),
                        })

                    options_by_response = {
                        response_name: next(
                            (
                                option
                                for option in prompt.options
                                if option.get("bind_id") == response_id
                            ),
                            None,
                        )
                        for response_name, response_id in response_ids.items()
                    }
                    available_responses = {
                        response_name
                        for response_name, option in options_by_response.items()
                        if option != None
                    }
                    if available_responses:
                        if not initial_candidates:
                            initial_candidates.update(available_responses)
                        next_response = response_order[len(resolved_responses)]
                        option = options_by_response[next_response]
                        self.assertIsNotNone(option)
                        resolved_responses.append(next_response)

                        if next_response == "Jarnbjorn":
                            payments = self._payment_effect_ids(option)
                            return self._choice(
                                option,
                                [option["all_legal_targets"][-1]],
                                payments[:1],
                            )
                        if next_response == "Chase Them Down":
                            return self._choice(
                                option,
                                [option["all_legal_targets"][-1]],
                            )
                        return self._choice(option)
                    return None

                devices = HeadlessDeviceManager(choice_provider=choose)
                game = run_file_with_devices(path, devices)
                thor = game.world.FindCardsOnField(name="Thor")[0]
                rhino = game.world.FindCardsOnField(name="Rhino")[0]
                main_scheme = game.world.FindCardsOnField(name="The Break-In!")[0]

                self.assertTrue(played_hammer_throw)
                self.assertEqual(initial_candidates, set(response_order))
                self.assertEqual(resolved_responses, list(response_order))
                self.assertFalse(thor.IsExhaust())
                self.assertEqual(main_scheme.threat, 0)
                self.assertLess(rhino.health, rhino.max_health)
                self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_exhausted_ms_marvel_cannot_recur_defense_events_before_desperate_defense_readies_her(self):
        fixture = TimingFixture(
            "automated_ms_marvel_defense_timing.json",
            "Exhausted Ms. Marvel defense timing",
            "rhino",
            ("ms_marvel",),
            180017,
            (
                'Puzzle.ClearHand()',
                'Puzzle.CreateHandCards("05005", "09015", "01090")',
                'Puzzle.PutIntoPlay("01167")',
            ),
            ("05005", "09015", "01090", "01167"),
        )
        scene = build_fixture_scene(fixture)
        commands = [
            'Puzzle.ChangeFormFor(0, "Hero")',
            'Puzzle.Exhaust("05001a")',
            'Puzzle.DoAttack("Vulture")',
        ]
        command_index = 0
        played_wiggle_room = False
        played_desperate_defense = False
        morphogenetics_offered = False
        exhausted_during_defense_events: list[bool] = []

        def choose(prompt):
            nonlocal command_index
            nonlocal played_wiggle_room, played_desperate_defense
            nonlocal morphogenetics_offered

            if prompt.event_name == "WhenPlayerInTurn" and command_index < len(commands):
                command = commands[command_index]
                command_index += 1
                return self._debug(command)
            if prompt.event_name == "WhenPlayerInTurn":
                return None
            if prompt.event_name == "WhenUnitBeingAttack":
                return CommandDescriptor()  # Do not make a basic defense.

            morphogenetics = next(
                (
                    option
                    for option in prompt.options
                    if "Morphogenetics" in option.get("name", "")
                ),
                None,
            )
            if morphogenetics != None:
                morphogenetics_offered = True
                return CommandDescriptor()

            hand = Engine.game.world.const_players[0].hand_cards.Get()
            if prompt.event_name == "WhenUnitWouldTakeDamage" and not played_wiggle_room:
                wiggle_room = next(face for face in hand if face.paper.card_id == "05005")
                option = next(
                    option
                    for option in prompt.options
                    if option.get("bind_id") == wiggle_room.card.object_id
                )
                hero = Engine.game.world.const_players[0].GetHero()
                exhausted_during_defense_events.append(hero.IsExhaust())
                played_wiggle_room = True
                return self._choice(option)

            if prompt.event_name == "WhenUnitWouldDefend" and not played_desperate_defense:
                desperate_defense = next(face for face in hand if face.paper.card_id == "09015")
                option = next(
                    option
                    for option in prompt.options
                    if option.get("bind_id") == desperate_defense.card.object_id
                )
                payments = self._payment_effect_ids(option)
                hero = Engine.game.world.const_players[0].GetHero()
                exhausted_during_defense_events.append(hero.IsExhaust())
                played_desperate_defense = True
                return self._choice(option, resources=payments[:1])

            return None

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = run_scene_with_devices(scene, devices)
        player = game.world.const_players[0]
        ms_marvel = player.GetHero()
        discarded_ids = [face.paper.card_id for face in player.discard_pile.Get()]

        self.assertEqual(command_index, len(commands))
        self.assertTrue(played_wiggle_room)
        self.assertTrue(played_desperate_defense)
        self.assertEqual(exhausted_during_defense_events, [True, True])
        self.assertFalse(morphogenetics_offered)
        self.assertFalse(ms_marvel.IsExhaust())
        self.assertEqual(ms_marvel.health, ms_marvel.max_health)
        self.assertIn("05005", discarded_ids)
        self.assertIn("09015", discarded_ids)
        self.assertEqual(ms_marvel.defense, ms_marvel.printed_defense)
        self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_basic_defense_automatically_targets_the_only_attacker(self):
        fixture = TimingFixture(
            "automated_singleton_defense_target.json",
            "Singleton defense target",
            "rhino",
            ("ms_marvel",),
            180018,
            ('Puzzle.PutIntoPlay("01167")',),
            ("01167",),
        )
        scene = build_fixture_scene(fixture)
        commands = [
            'Puzzle.ChangeFormFor(0, "Hero")',
            'Puzzle.DoAttack("Vulture")',
        ]
        command_index = 0
        declared_defense = False
        automatic_target: list[int] = []

        def choose(prompt):
            nonlocal command_index, declared_defense, automatic_target
            if prompt.event_name == "WhenPlayerInTurn" and command_index < len(commands):
                command = commands[command_index]
                command_index += 1
                return self._debug(command)
            if prompt.event_name == "WhenPlayerInTurn":
                return None
            if prompt.event_name == "WhenUnitBeingAttack" and not declared_defense:
                hero = Engine.game.world.const_players[0].GetHero()
                option = next(
                    option
                    for option in prompt.options
                    if option.get("bind_id") == hero.card.object_id
                )
                automatic_target = list(option.get("automatic_targets", []))
                self.assertEqual(
                    automatic_target,
                    list(option.get("all_legal_targets", [])),
                )
                self.assertFalse(option.get("automatic_submit"))
                declared_defense = True
                # The attacker is preselected, but the web client now waits
                # for OK so the player can cancel and choose another defender.
                # The eventual command remains targetless on the wire and the
                # controller restores the descriptor's automatic target.
                return CommandDescriptor(
                    str(option.get("choice_id") or option["id"]),
                    [],
                    [],
                )
            return None

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = run_scene_with_devices(scene, devices)
        hero = game.world.const_players[0].GetHero()
        vulture = game.world.FindCardsOnField(name="Vulture")[0]

        self.assertTrue(declared_defense)
        self.assertEqual(automatic_target, [vulture.card.object_id])
        self.assertTrue(hero.IsExhaust())
        self.assertLess(hero.health, hero.max_health)
        self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_optional_enter_play_responses_require_confirmation_for_only_target(self):
        for card_id, card_name in (("33011", "Beast"), ("40014", "Caliban")):
            with self.subTest(card_name=card_name):
                fixture = TimingFixture(
                    "optional_response_confirmation.json",
                    f"{card_name} optional response confirmation",
                    "rhino",
                    ("echo",),
                    730000 + int(card_id),
                    (),
                    (card_id,),
                )
                scene = build_fixture_scene(fixture)
                put_into_play = False

                def choose(prompt):
                    nonlocal put_into_play
                    if prompt.event_name == "WhenPlayerInTurn" and not put_into_play:
                        put_into_play = True
                        return self._debug(f'Puzzle.PutIntoPlay("{card_id}")')
                    if (
                        prompt.event_name == "AfterCardEnterPlay" and
                        prompt.ability_type == "Response"
                    ):
                        return None
                    return HeadlessDeviceManager._DefaultChoice(prompt)

                devices = HeadlessDeviceManager(choice_provider=choose)
                game = run_scene_with_devices(scene, devices)
                prompt = devices.stopped_prompt

                self.assertIsNotNone(prompt)
                self.assertTrue(prompt.show_cancel)
                self.assertEqual(prompt.ability_type, "Response")
                self.assertEqual(prompt.event_name, "AfterCardEnterPlay")
                self.assertEqual(len(prompt.options), 1)
                option = prompt.options[0]
                card = game.world.FindCardsOnField(name=card_name)[0]
                self.assertEqual(option.get("all_legal_targets"), [card.card.object_id])
                self.assertEqual(option.get("automatic_targets"), [card.card.object_id])
                self.assertFalse(option.get("automatic_submit"))
                self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_optional_interrupts_require_confirmation_for_only_target(self):
        echo_fixture = TimingFixture(
            "optional_echo_interrupt_confirmation.json",
            "Echo optional interrupt confirmation",
            "rhino",
            ("echo",),
            770001,
            (),
            (),
        )
        echo_changed_form = False

        def choose_echo(prompt):
            nonlocal echo_changed_form
            if prompt.event_name == "WhenPlayerInTurn" and not echo_changed_form:
                echo_changed_form = True
                return self._debug('Puzzle.ChangeFormFor(0, "Hero")')
            if (
                prompt.event_name == "WhenUnitWouldChangeForm" and
                prompt.ability_type == "Interrupt"
            ):
                return None
            return HeadlessDeviceManager._DefaultChoice(prompt)

        echo_devices = HeadlessDeviceManager(choice_provider=choose_echo)
        echo_game = run_scene_with_devices(
            build_fixture_scene(echo_fixture),
            echo_devices,
        )
        echo_prompt = echo_devices.stopped_prompt

        self.assertIsNotNone(echo_prompt)
        self.assertTrue(echo_prompt.show_cancel)
        self.assertEqual(echo_prompt.ability_type, "Interrupt")
        self.assertEqual(echo_prompt.event_name, "WhenUnitWouldChangeForm")
        self.assertEqual(len(echo_prompt.options), 1)
        echo_option = echo_prompt.options[0]
        self.assertEqual(
            echo_option.get("automatic_targets"),
            echo_option.get("all_legal_targets"),
        )
        self.assertFalse(echo_option.get("automatic_submit"))
        self.assertEqual(echo_game.world.event_manager.timing_occurrences, [])

        bamf_fixture = TimingFixture(
            "optional_bamf_interrupt_confirmation.json",
            "Bamf optional interrupt confirmation",
            "rhino",
            ("nightcrawler",),
            770002,
            (
                'Puzzle.ClearHand()',
                'Puzzle.CreateHandCards("48006")',
            ),
            ("48006",),
        )
        bamf_stage = 0

        def choose_bamf(prompt):
            nonlocal bamf_stage
            if prompt.event_name == "WhenPlayerInTurn" and bamf_stage == 0:
                bamf_stage = 1
                return self._debug('Puzzle.ChangeFormFor(0, "Hero")')
            if prompt.event_name == "WhenPlayerInTurn" and bamf_stage == 1:
                bamf = Engine.game.world.const_players[0].hand_cards.FindCard(
                    name="Bamf!"
                )
                option = next(
                    option
                    for option in prompt.options
                    if option.get("name") == "Play"
                    and option.get("bind_id") == bamf.card.object_id
                )
                bamf_stage = 2
                return self._choice(option)
            if prompt.event_name == "WhenPlayerInTurn" and bamf_stage == 2:
                bamf_stage = 3
                return self._debug('Puzzle.DoAttack("Rhino")')
            if (
                prompt.event_name == "WhenUnitWouldAttack" and
                prompt.ability_type == "Interrupt"
            ):
                return None
            return HeadlessDeviceManager._DefaultChoice(prompt)

        bamf_devices = HeadlessDeviceManager(choice_provider=choose_bamf)
        bamf_game = run_scene_with_devices(
            build_fixture_scene(bamf_fixture),
            bamf_devices,
        )
        bamf_prompt = bamf_devices.stopped_prompt

        self.assertIsNotNone(bamf_prompt)
        self.assertTrue(bamf_prompt.show_cancel)
        self.assertEqual(bamf_prompt.ability_type, "Interrupt")
        self.assertEqual(bamf_prompt.event_name, "WhenUnitWouldAttack")
        self.assertEqual(len(bamf_prompt.options), 1)
        bamf_option = bamf_prompt.options[0]
        self.assertEqual(
            bamf_option.get("automatic_targets"),
            bamf_option.get("all_legal_targets"),
        )
        self.assertFalse(bamf_option.get("automatic_submit"))
        self.assertEqual(bamf_game.world.event_manager.timing_occurrences, [])

    def test_indirect_damage_keeps_each_target_and_tough_replacement(self):
        path = OUTPUT_DIRECTORY / "12_indirect_divided_damage.json"
        commands = [
            'Puzzle.PutIntoPlay("04020")',
            'Puzzle.PutIntoPlay("19012")',
            'Puzzle.Reveal("29040")',
        ]
        command_index = 0
        assigned = False

        def choose(prompt):
            nonlocal command_index, assigned
            if prompt.event_name == "WhenPlayerInTurn" and command_index < len(commands):
                command = commands[command_index]
                command_index += 1
                return self._debug(command)
            if prompt.event_name == "WhenPlayerChooseAbility" and not assigned:
                option = prompt.options[0]
                war_machine = Engine.game.world.FindCardsOnField(name="War Machine")[0]
                martyr = Engine.game.world.FindCardsOnField(name="Martyr")[0]
                assigned = True
                return self._choice(
                    option,
                    [war_machine.card.object_id] + [martyr.card.object_id] * 3,
                )
            return None

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = run_file_with_devices(path, devices)
        war_machine = game.world.FindCardsOnField(name="War Machine")[0]

        self.assertTrue(assigned)
        self.assertEqual(war_machine.health, war_machine.max_health)
        self.assertFalse(war_machine.IsTough())
        self.assertEqual(game.world.FindCardsOnField(name="Martyr"), [])
        self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_basic_thwart_orders_when_defeated_victory_and_response(self):
        path = OUTPUT_DIRECTORY / "13_thwart_and_scheme_defeat.json"
        commands = [
            'Puzzle.ChangeForm("01010b", "Hero")',
            'Puzzle.PutIntoPlay("04047")',
            'Puzzle.Reveal("16127")',
            'Puzzle.SetThreat("16127", 2)',
        ]
        command_index = 0
        thwarted = False
        confirmed_optional_choices = 0
        confirmed_optional_responses = 0

        def choose(prompt):
            nonlocal command_index, thwarted
            nonlocal confirmed_optional_choices, confirmed_optional_responses
            if prompt.event_name == "WhenPlayerInTurn" and command_index < len(commands):
                command = commands[command_index]
                command_index += 1
                return self._debug(command)
            if prompt.event_name == "WhenPlayerInTurn" and not thwarted:
                option = next(option for option in prompt.options if option.get("name") == "Thwart")
                thwarted = True
                return self._choice(option, [option["all_legal_targets"][-1]])
            if prompt.ability_type == "ForcedInterrupt":
                option = next(
                    (option for option in prompt.options if option.get("name") == "When_Defeated"),
                    prompt.options[0],
                )
                return self._choice(option)
            if prompt.event_name == "WhenPlayerChooseAbility":
                option = prompt.options[0]
                self.assertEqual(
                    option.get("automatic_targets"),
                    option.get("all_legal_targets"),
                )
                # The Egg's optional ready effect still offers Cancel even
                # when the identity is its only legal target.
                self.assertEqual(prompt.options[-1]["name"], "Cancel")
                self.assertFalse(option.get("automatic_submit"))
                confirmed_optional_choices += 1
                return CommandDescriptor(
                    str(option.get("choice_id") or option["id"]),
                    [],
                    [],
                )
            if prompt.event_name == "AfterSchemeBeDefeated":
                option = prompt.options[0]
                self.assertEqual(
                    option.get("automatic_targets"),
                    option.get("all_legal_targets"),
                )
                self.assertFalse(option.get("automatic_submit"))
                confirmed_optional_responses += 1
                return CommandDescriptor(
                    str(option.get("choice_id") or option["id"]),
                    [],
                    [],
                )
            return None

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = run_file_with_devices(path, devices)
        identity = game.world.const_players[0].GetIdentity()
        investigator = game.world.FindCardsOnField(name="Skilled Investigator")[0]

        self.assertFalse(identity.IsExhaust())
        self.assertTrue(investigator.IsExhaust())
        self.assertEqual(len(game.world.const_players[0].hand_cards.Get()), 1)
        self.assertEqual(confirmed_optional_choices, 1)
        self.assertEqual(confirmed_optional_responses, 1)
        self.assertEqual(game.world.FindCardsOnField(name="Hujahdarian Monarch Egg"), [])
        self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_recovery_responses_can_resolve_in_either_order(self):
        path = OUTPUT_DIRECTORY / "14_recovery_response_window.json"
        for first_name in ("Response", "Cartoon_Power"):
            with self.subTest(first_name=first_name):
                commands = [
                    'Puzzle.PutIntoPlay("44008")',
                    'Puzzle.Damage("30001b", 2)',
                ]
                command_index = 0
                recovered = False
                response_count = 0

                def choose(prompt):
                    nonlocal command_index, recovered, response_count
                    if prompt.event_name == "WhenPlayerInTurn" and command_index < len(commands):
                        command = commands[command_index]
                        command_index += 1
                        return self._debug(command)
                    if prompt.event_name == "WhenPlayerInTurn" and not recovered:
                        option = next(option for option in prompt.options if option.get("name") == "Recover")
                        recovered = True
                        return self._choice(option)
                    if prompt.event_name in ("AfterUnitRecovery", "AfterUnitUseBasicPower"):
                        response_count += 1
                        option = next(
                            (option for option in prompt.options if option.get("name") == first_name),
                            prompt.options[0],
                        )
                        return self._choice(option)
                    return None

                devices = HeadlessDeviceManager(choice_provider=choose)
                game = run_file_with_devices(path, devices)
                identity = game.world.const_players[0].GetIdentity()
                truck = game.world.FindCardsOnField(name="Chimichanga Truck")[0]

                self.assertGreaterEqual(response_count, 1)
                self.assertFalse(identity.IsExhaust())
                self.assertTrue(truck.IsExhaust())
                self.assertEqual(identity.GetCounters("toon"), 1)
                self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_side_and_main_scheme_lifecycle_effects_survive_area_changes(self):
        path = OUTPUT_DIRECTORY / "15_scheme_lifecycle.json"
        commands = [
            'Puzzle.ChangeForm("01010b", "Hero")',
            'Puzzle.Reveal("16178a")',
            'Puzzle.SetThreat("16178a", 2)',
        ]
        command_index = 0
        thwarted = False
        completed_main = False

        def choose(prompt):
            nonlocal command_index, thwarted, completed_main
            if prompt.event_name == "WhenPlayerInTurn" and command_index < len(commands):
                command = commands[command_index]
                command_index += 1
                return self._debug(command)
            if prompt.event_name == "WhenPlayerInTurn" and not thwarted:
                option = next(option for option in prompt.options if option.get("name") == "Thwart")
                thwarted = True
                return self._choice(option, [option["all_legal_targets"][-1]])
            if prompt.ability_type == "ForcedInterrupt":
                option = next(
                    (option for option in prompt.options if option.get("name") == "When_Defeated"),
                    prompt.options[0],
                )
                return self._choice(option)
            if prompt.event_name == "WhenPlayerChooseAbility":
                return self._choice(prompt.options[0])
            if prompt.event_name == "WhenPlayerInTurn" and thwarted and not completed_main:
                completed_main = True
                return self._debug('Puzzle.SetThreat("02004b", 7)')
            return None

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = run_file_with_devices(path, devices)
        enterprise = game.world.FindCardsOnField(name="Criminal Enterprise")[0]
        corporate = game.world.FindCardsOnField(name="Corporate Acquisition")[0]

        self.assertTrue(completed_main)
        # Criminal Enterprise begins with 2 infamy in standard Risky
        # Business; Hostile Takeover's When Completed adds exactly 1.
        self.assertEqual(enterprise.GetCounters("infamy"), 3)
        self.assertEqual(corporate.paper.card_id, "02005b")
        self.assertEqual(game.world.FindCardsOnField(name="Badoon Blitz"), [])
        self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_multiplayer_optional_responses_rotate_from_first_player(self):
        path = OUTPUT_DIRECTORY / "16_multiplayer_priority.json"
        commands = [
            'Puzzle.ChangeFormFor(0, "Hero")',
            'Puzzle.ChangeFormFor(1, "Hero")',
            'Puzzle.PutIntoPlayFor(0, "04047")',
            'Puzzle.PutIntoPlayFor(1, "04047")',
            'Puzzle.Reveal("16127")',
            'Puzzle.SetThreat("16127", 2)',
        ]
        command_index = 0
        thwarted = False
        response_players: list[int] = []

        def choose(prompt):
            nonlocal command_index, thwarted
            if prompt.player_id == 0 and prompt.event_name == "WhenPlayerInTurn" and command_index < len(commands):
                command = commands[command_index]
                command_index += 1
                return self._debug(command)
            if prompt.event_name == "WhenPlayerChooseAbility" and command_index == 3:
                return self._choice(prompt.options[0])
            if prompt.player_id == 0 and prompt.event_name == "WhenPlayerInTurn" and not thwarted:
                option = next(option for option in prompt.options if option.get("name") == "Thwart")
                thwarted = True
                return self._choice(option, [option["all_legal_targets"][-1]])
            if prompt.ability_type == "ForcedInterrupt":
                option = next(
                    (option for option in prompt.options if option.get("name") == "When_Defeated"),
                    prompt.options[0],
                )
                return self._choice(option)
            if prompt.event_name == "WhenPlayerChooseAbility":
                return self._choice(prompt.options[-1])
            if prompt.event_name == "AfterSchemeBeDefeated":
                response_players.append(prompt.player_id)
                return self._choice(prompt.options[0])
            return None

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = run_file_with_devices(path, devices)
        investigators = game.world.FindCardsOnField(name="Skilled Investigator")

        self.assertEqual(response_players, [0, 1])
        self.assertTrue(all(card.IsExhaust() for card in investigators))
        self.assertEqual(
            [len(player.hand_cards.Get()) for player in game.world.const_players],
            [1, 1],
        )
        self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_into_the_fray_removes_threat_for_excess_damage(self):
        fixture = TimingFixture(
            "",
            "Into the Fray excess damage",
            "rhino",
            ("spider_man",),
            180017,
            (
                'Puzzle.ChangeFormFor(0, "Hero")',
                'Puzzle.ClearHand()',
                'Puzzle.CreateHandCards("13013", "01088", "01089")',
                'Puzzle.PutIntoPlay("01157")',
                'Puzzle.SetThreat("01097b", 3)',
            ),
            ("13013", "01088", "01089", "01157", "01097b"),
        )
        scene = build_fixture_scene(fixture)
        played = False

        def choose(prompt):
            nonlocal played
            world = Engine.game.world
            if prompt.event_name == "WhenPlayerInTurn" and not played:
                into_the_fray = next(
                    face
                    for face in world.const_players[0].hand_cards.Get()
                    if face.paper.card_id == "13013"
                )
                killmonger = world.FindCardsOnField(name="Killmonger")[0]
                option = next(
                    option
                    for option in prompt.options
                    if option.get("bind_id") == into_the_fray.card.object_id
                )
                played = True
                return self._choice(
                    option,
                    [killmonger.card.object_id],
                    self._payment_effect_ids(option),
                )
            if prompt.event_name == "WhenPlayerChooseAbility" and played:
                return self._choice(prompt.options[0])
            if prompt.event_name == "WhenPlayerInTurn" and played:
                return None
            return HeadlessDeviceManager._DefaultChoice(prompt)

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = run_scene_with_devices(scene, devices)
        main_scheme = game.world.FindCardsOnField(name="The Break-In!")[0]

        self.assertEqual(main_scheme.threat, 2)
        self.assertEqual(game.world.FindCardsOnField(name="Killmonger"), [])
        self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_photon_beam_places_two_progress_when_it_defeats_an_enemy(self):
        fixture = TimingFixture(
            "",
            "Photon Beam defeat progress",
            "rhino",
            ("ironheart",),
            180018,
            (
                'Puzzle.ChangeFormFor(0, "Hero")',
                'Puzzle.ClearHand()',
                'Puzzle.CreateHandCards("29006", "01088")',
                'Puzzle.PutIntoPlay("60203")',
            ),
            ("29006", "01088", "60203"),
        )
        scene = build_fixture_scene(fixture)
        played = False

        def choose(prompt):
            nonlocal played
            world = Engine.game.world
            if prompt.event_name == "WhenPlayerInTurn" and not played:
                photon_beam = next(
                    face
                    for face in world.const_players[0].hand_cards.Get()
                    if face.paper.card_id == "29006"
                )
                tracksuit_bro = world.FindCardsOnField(name="Tracksuit Bro")[0]
                option = next(
                    option
                    for option in prompt.options
                    if option.get("bind_id") == photon_beam.card.object_id
                )
                played = True
                return self._choice(
                    option,
                    [tracksuit_bro.card.object_id],
                    self._payment_effect_ids(option),
                )
            if prompt.event_name == "WhenPlayerInTurn" and played:
                return None
            return HeadlessDeviceManager._DefaultChoice(prompt)

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = run_scene_with_devices(scene, devices)
        ironheart = game.world.const_players[0].GetIdentity()

        self.assertEqual(ironheart.GetCounters("progress"), 2)
        self.assertEqual(game.world.event_manager.timing_occurrences, [])

    def test_recorded_nova_inputs_end_at_the_attack_that_opens_the_window(self):
        expected_lengths = {
            "01_nova_jarnbjorn_unlock.json": 7,
            "02_nova_jarnbjorn_both_legal.json": 8,
        }
        for filename, expected_length in expected_lengths.items():
            with self.subTest(filename=filename):
                scene = validate_file(OUTPUT_DIRECTORY / filename)
                self.assertFalse(scene.is_puzzle)
                self.assertEqual(len(scene.inputs), expected_length)
                self.assertIn("Attack", scene.inputs[-1].effect.id)
                self.assertTrue(scene.inputs[-1].crc)


if __name__ == "__main__":
    unittest.main()
