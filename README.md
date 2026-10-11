# Marvel LCG Digital — Community Build

This community-maintained build is based on [Marvel LCG Digital](https://irefrixs.itch.io/marvel-lcg), originally developed by the Irefrixs Team. It adds campaign support, community content, gameplay corrections, and interface improvements while keeping the game free to play.

The upstream developers have given permission for modified builds to be published while they finalize a permissive software license. See [ATTRIBUTION.md](ATTRIBUTION.md) for project and intellectual-property notices.

## Latest release: v1.3.3

[Download Community Build v1.3.3 for Windows](https://github.com/sdolle1775/marvel-lcg/releases/tag/v1.3.3).

v1.3.3 adds a complete local replay library with playback that stops at the recording's endpoint, restores optional discard and Psi-Weapon choices, corrects card and scenario timing, restores the sparkles animation, and updates community credits. It also fixes form-change entry triggers, upgrade discounts, Victory ordering, Kang's keywords, Purple Man's obligations, Nightcrawler's forced choices, Bulletproof Belle/Tough prevention, Kingpin's side-scheme reveals, and Synth-Suit. The main menu and Credits display **Community Build v1.3.3r**. It includes all earlier v1.3 releases and content, including:

- The complete **Fear No Evil** box: Daredevil and Echo, all player cards, five interchangeable Underling villains, five interchangeable scenarios, Kingpin's standalone scenario, all six modular encounter sets, and the full campaign.
- Rules Reference v1.8 simultaneous timing, enabled by default for new games. Interrupts and responses created by one occurrence share the correct timing window and can be resolved in player-chosen order. The legacy timing dispatcher remains available through the Rule settings.
- Updated v1.8 timing for Surge, Incite, Quickstrike, Teamwork, Toughness, Retaliate, Vulnerable, Villainous, Victory, When Defeated, When Completed, and related attack/damage workflows.
- A new optional **Show Deck During Full Search** setting, allowing players to inspect the complete searched deck or discard pile while still preserving random searches and shuffles.
- A dedicated Fear No Evil campaign setup interface for tracking scenario outcomes, Underlings, campaign cards, rewards, removed allies and Persona supports, and randomized scenario progression.

Campaign setup choices are saved in `campaign_settings.json`. When installing a new release, extract it into a new folder and copy this file from the previous installation to preserve those choices. Also copy any saves, replays, or custom decks you want to retain. You may copy `assets/cache` to reuse downloaded card artwork and avoid downloading it again. Keep `marvel-lcg.exe` beside its `_internal` folder, and do not copy the old executable or old `public` or `data` folders into the new installation.

See the [complete patch notes](PATCH_NOTES.md) and [installation guide](docs/install_guide.md) for details.

## Windows packaging

v1.3.3 uses the v1.3.2 release environment: Python 3.12.13, the same pinned dependencies and verified locally compiled bootloader, PyInstaller's one-folder package with an embedded Python module archive, and UPX disabled. The one-folder layout avoids extracting the executable into a temporary directory at startup.

Verify the downloaded archive with its accompanying `.sha256` file.

## Community build highlights

- **Campaigns:** Complete playable campaign flows for **Fear No Evil**, **Mutant Genesis**, **NeXt Evolution**, **Age of Apocalypse**, **Agents of S.H.I.E.L.D.**, **Galaxy's Most Wanted**, and **The Mad Titan's Shadow**.
- **Playable heroes:** Full **Wonder Man**, **Hercules**, **Daredevil**, and **Echo** hero expansions, each with a starter deck, identity-specific cards, an obligation, and a registered nemesis set. Daredevil includes his separate Sense deck, while Echo includes her tucked-event mechanics.
- **Player cards:** The complete **Fear No Evil** player-card set, including Starting and Team-Up cards, together with the aspect and basic player cards released alongside Wonder Man and Hercules.
- **Fear No Evil scenarios:** Five interchangeable Underlings—**Bullseye**, **Electro**, **Hammerhead**, **Purple Man**, and **Typhoid Mary**—can be paired with **Art Museum Heist**, **The Getaway**, **Protection Racket**, **The Raft Breakout**, or **Stop the Presses!**. **Kingpin** is implemented as a complete standalone scenario, together with the Disasters, Cops, Drive, The Owl, Tombstone, and Tracksuit Mafia modular sets.
- **Synthezoid Smackdown:** Standard and expert cooperative scenarios against **She-Hulk** and **Vision**, supported by the S.H.I.E.L.D. Ops, Thunderbolts, Taskmaster, Deadly Duo, Young Avengers, Scarlet Twins, Moon Knight, and Royal Guard encounter sets.
- **Trickster Takeover:** Complete standard and expert **Loki: God of Lies** scenarios, including the Loki Avatar stages, Synergy environments, Shatter the Illusion, and Trickster Magic content.
- **Civil War:** Expert scenario variants for **Iron Man**, **Captain Marvel**, **Captain America**, and **Spider-Woman**.
- Campaign implementations cover setup, progression, campaign logs, persistent health and cards, player assignments, missions, evidence, rewards, and campaign-specific scenario changes.
- Rules and card-engine implementations support default-on Rules Reference v1.8 timing, Starting abilities, Team-Up ally replacement, multi-villain targeting, alternate resource costs, and reusable modular-difficulty setup.
- The optional full-deck-search display exposes all cards in a complete search without changing random selection, shuffle, or hidden-information behavior when the option is disabled.
- The community content is registered throughout the card database, starter-deck library, scenario loader, encounter-set system, and campaign framework for play alongside the original Irefrixs content.

## Release and distribution

- [GitHub releases](https://github.com/sdolle1775/marvel-lcg/releases)
- [Release build and publishing guide](docs/release_guide.md)
- Standard card artwork is downloaded from the image servers configured in `launch.json` and cached locally. Downloaded card images are not included in the main release archive.
- The release build includes the small sounds, card backs, status cards, placeholders, and set textures required by the interface.

## Documentation

| Guide | Description |
| --- | --- |
| [Install Guide](docs/install_guide.md) | How to install and run the game |
| [How to Play](https://itch.io/t/3763917/how-to-play-this-game) | Game rules and controls |
| [Card Scripting Guide](docs/card_scripting_guide.md) | How to write card ability scripts |
| [Engine Architecture](docs/engine_architecture.md) | Engine internals for developers |
| [Debug Guide](docs/debug_guide.md) | How to debug the game |
| [Editor Guide](docs/editor_guide.md) | How to use the card editor |
| [Release Guide](docs/release_guide.md) | How to validate and package a release |

## Security warning

This game runs Python card scripts. Do not install or run third-party card scripts unless you trust their source.

这个游戏会运行用 Python 编写的卡牌脚本。除非你完全信任其来源，否则不要安装或运行任何第三方卡牌脚本。

## Screenshots

![](/docs/assets/image-1.jpg)
![](/docs/assets/image-2.jpg)
