from . import *
from cards.paper import Paper

@final
class Search:

    @staticmethod
    def EncounterCards(by_effect: 'Effect',
                        who_perform: 'Player|None|Literal["FirstPlayer"]'=None,
                        *,
                        include_discard_pile: bool,
                        include_set_aside: bool=False,
                        #
                        most_top: int|None=None,
                        finder: 'CardFinder|None'=None,
                        name: str|None=None,
                        trait: "CardFace.TRAITS|None"=None,
                        card_type: Type['TC']|CardFace=CardFace,
                        total: int|Literal["1*"]=1,
                        **kwargs: Unpack['CardFinder.KWArgs'],
                        ) -> List[TC]:
        from game.operate.worlds import Worlds

        if who_perform == None:
            who_perform = by_effect.world.GetCurrentPlayer()
        elif who_perform == "FirstPlayer":
            who_perform = by_effect.world.GetFirstPlayer()

        total = Worlds.ConvertPerPlayerIconToInt(total, by_effect)

        return Search.SearchForCards(
            by_effect,
            who_perform,
            include_encounter_deck=True,
            include_encounter_discard_pile=include_discard_pile,
            include_set_aside=include_set_aside,
            finder=finder,
            name=name,
            trait=trait,
            card_type=card_type,
            most_top=most_top,
            range=(total, total),
            **kwargs
        )

    @staticmethod
    def EncounterCard(by_effect: 'Effect',
                      who_perform: 'Player|None|Literal["FirstPlayer"]'=None,
                      *,
                      include_discard_pile: bool,
                      include_set_aside: bool=False,
                      #
                      most_top: int|None=None,
                      finder: 'CardFinder|None'=None,
                      name: str|None=None,
                      trait: "CardFace.TRAITS|None"=None,
                      card_type: Type['TC']|CardFace=CardFace,
                      **kwargs: Unpack['CardFinder.KWArgs'],
                      ) -> TC|None:
        if who_perform == None:
            who_perform = by_effect.world.GetCurrentPlayer()
        elif who_perform == "FirstPlayer":
            who_perform = by_effect.world.GetFirstPlayer()

        return Search.SearchForCard(
            by_effect,
            who_perform,
            include_encounter_deck=True,
            include_encounter_discard_pile=include_discard_pile,
            include_set_aside=include_set_aside,
            finder=finder,
            name=name,
            trait=trait,
            card_type=card_type,
            most_top=most_top,
            **kwargs
        )

    @staticmethod
    def EncounterCardTop(by_effect: 'Effect',
                        who_perform: 'Player|None|Literal["FirstPlayer"]',
                        most_top: int,
                        *,
                        finder: 'CardFinder|None'=None,
                        name: str|None=None,
                        trait: "CardFace.TRAITS|None"=None,
                        card_type: Type['TC']|CardFace=CardFace,
                        **kwargs: Unpack['CardFinder.KWArgs'],
                        ) -> TC|None:
        return Search.EncounterCard(
            by_effect,
            who_perform,
            include_discard_pile=False,
            include_set_aside=False,
            most_top=most_top,
            finder=finder,
            name=name,
            trait=trait,
            card_type=card_type,
            **kwargs
        )

    @staticmethod
    def EncounterCardsTop(by_effect: 'Effect',
                        who_perform: 'Player|None|Literal["FirstPlayer"]',
                        most_top: int,
                        *,
                        finder: 'CardFinder|None'=None,
                        name: str|None=None,
                        trait: "CardFace.TRAITS|None"=None,
                        card_type: Type['TC']|CardFace=CardFace,
                        total: int|Literal["1*"]=1,
                        **kwargs: Unpack['CardFinder.KWArgs'],
                        ) -> List[TC]:
        return Search.EncounterCards(
            by_effect,
            who_perform,
            include_discard_pile=False,
            include_set_aside=False,
            most_top=most_top,
            finder=finder,
            name=name,
            trait=trait,
            card_type=card_type,
            total=total,
            **kwargs
        )

    @staticmethod
    def PlayerCard(by_effect: 'Effect',
                    player: 'Player',
                    *,
                    include_player_deck: bool,
                    include_discard_pile: bool=False,
                    include_player_hand_cards: bool=False,
                    include_player_area: bool=False,
                    #
                    may: bool=False,
                    not_move: bool=False, # will not shuffle
                    #
                    finder: 'CardFinder|None'=None,
                    name: str|None=None,
                    trait: "CardFace.TRAITS|None"=None,
                    card_type: Type['TC']|CardFace=CardFace,
                    **kwargs: Unpack['CardFinder.KWArgs'],
                    ) -> TC|None:
        return Search.SearchForCard(
            by_effect,
            player,
            include_player_deck=include_player_deck,
            include_player_discard_pile=include_discard_pile,
            include_player_hand_cards=include_player_hand_cards,
            include_player_area=include_player_area,
            may=may,
            not_move=not_move,
            finder=finder,
            name=name,
            trait=trait,
            card_type=card_type,
            **kwargs,
        )

    @staticmethod
    def PlayerDeckTop(by_effect: 'Effect',
                    player: 'Player',
                    most_top: int,
                    *,
                    finder: 'CardFinder|None'=None,
                    name: str|None=None,
                    trait: "CardFace.TRAITS|None"=None,
                    card_type: Type['TC']|CardFace=CardFace,
                    **kwargs: Unpack['CardFinder.KWArgs'],
                    ) -> TC|None:
        return Search.SearchForCard(
            by_effect,
            player,
            include_player_deck=True,
            most_top=most_top,
            finder=finder,
            name=name,
            trait=trait,
            card_type=card_type,
            **kwargs,
        )

    # If only one card, it will `process_choose`
    # or it will open a window for `who_perform` to select
    # Only process one card
    @staticmethod
    def SearchForCard(by_effect: 'Effect',
                        who_perform: 'Player',
                        *,
                        # process
                        process_choose: Callable[[TC], Any]|None=None,
                        process_other: Callable[['CardFace'], Any]|None=None,
                        # from
                        include_encounter_deck: bool=False,
                        include_encounter_discard_pile: bool=False,
                        include_set_aside: bool=False,
                        include_removed_area: bool=False,
                        include_in_play: bool=False,

                        include_player_deck: bool|Literal["All"]=False,
                        include_player_discard_pile: bool|Literal["All"]=False,
                        include_player_hand_cards: bool|Literal["All"]=False,
                        include_player_area: bool|Literal["All"]=False,

                        include_victory_display: bool=False,
                        faces: List['CardFace']|None=None,
                        # 
                        most_top: int|None=None,
                        #
                        may: bool=False,
                        not_move: bool=False,
                        # finder
                        finder: 'CardFinder|None'=None,
                        name: str|None=None,
                        trait: "CardFace.TRAITS|None"=None,
                        card_type: Type['TC']|CardFace=CardFace,
                        **kwargs: Unpack['CardFinder.KWArgs'],
                        ) -> 'TC|None':

        found_faces = Search.SearchForCards(
            by_effect,
            who_perform,
            process_choose=process_choose,
            process_other=process_other,

            include_encounter_deck=include_encounter_deck,
            include_encounter_discard_pile=include_encounter_discard_pile,
            include_set_aside=include_set_aside,
            include_removed_area=include_removed_area,
            include_in_play=include_in_play,
            include_player_deck=include_player_deck,
            include_player_discard_pile=include_player_discard_pile,
            include_player_hand_cards=include_player_hand_cards,
            include_player_area=include_player_area,
            include_victory_display=include_victory_display,

            faces=faces,
            most_top=most_top,

            may=may,
            not_move=not_move,

            finder=finder,
            name=name,
            trait=trait,
            card_type=card_type,
            **kwargs,
        )

        if found_faces:
            return found_faces[0]
        else:
            return None

    @staticmethod
    def SearchForCards(by_effect: 'Effect',
                        who_perform: 'Player',
                        # process
                        *,
                        process_choose: Callable[[TC], Any]|None=None,
                        process_other: Callable[['CardFace'], Any]|None=None,
                        # from
                        include_encounter_deck: bool=False,
                        include_encounter_discard_pile: bool=False,
                        include_set_aside: bool=False,
                        include_removed_area: bool=False,
                        include_in_play: bool=False,
                        include_player_deck: bool|Literal["All"]=False,
                        include_player_discard_pile: bool|Literal["All"]=False,
                        include_player_hand_cards: bool|Literal["All"]=False,
                        include_player_area: bool|Literal["All"]=False,
                        include_victory_display: bool=False,
                        faces: List['CardFace']|None=None,
                        most_top: int|None=None,
                        #
                        may: bool=False,
                        not_move: bool=False,
                        range: 'SELECT.RANGE_TYPE'=(1,1),
                        # filter
                        finder: 'CardFinder|None'=None,
                        name: str|None=None,
                        trait: "CardFace.TRAITS|None"=None,
                        card_type: Type['TC']|None|CardFace=CardFace,
                        **kwargs: Unpack['CardFinder.KWArgs'],
                        ) -> List[TC]:
        from game.operate.worlds import Worlds
        # from game.operate.faces import Faces
        from game.message import Message
        if faces == None:
            faces = []

        if include_encounter_deck:
            # searched = Worlds.GetEncounterDeckCards(by_effect)
            decks: List[Deck] = []
            villains = Worlds.GetAllVillains(by_effect)
            for villain in villains:
                decks.append(villain.encounter_deck)
            if villains == []:
                decks.append(by_effect.world.scenario.encounter_deck)
            for deck in Types.RemoveDuplicates(decks):
                searched_faces = deck.Get(True)[:most_top]
                faces += searched_faces
                Message.WhenPlayerSearchingDeckCards_Text(who_perform, deck, most_top, searched_faces)
        if include_encounter_discard_pile:
            faces += Worlds.GetEncounterDiscardPileCards(by_effect)[:most_top]
        if include_set_aside:
            faces += Worlds.GetSetAsideAreaCards(by_effect)
        if include_in_play:
            faces += Worlds.GetOnFieldCards(by_effect)
        if include_removed_area:
            faces += by_effect.world.area_removed.Get(True)
        if include_player_deck == True:
            deck = who_perform.player_deck
            searched_faces = deck.Get(True)[:most_top]
            faces += searched_faces
            Message.WhenPlayerSearchingDeckCards_Text(who_perform, deck, most_top, searched_faces)
        elif include_player_deck == "All":
            for check_player in Worlds.GetPlayers(by_effect):
                deck = check_player.player_deck
                searched_faces = deck.Get(True)[:most_top]
                faces += searched_faces
                Message.WhenPlayerSearchingDeckCards_Text(who_perform, deck, most_top, searched_faces)

        if include_player_discard_pile == True:
            faces += who_perform.discard_pile.Get(True)[:most_top]
        elif include_player_discard_pile == "All":
            for check_player in Worlds.GetPlayers(by_effect):
                deck = check_player.discard_pile
                faces += deck.Get(True)[:most_top]

        if include_player_hand_cards == True:
            faces += who_perform.hand_cards.Get(True)
        elif include_player_hand_cards == "All":
            for check_player in Worlds.GetPlayers(by_effect):
                faces += check_player.hand_cards.Get(True)

        if include_player_area == True:
            faces += who_perform.GetPlayerAreaCards()
        elif include_player_area == "All":
            for check_player in Worlds.GetPlayers(by_effect):
                faces += check_player.GetPlayerAreaCards()

        if include_victory_display:
            faces += by_effect.world.victory_display.Get(True)

        finder = CardFinder(
            name=name,
            trait=trait,
            card_type=card_type,
            **kwargs
        ) & finder

        # A caller can pass any specialized deck through `faces`, so detect a
        # true full-deck search from the gathered cards rather than limiting
        # this option to the standard player and encounter deck parameters.
        full_search_decks: List[Deck] = []
        full_search_display_faces: List[CardFace] = []
        if most_top == None and \
            not not_move:
            candidate_decks = Types.RemoveDuplicates([
                face.card.area
                for face in faces
                if face.card.area.flags.is_deck
            ])
            for deck in candidate_decks:
                deck_faces = deck.Get(True)
                if deck_faces and all(face in faces for face in deck_faces):
                    full_search_display_faces.extend(deck_faces)
                    if not deck.flags.is_discards:
                        full_search_decks.append(deck)

        world = by_effect.world
        scene = getattr(world, "scene", None)
        controller_manager = getattr(world, "controller_manager", None)
        legacy_full_search_prompt = bool(
            scene and
            controller_manager and
            scene.UseLegacyFullSearchPrompt(
                controller_manager.replay.current_step_id
            )
        )

        from game.operate.search_internal import SearchInternal

        return SearchInternal.SearchForCardsInternal(
            by_effect,
            who_perform,
            faces,
            process_choose=process_choose,
            process_other=process_other,
            finder=finder,
            may=may,
            not_move=not_move,
            range=range,
            full_search_display_faces=full_search_display_faces,
            full_search_decks=(
                full_search_decks if legacy_full_search_prompt else []
            ),
            force_full_search_prompt=legacy_full_search_prompt,
        )

    @staticmethod
    def Collection(by_effect: 'Effect',
                    player: 'Player',
                    *,
                    name: str|None=None,
                    trait: "CardFace.TRAITS|None"=None,
                    card_type: Type['TC']|None=None,
                    card_class: "ClassCard.CARD_CLASS|None"=None,
                    card_classes: List["ClassCard.CARD_CLASS"]|Literal["Any"]|None=None, # Any = Any Aspect
                    set_name: str|None=None,
                    check_fn: Callable[['Paper'], bool]|None=None,
                    ) -> 'CardFace|None':
        from cards.database import CardsDB
        from game.card.factory import CardFactory

        if card_type != None:
            check_card_type = str(card_type)
        else:
            check_card_type = None

        if card_classes == "Any":
            card_classes = [
                "Aggression",
                "Justice",
                "Leadership",
                "Protection",
                "'Pool",
            ]

        # Card faces expose the printed "Hero" class as
        # "IdentitySpecific", while collection searches query raw papers.
        if card_class == "IdentitySpecific":
            card_class = "Hero"
        if card_classes != None:
            card_classes = [
                "Hero" if value == "IdentitySpecific" else value
                for value in card_classes
            ]

        paper_ids = CardsDB.GetPapers(card_type=check_card_type,
                                      trait=trait,
                                      card_class=card_class,
                                      card_classes=card_classes,
                                      set_name=set_name,
                                      check_fn=check_fn)

        if not paper_ids:
            return None

        # name = player.AskChoosePaper(["06019", "16046", "18018", "20015", "44052", "44055"])
        name = player.AskChoosePaper(paper_ids)
        card = CardFactory.GenerateCard(name, player.discard_pile, by_effect.world)

        return card.face

