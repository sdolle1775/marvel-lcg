import { WorldDescriptor } from './descriptor.js'
import { ClassName } from './class_name.js'
import { Message } from './message.js'
import { Cards } from './cards.js';
import { HoverCard } from './hover.js';


// Define the structure for the statistics data
interface PlayerStats {
    id: number;
    damage_dealt: number;
    damage_taken: number;
    thwarted_threat: number;
    // Add any future keys from KEY_NAME here
    [key: string]: number; // Allows indexing by string keys for generic stats
}

class GameStatistics {
    static currentStats: PlayerStats[] = [];
    static sortKey: string | null = null;
    static sortDirection: 'asc' | 'desc' = 'asc';

    static tableElement = document.getElementById('session-statistics') as HTMLTableElement;
    /**
     * Fetches statistics from the backend and converts the dictionary 
     * into an array of PlayerStats objects.
     */
    static async fetchStatistics() {
        try {
            const response = await fetch('/get_session_statistics');
            if (!response.ok) {
                throw new Error('Failed to fetch statistics');
            }
            
            const rawData = await response.json();
            
            // Convert the backend dictionary {player_id: stats_dict} 
            // into an array [{id: player_id, ...stats}]
            GameStatistics.currentStats = Object.entries(rawData).map(([id, stats]) => ({
                id: parseInt(id), // Ensure ID is a number
                ...(stats as Record<string, number>) // Spread the stats
            })) as PlayerStats[];

            GameStatistics.renderTable();

        } catch (error) {
            console.error("Error fetching session statistics:", error);
            // Display an error message in the table area
            const table = document.getElementById('session-statistics');
            if (table) {
                table.innerHTML = '<tr><td colspan="4">Error loading statistics.</td></tr>';
            }
        }
    }

    static renderTable() {
        
        if (!GameStatistics.tableElement || GameStatistics.currentStats.length === 0) {
            if (GameStatistics.tableElement) GameStatistics.tableElement.innerHTML = '<tr><td>No statistics available.</td></tr>';
            return;
        }

        // Determine headers dynamically from the first player's stats
        const headers = Object.keys(GameStatistics.currentStats[0]);
        
        // Clear the existing table content
        GameStatistics.tableElement.innerHTML = '';

        // Create the table header (<thead>)
        const thead = GameStatistics.tableElement.createTHead();
        const headerRow = thead.insertRow();
        
        headers.forEach(headerText => {
            const th = document.createElement('th');
            th.textContent = GameStatistics.formatHeader(headerText);
            th.dataset.key = headerText; // Store the original key for sorting
            th.addEventListener('click', () => GameStatistics.handleSort(headerText));
            
            // Add sorting indicator (optional visual enhancement)
            if (GameStatistics.sortKey === headerText) {
                th.textContent += GameStatistics.sortDirection === 'asc' ? ' ▲' : ' ▼';
            }
            
            headerRow.appendChild(th);
        });

        // Create the table body (<tbody>)
        const tbody = GameStatistics.tableElement.createTBody();
        GameStatistics.currentStats.forEach(stats => {
            const row = tbody.insertRow();
            headers.forEach(key => {
                const cell = row.insertCell();
                if (key === 'id') {
                    const card = Cards.getCard(stats.id);
                    if (card && card.pic_id !== undefined) {
                        const img = document.createElement('img');
                        img.src = card.pic_id; // Adjust the path as needed
                        img.alt = `${card.pic_id}`; // Add alt text for accessibility
                        img.style.width = '50px'; // Adjust size as needed
                        img.style.height = 'auto';
                        cell.appendChild(img);
                        cell.onmouseenter = () => {
                            HoverCard.showLogImage(stats.id, card.pic_id)
                        }
                    } else {
                        cell.textContent = 'No Image'; // Handle cases where card or pic_id is missing
                    }
                } else {
                    cell.textContent = stats[key].toString();
                }
            });
        });
    }

    /**
     * Utility function to format the header text (e.g., 'damage_dealt' to 'Damage Dealt').
     */
    static formatHeader(text: string): string {
        return text.replace(/_/g, ' ')
                .replace(/\b\w/g, char => char.toUpperCase());
    }

    // --- Sorting Logic ---

    /**
     * Handles the sorting of the data when a header is clicked.
     */
    static handleSort(key: string) {
        if (GameStatistics.sortKey === key) {
            // If the same header is clicked, toggle the direction
            GameStatistics.sortDirection = GameStatistics.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            // If a new header is clicked, set the new key and default to ascending
            GameStatistics.sortKey = key;
            GameStatistics.sortDirection = 'desc';
        }

        // Sort the current data array
        GameStatistics.currentStats.sort((a, b) => {
            const valueA = a[key];
            const valueB = b[key];
            
            if (valueA < valueB) {
                return GameStatistics.sortDirection === 'asc' ? -1 : 1;
            }
            if (valueA > valueB) {
                return GameStatistics.sortDirection === 'asc' ? 1 : -1;
            }
            return 0;
        });

        // Re-render the table with the sorted data
        GameStatistics.renderTable();
    }

}

///////////////////////////////////////////////////////////////////////////////
// Game
export class Game {
    static game_over = false
    static players_won = false
    static is_pause = false
    static is_lost_connect = true
    static forced_on_player = -1 // [-1, 0~3]
    // static current_player = 0 // 0, 1, 2, 3
    static total_players = 1
    static asking_players: number[] = [] // 0,1,2,3
    static full_search_presentation_players: number[] = []
    static current_step_id = -1

    static world_descriptor: WorldDescriptor

    static setGameOver(game_over: boolean) {
        if( Game.game_over != game_over ) {
            Game.game_over = game_over
            if( Game.game_over ) {
                document.body.classList.add(ClassName.game_over)
                console.log('Game over')
            } else {
                document.body.classList.remove(ClassName.game_over)
                GameStatistics.tableElement.innerHTML = '';
                document.getElementById('game-over-box-container')!.classList.remove('minimize')
                Message.cleanGameOverMessage()
            }

            if( Game.game_over ) {
                setTimeout(async () => {
                    await GameStatistics.fetchStatistics()
                    GameStatistics.renderTable()
                }, 1000);
            }
        }
    }
}

(window as any).Game = Game;

