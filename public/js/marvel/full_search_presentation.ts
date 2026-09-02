import { Cards } from './cards.js'
import { EffectDescriptor } from './data.js'
import { Effect } from './effect.js'
import { SelectStep, SelectStepValue } from './select.js'
import { UI } from './ui.js'

interface FullSearchPresentationPayload {
    presentation_id: number;
    card_ids: number[];
    legal_target_ids: number[];
    target_min?: number;
    target_max?: number;
    prompt_text: string;
}

interface PromptState {
    boxClassName: string;
    boxStyle: string;
    text: string;
}

interface ButtonState {
    className: string;
    text: string;
    disabled: boolean;
}

interface CardState {
    className: string;
    style: string;
    selectCount: string|null;
}

/**
 * Routes replay-neutral automatic-search inspection through the standard
 * client selector. Only its final OK is translated into a presentation ACK;
 * card selection itself uses Effect.onCardClick exactly like a gameplay choice.
 */
export class FullSearchPresentation {
    private static current: FullSearchPresentationPayload|undefined
    private static playerId = -1
    private static cardStates = new Map<HTMLElement, CardState>()
    private static deckClasses = new Map<HTMLElement, string>()
    private static promptState: PromptState|undefined
    private static okState: ButtonState|undefined
    private static endState: ButtonState|undefined
    private static previousEffect: EffectDescriptor|undefined
    private static previousSelectStep: SelectStepValue|undefined

    static init(): void {
        document.addEventListener('click', event => this.onClick(event), true)
    }

    static isActive(): boolean {
        return this.current != undefined
    }

    private static onClick(event: Event): void {
        if( !this.current ) {
            return
        }
        const target = event.target
        if( !(target instanceof Element) ) {
            return
        }

        // The normal button handler supplies the ACK, Settings may disable the
        // viewer, and cards inside the search deck must reach Effect.onCardClick.
        if( target.closest('#btn-ok') ||
            target.closest('#right-side-bar') ||
            target.closest('.full-search-inspection-deck')
        ) {
            return
        }

        // Clicking away uses the normal minimized-deck behavior but must not
        // activate an unrelated card while the server is awaiting inspection.
        event.preventDefault()
        event.stopImmediatePropagation()
        this.minimizeDecks()
    }

    private static openDeck(selectedDeck: HTMLElement): void {
        for( const deck of this.deckClasses.keys() ) {
            if( deck.classList.contains('full-search-inspection-deck') ) {
                deck.classList.toggle('clicked', deck == selectedDeck)
            }
        }
    }

    private static minimizeDecks(): void {
        for( const deck of this.deckClasses.keys() ) {
            if( deck.classList.contains('full-search-inspection-deck') ) {
                deck.classList.remove('clicked')
            }
        }
    }

    private static snapshotUI(): void {
        const promptBox = document.getElementById('prompt-box-container') as HTMLElement
        const promptText = document.getElementById('prompt-text') as HTMLElement
        this.promptState = {
            boxClassName: promptBox.className,
            boxStyle: promptBox.style.cssText,
            text: promptText.innerHTML,
        }
        this.okState = {
            className: UI.btn_ok_div.className,
            text: UI.btn_ok_div.innerHTML,
            disabled: UI.btn_ok_div.disabled,
        }
        this.endState = {
            className: UI.btn_end_div.className,
            text: UI.btn_end_div.innerHTML,
            disabled: UI.btn_end_div.disabled,
        }

        this.cardStates.clear()
        for( const card of document.querySelectorAll<HTMLElement>('.card') ) {
            this.cardStates.set(card, {
                className: card.className,
                style: card.style.cssText,
                selectCount: card.getAttribute('select-count'),
            })
        }
        this.deckClasses.clear()
        for( const deck of document.querySelectorAll<HTMLElement>('.deck') ) {
            this.deckClasses.set(deck, deck.className)
        }

        this.previousEffect = Effect.select_effect_obj
        this.previousSelectStep = SelectStep.getStep()
    }

    private static show(payload: FullSearchPresentationPayload): void {
        this.snapshotUI()

        // The fallback keeps a refreshed client usable until an already-running
        // pre-change server is restarted. Current servers always send the range.
        const defaultTarget = payload.legal_target_ids.length > 0 ? 1 : 0
        const targetMax = Math.min(
            payload.target_max ?? defaultTarget,
            payload.legal_target_ids.length,
        )
        const targetMin = Math.min(
            payload.target_min ?? defaultTarget,
            targetMax,
        )
        Effect.select_effect_obj = new EffectDescriptor({
            id: -1,
            name: payload.prompt_text,
            bind_id: -1,
            bind_player_id: this.playerId,
            all_legal_targets: payload.legal_target_ids,
            target_num_range: [targetMin, targetMax],
            select_rule: '',
            select_rule_param: [],
            target_must_include_traits: [],
            is_search: true,
            full_search_display_targets: payload.card_ids,
            automatic_submit: false,
        })

        // This is the same entry point used for ordinary target selection. It
        // supplies highlighting, selection numbers, sound, and OK validation.
        SelectStep.setTargets(true)
        UI.prompt.setTempPromptText(payload.prompt_text, false)

        const legalTargets = new Set(payload.legal_target_ids)
        const decks: HTMLElement[] = []
        let primaryDeck: HTMLElement|undefined
        for( const objectId of payload.card_ids ) {
            const deck = Cards.getDiv(objectId)?.parentElement
            if( !deck || !deck.classList.contains('deck') ) {
                continue
            }
            if( !decks.includes(deck) ) {
                decks.push(deck)
                deck.classList.add('full-search-inspection-deck')
            }
            if( !primaryDeck && legalTargets.has(objectId) ) {
                primaryDeck = deck
            }
        }

        primaryDeck ??= decks[0]
        if( primaryDeck ) {
            this.openDeck(primaryDeck)
        }

        // An automatic result cannot be cancelled. OK is still managed by the
        // normal selector and becomes available only when its range is valid.
        UI.btn_end_div.disabled = true
        document.body.classList.add('full-search-presentation-active')
    }

    static async fetch(playerId: number): Promise<void> {
        const response = await fetch(`get_full_search_presentation?p=${playerId}`)
        if( !response.ok ) {
            return
        }
        const payload = await response.json() as FullSearchPresentationPayload
        if( !payload.presentation_id || this.current?.presentation_id == payload.presentation_id ) {
            return
        }

        this.restoreUI()
        this.playerId = playerId
        this.current = payload
        this.show(payload)
    }

    /** Returns true when the standard OK button was consumed by inspection. */
    static dismissIfActive(): boolean {
        if( !this.current || UI.btn_ok_div.disabled ) {
            return false
        }
        void this.dismiss()
        return true
    }

    static async dismiss(): Promise<void> {
        const presentation = this.current
        const playerId = this.playerId
        this.current = undefined
        this.playerId = -1
        this.restoreUI()
        if( presentation ) {
            await fetch(
                `full_search_presentation_ack?p=${playerId}&id=${presentation.presentation_id}`,
                {method: 'POST'},
            )
        }
    }

    private static restoreButton(
        button: HTMLButtonElement,
        state: ButtonState|undefined,
    ): void {
        if( !state ) {
            return
        }
        button.className = state.className
        button.innerHTML = state.text
        button.disabled = state.disabled
    }

    private static restoreUI(): void {
        if( this.previousEffect ) {
            Effect.select_effect_obj = this.previousEffect
        }
        this.previousEffect = undefined
        if( this.previousSelectStep ) {
            SelectStep.restoreStep(this.previousSelectStep)
        }
        this.previousSelectStep = undefined

        for( const [card, state] of this.cardStates ) {
            card.className = state.className
            card.style.cssText = state.style
            if( state.selectCount == null ) {
                card.removeAttribute('select-count')
            } else {
                card.setAttribute('select-count', state.selectCount)
            }
        }
        this.cardStates.clear()

        for( const [deck, className] of this.deckClasses ) {
            deck.className = className
        }
        this.deckClasses.clear()

        const promptBox = document.getElementById('prompt-box-container') as HTMLElement
        const promptText = document.getElementById('prompt-text') as HTMLElement
        if( this.promptState ) {
            promptBox.className = this.promptState.boxClassName
            promptBox.style.cssText = this.promptState.boxStyle
            promptText.innerHTML = this.promptState.text
        }
        this.promptState = undefined

        this.restoreButton(UI.btn_ok_div, this.okState)
        this.okState = undefined
        this.restoreButton(UI.btn_end_div, this.endState)
        this.endState = undefined
        document.body.classList.remove('full-search-presentation-active')
    }

    static closeIfInactive(activePlayerIds: number[]): void {
        if( this.current && !activePlayerIds.includes(this.playerId) ) {
            this.current = undefined
            this.playerId = -1
            this.restoreUI()
        }
    }

    static onPreferenceChanged(playerId: number, enabled: boolean): void {
        if( !enabled && this.current && this.playerId == playerId ) {
            void this.dismiss()
        }
    }
}
