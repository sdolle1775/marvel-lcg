import { Card } from './card_info.js';

export interface HeroDeck {
    name?: string;
    hero: string[];
    obligations: string[];
    nemesis_set: string[];
    set_aside: string[];
    hero_deck: string[];
    player_deck: string[];
    side_deck: string[];
    aspect: string;
    aspect2: string;
}

interface MarvelCDBDeck {
    name?: string;
    hero_name?: string;
    hero_code?: string;
    meta?: string | { [key: string]: string };
    slots?: { [card_id: string]: number };
    sideSlots?: { [card_id: string]: number };
}


export class MarvelCDB {
    static readonly EXCLUDED_CARD_ID = "26002";
    static parseMeta(meta: MarvelCDBDeck['meta']): { [key: string]: string } {
        if (!meta) {
            return {};
        }
        if (typeof meta === 'string') {
            try {
                return JSON.parse(meta);
            } catch (error) {
                return {};
            }
        }
        return meta;
    }

    static async fetchDeck(deck_id: string): Promise<MarvelCDBDeck | null> {
        const addresses = [
            `https://marvelcdb.com/api/public/decklist/${deck_id}.json`,
            `https://marvelcdb.com/api/public/deck/${deck_id}.json`,
        ];

        for (const address of addresses) {
            try {
                const response = await fetch(address);
                if (response.ok) {
                    return await response.json();
                }
            } catch (error) {
                
            }
        }
        return null;
    }

    static async fetchStarterDeck(identity: string): Promise<HeroDeck | null> {
        try {
            const response = await fetch(`get_hero_json?${identity}`);
            if (!response.ok) {
                return null;
            }
            return await response.json();
        } catch (error) {
            return null;
        }
    }

    static toFileName(hero_name: string): string {
        return hero_name.replace(/[^a-z0-9]/gi, '_').toLowerCase();
    }

    static async build(
        deck: MarvelCDBDeck,
        card_dict: { [key: string]: Card },
    ): Promise<HeroDeck | null> {
        const identity = deck.hero_code || (deck.hero_name ? MarvelCDB.toFileName(deck.hero_name) : '');
        if (!identity) {
            return null;
        }

        const hero_deck = await MarvelCDB.fetchStarterDeck(identity);
        if (!hero_deck) {
            return null;
        }

        const meta = MarvelCDB.parseMeta(deck.meta);
        hero_deck.aspect = meta['aspect'] || "";
        hero_deck.aspect2 = meta['aspect2'] || "";
        hero_deck.player_deck = MarvelCDB.collectCards(deck.slots, card_dict, true);
        hero_deck.side_deck = MarvelCDB.collectCards(deck.sideSlots, card_dict, false);

        if (deck.name) {
            hero_deck.name = deck.name;
        }
        return hero_deck;
    }

    private static collectCards(
        slots: { [card_id: string]: number } | undefined,
        card_dict: { [key: string]: Card },
        skip_identity_cards: boolean,
    ): string[] {
        const cards: string[] = [];
        for (const card_id in slots) {
            if (card_id === MarvelCDB.EXCLUDED_CARD_ID) {
                continue;
            }
            if (skip_identity_cards && card_dict[card_id] && card_dict[card_id].class === "Hero") {
                continue;
            }
            const count = slots[card_id];
            if (typeof count !== 'number' || count <= 0) {
                continue;
            }
            for (let copy = 0; copy < count; copy++) {
                cards.push(card_id);
            }
        }
        return cards;
    }
}
