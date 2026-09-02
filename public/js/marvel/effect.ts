import { Lib } from './lib.js'
import { ButtonSetting, ClientPreferences, Setting } from './settings.js'
import { Game } from './game.js'
import { UI } from './ui.js'
import { SelectStep } from './select.js'
import { Music } from './music.js'
import { Cards } from './cards.js'
import { Button } from './buttons.js'
import { AskOptionPayload, EffectDescriptor } from './data.js'
import { AutoEffect } from './auto_targeting.js'
import { ClassName } from './class_name.js'
import { BtnOk } from './btn_ok.js'
import { HoverCard } from './hover.js'
import { AutoActivate } from './auto_activate.js'
import { Command } from './command.js'

////////////////////////////////////////////////////////////////////////////////
//
export class Effect {
    static options_button_div = document.getElementById('option-buttons') as HTMLElement

    private static clicking_card_div: HTMLElement|undefined = undefined
    private static clicked_card_div: HTMLElement|undefined = undefined // Which card do we process now?

    private static available_card_bind_object_ids: number[] = [] // Which CardFace.cards did the effects bind with?

    static response_json_ask: AskOptionPayload

    static getFullSearchDisplayTargets(): number[] {
        const playerId = Effect.select_effect_obj.bind_player_id ?? Setting.player_id
        if( !ClientPreferences.showDeckDuringFullSearch(playerId) ) {
            return []
        }
        return Effect.select_effect_obj.full_search_display_targets
    }
    static select_effect_obj = new EffectDescriptor({})

    static is_in_event: 'response' | 'interrupt' | 'in_turn' | 'asking' | '' = ''

    static get is_ex_effect() {
        return Effect.response_json_ask.is_ex_effect
    }

    static get show_cancel() {
        const response = Effect.response_json_ask
        const last_option = response?.options?.[response.options.length - 1]
        return response?.show_cancel == true || last_option?.name == "Cancel"
    }

    static reset() {
        Effect.options_button_div.replaceChildren()

        Effect.clicked_card_div = undefined
        Effect.clicking_card_div = undefined

        if( Effect.response_json_ask ) {
            Effect.response_json_ask.options = []
        }
        Effect.available_card_bind_object_ids = []

        Effect.select_effect_obj.clear()
        UI.selectCountClear()

        Effect.updateHighLight()
        Effect.updateButtons([])
    }

    static updateHighLight() {
        let new_added_highlight_target: number[] = []
        let changed_search_target: number[] = []
        const search_display_targets = new Set([
            ...Effect.select_effect_obj.all_legal_targets,
            ...Effect.getFullSearchDisplayTargets(),
        ])
        for( const card_div of document.querySelectorAll<HTMLElement>('.card') ) {
            const object_id = Number(card_div.dataset.id!)
            const pay_effect_id = Number(card_div.dataset.pay_effect_id!)
            const was_being_searched = card_div.classList.contains(ClassName.being_searching)
            card_div.classList.remove(ClassName.select_card)
            card_div.classList.remove(ClassName.select_pay_card)

            let should_peek = SelectStep.isCost() && Effect.select_effect_obj.getResources().includes(pay_effect_id)

            if( Effect.select_effect_obj.is_search || should_peek ) {
                if( search_display_targets.has(object_id) || should_peek) {
                    card_div.classList.add(ClassName.being_searching)
                } else {
                    card_div.classList.remove(ClassName.being_searching)
                }
            } else {
                card_div.classList.remove(ClassName.being_searching)
            }

            if( ((Effect.clicked_card_div && object_id == Number(Effect.clicked_card_div.dataset.id!) || object_id == Effect.select_effect_obj.bind_id) && !Effect.isExEffect() )
                && !(SelectStep.isTargets() && Effect.select_effect_obj.all_legal_targets.includes(object_id))) {
                card_div.classList.add(ClassName.select_card)
            }
            else
            if( Effect.select_effect_obj.resources.includes(pay_effect_id) ) {
                card_div.classList.add(ClassName.select_card)
                card_div.classList.add(ClassName.select_pay_card)
            }
            else
            if( SelectStep.isCost() && Effect.select_effect_obj.getResources().includes(pay_effect_id) ) {
                if( !Effect.select_effect_obj.selected_targets.includes(object_id) ) {
                    card_div.classList.remove(ClassName.highlight_effect)
                    if( card_div.classList.contains(ClassName.highlight_target) ) {
                        card_div.classList.remove(ClassName.highlight_target)
                        new_added_highlight_target.push(object_id)
                    }
                    card_div.classList.add(ClassName.being_searching)
                    card_div.classList.add(ClassName.highlight_pay)
                    // card_div.classList.remove(ClassName.active_card)
                } else {
                    card_div.classList.add(ClassName.select_card)
                }

                let index = Effect.select_effect_obj.getResources().indexOf(pay_effect_id)
                let res_text = Effect.select_effect_obj.getResText()[index]
                let resource_div = ""
                for( let c of res_text.split('') ) {
                    if( Setting.show_res_id ) {
                        resource_div += `<div class='res-${c.toLowerCase()}' style='color: white'>${pay_effect_id}</div>`
                    } else {
                        resource_div += `<div class='res-${c.toLowerCase()}'></div>`
                    }
                }
                const info_pay = card_div.querySelector('.info_pay')!
                if( resource_div ) {
                    info_pay.innerHTML = `${resource_div}`
                    info_pay.classList.add("has_pay")
                }
            }
            else
            if( Effect.select_effect_obj.selected_targets.includes(object_id) ) {
                card_div.classList.add(ClassName.select_card)
            }
            else
            {
                if( card_div.parentElement!.id != 'area-play' ) {
                    const info_pay = card_div.querySelector('.info_pay')!
                    if( info_pay.innerHTML != "" ) {
                        info_pay.innerHTML = ""
                        info_pay.classList.remove("has_pay")
                    }
                }
                let highlight_effect = false
                if( SelectStep.isCard() && Effect.isCardHasEffect(object_id) ) {
                    card_div.classList.add(ClassName.highlight_effect)
                    if( Effect.isCardHasForcedActionEffect(object_id) ) {
                        card_div.classList.add(ClassName.forced_action_effect)
                    } else {
                        card_div.classList.remove(ClassName.forced_action_effect)
                    }
                    if( card_div.classList.contains(ClassName.highlight_target) ) {
                        card_div.classList.remove(ClassName.highlight_target)
                        new_added_highlight_target.push(object_id)
                    }
                    card_div.classList.remove(ClassName.highlight_pay)
                    // card_div.classList.remove(ClassName.active_card)
                    highlight_effect = true
                }
                else
                if( SelectStep.isEffect() && false ) {
                }
                else
                if( SelectStep.isTargets() && Effect.select_effect_obj.all_legal_targets.includes(object_id) ) {
                    card_div.classList.remove(ClassName.highlight_effect)
                    card_div.classList.add(ClassName.highlight_target)
                    card_div.classList.remove(ClassName.highlight_pay)
                    // card_div.classList.remove(ClassName.active_card)
                    new_added_highlight_target.push(object_id)
                }
                else
                {
                    card_div.classList.remove(ClassName.highlight_effect)
                    if( card_div.classList.contains(ClassName.highlight_target) ) {
                        card_div.classList.remove(ClassName.highlight_target)
                        new_added_highlight_target.push(object_id)
                    }
                    card_div.classList.remove(ClassName.highlight_pay)
                }
                if( highlight_effect ) {
                    card_div.classList.add('show-cost')
                } else {
                    card_div.classList.remove('show-cost')
                }
            }

            if( was_being_searched != card_div.classList.contains(ClassName.being_searching) ) {
                changed_search_target.push(object_id)
            }
        }

        const changed_deck_targets = [...new Set([
            ...new_added_highlight_target,
            ...changed_search_target,
        ])]
        if( changed_deck_targets.length > 0 && !SelectStep.isCost() ) {
            Cards.render.printDeckWhenHighlightTarget(changed_deck_targets)
        }
    }

    static onCancel() {
        if( Effect.isExEffect() ) {
            if( SelectStep.isTargets() || SelectStep.isCost() ) {
                Effect.select_effect_obj.selected_targets = []
                // SelectStep.setTargets()
                Effect.updateHighLight()
                Music.playClickCardSound()
            }
        } else {
            UI.prompt.resetPromptText()
            Effect.options_button_div.replaceChildren()

            for(const card_div of document.querySelectorAll<HTMLElement>('.card')) {
                card_div.dataset.pay_effect_id = ''
            }

            Effect.clicked_card_div = undefined
            Effect.select_effect_obj.clear()
            UI.selectCountClear()

            SelectStep.setBegin()
            Effect.updateHighLight()
            Music.playClickCardSound()
            console.log('Cancel')
        }
        return
    }

    static onCardClick(card_div: HTMLElement, right: boolean, in_replay: boolean=false, by_mouse: boolean=false) {

        if( !right ) {
            if( card_div.parentElement!.classList.contains('deck') &&
                !card_div.parentElement!.classList.contains('clicked')
            ) {
                const only_one_target = card_div.classList.contains(ClassName.highlight_target) && card_div.parentElement!.querySelectorAll(`.${ClassName.highlight_target}`).length === 1
                let should_continue = true
                if( by_mouse ) {
                    if( only_one_target && !card_div.classList.contains(ClassName.being_searching) ) {
                    } else {
                        card_div.parentElement!.classList.add('clicked')
                        if( UI.temp_sorted_deck_div ) {
                            UI.tempSortDeck(false)
                            UI.temp_sorted_deck_div = null
                        }
                    }
                    should_continue = false
                }
                if( should_continue || 
                    in_replay || 
                    // Setting.scene_3d || 
                    only_one_target || 
                    (card_div.parentElement!.firstChild === card_div.parentElement!.lastChild) || 
                    (card_div.getAttribute('select-count') !== "")) {
                    should_continue = true;
                } else {
                    return;
                }
            }
        }

        if( Command.setLastClickCard(card_div) ) {
            return
        }

        if( Game.is_lost_connect ) {
            return
        }

        if( !right ) {
            let badge_new = card_div.querySelector<HTMLElement>('.badge-new')
            if( badge_new ) {
                badge_new.parentNode!.removeChild(badge_new)
            }
        }

        // console.log('click:', card_div.dataset)
        const object_id = Number(card_div.dataset.id!)
        console.log('click:', object_id)
        // Cancel

        if( !SelectStep.isCard() && !Effect.isExEffect() ) {

            if( ( Cards.getCard(object_id)!.effects.includes(Effect.select_effect_obj.id) && !Effect.select_effect_obj.all_legal_targets.includes(object_id) )
            // || CardFace.cards[object_id].resources.includes(CardEffect.select_effect_obj.id)
            || (Effect.select_effect_obj.id == -1 && Effect.clicked_card_div && Effect.clicked_card_div == card_div)
            || (Effect.select_effect_obj.selected_targets.length == 1 && Effect.clicked_card_div && Effect.select_effect_obj.selected_targets[0] == Number(Effect.clicked_card_div.dataset.id!) && Effect.clicked_card_div == card_div) ) {
                Effect.onCancel()
                return
            }
        }
        // Card + Effect
        if( SelectStep.isCard() ) {
            if( !Effect.isExEffect() && Effect.isCardHasEffect(object_id) ) {
                Effect.activeEffect(card_div)
                Music.playClickCardSound()
                // ~~This already done in `CardEffect.activeEffect`~~
                // No, we need this when one card bind more than one effect
                Effect.updateHighLight()
            }
        }
        else
        // Target
        if( SelectStep.isTargets() ) {
            let update_target = false
            let select_count = false
            if( Effect.select_effect_obj.selected_targets.length > 0 &&
                Effect.select_effect_obj.selected_targets.includes(object_id) )
            {
                const max_count = Lib.array.occurrence(Effect.select_effect_obj.all_legal_targets, object_id)
                let current_count = Lib.array.occurrence(Effect.select_effect_obj.selected_targets, object_id)
                if( Effect.select_effect_obj.start_x && current_count < max_count ) {
                    select_count = true
                    Effect.select_effect_obj.selected_targets.push(object_id)
                    card_div.setAttribute('select-count', "x" + (current_count+1).toString())
                }
                else {
                    card_div.setAttribute('select-count', "")
                    while (true) {
                        const index = Effect.select_effect_obj.selected_targets.indexOf(object_id);
                        if( index == -1 ) {
                            break
                        }
                        Effect.select_effect_obj.selected_targets.splice(index, 1);
                    }
                }
                Music.playClickCardSound()
                update_target = true
            }
            else
            if( Effect.select_effect_obj.all_legal_targets.includes(object_id) ){
                Effect.select_effect_obj.selected_targets.push(object_id)
                if( Lib.array.hasDuplicates(Effect.select_effect_obj.all_legal_targets) ) {
                    select_count = true
                    card_div.setAttribute('select-count', "x1")
                }
                Music.playClickCardSound()
                update_target = true
            }

            if( update_target ) {
                function check_select_rule() {
                    if( Effect.select_effect_obj.select_rule == "VillainAndMinionsEngagedSamePlayer" ) {
                        let one_villain = false
                        let player_ids: number[] = []
                        for( let id of Effect.select_effect_obj.selected_targets ) {
                            const card_type = Cards.getCard(id)!.card_type
                            if( card_type == 'EncounterVillain' ||
                                card_type == 'Leader'
                            ) {
                                if( one_villain ) {
                                    return false
                                }
                                if( !one_villain ) {
                                    one_villain = true
                                }
                            }
                            if( card_type == 'Minion' ) {
                                if( player_ids.length != 0 && !player_ids.includes( Cards.getCard(id)!.info['engaged_with']) ) {
                                    return false
                                }
                                player_ids.push(Cards.getCard(id)!.info['engaged_with'])
                            }
                        }
                        if( !one_villain ) {
                            return false
                        }
                        return true
                    }
                    else if( Effect.select_effect_obj.select_rule == "VillainAndMinionsEngagedWithYou" ) {
                        let one_villain = false
                        let player_id = Setting.player_id + 1
                        for( let id of Effect.select_effect_obj.selected_targets ) {
                            const card_type = Cards.getCard(id)!.card_type
                            if( card_type == 'EncounterVillain' ||
                                card_type == 'Leader'
                            ) {
                                if( one_villain ) {
                                    return false
                                }
                                if( !one_villain ) {
                                    one_villain = true
                                }
                            }
                            if( card_type == 'Minion' ) {
                                if( player_id != Cards.getCard(id)!.info['engaged_with'] ) {
                                    return false
                                }
                            }
                        }
                        if( !one_villain ) {
                            return false
                        }
                        return true
                    }
                    else if( Effect.select_effect_obj.select_rule == "DifferentCards" ) {
                        let card_names: string[] = []
                        for( let id of Effect.select_effect_obj.selected_targets ) {
                            if( card_names.includes(Cards.getCard(id)!.name) ) {
                                return false
                            }
                            card_names.push(Cards.getCard(id)!.name)
                        }
                        return true
                    }
                    else if( Effect.select_effect_obj.select_rule == "MustIncludeTraits" ) {
                        let must_include_traits = [...Effect.select_effect_obj.target_must_include_traits];
                        for( let id of Effect.select_effect_obj.selected_targets ) {
                            for( let trait of Object.keys(Cards.getCard(id)!.traits) ) {
                                if( must_include_traits.includes(trait) ) {
                                    must_include_traits = must_include_traits.filter(t => t !== trait);
                                }
                            }
                        }
                        return must_include_traits.length == 0
                    }
                    else if( Effect.select_effect_obj.select_rule == "DifferentType" ) {
                        let card_types: string[] = []
                        for( let id of Effect.select_effect_obj.selected_targets ) {
                            if( card_types.includes(Cards.getCard(id)!.card_type) ) {
                                return false
                            }
                            card_types.push(Cards.getCard(id)!.card_type)
                        }
                        return true
                    }
                    // else if( Effect.select_effect_obj.select_rule == "DifferentBaseType" ) {
                    //     let card_types: string[] = []
                    //     for( let id of Effect.select_effect_obj.selected_targets ) {
                    //         if( card_types.includes(Cards.getCard(id)!.card_type_base) ) {
                    //             return false
                    //         }
                    //         card_types.push(Cards.getCard(id)!.card_type_base)
                    //     }
                    //     return true
                    // }
                    else if( Effect.select_effect_obj.select_rule == "CombinedResourceCost" ||
                        Effect.select_effect_obj.select_rule == "CombinedPrintedCost"
                    ) {
                        let cost = 0
                        for( let id of Effect.select_effect_obj.selected_targets ) {
                            const card = Cards.getCard(id)!
                            cost += card.cost
                            if( cost > Effect.select_effect_obj.select_rule_param[1] ) {
                                return false
                            }
                        }
                        if( cost < Effect.select_effect_obj.select_rule_param[0] ) {
                            return false
                        }
                        return true
                    }
                    else if( Effect.select_effect_obj.select_rule == "CombinedResourceIcons" ) {
                        return true
                    }
                    else {
                        return true
                    }
                }

                let rule_check = check_select_rule()

                function isSelectedTargetsInRange(selectEffectObj: EffectDescriptor) {
                    const { selected_targets, target_num_range } = selectEffectObj;
                    return selected_targets.length >= target_num_range[0] &&
                        selected_targets.length <= target_num_range[1];
                }

                function check_no_other_target(selectEffectObj: EffectDescriptor) {
                    if( !selectEffectObj.select_rule.startsWith("VillainAndMinions") ) {
                        return false
                    }
                    let player_id = -1
                    for( const id of selectEffectObj.selected_targets ) {
                        if( Cards.getCard(id)!.card_type == 'Minion' ) {
                            player_id = Cards.getCard(id)!.info['engaged_with']
                            break
                        }
                    }

                    const ids = selectEffectObj.all_legal_targets
                    for( const id of ids ) {
                        const card_type = Cards.getCard(id)!.card_type
                        if( card_type == 'EncounterVillain' ||
                            card_type == 'Leader'
                        ) {
                            continue
                        }
                        if( !selectEffectObj.selected_targets.includes(id) ) {
                            if( card_type == 'Minion' ) {
                                if( Cards.getCard(id)!.info['engaged_with'] == player_id || player_id == -1 ) {
                                    return false
                                }
                            } else {
                                return false
                            }
                        }
                    }
                    return true
                }

                let no_other_target = check_no_other_target(Effect.select_effect_obj)

                if( (isSelectedTargetsInRange(Effect.select_effect_obj) || no_other_target ) &&
                    rule_check ) {
                    BtnOk.setDisable(false)
                    BtnOk.setOk('Ok')
                } else {
                    BtnOk.setDisable(false)
                    BtnOk.setCancel('Cancel')
                }

                if( !select_count ) {
                    if( Effect.select_effect_obj.start_x ) {
                        for( const object_id of Effect.select_effect_obj.selected_targets ) {
                            const card_div = Cards.getDiv(object_id)!
                            let current_count = Lib.array.occurrence(Effect.select_effect_obj.selected_targets, object_id)
                            card_div.setAttribute('select-count', `x${current_count}`)
                        }
                    } else {
                        let deck_select_index: {[key: string]: number} = {}
                        for( let i=0; i<Effect.select_effect_obj.selected_targets.length; i++ ) {
                            const object_id = Effect.select_effect_obj.selected_targets[i]
                            const card_div = Cards.getDiv(object_id)!
                            card_div.setAttribute('select-count', String(i+1))
                            if( card_div.parentElement?.classList.contains('deck') ) {
                                const parent_div_id = card_div.parentElement.id;
                                if (deck_select_index[parent_div_id] === undefined) {
                                    deck_select_index[parent_div_id] = 0;
                                }
                                card_div.style.setProperty('--select-index', String(deck_select_index[parent_div_id]))
                                deck_select_index[parent_div_id] += 1
                            }
                        }
                    }
                }

                if( rule_check ) {
                    SelectStep.setTargets(true)
                    if( Effect.select_effect_obj.selected_targets.length == 1 && Effect.select_effect_obj.target_num_range[1] == 1 ) {
                        Button.doPost(false)
                    }
                    else if( Effect.select_effect_obj.selected_targets.length == Effect.select_effect_obj.target_num_range[1] || no_other_target ) {
                        Button.doPost(false)
                    }
                }
            }

            console.log(object_id, Effect.select_effect_obj.selected_targets)
            Effect.updateHighLight()
        }
        else
        // Pay
        if( SelectStep.isCost() ) {
            let click_payable_card = false
            let cancel_target = false
            if( card_div.dataset.pay_effect_id ) {
                let pay_effect_id = Number(card_div.dataset.pay_effect_id)
                if( Effect.select_effect_obj.getResources().includes(pay_effect_id) ){
                    click_payable_card = true

                    let max_count = Lib.array.occurrence(Effect.select_effect_obj.getResources(), pay_effect_id)
                    let current_count = Lib.array.occurrence(Effect.select_effect_obj.resources, pay_effect_id)
                    if( max_count > current_count ) {
                        Effect.select_effect_obj.resources.push(pay_effect_id)
                        if( current_count+1 >= 2) {
                            card_div.setAttribute('select-count', "x" + (current_count+1).toString())
                        } else {
                            card_div.setAttribute('select-count', "")
                        }
                    }
                    else {
                        card_div.setAttribute('select-count', "")
                        while (true) {
                            const index = Effect.select_effect_obj.resources.indexOf(pay_effect_id);
                            if( index == -1 ) {
                                break
                            }
                            Effect.select_effect_obj.resources.splice(index, 1);
                        }
                    }
                    Music.playClickCardSound()
                }
            }
            if( click_payable_card ) {
                // console.log(pay_effect_id)
                console.log(Effect.select_effect_obj.resources)
            }
            else
            {
                if( Effect.select_effect_obj.selected_targets.includes(object_id) ) {
                    // Cancel target
                    card_div.setAttribute('select-count', "")
                    while (true) {
                        const index = Effect.select_effect_obj.selected_targets.indexOf(object_id);
                        if( index == -1 ) {
                            break
                        }
                        Effect.select_effect_obj.selected_targets.splice(index, 1);
                    }

                    if( Effect.select_effect_obj.start_x ) {
                        for( const object_id of Effect.select_effect_obj.selected_targets ) {
                            const current_count = Lib.array.occurrence(Effect.select_effect_obj.selected_targets, object_id)
                            const card_div = Cards.getDiv(object_id)!
                            card_div.setAttribute('select-count', `x${current_count}`)
                        }
                    } else {
                        let deck_select_index: {[key: string]: number} = {}
                        for( let i=0; i<Effect.select_effect_obj.selected_targets.length; i++ ) {
                            const x = Effect.select_effect_obj.selected_targets[i]
                            const card_div = Cards.getDiv(x)!
                            card_div.setAttribute('select-count', `${Number(i)+1}`)
                            if( card_div.parentElement?.classList.contains('deck') ) {
                                const parent_div_id = card_div.parentElement.id;
                                if (deck_select_index[parent_div_id] === undefined) {
                                    deck_select_index[parent_div_id] = 0;
                                }
                                card_div.style.setProperty('--select-index', String(deck_select_index[parent_div_id]))
                                deck_select_index[parent_div_id] += 1
                            }
                        }
                    }
                    SelectStep.setTargets(true)
                    Music.playClickCardSound()
                    cancel_target = true
                }
            }

            Effect.updateHighLight()
            if( !cancel_target ) {
                SelectStep.setCost(true)
            } else
            if( Effect.select_effect_obj.all_legal_targets.length == 1 && Effect.select_effect_obj.all_legal_targets.includes(Effect.select_effect_obj.bind_id) && !Effect.isExEffect() ) {
                SelectStep.setBegin()
                Effect.updateHighLight()
                Effect.clicked_card_div = undefined
            }
        }
    }

    static isCardHasEffect(object_id: number) {
        return Effect.available_card_bind_object_ids.includes(object_id)
    }

    static isCardHasForcedActionEffect(object_id: number) {
        if( !Effect.available_card_bind_object_ids.includes(object_id) ) {
            return false
        }
        for(const option of Effect.response_json_ask.options ) {
            if( option.bind_id == object_id ) {
                if( option.name == "Forced_Action") {
                    return true
                }
            }
        }
        return false
    }

    static getSelectAbleObject(object_id: number) {
        let json_objs: EffectDescriptor[] = []
        for( let select_json of Effect.response_json_ask.options ) {
            let found_object_id = select_json.bind_id
            if( object_id == found_object_id ) {
                json_objs.push(select_json)
            }
        }
        return json_objs
    }

    static isExEffect() {
        return Effect.clicking_card_div && Effect.is_ex_effect
    }
    static activeEffect(card_div: HTMLElement, forced=false) {
        if( Effect.clicked_card_div == card_div && !forced ) {
            Effect.clicked_card_div = undefined
        } else {
            Effect.clicked_card_div = card_div
        }

        if( Effect.clicked_card_div ) {
            const object_id = Number(card_div.dataset.id!)
            let json_objs = Effect.getSelectAbleObject(object_id)
            Effect.updateButtons(json_objs)
        } else {
            Effect.updateButtons([])
        }
    }

    private static isResponse(name: string) {
        return Effect.response_json_ask.ability_type == "Response"
        return ["Response", "Hero Response", "Alter-Ego Response",
            '"Do You Even Lift?"', "Morphogenetics", '"Have at thee!"', "Widowmaker",
            "Puny Pest", "Giant Nuisance", "Small but Mighty", "Super Speed",
            '"Murdered You!"', "Finesse", "Precision", "Locked and Loaded",
            "Dizzying Reflexes", "Spider-Nonsense", "Steel Skin", "Healing Factor",
            "Angel of Life", "Angel of Death", "Living Weapon", "Energy Absorption", 
            "Mission Prep", "Time to Unwind", "Cybernetic Upgrades", "Cartoon Power",
            "Temporally Displaced", "Cool Off", "Survivor",
        ].includes(name)
    }

    private static isInterrupt(name: string) {
        return Effect.response_json_ask.ability_type == "Interrupt"
        // "Psionic Bond",
        return ["Interrupt", "Hero Interrupt", "Alter-Ego Interrupt", "First Player Interrupt",
            "Spider-Sense", "Superhuman Agility", "Chaos Control",  "Throw de Card",
            "Psi-Energy Control", '"Freeze!"', '"I Object!"', 
        ].includes(name)
    }

    private static updateButtons(options: EffectDescriptor[]){
        Effect.options_button_div.replaceChildren()

        if( options.length == 0 ) {
            return
        }

        console.log(options)

        function UpdateCards(option: EffectDescriptor, can_auto_activate = false) {
            Effect.select_effect_obj = new EffectDescriptor(option)

            console.log('current effect:', Effect.select_effect_obj)
            let can_select_all_as_target = false
            let targets = Effect.select_effect_obj.all_legal_targets
            console.log('targets:', targets)
            if( targets.length < Effect.select_effect_obj.target_num_range[0] ) {
                // no target
            }
            else
            {
                UI.prompt.setTempPromptText(`<span class='effect-text'>${Effect.select_effect_obj.name_with_space}</span>`)
                if( targets.length > 0 && Effect.select_effect_obj.target_num_range[1] > 0 ) {
                    if( Effect.select_effect_obj.automatic_targets.length > 0 ) {
                        SelectStep.setTargets(true)
                        if( Effect.select_effect_obj.automatic_submit &&
                            !ButtonSetting.is_replay ) {
                            Button.doPost(true)
                        }
                        Effect.updateHighLight()
                        return
                    }
                    if( targets.length >= Effect.select_effect_obj.target_num_range[0] &&
                        // Effect.select_effect_obj.target_num_range[0] > 0 && // Fix for "03006", also fix 'End Phase' 'Resolve Mulligans'
                        targets.length <= Effect.select_effect_obj.target_num_range[1] ) {
                        can_select_all_as_target = true
                    }

                    // We don't auto select last card on hand in turn end phase
                    // We still need this for hand size > max hand size
                    if( Effect.isEndPhaseOrResolveMulligans()
                    ) {
                        can_select_all_as_target = false
                    }

                    if( Effect.getFullSearchDisplayTargets().length == 0 &&
                        (can_select_all_as_target || ButtonSetting.auto_target_forced) &&
                        !ButtonSetting.is_replay &&
                        ButtonSetting.auto_target )
                    {
                        Effect.select_effect_obj.selected_targets = []
                        SelectStep.setTargets(true)
                        // const object_id = CardEffect.select_effect_obj.bind_id
                        // const effect_card_div = CardManager.getDiv(object_id)
                        for( let object_id of targets ) {
                            if( !can_select_all_as_target ) {
                                if( Effect.select_effect_obj.selected_targets.length >= Effect.select_effect_obj.target_num_range[0] ) {
                                    break
                                }
                            }

                            let card_div = Cards.getDiv(object_id)!
                            if( (card_div.parentElement!.id == "player-all-hand-cards" && !ButtonSetting.auto_target_forced) ||
                                Effect.select_effect_obj.select_rule.startsWith('Combined')
                            ) {
                                // no auto click hand cards,
                                // fix "02047", "03006"
                            } else {
                                // UI.drawLine(effect_card_div, card_div)
                                Effect.onCardClick(card_div, false, true)
                                HoverCard.whenCardActive(card_div)
                            }
                        }
                    }
                    else {
                        targets = []
                        Effect.select_effect_obj.selected_targets = []
                        SelectStep.setTargets(true)
                    }

                    if( can_select_all_as_target &&
                        can_auto_activate &&
                        ButtonSetting.auto_target &&
                        !ButtonSetting.is_replay
                    ) {
                        if( AutoActivate.isAutoActivate2(Cards.getDiv(option.bind_id)!) ) {
                            Button.doPost(false)
                        }
                    }
                } else {
                    SelectStep.setTargets(false)
                    if( AutoEffect.isAutoEffectTargeting() ) {
                        SelectStep.setCost(true)
                        if( AutoActivate.isAutoActivate2(Cards.getDiv(option.bind_id)!) ) {
                            Button.doPost(false)
                        }
                    }
                    else if( Effect.select_effect_obj.getCost() ) {
                        Button.doPost(false)
                    }
                }
            }
            Effect.updateHighLight()
        }

        SelectStep.setEffect()

        // These need target, so we don't auto select
        // "Thwart", "Attack"
        if( (
                options.length == 1 || ( options.length == 2 && options[1].name == 'Cancel' )
            ) &&
            options[0].name_with_space != "Ask" &&
            ( ["", "Play", "Play 1", "Play 2", "Defense", "Recover", "Change Form",
                "Interrupt", "Hero Interrupt", "Alter-Ego Interrupt", "First Player Interrupt",
                "Response", "Hero Response", "Alter-Ego Response", "Forced Response",
                "Action", "Action 1", "Forced Action", "Hero Action", "Hero Action 1", "Alter-Ego Action", "First Player Action", 
                "Special", "When Defeated",
                "Game Rule", "Debug Rule", "Resolve Mulligans", "End Phase", "Ally Limit",
                "ChooseAbility",
            ].includes(options[0].name_with_space)
            || options[0].target_num_range[1] >= 1
            || options[0].name_with_space.startsWith("Spend ")
        )) {
            let can_auto_activate = false
            if( Effect.isResponse(options[0].name_with_space) ||
                Effect.isInterrupt(options[0].name_with_space)
            ){
                can_auto_activate = AutoEffect.isAutoEffectTargeting() && AutoActivate.isHasAutoActivate()
            }
            UpdateCards(options[0], can_auto_activate)

            if( options.length > 1) {
                BtnOk.enableCancelButton()
            }
        }
        else
        {
            for( const json_obj of options ) {
                if( json_obj.name_with_space == 'Cancel' && options[options.length-1] == json_obj ) {
                    continue
                }
                let button = document.createElement('button')
                button.classList.add('button')
                button.innerHTML = Lib.game.cleanResText(json_obj.name_with_space)
                button.dataset.json_str = JSON.stringify(json_obj)
                if( json_obj.failure_reason != '' ) {
                    button.classList.add('disable')
                    button.dataset.failure_reason = json_obj.failure_reason
                    if( Setting.is_debug ) {
                        button.classList.add('more-info')
                    }
                } else {
                    button.addEventListener('click', function(e){
                        const btn = e.target as HTMLElement
                        btn.classList.toggle('clicked')
                        if( btn.classList.contains('clicked') ) {
                            for( let child of Effect.options_button_div.childNodes ) {
                                if( child instanceof HTMLButtonElement && child != btn ) {
                                    child.classList.remove('clicked')
                                }
                            }
                            UpdateCards(JSON.parse(btn.dataset.json_str!))
                            console.log(button.innerHTML)
                        } else {
                            SelectStep.setEffect()
                            Effect.select_effect_obj.clear()
                            UI.selectCountClear()
                            Effect.updateHighLight()
                        }
                        e.stopPropagation()
                        e.preventDefault()
                    })
                }
                Effect.options_button_div.appendChild(button)
            }
        }
    }

    static setOptions() {
        Effect.options_button_div.replaceChildren()

        Effect.is_in_event = ''
        if( Effect.response_json_ask.ability_type == "Response" ) {
            Effect.is_in_event = 'response'
        }
        else
        if( Effect.response_json_ask.ability_type == "Interrupt" ) {
            Effect.is_in_event = 'interrupt'
        }
        else
        if( Effect.response_json_ask.ability_type == "Normal" ) {
            if( Effect.response_json_ask.event_name == "WhenPlayerChooseAbility" ) {
                Effect.is_in_event = 'asking'
            } else {
                Effect.is_in_event = 'in_turn'
            }
        }

        Effect.available_card_bind_object_ids = []

        let has_options = false
        for( const option of Effect.response_json_ask.options ) {
            const object_id = option.bind_id
            if( !Effect.available_card_bind_object_ids.includes(object_id) && option.failure_reason == '') {
                Effect.available_card_bind_object_ids.push(object_id)
            }
            has_options = true
        }

        SelectStep.setBegin()
        Effect.updateHighLight()
    }

    static update() {
        if( !Effect.response_json_ask || Effect.response_json_ask.options.length < 1 ) {
            return
        }

        let auto_effect = false
        if( UI.is_in_play_turn ) {
            auto_effect = false
        }
        else
        if( Effect.response_json_ask?.options.length >= 1 &&
            ( AutoEffect.isAutoEffectTargeting() || AutoActivate.isHasAutoActivate() || UI.event_name == "WhenPlayerLikeInTurn" )) {
            auto_effect = true
        }

        if( Effect.available_card_bind_object_ids.length >= 1 ) {
            const object_id = Effect.available_card_bind_object_ids[0]
            const card_div = Cards.getDiv(object_id)!
            if( Effect.available_card_bind_object_ids.length == 1 ) {
                Effect.clicking_card_div = card_div
            } else {
                for( const t_object_id of Effect.available_card_bind_object_ids ) {
                    if( AutoActivate.isAutoActivate(t_object_id) ) {
                        const card_div = Cards.getDiv(t_object_id)!
                        Effect.clicking_card_div = card_div
                        break
                    }
                }
            }
        }

        if( Effect.clicking_card_div && (Effect.isExEffect() || auto_effect) ) {
            Effect.activeEffect(Effect.clicking_card_div, true)
        }
        Effect.updateHighLight()
    }

    static isEndPhaseOrResolveMulligans() {
        return Effect.select_effect_obj.name_with_space == 'End Phase' ||
                Effect.select_effect_obj.name_with_space == 'Resolve Mulligans'
    }

    static isMandatoryHandSizeDiscard() {
        return Effect.isEndPhaseOrResolveMulligans() &&
                Effect.select_effect_obj.target_num_range[0] > 0
    }
}

(window as any).Effect = Effect;
