import { Lib } from './lib.js'
import { ButtonSetting, Setting } from './settings.js'
import { CardDescriptor } from './descriptor.js'
import { Game } from './game.js'
import { UI } from './ui.js'
import { HoverCard } from './hover.js'
import { Effect } from './effect.js'
import { CardStatistics } from '../module/card_statistics.js';
import { MoveCard } from './move-card.js';
import { ClassName } from './class_name.js'
import { copyToClipboard } from '../lib/clipboard.js'
import { AutoActivate } from './auto_activate.js'
import { CardAnimation } from './card_animation.js'

function delete_all_data(card_div: HTMLElement) {
    let last_child = card_div.querySelector('.info') as HTMLElement
    Object.keys(last_child.dataset).forEach(dataKey => {
        delete last_child.dataset[dataKey];
    });
}

class CardRender {
    private static print_cards_objs: Record<string, CardDescriptor[]> = {};

    private static stat_skip_render = 0
    private static stat_do_render: number[] = []
    // private static stat_do_render2: HTMLElement[] = []

    public static lastRightClickTimes = new Map()
    private static control_by_player_classes = Array.from({ length: 5 }, (_, i) => `control_player_${i}`);

    private static area_names: string[] = [
        'victory-display',
        'removed-pool',

        'area-villain',
        'area-schemes-main',
        'area-schemes-side',
        'encounter-deck-0',
        'encounter-deck-1',
        'encounter-deck-2',
        'encounter-deck-3',
        'encounter-discard-pile-0',
        'encounter-discard-pile-1',
        'encounter-discard-pile-2',
        'encounter-discard-pile-3',

        'area-play',
        'area-removed',
        'area-advanced',
        'nemesis-pool',

        'player-0-player-deck',
        'player-0-player-discard-pile',
        'player-0-additional-deck',
        'player-0-additional-discard-pile',
        
        'player-1-player-deck',
        'player-1-player-discard-pile',
        'player-1-additional-deck',
        'player-1-additional-discard-pile',
        
        'player-2-player-deck',
        'player-2-player-discard-pile',
        'player-2-additional-deck',
        'player-2-additional-discard-pile',
        
        'player-3-player-deck',
        'player-3-player-discard-pile',
        'player-3-additional-deck',
        'player-3-additional-discard-pile',
        
        'area-rule',
        
        'player-all-area-hero',
        'player-all-allies',
        'player-all-supports',
        'player-all-engaged-minions',

        'player-all-hand-cards',
    ]

    ////////////////////////////////////////////////////////////////////////////////
    //
    static printDeckWhenHighlightTarget(object_ids: number[], is_temp_sort=false) {
        let area_names: Set<string> = new Set()

        for( const object_id of object_ids ) {
            area_names.add(Cards.getDiv(object_id)!.parentElement!.id)
        }
        for( const area_name of area_names )
        {
            if( area_name.startsWith('encounter-deck') ||
                area_name.startsWith('encounter-discard-pile') ||
                area_name.endsWith('deck') ||
                area_name.endsWith('discard-pile') ) {
                    CardRender.printAreaCards(CardRender.print_cards_objs[area_name], area_name, !is_temp_sort, is_temp_sort)
            }
        }
    }

    private static printAreaCards(
        areaCards: CardDescriptor[],
        areaName: string,
        isSelecting = false,
        isTempSort = false
    ) {
        const parent = document.querySelector<HTMLElement>(`#${areaName}`);
        if (!parent) return;
    
        // -- 1. Determine area type and settings --
        const isHandArea = areaName.endsWith('hand-cards');
        const shouldCheckHide = ButtonSetting.hide_no_action_cards > 0 && (
            areaName.endsWith('allies') ||
            areaName.endsWith('supports') ||
            areaName.endsWith('area-hero')
        );
    
        // -- 2. Sort cards according to area and settings --
        const cardArea = CardRender.getCardArea(areaName);
        const sortedCards = CardRender.getSortedCards(areaCards, cardArea, areaName, isSelecting, isTempSort);
        const displaysTargetOrder = isSelecting && cardArea === 'deck' && Effect.select_effect_obj.display_in_target_order;
        const displaysFullSearch = isSelecting && cardArea === 'deck' && Effect.getFullSearchDisplayTargets().length > 0;
        parent.classList.toggle(
            'selection-order-top-first',
            displaysTargetOrder || displaysFullSearch
        );
    
        // -- 3. Filter visible/rendered cards based on hide rules --
        const visibleCards = CardRender.getVisibleCards(
            sortedCards,
            cardArea,
            areaName,
            isHandArea,
            shouldCheckHide
        );
    
        // -- 4. Render cards in DOM, updating or skipping as needed --
        const renderedCardIds = CardRender.renderCardList(
            sortedCards,
            visibleCards,
            parent,
            areaName,
            isHandArea,
            isSelecting
        );
    
        // -- 5. Update parent styles and clean up removed cards --
        CardRender.updateParentCardCounts(parent, areaCards, visibleCards);
        CardRender.cleanupOrphanCardDivs(parent, renderedCardIds);
    
        // Hide parent if area is now empty and version requires it
        if (!areaCards || areaCards.length === 0) {
            if (Setting.ver === 1) parent.classList.add('hide');
        }
    }
    
    // -- Helper methods below --
    
    private static getCardArea(areaName: string): 'dealt' | 'hand' | 'area' | 'discard_pile' | 'deck' | null {
        const areaMap: { [suffix: string]: 'dealt' | 'hand' | 'area' | 'discard_pile' | 'deck' } = {
            'dealt-encounter-cards': 'dealt',
            'hand-cards': 'hand',
            'allies': 'area',
            'supports': 'area',
            'area-hero': 'area',
            'engaged-minions': 'area',
            'area-villain': 'area',
            'area-schemes-main': 'area',
            'area-schemes-side': 'area',
            'discard-pile': 'discard_pile',
            'discard-pile-0': 'discard_pile',
            'discard-pile-1': 'discard_pile',
            'discard-pile-2': 'discard_pile',
            'discard-pile-3': 'discard_pile',
            'deck': 'deck',
            'encounter-deck-0': 'deck',
            'encounter-deck-1': 'deck',
            'encounter-deck-2': 'deck',
            'encounter-deck-3': 'deck'
        };
        for (const [suffix, area] of Object.entries(areaMap)) {
            if (areaName.endsWith(suffix)) return area;
        }
        return null;
    }
    
    private static getSortedCards(
        areaCards: CardDescriptor[],
        cardArea: string | null,
        areaName: string,
        isSelecting: boolean,
        isTempSort: boolean
    ): CardDescriptor[] {
        if (!areaCards || areaCards.length === 0) return [];
    
        // -- Dealt areas: no sort --
        if (!cardArea || cardArea === "dealt") {
            return [...areaCards];
        }
    
        // -- Deck & discard pile sorting --
        if (cardArea === "deck" || cardArea === "discard_pile") {
            if (!isSelecting) {
                if (cardArea === "discard_pile" || isTempSort) {
                    if (ButtonSetting.sort_discard_pile_cards === 1 || isTempSort) {
                        return [...areaCards].sort((a, b) => a.object_id - b.object_id);
                    } else if (ButtonSetting.sort_discard_pile_cards === 2) {
                        return [...areaCards].sort(CardRender.compareByTypeNameId);
                    }
                    return [...areaCards];
                }
                return [...areaCards];
            } else {
                if (Effect.getFullSearchDisplayTargets().length > 0) {
                    // Preserve the deck's live bottom-to-top array order. The
                    // top card remains the rightmost card in the open deck.
                    return [...areaCards];
                }

                if (Effect.select_effect_obj.display_in_target_order) {
                    // Ordered selectors provide targets in the order they will be
                    // drawn or placed. Display that sequence from right to left so
                    // it runs back toward the decks on the left side of the table.
                    const targetOrder = new Map<number, number>();
                    Effect.select_effect_obj.all_legal_targets.forEach((objectId, index) => {
                        if (!targetOrder.has(objectId)) targetOrder.set(objectId, index);
                    });

                    return [...areaCards].sort((a, b) => {
                        const aOrder = targetOrder.get(a.object_id);
                        const bOrder = targetOrder.get(b.object_id);
                        if (aOrder !== undefined && bOrder !== undefined) return bOrder - aOrder;
                        if (aOrder !== undefined) return 1;
                        if (bOrder !== undefined) return -1;
                        return 0;
                    });
                }

                // Swap and ordinary search effects follow the cards' live area
                // order, which can change between selections.
                return [...areaCards].sort((a, b) => {
                    const aLegal = Effect.select_effect_obj.all_legal_targets.includes(a.object_id);
                    const bLegal = Effect.select_effect_obj.all_legal_targets.includes(b.object_id);
                    if (aLegal && bLegal) return 0;
                    if (aLegal) return 1;
                    if (bLegal) return -1;
                    return 0;
                });
            }
        }
    
        // -- Area sorting (allies/supports/hero/etc) --
        if (cardArea === "area"
            && !areaName.endsWith('engaged-minions')
            && !areaName.endsWith('area-villain')
            && !areaName.endsWith('area-schemes-main')
            && !areaName.endsWith('area-schemes-side')
        ) {
            if (ButtonSetting.sort_area_cards === 1) {
                return CardRender.sortCardStates(areaCards, 1);
            }
            if (ButtonSetting.sort_area_cards === 2) {
                return CardRender.sortCardStates(areaCards, 2);
            }
            return [...areaCards];
        }
    
        // -- Hand sorting --
        if (cardArea === "hand") {
            if (ButtonSetting.sort_hand_cards === 1) {
                return [...areaCards].sort((a, b) => {
                    if (a.control_player < b.control_player) return -1;
                    if (a.control_player > b.control_player) return 1;
                    return a.object_id - b.object_id;
                });
            }
            if (ButtonSetting.sort_hand_cards === 2) {
                return [...areaCards].sort(CardRender.compareHandSort);
            }
            return [...areaCards];
        }
    
        // -- Default: no sort --
        return [...areaCards];
    }
    
    private static sortCardStates(cards: CardDescriptor[], by: number): CardDescriptor[] {
        // Group by control_player, then handle bind_object_id, then sort
        const groups: CardDescriptor[][] = [];
        const controlMap = new Map<number, CardDescriptor[]>();
        for (const card of cards) {
            if (!controlMap.has(card.control_player)) controlMap.set(card.control_player, []);
            controlMap.get(card.control_player)!.push(card);
        }
        const bindCards = new Map<number, CardDescriptor[]>();
        for (const group of controlMap.values()) {
            const mainGroup: CardDescriptor[] = [];
            for (const card of group) {
                if (card.bind_object_id !== 0) {
                    if (!bindCards.has(card.bind_object_id)) bindCards.set(card.bind_object_id, []);
                    bindCards.get(card.bind_object_id)!.push(card);
                } else {
                    mainGroup.push(card);
                }
            }
            if (mainGroup.length > 0) groups.push(mainGroup);
        }
    
        function sortFn(a: CardDescriptor, b: CardDescriptor): number {
            if (b.card_type === "StatusCard") return 1;
            if (b.is_dealt_card) return 1;
            if (b.card_type === "Hero" || b.card_type === "AlterEgo") return 1;
            if (a.is_face_up === b.is_face_up && a.is_face_up === false) return 0;
            if (a.is_face_up === b.is_face_up) {
                if (by === 2) {
                    if (a.name < b.name) return -1;
                    if (a.name > b.name) return 1;
                }
                return a.object_id - b.object_id;
            }
            return a.is_face_up ? -1 : 1;
        }
        bindCards.forEach(list => list.sort(sortFn));
        groups.forEach(group => group.sort(sortFn));
    
        const result: CardDescriptor[] = [];
        function pushWithBinds(card: CardDescriptor) {
            result.push(card);
            if (bindCards.has(card.object_id)) {
                for (const c of bindCards.get(card.object_id)!) pushWithBinds(c);
            }
        }
        groups.flat().forEach(card => pushWithBinds(card));
        return result;
    }
    
    private static compareByTypeNameId(a: CardDescriptor, b: CardDescriptor): number {
        if (a.card_type < b.card_type) return -1;
        if (a.card_type > b.card_type) return 1;
        if (a.name < b.name) return -1;
        if (a.name > b.name) return 1;
        return a.object_id - b.object_id;
    }
    private static compareHandSort(a: CardDescriptor, b: CardDescriptor): number {
        if (a.control_player < b.control_player) return -1;
        if (a.control_player > b.control_player) return 1;
        if (a.card_type < b.card_type) return -1;
        if (a.card_type > b.card_type) return 1;
        if (a.name < b.name) return -1;
        if (a.name > b.name) return 1;
        return a.object_id - b.object_id;
    }
    
    private static getVisibleCards(
        sortedCards: CardDescriptor[],
        cardArea: string | null,
        areaName: string,
        isHandArea: boolean,
        shouldCheckHide: boolean
    ): CardDescriptor[] {
        // Filtering logic for hidden cards, based on area and settings
        if (isHandArea && !ButtonSetting.show_all_hand_cards) {
            return sortedCards.filter(card => !CardRender.shouldHideHandCard(card));
        }
        if (shouldCheckHide) {
            return sortedCards.filter(card => !CardRender.shouldHideAreaCard(card));
        }
        return sortedCards;
    }
    
    private static shouldHideHandCard(card: CardDescriptor): boolean {
        if (CardAnimation.active_card_object_ids.includes(card.object_id)) return false;
        if (card.control_player === Game.forced_on_player) return false;
        return true;
    }
    
    private static shouldHideAreaCard(card: CardDescriptor): boolean {
        if (CardAnimation.active_card_object_ids.includes(card.object_id)) return false;
        if (card.control_player === Game.forced_on_player) return false;
        if (card.is_in_play && card.is_face_up) {
            if (Setting.render_card_blacklist.has(card.card_id)) return true;
            if (ButtonSetting.hide_no_action_cards === 2) {
                if (
                    card.card_type === 'Hero' ||
                    card.card_type === 'AlterEgo'
                ) return false;
            } else {
                if (
                    card.is_action ||
                    card.card_type === 'Ally' ||
                    card.card_type === 'Hero' ||
                    card.card_type === 'AlterEgo' ||
                    card.card_type === 'StatusCard'
                ) return false;
            }
            if (Setting.render_card_whitelist.has(card.card_id)) return false;
            if (!card.visible_for_players.includes(Setting.player_id)) return true;
        }
        let bind_card_id = Cards.getCard(card.bind_object_id)?.card_id
        if( bind_card_id && Setting.render_under_card_whitelist.has(bind_card_id))
            return false;
        return true;
    }
    
    // -- Rendering logic --
    private static renderCardList(
        sortedCards: CardDescriptor[],
        visibleCards: CardDescriptor[],
        parent: HTMLElement,
        areaName: string,
        isHandArea: boolean,
        isSelecting: boolean
    ): number[] {
        // Decide if area should show details
        const showDetail = CardRender.isShowDetailArea(areaName);
        // Cache area type for reverse order in "area" types
        const cardArea = CardRender.getCardArea(areaName);
        const renderedIds: number[] = [];
        const n = sortedCards.length;
        for (let i = 0; i < n; i++) {
            const j = cardArea === "area" ? n - i - 1 : i;
            const card = sortedCards[j];
            const isHidden = !visibleCards.includes(card);
            const cardDiv = Cards.getDiv(card.object_id)!;
            const needsRender =
                card.need_render ||
                CardAnimation.active_card_object_ids.includes(card.object_id) ||
                parent.children[i] !== cardDiv;

            if (needsRender || !card.lastRenderState) {
                // if( card.object_id == 1 ) {
                //     console.log("do_render: (1)", card.need_render, CardAnimation.active_card_object_ids.includes(card.object_id), parent.children[i] !== cardDiv)
                // }

                CardRender.stat_do_render.push(card.object_id);
                CardRender.printCard(card, parent, isHandArea, showDetail, i, isSelecting);
            } else {
                CardRender.stat_skip_render += 1;
            }

            if (isHidden !== cardDiv.classList.contains('hide')) {
                MoveCard.updating_area.add(parent);
            }

            renderedIds.push(card.object_id);
            if (isHidden) {
                cardDiv.classList.add('hide');
            } else if (cardDiv.classList.contains('hide')) {
                cardDiv.classList.remove('hide');
            }
        }
        parent.classList.remove('hide');
        return renderedIds;
    }
    
    private static isShowDetailArea(areaName: string): boolean {
        return [
            'area-schemes-main', 'area-schemes-side', 'area-villain',
            'area-environment', 'area-play', 'player-all-area-hero',
            'player-all-allies', 'player-all-supports', 'player-all-engaged-minions'
        ].includes(areaName);
    }
    
    private static updateParentCardCounts(parent: HTMLElement, areaCards: CardDescriptor[], visibleCards: CardDescriptor[]) {
        if (areaCards && areaCards.length > 0) {
            parent.dataset.total_cards = areaCards.length.toString();
            parent.style.setProperty('--total-cards', areaCards.length.toString());
        } else {
            parent.dataset.total_cards = "";
            parent.style.setProperty('--total-cards', "0");
        }
    }
    
    private static cleanupOrphanCardDivs(parent: HTMLElement, renderedCardIds: number[]) {
        // Remove or hide any card nodes that are not rendered anymore
        const markRemove: HTMLElement[] = [];
        for (let i = 0, max = parent.children.length; i < max; i++) {
            const node = parent.childNodes[i];
            if (node instanceof HTMLElement) {
                const id = Number(node.dataset.id!);
                if (id >= Cards.max_card_object_id) {
                    markRemove.push(node);
                } else if (!renderedCardIds.includes(id)) {
                    node.classList.add('hide');
                    delete_all_data(node);
                }
            }
        }
        for (const node of markRemove) {
            node.parentNode?.removeChild(node);
            const object_id = Number(node.dataset.id)
            const card = Cards.getCard(object_id)!
            card.lastRenderState = ""
            // if( object_id == 20 ) {
            //     console.log("do_render: (20) clean render")
            // }
        }
    }

    static updateCardsData() {
        CardRender.print_cards_objs['area-schemes-main'] = Game.world_descriptor.area_schemes_main
        CardRender.print_cards_objs['area-schemes-side'] = Game.world_descriptor.area_schemes_side

        CardRender.print_cards_objs['area-villain'] = []
        CardRender.print_cards_objs['area-villain'].push    (...Game.world_descriptor.area_villain)

        function customSort(arr: CardDescriptor[]): CardDescriptor[] {
            // Create a mapping of id to object for quick access
            const idMap = new Map<number, CardDescriptor>();
            const noBindId: CardDescriptor[] = [];
        
            // Populate the map and separate objects without bind_id
            for (const obj of arr) {
                if (obj.bind_object_id === 0) {
                    noBindId.push(obj);
                } else {
                    idMap.set(obj.object_id, obj);
                }
            }
        
            // Sort objects without bind_id by id
            noBindId.sort((a, b) => a.object_id - b.object_id);
        
            // Create the final sorted array
            const sortedArray: CardDescriptor[] = [];
        
            // Insert objects without bind_id into the sorted array
            for (const obj of noBindId) {
                sortedArray.push(obj);
                
                // Collect objects that should be inserted after this one
                const toInsert: CardDescriptor[] = [];
                
                for (const [key, value] of idMap) {
                    if (value.bind_object_id === obj.object_id) {
                        toInsert.push(value);
                    }
                }

                // Sort the objects to be inserted by their id
                toInsert.sort((a, b) => a.object_id - b.object_id);

                // Insert the sorted objects after the current object
                sortedArray.push(...toInsert);

                // Remove inserted objects from the map
                for (const item of toInsert) {
                    idMap.delete(item.object_id);
                }
            }
        
            // Add any remaining objects from the map (those with bind_id that were not matched)
            for (const value of idMap.values()) {
                sortedArray.push(value);
            }
        
            return sortedArray;
        }
        const sorted_area_environment = customSort(Game.world_descriptor.area_environment)
        CardRender.print_cards_objs['area-villain'].push    (...sorted_area_environment)
        CardRender.print_cards_objs['area-villain'].push    (...Game.world_descriptor.area_rule)
        CardRender.print_cards_objs['area-villain'].push    (...Game.world_descriptor.area_mission)

        CardRender.print_cards_objs[`encounter-deck-0`] = Game.world_descriptor.encounter_deck
        CardRender.print_cards_objs[`encounter-discard-pile-0`] = Game.world_descriptor.encounter_discard_pile
        for( let j=1; j<4; j++ ) {
            let i = j-1
            if( Game.world_descriptor.additional_decks.length > i ) {
                CardRender.print_cards_objs[`encounter-deck-${j}`]       = Game.world_descriptor.additional_decks[i]
                CardRender.print_cards_objs[`encounter-discard-pile-${j}`] = Game.world_descriptor.additional_discard_piles[i]
            }
        }

        CardRender.print_cards_objs['area-play'] = []
        CardRender.print_cards_objs['area-play'].push       (...Game.world_descriptor.area_processing)
        CardRender.print_cards_objs['area-play'].push       (...Game.world_descriptor.area_revealing)
        CardRender.print_cards_objs['area-play'].push       (...Game.world_descriptor.area_boost)
        CardRender.print_cards_objs['area-play'].push       (...Game.world_descriptor.area_resources)

        CardRender.print_cards_objs['nemesis-pool'] = []
        CardRender.print_cards_objs['area-removed'] = []
        // CardRender.print_cards_objs['area-removed'].push    (...Game.world_descriptor.area_insert)
        for( let i=0; i<Game.world_descriptor.players.length; i++ ) {
            CardRender.print_cards_objs['nemesis-pool'].push(...Game.world_descriptor.players[i].set_aside_nemesis_sets)
            CardRender.print_cards_objs['area-removed'].push(...Game.world_descriptor.players[i].set_aside_deck)
        }
        CardRender.print_cards_objs['area-removed'].push    (...Game.world_descriptor.area_set_aside)
        CardRender.print_cards_objs['area-removed'].push    (...Game.world_descriptor.area_removed)
        const sorted_area_evidence = Game.world_descriptor.area_evidence.sort((a, b) => a.object_id - b.object_id)
        CardRender.print_cards_objs['area-removed'].push    (...sorted_area_evidence)

        CardRender.print_cards_objs['area-advanced'] = []
        CardRender.print_cards_objs['area-advanced'].push    (...Game.world_descriptor.villain_deck)
        CardRender.print_cards_objs['area-advanced'].push    (...Game.world_descriptor.main_schemes_deck)

        CardRender.print_cards_objs['removed-pool'] = []
        CardRender.print_cards_objs['removed-pool'].push(...Game.world_descriptor.area_status_cards)
        CardRender.print_cards_objs['removed-pool'].push(...Game.world_descriptor.area_insert)

        CardRender.print_cards_objs['victory-display'] = Game.world_descriptor.victory_display

        CardRender.print_cards_objs[`player-all-hand-cards`]      = []
        CardRender.print_cards_objs[`player-all-area-hero`]       = []
        CardRender.print_cards_objs[`player-all-allies`]          = []
        CardRender.print_cards_objs[`player-all-supports`]        = []
        CardRender.print_cards_objs[`player-all-engaged-minions`] = []
        for( let i=0; i<Game.world_descriptor.players.length; i++ ) {
            CardRender.print_cards_objs[`player-all-hand-cards`].push          (...Game.world_descriptor.players[i].hand_cards)
            CardRender.print_cards_objs[`player-all-area-hero`].push           (...Game.world_descriptor.players[i].area_hero)
            CardRender.print_cards_objs[`player-all-area-hero`].push           (...Game.world_descriptor.players[i].dealt_encounter_cards)
            CardRender.print_cards_objs[`player-all-area-hero`].push           (...Game.world_descriptor.players[i].environment_area)
            CardRender.print_cards_objs[`player-all-area-hero`].push           (...Game.world_descriptor.players[i].obligations_area)
            CardRender.print_cards_objs[`player-all-supports`].push            (...Game.world_descriptor.players[i].supports)
            CardRender.print_cards_objs[`player-all-allies`].push              (...Game.world_descriptor.players[i].allies)
            CardRender.print_cards_objs[`player-all-engaged-minions`].push     (...Game.world_descriptor.players[i].engaged_enemies)
        }

        for( let i=0; i<Game.world_descriptor.players.length; i++ ) {
            CardRender.print_cards_objs[`player-${i}-player-deck`]                = Game.world_descriptor.players[i].player_deck
            CardRender.print_cards_objs[`player-${i}-player-discard-pile`]        = Game.world_descriptor.players[i].player_discard_pile
            CardRender.print_cards_objs[`player-${i}-additional-deck`]            = Game.world_descriptor.players[i].additional_deck
            CardRender.print_cards_objs[`player-${i}-additional-discard-pile`]    = Game.world_descriptor.players[i].additional_discard_pile
        }

    }

    private static printCard(card: CardDescriptor, parent_element: HTMLElement, is_hand_card: boolean, show_detail: boolean, index: number, is_selecting: boolean) {

        function change_value(card_div: HTMLElement, value: number, span_class: string[]) {
            const instanceIndex = card_div.getElementsByClassName('change-value').length;
            let timeout = instanceIndex * 200

            const effect = document.createElement('div')
            effect.dataset.value = value > 0 ? "+" + value : value.toString()
            Lib.assert(value != 0)
            // if( isNaN(value) ) {
            //     let x = 1
            // }
            effect.classList.add('change-value')
            effect.style.setProperty('--instance-index', instanceIndex.toString());

            if( value > 0 ) {
                effect.classList.add('add')
            } else {
                effect.classList.add('sub')
            }
            if( span_class ) {
                effect.classList.add(...span_class)
            }

            effect.classList.add('hide')

            card_div.appendChild(effect)
            // bad for rotate card
            // card_div.querySelector('.face')!.appendChild(effect)

            setTimeout(() => {

                effect.classList.remove('hide')

                setTimeout(function() {
                    effect.parentNode!.removeChild(effect)
                }, 2000);

            }, timeout);
        }

        const object_id = card.object_id
        const card_id = card.card_id
        const pic_id = card.pic_id
        const card_div = Cards.getDiv(object_id)!
        const old_parent = card_div.parentElement

        if (show_detail) {
            const weatherMap: Record<string, string> = {
                "36002": '',
                "36003": 'rain',
                "36004": 'storm',
                "36005": 'snow',
            };

            if( card_id in weatherMap ) {
                const weather = weatherMap[card_id];
                UI.changeWeather(weather);
            }
        }

        if( object_id >= Cards.max_card_object_id ) {
            if( old_parent ) {
                old_parent.removeChild(card_div)
            }
            return
        }
        else
        if( !card.is_new ) {
            let badge_new = card_div.querySelector('.badge-new')
            if( badge_new ) {
                badge_new.parentNode!.removeChild(badge_new)
            }
        }

        card_div.dataset.pay_effect_id = ''

        // clean all card_type
        Lib.game.removeTypeClasses(card_div)
        Lib.game.addTypeClass(card_div, card.card_type, card.name)

        if( card_div.style.getPropertyValue('--bg-image-true') != `url("${pic_id}")` ) {
            card_div.style.setProperty('--bg-image-true', `url("${pic_id}")`)
        }
        if( card_div.style.getPropertyValue('--bg-image-false') != `url("${card.down_card_id}")` ) {
            card_div.style.setProperty('--bg-image-false', `url("${card.down_card_id}")`)
        }

        let is_facedown = card_div.classList.contains(ClassName.facedown)
        let url_text = ""
        if( card.isVisible() ) {
            url_text = card_div.style.getPropertyValue('--bg-image-true')
            if( !card.is_face_up ) {
                card_div.classList.add(ClassName.facedown)
                card_div.classList.add(ClassName.peeking)
            } else {
                card_div.classList.remove(ClassName.facedown)
                card_div.classList.remove(ClassName.peeking)
            }
        } else {
            url_text = card_div.style.getPropertyValue('--bg-image-false')
            card_div.classList.add(ClassName.facedown)
            card_div.classList.remove(ClassName.peeking)
        }

        if( card.object_id == 4 ) {
            let a = 1
        }

        let flip = false
        if( old_parent && old_parent.id == "player-all-hand-cards" ||
            parent_element.id == "player-all-hand-cards"
        ) {
            flip = false
        }
        else
        if( is_facedown != card_div.classList.contains(ClassName.facedown) ) {
            flip = true
        }
        else {
            let bg = card_div.style.getPropertyValue('--bg-image')
            if( url_text != bg && bg != "" ) {
                flip = true // for hero card flip
            }
        }

        card_div.style.setProperty('--bg-image', url_text)

        let card_div_info = card_div.querySelector('.info') as HTMLElement
        // Update cost
        if( is_hand_card ) {
            card_div_info.innerHTML = ""
            // card_div_bind_image_info.innerHTML = ""
        }

        // ready
        if( !card.is_ready ) {
            card_div.classList.add(ClassName.exhausted)
        } else {
            card_div.classList.remove(ClassName.exhausted)
        }

        // if( object_id == 8 ) {
        //     let a = 1
        // }

        // ~= 2ms
        if( show_detail ) {
            const show_info_list: Record<string, string> = {
                'health': '',
                'confused': 'Confused', 'stunned': 'Stunned', 'tough': 'Tough',
                'recover': 'REC', 'attack': 'ATK', 'scheme': 'SCH', 'thwart': 'THW',
                'defense': 'DEF', 'hand_size': 'HSZ',
                'threat': '', 'target_threat': '',
                'acceleration_icon': 'accelerate',
                'amplify': 'Amplify', 'crisis': 'Crisis', 'hazard': 'Hazard',
                'retaliate': 'RTL',
                'attack_consequential_damage': '', 'thwart_consequential_damage': '',
                'restricted': 'Restricted', 'escalation_threat': 'escalate',
                'boost_const': 'Boost', 'villainous': 'Villainous',
                'engaged_with': '', 'with_player': '',
                // 'ally_limit': 'Ally Limit', 'restricted_limit': 'Restricted',
                'temporary': 'Temporary', 'vulnerable': 'Vulnerable'}
            const hide_when_zero: string[] = [
                'stunned', 'tough', 'confused', 'retaliate', 'guard', 'stalwart',
                'quickstrike', 'patrol', 'villainous',
                'acceleration', 'crisis', 'hazard', 'steady', 'toughness',
                'restricted', 'acceleration_token', 'accelerate', 'escalation_threat',
                'assault', 'temporary', 'teamwork', 'vulnerable', 'peril', 'permanent',
            ]
            const hide_value: string[] = [
                'restricted', 'guard', 'patrol', 'toughness', 'quickstrike',
                'steady', 'stalwart', 'permanent',
                'assault', 'crisis', 'Temporary',
                'villainous', 'teamwork', 'vulnerable',
            ]
            const color_counter: string[] = ['confused', 'stunned', 'tough', 'acceleration', 'active', 'acceleration_token', 'accelerate', 'first_player']
            const hover_only_keys: string[] = ['victory', 'ally_limit', 'restricted_limit', 'hand_size']
            const debug_only_keys: string[] = [
                'incite', 'printed_stage', 'surge',
                'is_completed',
                // 'boost',
            ]
            const hide_keys: string[] = [
                'curr_ally_limit',
                'curr_restricted_limit',
            ]

            let info_div = ""
            let all_info = card.info
            let data_copy = card_div.querySelector('.info')!.cloneNode() as HTMLElement
            delete_all_data(card_div)
            for( let [key, value] of Object.entries(all_info) ) {
                if( value != undefined ) {
                    let span_class = ''
                    let key_name = ''
                    let is_token = false
                    let is_counter = false
                    let is_form = false
                    key = key.replace("'", "")
                    if( key == 'k_health' && card.card_type_base == "Unit" ) {
                        key = 'health'
                    }
                    else if( key == 'k_threat' && card.card_type_base == "Scheme" ) {
                        key = 'threat'
                    }
                    else if( key == 'k_first_player_token' || key == 'c_active' ) {
                    }
                    else
                    if( key.endsWith('_printed') ) {
                        continue
                    }
                    else
                    if( key.startsWith('f_') ) { // counter
                        span_class = key.replace(/^f_/, '').toLowerCase()
                        key_name = span_class
                        is_form = true
                    }
                    else
                    if( key.startsWith('c_') ) { // counter
                        span_class = key
                        key_name = span_class.replace(/^c_/, '').toLowerCase()
                        is_counter = true
                    }
                    else
                    if( key.startsWith('k_') ) { // token
                        span_class = key.toLowerCase()
                        key_name = span_class.replace(/^k_/, '').replace(/_token$/, '')
                        is_token = true
                    }
                    else
                    if( value == 0 && key == 'defense' && card.card_type == 'Ally' ) {
                        span_class = key.toLowerCase()
                    }
                    else
                    if( value <= 0 && hide_when_zero.includes(key) ) {
                        span_class = key.toLowerCase()
                    } else {
                        if( show_info_list[key] == undefined ) {
                            span_class = key.toLowerCase()
                            key_name = key
                        }
                        else if( show_info_list[key] ) {
                            span_class = key.toLowerCase()
                            key_name = show_info_list[key]
                        }
                    }

                    // Hide change
                    let hide_change = true
                    // if( !['attack_consequential_damage', 'thwart_consequential_damage'].includes(key) ) {
                    //     hide_change = false
                    // }
                    if( parent_element.classList.contains("area") && parent_element.id != 'area-play' ) {
                        hide_change = false
                    }

                    if( !hide_change ) {
                        let last_value = Number(data_copy.getAttribute(`data-${key}`)!)
                        // const default_zero_keys = ['threat', 'attack', 'scheme', 'attack_consequential_damage', 'thwart_consequential_damage']
                        // const default_zero_keys = ['threat', 'attack', 'scheme', 'recover', 'thwart', 'defense']
                        const default_zero_keys = ['threat']
                        const is_default_zero_key = default_zero_keys.includes(key)
                        if( (last_value || is_token || is_counter || is_default_zero_key ) && last_value != value && key != 'target_threat' ) {
                            if( !last_value && ( is_counter || is_token || is_default_zero_key ) ) {
                                last_value = 0
                            }
                            let the_value = value - last_value

                            if( the_value != 0) {
                                let class_name = span_class ? [span_class] : []
                                if( (is_counter || is_token) && !color_counter.includes(span_class) ) {
                                    if( is_counter ) {
                                        class_name.push(...['counter'])
                                    } else {
                                        class_name.push(...['token'])
                                    }
                                }
                                if( class_name.length == 0 ) {
                                    class_name = [key]
                                }
                                change_value(card_div, the_value, class_name)
                            }
                        }
                    }

                    // if( object_id == 82 ) {
                    //     console.log(key)
                    //     let a = 1
                    // }

                    function addIcons(key: string, value: number) {
                        let iconMap: Record<string, string> = {
                            'hazard': `<span name="Hazard" class="icon icon-hazard"></span>`,
                            'crisis': `<span name="Crisis" class="icon icon-crisis"></span>`,
                            'amplify':`<span name="Amplify" class="icon icon-amplify"></span>`,
                            // 'k_acceleration_token': `<span name="Acceleration" class="icon icon-acceleration-token"></span>`,
                            'acceleration_icon': `<span name="Acceleration" class="icon icon-acceleration"></span>`
                        };

                        if (iconMap[key] && value) {
                            // info_div += `<div>${iconMap[key].repeat(value)}</div>`;
                            info_div += `${iconMap[key].repeat(value)}`;
                        }
                    }

                    // Call the function with the appropriate key and value
                    if( ['hazard', 'crisis', 'amplify', 'acceleration_icon'].includes(key) ) {
                        addIcons(key, value);
                    }
                    else
                    if( key == 'k_first_player_token' || key == 'c_active' ) {
                        if( value ) {
                            info_div += `<div class='k_first_player_token'><i class="fa fa-flag" aria-hidden="true"></i></div>`
                        }
                    }
                    else
                    if( key == 'ally_limit' ) {
                        info_div += `<div class='hover-only'><span class='${span_class}'>Ally Limit</span><span>:${all_info['curr_ally_limit']}/${value}</span></div>`
                    }
                    else
                    if( key == 'restricted_limit' ) {
                        info_div += `<div class='hover-only'><span class='${span_class}'>Restricted</span><span>:${all_info['curr_restricted_limit']}/${value}</span></div>`
                    }
                    else if( key == 'is_infinite_health' ) {
                        if( value ) {
                            info_div += `<div class='infinite_health'>N</div>`
                        }
                    }
                    else if( ['health'].includes(key) ) {
                        // for ::after
                        info_div += `<div class='${key}'>${value}</div>`
                    }
                    else if ('guard' == key && value > 0 ) {
                        info_div += `<div class='${key}'><i class="fa fa-shield" aria-hidden="true"></i></div>`
                    }
                    else if( ['target_threat', 'threat'].includes(key) ) {
                        if( key == 'target_threat' && value > 0 ||
                            key == 'threat' ) {
                            info_div += `<div class='${key}' style='display: none'></div>`
                        }
                    }
                    else if( key == 'treat_as_if_blank' ) {
                        info_div += `<div class='${key}'></div>`
                    }
                    else if( key == 'escalation_threat' ) {

                    }
                    else if( key == 'boost_const' ) {
                        let boost_div = ""
                        for(let i = 0; i < value; i++) {
                            boost_div += `<div class='icon-boost'></div>`
                        }
                        card_div.querySelector('.info_pay')!.innerHTML = `${boost_div}`
                        info_div += `<div class='debug-only'><span class='${span_class}'>${key_name}</span><span>:${value}</span></div>`
                    }
                    else if( debug_only_keys.includes(key) ) {
                        info_div += `<div class='debug-only'><span class='${span_class}'>${key_name}</span><span>:${value}</span></div>`
                    }
                    else if( hide_keys.includes(key) ) {
                    }
                    else if( hover_only_keys.includes(key) ) {
                        if( value > 0 ) {
                            info_div += `<div class='hover-only'><span class='${span_class}'>${key_name}</span><span>:${value}</span></div>`
                        }
                    }
                    else if( is_counter ) {
                        if( value != 0 ) {
                            info_div += `<div><span>${value}x</span><span class='${span_class} counter'>${key_name}</span></div>`
                        }
                    }
                    else if( key == 'k_acceleration_token' ) {
                        if( value != 0 ) {
                            info_div += `<div><span>${value}x</span><span name="Acceleration" class="icon icon-acceleration-token"></span></div>`
                        }
                    }
                    else if( is_form ) {
                        if( value != 0 ) {
                            info_div += `<div><span class='${span_class} form'>${key_name}</span></div>`
                        }
                    }
                    else if( is_token ) {
                        if( value != 0 ) {
                            info_div += `<div><span>${value}x</span><span class='${span_class} token'>${key_name}</span></div>`
                        }
                    }
                    else if( key_name ) {
                        if( hide_value.includes(key) ) {
                            info_div += `<div><span class='${span_class} hide-value'>${key_name}</span></div>`
                        } else {
                            let ex_data = ""
                            function repeatStar(x: number) {
                                if (!Number.isInteger(x)) {
                                    return '';
                                }
                                let result = '';
                                for (let i = 0; i < x; i++) {
                                    result += '<i class="icon icon-consequential consequential_icon"></i>';
                                }
                                return result;
                            }

                            if( key_name == 'ATK' ) {
                                ex_data = `${repeatStar(all_info['attack_consequential_damage'])}`
                            }
                            if( key_name == 'THW' ) {
                                ex_data = `${repeatStar(all_info['thwart_consequential_damage'])}`
                            }
                            info_div += `<div><span class='${span_class}'>${key_name}</span><span>:${value}</span>${ex_data}</div>`
                        }
                    }
                    if( key == 'cost' ) {
                        // card_div_bind_image_info.setAttribute(`data-${key}`, value.toString())
                    } else {
                        card_div_info.setAttribute(`data-${key}`, value.toString())
                    }
                }
            }

            for( let [key, text] of Object.entries(card.buffs) ) {
                info_div += `<div><span class='buff-${key}'>${text}</span></div>`
            }

            for( let [key, value] of Object.entries(card.traits) ) {
                if( value != undefined ) {
                    let span_class = ''
                    let key_name = ''
                    let is_trait = false
                    key = key.replace("'", "")

                    span_class = key.toLowerCase()
                    key_name = span_class.replace(/^t_/, '')
                    is_trait = true

                    let last_value = Number(data_copy.getAttribute(`data-${key}`)!)
                    if( last_value != value  ) {
                        let the_value = value - last_value
                        if( the_value != 0) {
                            // change_value(card_div, the_value, 'trait')
                        }
                    }

                    info_div += `<div><span class='${span_class} trait'>${key_name}</span></div>`
                    card_div_info.setAttribute(`data-${key}`, value.toString())
                }
            }

            if( card.name == "Archangel" ) {
                info_div += `<div><span class='archangel trait'></span></div>`
            }

            info_div += `<div class="control_player"><i class="fa fa-bookmark" aria-hidden="true"></i></div>`

            card_div_info.innerHTML = `<div class='name'>${card.name}</div>` + info_div
        } else {
            card_div_info.innerHTML = ""
        }


        let game_area = card_div.querySelector('.face')!

        const controlPlayerIndex = card.control_player;

        if (controlPlayerIndex !== -1) {
            const controlPlayerClass = `control_player_${controlPlayerIndex}`;
            // Add the current control player class if not already present
            if (!game_area.classList.contains(controlPlayerClass)) {
                // Remove all control player classes in one go
                game_area.classList.remove(...CardRender.control_by_player_classes);
                game_area.classList.add(controlPlayerClass);
            }
        } else {
            // Remove all control player classes if no control player is set
            game_area.classList.remove(...CardRender.control_by_player_classes);
        }

        let game_area_class = `game_area_${card.game_area}`
        if( !game_area.classList.contains(game_area_class) ) {
            for(let i=1; i<=5; i++) {
                game_area.classList.remove(`game_area_${i}`)
            }
            game_area.classList.add(game_area_class)
        }

        if( Setting.show_card_id ) {
            // card_div.querySelector('.debug-text').innerHTML = `<div><p>c${card.id}</p>
            // <p>${card.curr_card_id}</p>
            // <br/>bind:(${card.bind_object_id})
            // <br/>effects:[${card.effects}]
            // <br/>res:[${card.resources}]
            // <br/>
            // <br/>crc:[${card.crc}]
            // <br/>by:[${card.effect_by_cards}]
            // <br/>to:[${card.effect_to_cards}]</div>`

            card_div.querySelector('.debug-text')!.innerHTML = `
            <div><div class='debug-name'><span>c${card.object_id}</span><span>${card.card_id}</span></div>
            <br/>
            <p>bind: (${card.bind_object_id})</p>
            <p>effects:<br/>[${card.effects.join(", ")}]</p>
            <p style='color: orange'>res:<br/>[${card.resources.join(", ")}]</p>
            <br/>
            <p>crc: [${card.ui.crc}]</p>
            <p>by: [${card.ui.effect_by_cards.join(", ")}]</p>
            <p>to: [${card.ui.effect_to_cards.join(", ")}]</p></div>
            `

            card_div.querySelector<HTMLElement>('.debug-text')!.onclick = (e) => {
                const text = card_id.toString()
                copyToClipboard(text);
                e.stopPropagation();
                e.preventDefault();
            }
        }

        if( card.buffs['BuffCannotBeStunned'] ) {
            card_div.classList.add('buff-cannot-be-stunned')
        } else {
            card_div.classList.remove('buff-cannot-be-stunned')
        }

        if( card.buffs['BuffCannotBeConfused'] ) {
            card_div.classList.add('buff-cannot-be-confused')
        } else {
            card_div.classList.remove('buff-cannot-be-confused')
        }

        if( card.info['steady'] ) {
            card_div.classList.add('steady')
        } else {
            card_div.classList.remove('steady')
        }

        if( card.bind_object_id ) {
            card_div.classList.add('bind-card')
        } else {
            card_div.classList.remove('bind-card')
        }

        if( card.ui.is_obligation ) {
            card_div.classList.add('obligation')
        } else {
            card_div.classList.remove('obligation')
        }

        card_div.classList.remove('hover_bind')
        card_div.classList.remove('hover_effected_to')
        card_div.classList.remove('hover_effected_by')

        let is_in_play_turn = UI.is_in_play_turn

        if( old_parent != parent_element ) {
            MoveCard.appendChildWithCallback(parent_element, card_div, index, 1500)
        }

        if( flip ) {
            CardAnimation.flipCard(card_div)
            if( AutoActivate.config.has(card_id) ) {
                card_div.classList.add(ClassName.auto_activate)
            } else {
                card_div.classList.remove(ClassName.auto_activate)
            }
        }

        if( parent_element != old_parent || card_div.classList.contains('hide') ) {
            // const start = performance.now();
            UI.anime_move_cards_count += 1
            CardAnimation.moveCard(card_div, parent_element, old_parent, index, true)
        }
        else if( parent_element == old_parent && parent_element.childNodes[index] != card_div ) {
            // if( parent_element.classList.contains('area') && !parent_element.classList.contains('hand-cards') ) {
            if( parent_element.classList.contains('area') ) {
                UI.anime_move_cards_count += 1
                CardAnimation.moveCard(card_div, parent_element, old_parent, index, false)
            }
            else
            if( !is_selecting )
            {
                UI.anime_shuffle_cards_count += 1
                // let do_offset_width = UI.anime_shuffle_cards_count < 5
                CardAnimation.shuffleCard(card_div, parent_element, index)
            }
            else {
                card_div.classList.remove(ClassName.card_shuffle)
                parent_element.insertBefore(card_div, parent_element.childNodes[index]);
                // move_card(card_div, parent_element, index, false)
            }
        }

        if( ( !is_in_play_turn|| !Game.asking_players.includes(Setting.player_id) )
            && UI.event_name != 'LookAt_Text'
        ) {
            CardAnimation.activeCard(card_div, old_parent)
        }

        card.doRender()

        return card_div
    }

    static printCards() {
        CardRender.updateCardsData()

        UI.anime_move_cards_count = 0
        UI.anime_shuffle_cards_count = 0
        CardAnimation.setAnimeTimeInit()

        for( const area_name of CardRender.area_names )
        {
            let is_temp_sort = false
            if( UI.temp_sorted_deck_div ) {
                let element = document.querySelector(`#${area_name}`) as HTMLElement
                if( element == UI.temp_sorted_deck_div ) {
                    is_temp_sort = true
                }
            }
            CardRender.printAreaCards(CardRender.print_cards_objs[area_name], area_name, false, is_temp_sort)
        }
        if( UI.global_first_create ) {
            MoveCard.doMoveFirstTime()
        } else {
            MoveCard.doMove()
        }
        UI.global_first_create = false

        if( HoverCard.hover_card ) {
            HoverCard.updateHoverEffects(Number(HoverCard.hover_card.dataset.id!), true)
        }

        CardAnimation.showEvent()

        console.log("do_render:", Game.world_descriptor.render_id, CardRender.stat_do_render, "/", CardRender.stat_skip_render)
        // if( CardRender.stat_do_render < 5 && CardRender.stat_do_render > 0 ) {
        //     console.log("do_render:", CardRender.stat_do_render2)
        // }
        CardRender.stat_skip_render = 0
        CardRender.stat_do_render = []
        // CardRender.stat_do_render2 = []

        CardAnimation.setAnimeTimeEnd()

        return
    }


    static update(cards_json: any) {
        CardRender.print_cards_objs = {}
        // if( cards_json ){
        //     try {
        //         CardRender.print_cards_objs = cards_json
        //     } catch (error) {
        //         Lib.alert(cards_json)
        //     }
        // }

        // console.log(`called_time: ${Game.world_state.prompt}`)
        // console.time('called_time ShowPrintCards');

        // let is_in_play_turn = UI.is_in_play_turn
        
        if( UI.event_name == 'LookAt_Text' ) {
            document.querySelectorAll<HTMLElement>(`.card.${ClassName.active_card}`).forEach(card_div => {
                card_div.classList.remove(ClassName.active_card)
            })
        } else {
            document.querySelectorAll<HTMLElement>('.card').forEach(card_div => {
                const object_id = Number(card_div.dataset.id!)
                if( card_div.classList.contains(ClassName.active_card) ) {
                    if( !CardAnimation.active_card_object_ids.includes(object_id) ) {
                        card_div.classList.remove(ClassName.active_card)
                        console.log("un active:", object_id)
                    }
                }
                if( Effect.response_json_ask ) {
                    for( let x of Effect.response_json_ask.options ) {
                        let found = false
                        let card_div_bind_image_info = card_div.querySelector('.bind-image-info') as HTMLElement
                        if( x.bind_id == object_id ) {
                            let cost = x.getCost().replaceAll("|", "/")
                            if( cost != "" ) {
                                card_div_bind_image_info.setAttribute('data-cost', cost)
                            }
                            found = true
                            break
                        }
                        if( !found ) {
                            card_div_bind_image_info.setAttribute('data-cost', "")
                        }
                    }
                }
            })
        }


        CardRender.printCards()
        // console.timeEnd('called_time ShowPrintCards');

        Effect.update()
    }
}

export class Cards {

    public static render = CardRender
    public static cards: CardDescriptor[] = []

    static max_card_object_id = 0

    private static card_statistics = new CardStatistics()

    private static translate_json: Record<string, string>

    static {
        Cards.card_statistics.loadAllCards(true, false)

        async function load_translate() {
            const response_translate = await fetch(`get_translate_json?`);
            if (!response_translate.ok) {
                throw new Error('Network response was not ok: ' + response_translate.statusText);
            }
            Cards.translate_json = await response_translate.json()
        }
        load_translate()
    }

    static getText(card_id: string): string {
        if( card_id in Cards.translate_json ) {
            return Cards.translate_json[card_id]
        } else
        if( card_id in Cards.card_statistics.const_card_dict ) {
            return Cards.card_statistics.const_card_dict[card_id].text
        }
        else {
            return ""
        }
    }

    static findObjectIdByEffectId(effect_id: number) {
        for( const card of Cards.cards ) {
            if( card.effects.includes(effect_id) ) {
                return card.object_id
            }
        }
        return null
    }

    static getDiv(object_id: number): HTMLElement|undefined {
        const card = Cards.getCard(object_id)
        if( card ) {
            return card.card_div
        }
        return undefined
    }

    static getCard(object_id: number): CardDescriptor|undefined {
        try {
            return Cards.cards[object_id];
        } catch {
            return undefined
        }
    }

    static getSpanTextHelp(object_id: string, card_id: string, name: string): string {
        const p1 = object_id
        const p2 = card_id
        const p4 = name
        const escapedP4 = p4.replace(/'/g, "\\&apos;");

        // onclick='Debug.clicked_card_id.value = "${p2}"' 
        let span = `<span class='log-card' 
                    onmouseover='HoverCard.showLogImage(${p1}, "${p2}")' 
                    onmouseleave='HoverCard.set(null)' 
                    data-id='${p2}' 
                    oncontextmenu=__oncontextmenu__
                    >${p4}</span>`;
        let oncontextmenu = `"HistoryLog.showMenu(event, ${p1}, '${p2}', '${escapedP4}')"`
        return span.replaceAll('__oncontextmenu__', oncontextmenu)
    }

    static getSpanText(object_id: number): string {
        const card = Cards.getCard(object_id)
        if( !card?.isVisible() ) {
            return `<span class='log-card'>???</span>`
        }

        const p1 = object_id
        const p2 = card.card_id
        const p4 = card.name

        return Cards.getSpanTextHelp(String(object_id), card.card_id, card.name)
    }
}

(window as any).Cards = Cards;
