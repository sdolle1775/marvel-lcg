import { CardStatistics } from '../module/card_statistics.js';
import { Card } from '../module/card_info.js';
import { HeroDeck, MarvelCDB } from '../module/marvelcdb.js';

declare global {
    interface Window {
        SetHero?: (hero: unknown, slot: number) => void;
        Reset?: (element: HTMLElement) => void;
    }
}

const PICKER_CONTAINERS = '#set-images,#set-content,#modular-sets,#encounter-sets,#hero-modal';
const HERO_SLOTS = [1, 2, 3, 4];

interface SlotCaption {
    root: HTMLElement;
    identity: HTMLElement;
    deck: HTMLElement;
    aspect: HTMLElement;
    count: HTMLElement;
}

class NewGameScreen {

    private static card_dict: { [key: string]: Card } = {};
    private static cards_loading: Promise<void> | null = null;

    private static starters: HeroDeck[] = [];
    private static starters_loaded: boolean = false;
    private static open_slot: number = 1;
    private static captions: { [slot: number]: SlotCaption } = {};

    static init(): void {
        NewGameScreen.watchForNewImages();
        NewGameScreen.prepareHeroSlots();
    }


    private static loadCards(): Promise<void> {
        if (!NewGameScreen.cards_loading) {
            NewGameScreen.cards_loading = (async () => {
                const statistics = new CardStatistics();
                await statistics.loadAllCards(false, true);
                NewGameScreen.card_dict = statistics.const_card_dict;
            })();
        }
        return NewGameScreen.cards_loading;
    }

    static toFileName(path: string): string {
        return String(path).replace(/^.*[\\/]/, '').replace(/\.[^/.]+$/, '');
    }

    static toCardId(entry: string): string {
        return String(entry).split(',')[0];
    }


    static toIdentityName(name: string): string {
        return String(name).replace(/^\*\s*/, '');
    }

    static toTitle(name: string): string {
        return String(name)
            .replace(/_/g, ' ')
            .replace(/\bexpert\b/i, '(Expert)')
            .replace(/\bWIP\b/i, '(WIP)')
            .replace(/\b\w/g, character => character.toUpperCase())
            .replace(/\b[IVX]+\b/gi, numeral => numeral.toUpperCase())
            .trim();
    }

    private static addCaption(element: Element | null, text: string): void {
        if (!element || !text || element.querySelector(':scope > .scene-cap')) {
            return;
        }
        const caption = document.createElement('span');
        caption.className = 'scene-cap';
        caption.textContent = text;
        element.appendChild(caption);
    }

    private static decorate(): void {
        document.querySelectorAll<HTMLElement>('#set-images > div.set').forEach(set => {
            NewGameScreen.addCaption(set, set.dataset.package || set.dataset.title || '');
        });

        document.querySelectorAll<HTMLButtonElement>('#set-content .details button[value]').forEach(button => {
            if (button.disabled) {
                return;
            }
            NewGameScreen.addCaption(button, NewGameScreen.toTitle(button.value));
        });

        const set_buttons = '#encounter-sets button[data-name], #modular-sets button[data-name]';
        document.querySelectorAll<HTMLButtonElement>(set_buttons).forEach(button => {
            NewGameScreen.addCaption(button, NewGameScreen.toTitle(button.dataset.name || ''));
        });

        const controls = document.querySelectorAll<HTMLElement>('button, input[type="button"]');
        controls.forEach(control => {
            if (control.closest(PICKER_CONTAINERS)) {
                return;
            }
            if (control.classList.contains('hm-tab') || control.classList.contains('hm-close')) {
                return;
            }
            if (control.classList.contains('ui-btn')) {
                return;
            }
            control.classList.add('ui-btn');

            const input = control as HTMLInputElement;
            const label = (control.textContent || input.value || '').toLowerCase();
            if (label.includes('create scene')) {
                control.classList.add('ui-btn-primary');
            }
        });
    }

    private static watchForNewImages(): void {
        const observer = new MutationObserver(() => NewGameScreen.decorate());
        observer.observe(document.body, { childList: true, subtree: true });
        NewGameScreen.decorate();
    }

    private static buildPicker(): HTMLElement {
        const overlay = document.createElement('div');
        overlay.id = 'hero-modal-overlay';
        overlay.innerHTML = `
      <div id="hero-modal" role="dialog" aria-modal="true">
        <header>
          <h2>Choose a Hero</h2>
          <button class="hm-close" title="Close">&times;</button>
        </header>
        <div class="hm-tabs">
          <button class="hm-tab active" data-pane="starters">Starters</button>
          <button class="hm-tab" data-pane="upload">Deck File</button>
          <button class="hm-tab" data-pane="cdb">MarvelCDB</button>
        </div>
        <div class="hm-body">
          <div class="hm-pane active" data-pane="starters">
            <div id="hm-starter-grid">Loading starter decks...</div>
          </div>
          <div class="hm-pane" data-pane="upload">
            <p class="hm-hint">Choose a hero deck saved by this game or exported from the deck editor.</p>
            <div class="hm-drop">
              <input type="file" id="hm-file" accept=".json">
            </div>
          </div>
          <div class="hm-pane" data-pane="cdb">
            <p class="hm-hint">Enter the deck number from the marvelcdb.com address. Published decks and shared personal decks are both accepted.</p>
            <div class="hm-row">
              <input type="text" id="hm-cdb-id" placeholder="2345" inputmode="numeric">
              <button class="ui-btn ui-btn-primary" id="hm-cdb-go">Load</button>
            </div>
            <div class="hm-status" id="hm-cdb-status"></div>
          </div>
        </div>
      </div>`;
        document.body.appendChild(overlay);

        overlay.addEventListener('click', event => {
            if (event.target === overlay) {
                NewGameScreen.closePicker();
            }
        });

        const close = overlay.querySelector<HTMLButtonElement>('.hm-close');
        if (close) {
            close.onclick = () => NewGameScreen.closePicker();
        }

        overlay.querySelectorAll<HTMLButtonElement>('.hm-tab').forEach(tab => {
            tab.onclick = () => {
                overlay.querySelectorAll<HTMLElement>('.hm-tab').forEach(other => {
                    other.classList.toggle('active', other === tab);
                });
                overlay.querySelectorAll<HTMLElement>('.hm-pane').forEach(pane => {
                    pane.classList.toggle('active', pane.dataset.pane === tab.dataset.pane);
                });
            };
        });

        const file = overlay.querySelector<HTMLInputElement>('#hm-file');
        if (file) {
            file.onchange = async () => {
                const chosen = file.files ? file.files[0] : null;
                if (!chosen) {
                    return;
                }
                try {
                    const hero = JSON.parse(await chosen.text()) as HeroDeck;
                    NewGameScreen.chooseHero(hero, hero.name || 'Deck file');
                } catch (error) {
                    NewGameScreen.setStatus('That file does not hold a hero deck.', 'err');
                }
            };
        }

        const identifier = overlay.querySelector<HTMLInputElement>('#hm-cdb-id');
        const load = overlay.querySelector<HTMLButtonElement>('#hm-cdb-go');
        if (identifier && load) {
            load.onclick = () => NewGameScreen.importFromMarvelCDB(identifier.value);
            identifier.addEventListener('keydown', event => {
                if (event.key === 'Enter') {
                    NewGameScreen.importFromMarvelCDB(identifier.value);
                }
            });
        }

        return overlay;
    }

    private static openPicker(slot: number): void {
        NewGameScreen.open_slot = slot;
        const overlay = document.getElementById('hero-modal-overlay') ?? NewGameScreen.buildPicker();
        NewGameScreen.setStatus('', '');
        overlay.classList.add('open');
        NewGameScreen.loadStarters();
    }

    private static closePicker(): void {
        const overlay = document.getElementById('hero-modal-overlay');
        if (overlay) {
            overlay.classList.remove('open');
        }
    }

    private static setStatus(text: string, state: string): void {
        const status = document.getElementById('hm-cdb-status');
        if (!status) {
            return;
        }
        status.className = 'hm-status' + (state ? ' ' + state : '');
        status.textContent = text;
    }

    private static chooseHero(hero: HeroDeck, deck_label: string): void {
        if (typeof window.SetHero !== 'function') {
            NewGameScreen.setStatus('The screen is still loading, please try again.', 'err');
            return;
        }
        const slot = NewGameScreen.open_slot;
        window.SetHero(hero, slot);
        NewGameScreen.fillCaption(slot, hero, deck_label);
        NewGameScreen.closePicker();
    }

    private static async loadStarters(): Promise<void> {
        if (NewGameScreen.starters_loaded) {
            return;
        }
        NewGameScreen.starters_loaded = true;

        const grid = document.getElementById('hm-starter-grid');
        try {
            const response = await fetch('list_starter_deck?', { cache: 'no-store' });
            const files: string[] = await response.json();
            const names = files.map(file => NewGameScreen.toFileName(file));

            const decks = await Promise.all(names.map(name => MarvelCDB.fetchStarterDeck(name)));
            NewGameScreen.starters = decks.filter((deck): deck is HeroDeck => {
                return deck !== null && Array.isArray(deck.hero) && deck.hero.length > 0;
            });
            NewGameScreen.starters.sort((left, right) => {
                return (left.name || '').localeCompare(right.name || '');
            });

            NewGameScreen.showStarters();
        } catch (error) {
            if (grid) {
                grid.textContent = 'The starter decks could not be loaded.';
            }
            NewGameScreen.starters_loaded = false;
        }
    }

    private static showStarters(): void {
        const grid = document.getElementById('hm-starter-grid');
        if (!grid) {
            return;
        }
        grid.replaceChildren();

        for (const starter of NewGameScreen.starters) {
            const button = document.createElement('button');
            button.className = 'hm-hero';
            button.type = 'button';

            const image = document.createElement('img');
            image.src = NewGameScreen.toCardId(starter.hero[0]);
            image.loading = 'lazy';

            const caption = document.createElement('span');
            caption.className = 'scene-cap';
            caption.textContent = starter.name || '';

            button.append(image, caption);
            button.onclick = () => NewGameScreen.chooseHero(structuredClone(starter), 'Starter');
            grid.appendChild(button);
        }
    }

    private static async importFromMarvelCDB(deck_id: string): Promise<void> {
        const identifier = String(deck_id || '').trim();
        if (!identifier) {
            NewGameScreen.setStatus('Enter a deck number first.', 'err');
            return;
        }

        NewGameScreen.setStatus('Loading...', '');
        const deck = await MarvelCDB.fetchDeck(identifier);
        if (!deck) {
            NewGameScreen.setStatus('No deck was found with that number.', 'err');
            return;
        }

        await NewGameScreen.loadCards();
        const hero = await MarvelCDB.build(deck, NewGameScreen.card_dict);
        if (!hero) {
            const identity = deck.hero_name || deck.hero_code || 'that identity';
            NewGameScreen.setStatus(`This build has no deck for ${identity}.`, 'err');
            return;
        }

        NewGameScreen.setStatus(`Loaded ${hero.name || ''}.`, 'ok');
        NewGameScreen.chooseHero(hero, deck.name || 'MarvelCDB');
    }

    private static fillCaption(slot: number, hero: HeroDeck, deck_label: string): void {
        const caption = NewGameScreen.captions[slot];
        if (!caption) {
            return;
        }
        caption.root.classList.add('filled');
        caption.identity.textContent = '...';
        caption.deck.textContent = deck_label;
        caption.aspect.textContent = '';

        const size = (hero.hero_deck || []).length + (hero.player_deck || []).length;
        caption.count.textContent = size ? `${size} cards` : '';

        NewGameScreen.describeHero(slot, hero, deck_label);
    }

    private static clearCaption(slot: number): void {
        const caption = NewGameScreen.captions[slot];
        if (!caption) {
            return;
        }
        caption.root.classList.remove('filled');
        caption.identity.textContent = '';
        caption.deck.textContent = '';
        caption.aspect.textContent = '';
        caption.count.textContent = '';
    }

    private static async describeHero(slot: number, hero: HeroDeck, deck_label: string): Promise<void> {
        const caption = NewGameScreen.captions[slot];
        if (!caption) {
            return;
        }

        try {
            await NewGameScreen.loadCards();

            const identity_id = NewGameScreen.toCardId((hero.hero || [])[0] || '');
            const identity = NewGameScreen.card_dict[identity_id];
            caption.identity.textContent = identity
                ? NewGameScreen.toIdentityName(identity.name)
                : deck_label;

            const aspects = new Set<string>();
            for (const card_id of (hero.player_deck || [])) {
                const card = NewGameScreen.card_dict[card_id];
                if (card && card.class && card.class !== 'Hero' && card.class !== 'Basic') {
                    aspects.add(card.class);
                }
            }
            caption.aspect.textContent = Array.from(aspects).join(' / ');
        } catch (error) {
            caption.identity.textContent = deck_label;
        }
    }

    private static prepareHeroSlots(): void {
        let row: HTMLElement | null = null;

        for (const slot of HERO_SLOTS) {
            const input = document.getElementById(`heroes-${slot}`) as HTMLInputElement | null;
            if (!input) {
                continue;
            }
            const label = input.closest('label');
            if (!label || !label.parentElement) {
                continue;
            }
            row = label.parentElement;

            const seat = document.createElement('div');
            seat.className = 'hero-slot';
            label.parentElement.insertBefore(seat, label);
            seat.appendChild(label);

            const caption = document.createElement('div');
            caption.className = 'hero-cap';
            caption.innerHTML =
                `<div class="hc-player">Player ${slot}</div>` +
                `<div class="hc-char"></div>` +
                `<div class="hc-deck"></div>` +
                `<div class="hc-aspect"></div>` +
                `<div class="hc-count"></div>`;
            seat.appendChild(caption);

            NewGameScreen.captions[slot] = {
                root: caption,
                identity: caption.querySelector<HTMLElement>('.hc-char')!,
                deck: caption.querySelector<HTMLElement>('.hc-deck')!,
                aspect: caption.querySelector<HTMLElement>('.hc-aspect')!,
                count: caption.querySelector<HTMLElement>('.hc-count')!,
            };

            input.addEventListener('click', event => {
                event.preventDefault();
                event.stopImmediatePropagation();
                NewGameScreen.openPicker(slot);
            }, true);

            input.addEventListener('contextmenu', event => {
                event.preventDefault();
                if (typeof window.Reset === 'function') {
                    window.Reset(input);
                }
                NewGameScreen.clearCaption(slot);
            });
        }

        if (row) {
            row.classList.add('hero-row');
        }
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => NewGameScreen.init());
} else {
    NewGameScreen.init();
}
