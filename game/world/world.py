from typing import Final, TypeAlias
from core import *

from game.card.face import *
from game.ability import *
from game.player import *
from game.deck import *
from game.scene import *
from game.message import *
from engine.job import JobManager
from engine.controller import *
from game.world.game_area import *
from engine.lib import Json
from game.world.game_over import GameOverReason

from game.world.world_action import WorldAction
from game.world.world_find import WorldFind
from game.world.phase import Phase, PhaseName

from game.world.variable import Variable
from game.world.world_rule import WorldRule
from game.world.world_stat import WorldStat
from game.world.world_render import WorldRender
from game.world.cheat.cheat_cmd import CheatCommand

GAME_OVER: TypeAlias = Literal[True, False]


def IsUsingPoolAspect(hero: 'HeroDescriptor', player: 'Player') -> bool:
    selected_aspects = [hero.aspect, hero.aspect2]
    selected_aspects = [
        aspect.strip().lower().lstrip("'")
        for aspect in selected_aspects
        if aspect.strip()
    ]
    if selected_aspects:
        return "pool" in selected_aspects

    # Legacy deck files did not store their selected aspect. Avoid treating a
    # legal off-aspect inclusion as a selected aspect; only infer 'Pool when it
    # is the sole aspect represented in the deck.
    has_pool_cards = player.player_deck.FindCardSize(
        CardFinder(card_class="'Pool")
    ) > 0
    has_other_aspect_cards = player.player_deck.FindCardSize(
        CardFinder(card_classes=[
            "Aggression",
            "Justice",
            "Leadership",
            "Protection",
        ])
    ) > 0
    return has_pool_cards and not has_other_aspect_cards


def IsTeamUpForPlayers(
    team_up_card: 'HasTeamUp',
    player: 'Player',
    other_player: 'Player',
) -> bool:
    """Return whether the Team-Up card names these two identities."""
    first_character, second_character = team_up_card.team_up
    return (
        player.IsName(*first_character) and
        other_player.IsName(*second_character)
    ) or (
        player.IsName(*second_character) and
        other_player.IsName(*first_character)
    )


def DoesIdentitySpecificAllyMatchPlayer(
    ally: 'Ally',
    player: 'Player',
) -> bool:
    """Match an ally to an identity using its hero/alter-ego names."""
    identity = player.GetIdentity()
    if not ally.CanCoexistWith(identity):
        return True

    # Some signature allies use the other identity's alter-ego as their
    # title (for example, Shuri and T'Challa), so the normal in-play unique
    # check alone does not identify every v1.8 deck-construction match.
    ally_names = [ally.name]
    if ally.printed_subtitle:
        ally_names.append(ally.printed_subtitle)
    return player.IsName(*ally_names)


def FindTeamUpAllyRemovalCandidates(
    players: Sequence['Player'],
) -> Dict['Player', List['Ally']]:
    """Find loaded signature allies eligible for the v1.8 Team-Up swap."""
    candidates: Dict['Player', List['Ally']] = {}

    for player in players:
        loaded_deck = player.player_deck.GetAll()
        team_up_cards = [
            face for face in loaded_deck
            if HasTeamUp.IsType(face)
        ]
        identity_specific_allies = [
            face for face in loaded_deck
            if Ally.IsType(face) and
            ClassCard.IsType(face) and
            face.IsClass("IdentitySpecific")
        ]

        matching_allies: Set['Ally'] = set()
        for other_player in players:
            if other_player == player:
                continue
            if not any(
                IsTeamUpForPlayers(team_up_card, player, other_player)
                for team_up_card in team_up_cards
            ):
                continue
            matching_allies.update(
                ally for ally in identity_specific_allies
                if DoesIdentitySpecificAllyMatchPlayer(ally, other_player)
            )

        if matching_allies:
            candidates[player] = sorted(
                matching_allies,
                key=lambda ally: (ally.name, ally.paper.card_id),
            )

    return candidates


class World(WorldAction, WorldFind):

    def __init__(self, scene: 'Scene', controllers: List['Controller']) -> None:
        from game.deck import Deck2, DeckType
        from game.card.face.base import SchemeSide2
        from game.card.face.card_type import Environment
        from game.card.face.card_type import MainScheme
        from game.event.manager import EventManager
        from game.buff.manager import BuffManager
        # from game.message.on_event.manager import OnEventManager
        from game.object.manager import ObjectManager
        from game.operate.worlds import Worlds
        from game.world.limit_monitor import PlayerSideSchemeLimit

        self.object_manager = ObjectManager()
        self.rule = WorldRule()
        self.render = WorldRender(self)

        self.scenario = Scenario("Scenario", self)
        scenario = self.GetScenario()

        self.game_areas: List['GameArea'] = [GameArea(self)]

        self.players: List['Player'] = []
        # Add separate game area
        # Cards and components in one game area cannot affect another game area
        # Players cannot attack or defend enmies in other game areas
        # Players cannot target any game elements in the other game areas

        self.const_seat_order_players: List['Player'] = []
        self.current_player: 'Player|None' = None
        self.asking_player: List['Player'] = []

        self.phase = Phase()
        self.stat = WorldStat()
        self.store = Variable()

        self.area_removed       = Deck2(scenario, DeckType.RemovedArea, CardFace)
        self.area_insert        = Deck2(scenario, DeckType.RemovedArea, Insert)
        self.area_status_cards  = Deck2(scenario, DeckType.RemovedArea, CardFace)
        self.aside_deck         = Deck2(scenario, DeckType.AsideDeck, CardFace)
        self.aside_modular      = Deck2(scenario, DeckType.AsideDeck, CardFace)
        self.area_boosting      = Deck2(scenario, DeckType.BoostingArea, CardFace)
        self.area_environment   = Deck2(scenario, DeckType.EnvironmentArea, Environment)
        self.area_evidence      = Deck2(scenario, DeckType.EvidenceArea, Evidence)
        self.area_rule          = Deck2(scenario, DeckType.RuleArea, CardFace)
        self.area_mission       = Deck2(scenario, DeckType.MissionArea, CardFace)
        self.area_processing    = Deck2(scenario, DeckType.ProcessingArea, CardFace)
        self.area_revealing     = Deck2(scenario, DeckType.RevealingArea, CardFace)

        self.victory_display    = Deck2(scenario, DeckType.VictoryDisplay, CardFace)

        self.area_schemes_main  = Deck2(scenario, DeckType.MainSchemesArea, MainScheme)
        self.area_schemes_side  = Deck2(scenario, DeckType.SideSchemesArea, SchemeSide2)
        self.main_schemes_deck  = Deck2(scenario, DeckType.MainSchemesDeck, MainScheme)

        self.round_id = 0
        self.phase_id = 0
        self.event_manager = EventManager(self)
        self.buff_manager = BuffManager(self)
        # self.on_event_manager = OnEventManager(self)
        self.scene = scene

        self.game_over = GameOverReason(self)

        player_num = len(scene.players)

        for i in (0, 1, 2, 3)[:player_num]:
            player = Player(scene.players[i].name, controllers[i], i, self)
            self.players.append(player)
            self.const_seat_order_players.append(player)

        self.started_player_num: Final = player_num

        self.additional_decks: List[Deck] = []
        self.additional_discard_piles: List[Deck] = []
        self.set_aside_reference_card_ids: List[str] = []

        self.scenario_decks: Dict[Worlds.ASIDE_DECK_NAME, SetAsideDeck] = {}
        for name in Types.LiteralToList(Worlds.ASIDE_DECK_NAME):
            self.scenario_decks[name] = SetAsideDeck()

        self.limit_player_side_scheme = PlayerSideSchemeLimit(self)
        self.controller_manager = controllers[0].manager
        self.cheat = CheatCommand(self)

        from game.operate.campaign_logs import CampaignLog
        for name in scene.campaign.campaign_log:
            value = scene.campaign.campaign_log[name]
            CampaignLog.SetStr(name, value, self)

        self.insert: Insert

    ################################################################################
    #
    def LoadFromJson(self, file_name: str, controllers: List['Controller']) -> None:
        from game.render.descriptor.world import WorldDescriptor
        from game.card.factory import CardFactory

        world_descriptor = Json.LoadAs(file_name, WorldDescriptor)
        self.players = []
        for i in (0, 1, 2, 3)[:world_descriptor.players]:
            player = Player(world_descriptor.players[i].area_hero[0].name, controllers[i], i, self)
            self.players.append(player)
            self.const_seat_order_players.append(player)
            player.setup.SelectIdentity(player.name,
                [world_descriptor.players[i].area_hero[0].card_id] + world_descriptor.players[i].area_hero[0].down_card_ids,
                [], [], [], [])

            for card in world_descriptor.players[i].player_deck:
                CardFactory.GenerateCard(card.card_id, self.players[0].player_deck, self)

            for card in world_descriptor.players[i].hand_cards:
                CardFactory.GenerateCard(card.card_id, self.players[0].hand_cards, self)

            pass

        for card in world_descriptor.villain_deck:
            CardFactory.GenerateCard(card.card_id, self.scenario.villain_deck, self)

    ################################################################################
    #
    def GetScenario(self) -> 'Scenario':
        return self.scenario

    def GetFirstGameArea(self) -> 'GameArea':
        return self.game_areas[0]

    def CreateGameArea(self) -> 'GameArea':
        self.game_areas.append(GameArea(self))
        return self.game_areas[-1]

    def SelectScenario(self, villains: Sequence[str], schemes: Sequence[str]) -> None:
        from game.card.factory import CardFactory
        from game.effect.rule import GameRule

        main_schemes = CardFactory.GenerateCards(schemes, self.main_schemes_deck, self)
        main_scheme = main_schemes[0].face

        main_scheme.PutIntoPlay(self.GetFirstPlayer(), GameRule(main_scheme))

        self.GetScenario().SelectVillain(villains)

    def Initialize(self) -> None:
        from game.card.factory import CardFactory
        from game.message import Message
        from game.effect.rule import GameRule
        from game.operate.worlds import Worlds
        from game.operate.faces import Faces

        # We register these ability bind card main scheme
        self.event_manager.RegisterPlayRule()

        initialize_message = Message.WhenGameInitialize(self)
        initialize_message.Send()

        Message.TextRender("\n--- Select Hero and Villain ---", self)
        # [x] 1. Select Identities
        # [x] 2. Set Hit Points
        # [x] 3. Select First Player
        # [x] 4. Set Aside Obligation
        # [x] 5. Set Aside Nemesis Sets
        # [x] 6. Shuffle Player Decks
        for player in self.const_players:
            i = self.const_players.index(player)
            scene_player = self.scene.players[i]
            player.setup.SelectIdentity(scene_player.name, scene_player.hero, scene_player.hero_deck, scene_player.obligations, scene_player.nemesis_set, scene_player.player_deck)

        if self.is_game_over:
            return

        # Preserve the eligible cards from the originally loaded deck. Setup
        # may move the ally before the choice that precedes the opening draw.
        team_up_ally_removal_candidates = FindTeamUpAllyRemovalCandidates(
            self.const_players,
        )

        identity = self.const_players[0].GetIdentity()
        identity.SetActive(GameRule(identity))


        # [x] 7. Collect Tokens and Status Cards
        # [x] 8. Select Scenario
        campaign = self.scene.campaign
        if self.rule.mode_skirmish:
            villain = [identity.GetControlByPlayer().AskChoosePaper(campaign.villain)]
        else:
            villain = campaign.villain
        self.SelectScenario(villain, campaign.schemes)

        if self.is_game_over:
            return

        game_start_effect = GameRule(Worlds.GetAllMainSchemes(self)[0])

        Message.TextRender("\n--- Set Up ---", self)
        message = Message.WhenGameBeginSetup(campaign, self)
        message.Send()

        # [x] 9. Set the Villain’s Hit Points
        scenario = self.GetScenario()
        if not message.skip_put_villain_into_play:
            if scenario.villain_deck.GetSize():
                villain = scenario.villain_deck.Get()[0]
                player = self.GetFirstPlayer()
                villain.PutIntoPlay(player, game_start_effect)

        if self.is_game_over:
            return

        # [x] 10. Create and Shuffe Encounter Deck
        if not message.skip_create_encounter_deck:
            encounters: List[str] = campaign.encounters[:]
            from game.card.factory import CardFactory
            for encounter_set in message.encounter_set_names:
                encounters += CardFactory.LoadEncounterSet(encounter_set)

            CardFactory.GenerateCards(encounters, scenario.encounter_deck, self)
            Message.WhenDeckCreated_Text(scenario.encounter_deck)

            if not message.no_use_obligation:
                for player in self.const_players:
                    Faces.MoveAllToDeck([x.face for x in player.set_aside_obligations], scenario.encounter_deck, "Top", game_start_effect)

            if self.rule.crisis_of_infinite_deadpools:
                used_pool_aspect = any(
                    IsUsingPoolAspect(self.scene.players[index], player)
                    for index, player in enumerate(self.const_players)
                )
                if used_pool_aspect:
                    dreadpool = CardFactory.LoadEncounterSet("dreadpool")
                    CardFactory.GenerateCards(dreadpool, self.aside_deck, self)
                    Message.WhenDeckCreated_Text(self.aside_deck)

                    face = self.aside_deck.FindCard(name="44037")
                    if face:
                        Faces.MoveAllTo([face], scenario.encounter_deck, game_start_effect)

            scenario.encounter_deck.Shuffle(game_start_effect)

            message.CreateSetAside()
            message.CreateSetAsideModular()

        if self.is_game_over:
            return

        # Move nemesis sets
        for player in self.const_players:
            faces = [card.face for card in player.set_aside_obligations if card.face in player.set_aside_nemesis_sets.Get()]
            Faces.RemoveAllFromGame(faces, game_start_effect)

        if self.is_game_over:
            return

        # For 21165a
        for scheme in Worlds.GetAllMainSchemes(self):
            scheme.Setup(True)

        # [x] 11. Put Setup Cards Into Play
        # A card with the setup keyword begins the game in play.
        decks = [x.player_deck for x in self.const_players] + \
                [x.set_aside_nemesis_sets for x in self.const_players] + \
                [self.GetScenario().encounter_deck] + \
                self.additional_decks
        faces = [x for y in decks for x in y.GetAll() if HasSetup.IsType(x) and x.printed_setup > 0]
        for face in faces:
            face.ProcessSetup(game_start_effect)

        if self.is_game_over:
            return

        # [x] 12. Resolve Scenario Setup and When Revealed abilities
        self.phase.SetState(Phase.State.ScenarioSetup)
        for scheme in Worlds.GetAllMainSchemes(self):
            scheme.Setup(False)
            scheme.Advance(None, game_start_effect) # Has already reveal here

        for villain in Worlds.GetAllVillains(self):
            villain.Setup(False)
            villain.Reveal(None, game_start_effect)

        # Evidence
        faces = [x for y in decks for x in y.GetAll() if Evidence.IsType(x)]
        for face in faces:
            face.Setup(False)

        if self.is_game_over:
            return

        # [x] 13. Campaign Setup
        campaign_message = Message.WhenCampaignSetup(self)
        campaign_message.Send()

        self.ResolveTeamUpAllyRemovalChoices(
            team_up_ally_removal_candidates,
        )

        self.ResolveStartingCardChoices(game_start_effect)

        # [x] 14. Draw Cards
        Message.TextRender("\n--- Draw Cards ---", self)
        if not self.rule.disable_setup_draw_cards:
            for player in self.const_players:
                player.DrawUp("Max", game_start_effect)

        # [x] 15. Resolve Mulligans
        self.phase.SetState(Phase.State.ResolveMulligans)
        Message.TextRender("\n--- Resolve Mulligans ---", self)
        if not self.rule.disable_resolve_mulligans:
            def process_player(player: 'Player'):
                player.phase.ResolveMulligans(Message.WhenPlayerResolveMulligans(player))
            JobManager.Simultaneous(process_player, self.const_players)

        if self.rule.additional_resolve_mulligans:
            def process_player(player: 'Player'):
                player.phase.ResolveMulligans(Message.WhenPlayerResolveMulligans(player))
            JobManager.Simultaneous(process_player, self.const_players)

        # Campaign instructions that happen after player setup must wait
        # until every configured mulligan pass is over. Send this even when
        # mulligans are disabled so campaign setup reaches the same printed
        # checkpoint.
        if self.rule.mode_campaign.val and \
            self.scene.campaign.campaign_id == "fear_no_evil":
            Message.AfterPlayersResolveMulligans(self).Send()

        # [x] 16. Resolve Character Setup Abilities
        Message.TextRender("\n--- Resolve Character Setup Abilities ---", self)
        for player in self.const_players:
            player.GetIdentity().Setup(False)

        if self.is_game_over:
            return

        if self.rule.ex_start_hand_size:
            for player in self.const_players:
                player.DrawUp(self.rule.ex_start_hand_size, game_start_effect)

        self.phase.SetState(Phase.State.InitFinished)

        begin_message = Message.WhenGameWouldBegin(self)
        begin_message.Send()

        return

    def ResolveTeamUpAllyRemovalChoices(
        self,
        candidates: Dict['Player', List['Ally']],
    ) -> None:
        """Offer the v1.8 Team-Up replacement before opening hands are drawn."""
        from game.effect.rule import GameRule
        from game.operate.faces import Faces

        for player in self.const_players:
            for ally in candidates.get(player, []):
                # Setup instructions take precedence. The ally is eligible
                # only while it remains in the player deck.
                if ally.card.area != player.player_deck:
                    continue

                should_remove = player.AskChooseOneText(
                    [True, False],
                    [
                        f"Remove {ally.name} from the game (v1.8 Team-Up rule)",
                        f"Keep {ally.name}",
                    ],
                )
                if should_remove:
                    Faces.RemoveAllFromGame(
                        [ally],
                        GameRule(player.GetIdentity()),
                    )

    def ResolveStartingCardChoices(self, game_start_effect: 'Effect') -> None:
        """Offer Starting cards after setup and before the opening draw."""
        from game.operate.faces import Faces

        for player in self.const_players:
            starting_cards = [
                face for face in player.player_deck.GetAll()
                if HasStarting.IsType(face) and face.printed_starting > 0
            ]
            for face in starting_cards:
                # A setup instruction can move the card before this point.
                if face.card.area != player.player_deck:
                    continue
                should_add = player.AskChooseOneText(
                    [True, False],
                    [
                        f"Add {face.name} to your hand (Starting)",
                        f"Leave {face.name} in your deck",
                    ],
                )
                if should_add:
                    Faces.MoveAllTo([face], player.hand_cards, game_start_effect)
                    # The Starting rules allow at most one Starting card per
                    # player deck; stop after resolving the selected card.
                    break

    ################################################################################
    # Phase
    def PlayerPhase(self) -> None:

        def turn_begin():
            self.stat.OnTurnBegin()
        def turn_end():
            self.stat.OnTurnEnd()

        self.phase.SetState(Phase.State.PlayerTurn)

        def get_player_phase_order():
            players = self.const_players[:]
            for player in players:
                if player.flag.Get("YOU_TAKE_THE_FIRST_TURN_DURING_THE_PLAYER_PHASE"):
                    players.remove(player)
                    players.insert(0, player)
            return players

        for player in get_player_phase_order():
            self.current_player = player
            turn_begin()
            player.phase.BeginTurn()
            player.phase.PlayerTurn()
            if self.is_game_over:
                return
            player.phase.EndTurn()
            turn_end()

        self.phase.SetState(Phase.State.PlayerTurnEnd)

    def PlayersEndPhase(self) -> None:
        def process_player(player: 'Player'):
            player.phase.EndPhase()
        JobManager.Simultaneous(process_player, self.const_players)

    def VillainPhase(self) -> None:
        from game.message import Message
        from game.effect.rule import GameRule
        from game.operate.worlds import Worlds

        for player in self.const_players:
            player.stat.this_phase_revealed_cards = []

        def process_villain_phase_step(step: int, callback: Callable[[], None], phase: 'Phase.State') -> None:
            self.phase.SetState(phase)

            step_message = Message.WhenVillainPhaseStepStart(step, self)
            step_message.Send()

            callback()

            if self.is_game_over:
                return

            after_step_message = Message.AfterResolveVillainPhaseStep(step, step_message)
            after_step_message.Send()
            return

        def place_threat() -> None:
            self.current_player = None
            start_message = Message.WhenMainSchemePhaseStart(self)
            start_message.Send()
            for scheme in Worlds.GetAllMainSchemes(self):
                scheme.Phase()
            end_message = Message.WhenMainSchemePhaseEnd(self)
            end_message.Send()

        def enemy_activation() -> None:
            for player in self.const_players:
                self.current_player = player
                effect = GameRule(player.GetIdentity())
                Worlds.Enemies.VillainAndEngagedMinionsActivateAgainstYou(effect, player)
            return

        def deal_encounter_cards() -> None:
            Message.TextRender("\n--- Encounter Cards Phase ---", self)
            num = 1 + self.rule.mode_heroic

            hazards: Dict[GameArea, List[HasHazard]] = {}
            for player in self.const_players:
                game_area = player.GetGameArea()

                if game_area not in hazards:
                    hazards[game_area] = Worlds.GetHazardFaces(game_area)

                self.current_player = player
                player.DealEncounterCards(num, GameRule(player.GetIdentity()))

            for game_area in hazards:
                while hazards[game_area]:
                    for player in game_area.FindAllPlayers():
                        for face in hazards[game_area][:]:
                            player.DealEncounterCards(1, GameRule(face))
                            hazards[game_area].remove(face)
                            break
                        if self.is_game_over:
                            return
            return

        def reveal_encounter_cards() -> None:
            while any(player.dealt_encounter_cards.GetSize() != 0 for player in self.const_players):
                for player in self.const_players:
                    self.current_player = player
                    player.RevealEncounterCards()
                    if self.is_game_over:
                        return
            return

        # STEP ONE  - PLACE THREAT
        # STEP TWO  - VILLAIN AND MINION ACTIVATIONS
        # STEP THREE - DEAL ENCOUNTER CARDS
        # STEP FOUR - REVEAL ENCOUNTER CARDS
        steps_data: Final = {
            1: (place_threat,           Phase.State.PlaceThreat),
            2: (enemy_activation,       Phase.State.EnemyActivation),
            3: (deal_encounter_cards,   Phase.State.DealEncounterCards),
            4: (reveal_encounter_cards, Phase.State.RevealsEncounterCards),
        }
        for step_number, (action, state) in steps_data.items():
            process_villain_phase_step(step_number, action, state)
            if self.is_game_over:
                return
        return

    def AutoSaveOnRoundStart(self) -> None:
        """Write auto_save.json when a live round begins.

        A failed save is logged and ignored so it cannot end the current game.
        Replays, fast-forwards, puzzles, and unit tests are skipped so they
        cannot overwrite a player's checkpoint.
        """
        from game.test import Test
        from engine import Engine
        from engine.log import Log

        if Test.IsInTesting() or Engine.in_unit_test:
            return
        if self.scene.is_puzzle or self.controller_manager.replay.is_replay:
            return
        if self.controller_manager.skip.is_skipping:
            return
        if not Engine.game.session.auto_save_enabled:
            return

        try:
            Engine.statistics.Save()
            saved = Engine.game.session.SaveScene(
                name="auto_save.json",
                delete_old=False,
            )
            if saved:
                Log.Info("SESSION", f"Auto-save: {saved}")
        except Exception as exc:
            Log.Warn("SESSION", f"Auto-save failed: {exc}")

    def OnGameLoop(self) -> None:
        from game.message import Message
        from game.effect.rule import GameRule

        def game_round() -> None:

            def start_round() -> None:
                self.phase.SetState(Phase.State.StartRound)
                self.current_player = None
                self.round_id += 1
                self.AutoSaveOnRoundStart()
                start_message = Message.WhenRoundStart(self.round_id, self)
                start_message.Send()

                for player in self.const_players:
                    player.phase.BeginRound()

                self.controller_manager.OnBeginRound()

            def end_round() -> None:
                self.phase.SetState(Phase.State.EndRound)
                self.current_player = None
                round_message = Message.WhenRoundEnd(self)
                round_message.Send()
                self.stat.OnRoundEnd()
                self.buff_manager.OnRoundEnd()

                for player in self.const_players:
                    player.phase.EndRound()

                # Pass the first player token clocwise to the next player.

                end_round_effect = GameRule(self.const_players[0].GetIdentity())
                self.players = Types.Rotate(self.players, 1)
                self.UpdatePlayersOrder(end_round_effect)
                if not bool(self.rule.v18_timing):
                    self.ProcessTemporary(end_round_effect)

                end_message = Message.AfterRoundEnd(round_message)
                end_message.Send()

            def phase_begin(phase_type: PhaseName) -> None:
                self.phase_id += 1

                phase_message = Message.WhenPhaseBegin(phase_type, self)
                phase_message.Send()

                for player in self.const_players:
                    player.phase.BeginPhase()

                self.controller_manager.OnBeginPhase()

                begin_message = Message.AfterPhaseBegin(phase_message)
                begin_message.Send()

            def phase_end(phase_type: PhaseName) -> None:
                from game.message import Message

                self.phase.SetState(Phase.State.EndPhase)
                self.current_player = None

                phase_message = Message.WhenPhaseEnd(self.phase_id, phase_type, self)
                phase_message.Send()

                self.stat.OnPhaseEnd()

                end_message = Message.AfterPhaseEnd(self.phase_id, phase_type, phase_message)
                end_message.Send()

            start_round()
            if self.is_game_over:
                return

            phase_begin("Player")
            if self.is_game_over:
                return
            self.PlayerPhase()
            if self.is_game_over:
                return
            self.PlayersEndPhase()
            if self.is_game_over:
                return
            phase_end("Player")
            if self.is_game_over:
                return

            phase_begin("Villain")
            if self.is_game_over:
                return
            self.VillainPhase()
            if self.is_game_over:
                return
            phase_end("Villain")
            if self.is_game_over:
                return

            end_round()


        while not self.is_game_over:
            game_round()

    def OnGameOver(self, reason: 'GameOverReason'):
        from game.message import Message
        assert reason.reason != None
        Message.GameOver_Text(reason.players_won, reason.reason, reason.by_effect, self)

    ################################################################################
    #
    def SetGameOver(self, player_won: bool, by_effect: 'Effect'):
        return self.game_over.SetPlayersWon(player_won, by_effect)

    @property
    def is_game_over(self) -> bool:
        return self.game_over.is_game_over

    @property
    def is_game_started(self) -> bool:
        return self.phase.IsGameStarted()

    @property
    def is_initializing(self) -> bool:
        return self.phase.IsGameInitializing()

    ################################################################################
    # Advance
    def AdvanceMainScheme(self, prev_scheme: 'MainScheme', to_face: Literal["2A", "3A"]|CardFace|None, by_effect: 'Effect'):
        from game.message import Message
        from game.effect.rule import GameRule
        from game.operate.faces import Faces

        assert prev_scheme.card.back_faces, f"{prev_scheme.card=}"
        message = Message.WhenMainSchemeWouldAdvance(prev_scheme, by_effect)
        message.Send()
        if message.is_be_instead:
            return
        if prev_scheme.card.printed_faces[0] == prev_scheme:
            card = prev_scheme.card
            card.Flip(GameRule(card.face))
            # Reveal is call when `Filp`
            # card.face.Reveal(None, GameRule(card.face))
        elif self.main_schemes_deck.GetSize() > 0:
            if to_face == None:
                scheme = self.main_schemes_deck.Get()[0]
            elif to_face == "2A":
                scheme = self.main_schemes_deck.FindCard(CardFinder(stage=2), card_type=MainScheme)
                assert scheme != None
            elif to_face == "3A":
                scheme = self.main_schemes_deck.FindCard(CardFinder(stage=3), card_type=MainScheme)
                assert scheme != None
            else:
                scheme = to_face
                assert MainScheme.IsType(scheme)
            acceleration_token = prev_scheme.acceleration_token
            # Fix "32127b"
            if not prev_scheme.card.area.flags.is_victory_display:
                Faces.RemoveAllFromGame([prev_scheme], GameRule(prev_scheme))
            scheme.PlaceAccelerationToken(acceleration_token, GameRule(scheme))
            scheme.Reveal(None, by_effect)
        elif self.area_schemes_main.GetSize() == 1:
            self.game_over.SetGameOverByRule("The Final Stage of the Main Scheme was Completed")
        after_message = Message.AfterMainSchemeAdvanced(message)
        after_message.Send()

    def CheckIsAllPlayersEliminated(self):
        for player in self.const_players:
            if not player.GetIdentity().IsDefeated() and not player.is_eliminated:
                return False
        self.game_over.SetGameOverByRule("All players were eliminated")
        return True

    ################################################################################
    #
    def GetPhaseText(self) -> str:
        if self.phase.state == Phase.State.PlayerTurn:
            assert self.current_player != None
            return f"Player {self.const_seat_order_players.index(self.current_player)+1} Turn"
        else:
            return self.phase.state
