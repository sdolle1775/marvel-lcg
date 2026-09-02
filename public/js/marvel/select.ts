import { Lib } from './lib.js'
import { Effect } from './effect.js'
import { Cards } from './cards.js'
import { UI } from './ui.js'
import { BtnOk } from './btn_ok.js'

export type SelectStepValue = 'cost' | 'target' | 'effect' | 'card'

////////////////////////////////////////////////////////////////////////////////
//
export class SelectStep {
    private static step: SelectStepValue = 'card'
    static getStep(): SelectStepValue {
        return SelectStep.step
    }
    static restoreStep(step: SelectStepValue): void {
        SelectStep.step = step
    }
    static isCost() {
        return SelectStep.step == 'cost'
    }
    static isTargets() {
        return SelectStep.step == 'target'
    }
    static isEffect() {
        return SelectStep.step == 'effect'
    }
    static isCard() {
        return SelectStep.step == 'card'
    }
    static reset() {
        SelectStep.step = 'card'
    }

    ////////////////////////////////////////////////////////////////////////////////
    //
    static setCard() {
        SelectStep.step = 'card'
        BtnOk.setDisable(false)
        BtnOk.setCancel('End')
        // console.log('current_select_step:', SelectStep.current_select_step)
    }
    static setEffect() {
        UI.prompt.resetPromptText()
        SelectStep.step = 'effect'
        BtnOk.setDisable(false)
        BtnOk.setCancel('Cancel')
        // console.log('current_select_step:', SelectStep.current_select_step)
    }
    static setTargets(need_target = true) {
        SelectStep.step = 'target'
        BtnOk.setDisable(false)
        BtnOk.setCancel('Cancel')
        if( Effect.isMandatoryHandSizeDiscard() ) {
            BtnOk.btn_end_div.disabled = true
        }

        Effect.updateHighLight()

        if( need_target ) {
            console.log(Effect.select_effect_obj.selected_targets)
            if( Effect.select_effect_obj.selected_targets.length >= Effect.select_effect_obj.target_num_range[0] &&
                Effect.select_effect_obj.selected_targets.length <= Effect.select_effect_obj.target_num_range[1] ) {
                BtnOk.setOk('Targets')
            } else {
            }

            let names = []
            for( const object_id of Effect.select_effect_obj.selected_targets ) {
                const span = Cards.getSpanText(object_id)
                names.push(span)
            }

            const object_id = Effect.select_effect_obj.bind_id
            let name = Cards.getSpanText(object_id)
            let effect_name = `${Effect.select_effect_obj.name_with_space}`
            // Select target [
            UI.prompt.setTempPromptText(`${name} <span class='effect-text'>${effect_name}</span> (${Effect.select_effect_obj.target_num_range[0]}~${Effect.select_effect_obj.target_num_range[1]})<br/>${names.join(", ")}`)
        } else {
            BtnOk.setOk('Targets')
            // UI.resetPromptText()
        }
        // console.log('current_select_step:', SelectStep.current_select_step)
    }
    static setCost(need_cost = true) {
        let ok = false
        let over_pay = false
        SelectStep.step = 'cost'
        if( !need_cost || Effect.select_effect_obj.getCost() == "" || Effect.select_effect_obj.isCostRuleUpTo() ) {
            // UI.resetPromptText()
            // UI.setBtnCancelText('Cancel', false)
            // UI.setBtnOkText('Cost', true)
            ok = true
        } else {
            // if( CardEffect.select_effect_obj.cost != "" && CardEffect.select_effect_obj.cost != "0" ) {
            let paid_list = []
            let cost_options = Effect.select_effect_obj.getCost().split('|')
            for( let i of Effect.select_effect_obj.resources ) {
                let index = Effect.select_effect_obj.getResources().indexOf(i)
                let c = Effect.select_effect_obj.getResText()[index]
                if( Lib.string.isNumeric(c) ) {
                    paid_list.push(c)
                } else {
                    paid_list.push(...c.split(''))
                }
            }
            function to_array(s: string) {
                let r = ""
                for( let x of s ) {
                    if( Lib.string.isStringANumber(x) ) {
                        r += "A".repeat(Number(x))
                    }
                    else {
                        r += x
                    }
                }
                return r
            }

            let has_cost = to_array(paid_list.toString().replaceAll(",", ""))

            function get_appear_count(str: string, char: string) {
                let m = str.match(new RegExp(char, "g"))
                if( m ) {
                    return m.length
                }
                return 0
            }

            function checkCost(cost: string) {
                let need_cost = to_array(cost)
                let same_type = true
                let different_type = 0
                let last_type = ""
                let has_g = get_appear_count(has_cost, "G")
                let has_a = get_appear_count(has_cost, "A")
                let need_g = get_appear_count(need_cost, 'G')
                for(let c of ['R', 'B', 'Y']) {
                    let has_type = get_appear_count(has_cost, c)
                    let diff = has_type - get_appear_count(need_cost, c)
                    if( has_type ) {
                        different_type += 1
                        if( same_type ) {
                            if( last_type ) {
                                same_type = false
                            } else {
                                last_type = c
                            }
                        }
                    }
                    if( diff >= 0 ) {
                        has_a += diff
                    } else {
                        need_g += -diff
                    }
                }
                if( has_g ) {
                    different_type += has_g
                    different_type = Math.min(3, different_type)
                }
                has_g -= need_g
                let need_a = get_appear_count(need_cost, 'A')
                if( need_a ) {
                    has_a -= need_a
                    if( has_a < 0 ) {
                        has_g += has_a
                        has_a = 0
                    }
                }
                let cost_ok = has_g >= 0 && has_a >= 0
                if( Effect.select_effect_obj.isCostRuleSameType() && !same_type ) {
                    cost_ok = false
                }
                if( Effect.select_effect_obj.isCostRuleDifferentType() ) {
                    cost_ok = different_type >= need_a
                }
                return {
                    ok: cost_ok,
                    overPay: has_a > 0 || has_g > 0
                }
            }

            let matches = cost_options.map(checkCost)
            let matched = matches.find(match => match.ok && !match.overPay)
                ?? matches.find(match => match.ok)
            ok = matched !== undefined
            over_pay = matched?.overPay ?? false

            let paid_list_copy = paid_list.slice()
            const object_id = Effect.select_effect_obj.bind_id
            // let name = Cards.getCard(object_id)!.name
            function cover_res(re_text: string[])
            {
                let text = ""
                for( let c of re_text ) {
                    if( Lib.string.isStringANumber(c) ) {
                        text += c
                    }
                    else
                    {
                        let x = c
                        x = x.replaceAll("R", `<span class='icon-physical'></span>`)
                        x = x.replaceAll("B", `<span class='icon-mental'></span>`)
                        x = x.replaceAll("Y", `<span class='icon-energy'></span>`)
                        x = x.replaceAll("G", `<span class='icon-wild'></span>`)
                        text += x
                    }
                }
                return text
            }

            let cost_text = cost_options.map(cost => cover_res(cost.split(''))).join(" or ")
            let paid_text = cover_res(paid_list_copy)
            UI.prompt.setTempPromptText(`<span class='cost-text'>Cost</span> [${Cards.getSpanText(object_id)}]<br/>(${paid_text}) / (${cost_text})`)
            // console.log(text)
        }
        if( ok ) {
            BtnOk.setDisable(false)
            if( over_pay ) {
                BtnOk.setOk('OverPay')
            } else {
                BtnOk.setOk('Cost')
            }
        } else {
            BtnOk.setCancel('Cost')
        }
        // console.log('current_select_step:', SelectStep.current_select_step)
    }
    static cancel() {
        SelectStep.step = 'cost'
    }
    static setBegin() {
        if( Effect.response_json_ask.options.length > 0) {
            SelectStep.setCard()
        }
    }
}
