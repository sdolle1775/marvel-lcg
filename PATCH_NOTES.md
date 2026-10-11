# Unreleased

## Card image downloads ([#134](https://github.com/sdolle1775/marvel-lcg/issues/134))

- Failed downloads use a temporary text-only fallback and can retry after a 30-second cooldown when the image is requested again, without restarting the game.
- Temporarily unreachable image hosts are skipped while the next configured provider is tried. Connection and response-body timeouts allow more time for successful downloads.
- Remote responses are checked before being written to the artwork cache. Invalid responses fall through to the next provider, corrupt cached files can be downloaded again, and file extensions follow the actual image format.
- Corrected the update instructions: downloaded `assets/cache` artwork can be copied into a new installation and reused. The release archive still excludes downloaded artwork.

---

# Marvel Champions Digital v1.3.3

Application version: **1.3.3r**
Windows file version: **1.3.3.0**

This release includes all changes since v1.3.2. The previous v1.3 release descriptions follow below.

## Local replay library and playback

- **Save Replay ([#122](https://github.com/sdolle1775/marvel-lcg/issues/122)):** Saves the complete recorded game history locally in the configured replay folder, including completed games. Saved recordings are available from **Replay** on the main menu without manually moving a browser download into the replay folder.
- **Playback controls:** Replay mode follows the recorded choices with Next or Auto and stops at the end of the recording. It stays in playback until the player explicitly chooses **Continue Game**, instead of silently switching to normal play. Normal save loading remains available for resuming a game.
- **Replay handling:** Added safe replay-library filenames, refreshed local replay listings, and retained the full recording when replaying or saving it again.

## Card and scenario fixes

- **Pawn Shop Showdown ([#105](https://github.com/sdolle1775/marvel-lcg/issues/105)):** The upgrade discount applies to the destination play area and is consumed by the first actual upgrade play each round, including a zero-cost upgrade. Cost previews and putting an upgrade into play without playing it no longer consume the discount. Upgrade costs are checked separately for their possible destinations.
- **Hung Out to Dry and form changes ([#106](https://github.com/sdolle1775/marvel-lcg/issues/106)):** Changing an identity's form or flipping an upgrade no longer counts as entering play. This prevents false obligation triggers and extra Pawn Shop Showdown threat, including Vision's mass-form changes. Continuous modifiers, health checks, statuses, attachments, counters, and printed form-change abilities still refresh correctly. Uses are initialized on setup without being refilled by later flips; Collector's health recovery is preserved.
- **Daredevil's Acute Tactility and Enhanced Olfaction ([#107](https://github.com/sdolle1775/marvel-lcg/issues/107)):** Their enemy-defeat Interrupts resolve before the enemy and attached Sense cards leave play, so Daredevil can receive the printed benefits at the correct time.
- **Teamwork ([#108](https://github.com/sdolle1775/marvel-lcg/issues/108)):** The entering minion activates under the current rules without incorrectly activating existing minions or requiring a legacy rule switch.
- **Stun and confuse ([#109](https://github.com/sdolle1775/marvel-lcg/issues/109)):** The v1.8 workflow permits an attack or thwart ability to clear the corresponding status even when it has no otherwise valid target. This also fixes attack/thwart Specials during Wakanda Forever, including Vibranium Suit.
- **Berserker Barrage ([#113](https://github.com/sdolle1775/marvel-lcg/issues/113)):** Repeated attacks finish correctly when the player chooses to use the event's follow-up.
- **Defeat and Victory ([#115](https://github.com/sdolle1775/marvel-lcg/issues/115)):** Defeat abilities finish before the defeated card moves to the victory display. The deterministic Victory destination no longer adds a redundant ordering choice. Older recordings with that choice remain aligned when loaded.
- **Kang's separate game areas ([#116](https://github.com/sdolle1775/marvel-lcg/issues/116)):** Retaliate and Vulnerable continue to resolve after players move into Kang's stage-two game areas.
- **Purple Man's command obligations ([#117](https://github.com/sdolle1775/marvel-lcg/issues/117)):** Obligations in a player's play area now ready during that player's end phase, allowing their printed once-per-turn actions and limited uses to work on later turns.
- **Nightcrawler and forced timing choices ([#118](https://github.com/sdolle1775/marvel-lcg/issues/118)):** Mandatory ordering choices cannot be skipped with End or an empty submission. The prompt refreshes instead of leaving the round-end discard sequence stuck. The reported Azazel engagement occurred in alter-ego form, where Quickstrike correctly does not attack.
- **Bulletproof Belle and Tough ([#119](https://github.com/sdolle1775/marvel-lcg/issues/119)):** Damage prevention records the prevented damage correctly and allows damage-dealt responses to resolve even when Tough prevents damage taken. Bulletproof Belle prevents attack damage while the attack continues through its remaining resolution. Separate boost damage can still consume Tough before the attack's damage is prevented.
- **Kingpin's side-scheme searches ([#120](https://github.com/sdolle1775/marvel-lcg/issues/120)):** Organized Crime and nemesis side schemes are found and revealed as encounter side schemes, preventing the reported failure during the Kingpin/Bishop game.
- **Synth-Suit ([#124](https://github.com/sdolle1775/marvel-lcg/issues/124)):** Its optional ready response occurs after the controller's Preparation ability finishes resolving, including Ready for a Fight changing form and defending. Internal temporary effects do not produce duplicate responses.
- **Imprisoned:** Corrected its reveal and attachment flow so it attaches to the affected identity without repeating attachment setup. Its printed restrictions, payment options, and boost reveal still apply.
- **Related response timing:** Runaway Nuclear Reaction resolves after damage is dealt to Radioactive Man, counts that damage even when Tough prevents damage taken, excludes Overkill damage to the villain, and does not trigger again from its own explosion. Nelson and Murdock responds after an Attorney defeats a side scheme; Hammerhead's Consolidate Power responds after a minion is defeated; Flight of the Valkyrior remembers the Death-Glow enemy through the defeat and offers its response afterward. Deadpool's mandatory consequential-damage healing uses a Forced Interrupt.
- **Psylocke's Psi-Weapons ([#130](https://github.com/sdolle1775/marvel-lcg/issues/130)):** Generating resources offers an explicit **Keep** or **Flip** choice for the weapon used. Automatic targeting no longer flips it without consent. Removed an unprinted exhaust-to-flip action while retaining Psylocke's printed basic-power Interrupt.

## Optional choices and discards

- **Optional ability choices ([#114](https://github.com/sdolle1775/marvel-lcg/issues/114)):** A single legal optional outcome still requires confirmation. Automatic targeting can select a deterministic target inside a chosen ability without accepting the optional ability itself.
- **Shuri's upgrade Specials ([#131](https://github.com/sdolle1775/marvel-lcg/issues/131)):** Players may keep each upgrade and resolve its initial Special or explicitly discard it for the printed bonus, with automatic targeting enabled or disabled.
- **Other optional discards:** Restored explicit decisions for Melinda May's inspected encounter card, Weapons Training, Goldballs' attack bonus, Stryfe's discard option, and Magnetic Missile's discard-or-damage choice. Declining an optional discard still resolves the required remaining instructions.
- **S.H.I.E.L.D. Mobile Bunker:** The recipient may decline before drawing or discarding; accepting still requires the printed two-card discard.
- **Required costs:** Mandatory discards and minimum discard costs, including Adam Warlock's events, remain mandatory. Optional discard quantities and player decisions are no longer submitted automatically by the client.

## Interface, assets, and credits

- **Sparkles animation ([#123](https://github.com/sdolle1775/marvel-lcg/issues/123)):** Restored the missing `sparkles.gif` interface texture, added attribution, and made it a required release input. Interface textures, including this animation and Storm's weather assets, are bundled; standard card artwork continues to download on demand.
- **Credits:** Shows the running community-build version, credits Sam (sdolle1775) and community contributors, links to community source and releases, and retains a dedicated original-development credit for the Irefrixs Team.
- **Version display:** The main menu and Credits show **Community Build v1.3.3r** from the live application version. Updated the gameplay interface's cache version and the executable's Windows version to match this release.
- **Development instructions:** Clarified installation dependencies and the recommended source-checkout setup.

## Windows package and installation

Built using the v1.3.2 release environment: Python 3.12.13, the same pinned dependencies and verified locally compiled bootloader, PyInstaller's one-folder layout with an embedded Python module archive, and UPX disabled. Verify the downloaded ZIP with its accompanying `.sha256` file.

1. Extract the ZIP into a new, empty folder rather than overwriting an older installation.
2. Keep `marvel-lcg.exe` beside the included `_internal` folder.
3. Copy `campaign_settings.json`, personal saves, the `replays` folder, campaign logs, and custom decks from your previous installation if desired.
4. Do not copy the old executable or old `public`, `data`, or cache folders into the new installation.
5. Open **Replay** on the main menu to watch locally saved recordings; choose **Continue Game** only when you want to resume play from the recording's endpoint.

Standard card artwork is downloaded on demand. This community-maintained build is based on the original Irefrixs Team project.

---

# Marvel Champions Digital v1.3.2

Application version: **1.3.2r**
Windows file version: **1.3.2.0**

This release contains all fixes and improvements made since v1.3.1.

## Antivirus notice

The Windows package remains unsigned. VirusTotal reported antivirus detections for the v1.3.2 executable; the [public VirusTotal report](https://www.virustotal.com/gui/file/7572b331addeede32e964618da9d7d0a61a0869b736046de3df8d89e8c28fe75?nocache=1) is provided for transparency and matches the exact executable included in this release (SHA-256: `7572b331addeede32e964618da9d7d0a61a0869b736046de3df8d89e8c28fe75`). The same executable passed a local Microsoft Defender custom scan before publication. Detection results can differ between engines and change over time; treat this as an unresolved antivirus warning and scan the downloaded package yourself. Verify the ZIP with its accompanying `.sha256` file.

## Card and rules fixes

- **Miscreant / main-scheme lookup ([#93](https://github.com/sdolle1775/marvel-lcg/issues/93)):** Fixed a scripting error that treated a scenario-initiated effect as player-initiated when finding the main scheme. Encounter effects can now resolve that lookup without the player-ownership assertion, while scenarios with player-specific main schemes retain their targeting rules.
- **Carjacking ([#94](https://github.com/sdolle1775/marvel-lcg/issues/94)):** The discarded Vehicle was not identified before the player had to decide whether to spend resources or reveal it. The found card is now presented and named in both choices, including when discarding it empties and reshuffles the encounter deck.
- **Second Chance ([PR #100](https://github.com/sdolle1775/marvel-lcg/pull/100)):** Added the missing When Defeated effect. Each player may shuffle all identity-specific cards from their discard pile into their deck.
- **Dynamic Duo ([PR #100](https://github.com/sdolle1775/marvel-lcg/pull/100)):** Added its Team-Up and matching-ally searches. Both selections now finish before the cards move to hand, followed by one deck shuffle. The deck also shuffles when the searches find nothing or select only cards from the discard pile.
- **Deadly Sai ([#97](https://github.com/sdolle1775/marvel-lcg/issues/97)):** Removed an unprinted boost effect that added another 2 ATK. Its two printed boost icons now resolve without that extra attack bonus; its attachment effects are unchanged.
- **Eye on the Target ([#98](https://github.com/sdolle1775/marvel-lcg/issues/98)):** Recognizes Bullseye already in play as either a villain or a minion. An existing Bullseye attacks; if he must be found and revealed, the card no longer adds an attack after revealing him.
- **Daredevil's Acute Tactility and Enhanced Olfaction ([#99](https://github.com/sdolle1775/marvel-lcg/issues/99)):** Moved their last-threat interrupts to before Daredevil removes the final threat. The Sense cards now resolve and discard before the scheme is defeated, allowing interactions such as Focus the Senses to find them at the correct time.
- **Hunted / Prism Dust ([#104](https://github.com/sdolle1775/marvel-lcg/issues/104)):** Fixed Hunted remaining in the processing area when Prism Dust defeated the fetched minion before Hunted could attach. Hunted now goes to the discard pile and can be retrieved with Undercover Work.
- **Overkill damage modifiers:** Effects that increase damage taken by the receiving enemy, such as Exploit Weakness, now apply to Overkill damage reaching that enemy. Modifiers to the original attack are not applied a second time.
- **Disasters encounter icons:** Added the missing crisis icons and their gameplay effect to Mystic Incursion, Sinking Ferry, and Towering Inferno. Corrected Collapsing Bridge to use its printed hazard icon instead of a crisis icon.

## Saves, search display, and performance

- **Replay recovery ([#96](https://github.com/sdolle1775/marvel-lcg/issues/96)):** A saved choice that no longer matched the current prompt could cause an error or leave automatic replay stuck. Loading now stops at a usable prompt, explains which replay step could not be restored, and lets the player choose how to continue. Auto and Next cannot repeatedly submit the rejected choice.
- **Full-deck search display:** Search previews are now shown only to the player performing the search, including when a different player's deck is searched. Other players and spectators no longer receive the private preview. In hotseat play, the preview clears before control returns to another player. Searches still finish with their normal card movement and shuffle behavior, and searches configured to defer movement or shuffling retain that behavior when no eligible card is found.
- **Game-log performance ([#101](https://github.com/sdolle1775/marvel-lcg/issues/101)):** Adding a log entry now appends the new entry instead of rebuilding the browser's entire log. This reduces repeated browser work as the history grows. Existing log links, scrolling, and rewind behavior are preserved; this change does not remove the engine's cost of replaying a long game during Undo.

## Rise of Red Skull campaign settings

- **Removed Tech upgrades ([#103](https://github.com/sdolle1775/marvel-lcg/issues/103)):** Kept the single-choice Tech Upgrade radio buttons and added a **Player N tech upgrade removed from campaign - Yes** checkbox for each player. Checking it prevents that player's selected Tech card from being added during campaign setup and removes existing copies from their deck or play area. Another player's copy is unaffected, and checking Yes with no selection does nothing.
- **Improved conditions:** Added **Player N "Basic" Condition replaced with "Improved" side - Yes** for each player. Campaign setup uses the matching Improved side of their selected Basic condition when checked.
- **Condition selection and saved settings:** Only Basic conditions can be selected directly. Improved cards remain visible as greyed-out radio choices with hover previews. Existing saved Improved selections load as the corresponding Basic selection with Yes checked, preserving the chosen condition. Each player's removal and improvement flags save independently.

## Windows package and installation

The v1.3.2 package uses the same Python 3.12.13 runtime, pinned dependencies, verified bootloader, PyInstaller one-folder layout, embedded Python module archive, and UPX-disabled configuration used for v1.3.1. The package remains unsigned; matching the build method does not guarantee identical antivirus results.

1. Extract the ZIP into a new, empty folder. Do not overwrite an older installation.
2. Keep `marvel-lcg.exe` beside the included `_internal` folder.
3. Copy `campaign_settings.json`, personal saves, replays, campaign logs, and custom decks from the previous installation if desired.
4. Do not copy the old executable or old `public`, `data`, or cache folders into the new installation.
5. Verify the archive with its accompanying `.sha256` file.

Standard card artwork is downloaded on demand. This community-maintained build is based on the Irefrixs Team project. See `PATCH_NOTES.md` in the download for the cumulative change list.

---

# Marvel Champions Digital v1.3.1

Application version: **1.3.1r**
Windows file version: **1.3.1.0**

This release contains gameplay and timing corrections made after v1.3.0.2.

## Gameplay and timing fixes

- Corrected **Photographic Reflexes** so Echo can play a tucked event owned by another player as though it were in her hand, including normal costs, targets, and resolution.
- Corrected the shared Echo event selector so **Study the Tape** no longer makes **Photographic Reflexes** incorrectly eligible for **Choreography**. Photographic Reflexes remains available to effects that explicitly permit it.
- Corrected multiplayer v1.8 timing-order prompts so **Call for Backup** and similar effects controlled by another player do not retain a stale disabled state and freeze the game.
- Corrected persistent attached maximum-health modifiers across villain face swaps. The same physical card no longer receives the modifier twice, and legacy saves are replayed once with the corrected health state.
- Corrected effects such as **Beguiled** that treat an attached ally as a minion so the conversion does not react to its own face swap and execute twice.
- Corrected **Photon Beam** so defeating its target places 2 progress counters on Ironheart while a non-defeating attack still places 1.
- Restored excess-damage follow-up effects under grouped v1.8 timing, including **Into the Fray** removing threat after its attack defeats a minion with excess damage.
- Corrected indirect attacks reduced to 0 damage so they emit the normal zero-damage attack presentation and resolve cleanly.

The Windows package remains unsigned. Verify this release archive with its accompanying `.sha256` file and scan the downloaded package yourself.

---

# Marvel Champions Digital v1.3.0.2

Application version: **1.3.0.2r**
Windows file version: **1.3.0.2**

This hotfix contains corrections made after v1.3.0.1.

## Hotfix highlight: optional Interrupts

- Restored explicit confirmation for optional Interrupts under the v1.8 timing workflow, including **Echo's alter-ego Interrupt**, when only one legal ability or target is available. Deterministic targeting inside an already chosen ability can still resolve automatically, while Forced Interrupts remain mandatory.

## Additional hotfix fixes

- Corrected **Deft Focus** so its discount applies to a Superpower card played from **Daredevil's Sense deck** as if it were in his hand.
- Corrected **Chameleon** so its SCH and ATK can use the highest printed THW and ATK among the appropriate friendly characters without raising an invalid-filter error.
- Corrected **Mutant Mayhem** so its Alliance cost requires one X-Men ally and one X-Force ally rather than allowing two allies with the same required trait.
- Corrected **Raised by the Kingpin** so it prevents damage dealt by Echo herself without incorrectly preventing damage dealt by her allies.
- Restored set and box images on systems where Pillow's optional WebP decoder is unavailable by passing valid WebP data through to the browser and returning the correct image content type.

The Windows package remains unsigned. See the v1.3.0 antivirus notice below, verify this hotfix archive with its accompanying `.sha256` file, and scan the downloaded package yourself.

---

# Marvel Champions Digital v1.3.0.1

Application version: **1.3.0.1r**
Windows file version: **1.3.0.1**

This hotfix contains corrections made after v1.3.0.

## Hotfix fixes

- Corrected conditional **Surge** under the v1.8 timing workflow. Encounter cards such as **Assault** and **Gang-Up** now gain and resolve Surge when their When Revealed condition is met, and the keyword remains part of that cancellable When Revealed effect.
- Restored explicit confirmation for optional Responses, including optional keyword Responses, when only one legal response is available. Deterministic targeting inside an already chosen ability can still resolve automatically.
- Corrected **Colossus** setup so **Organic Steel** can be searched for only in his deck, as printed, and not in his discard pile.
- Corrected **Goblin** so damage is permitted only when its source is a card with a printed physical resource. Retaliate and other damage without a qualifying printed card resource no longer damage Goblin.

The Windows package remains unsigned. See the v1.3.0 antivirus notice below, verify this hotfix archive with its accompanying `.sha256` file, and scan the downloaded package yourself.

---

# Marvel Champions Digital v1.3.0

Application version: **1.3.0r**
Windows file version: **1.3.0.0**

This release completes **Fear No Evil**, adds its full campaign, and makes the new Rules Reference v1.8 timing workflow the default for new games. These notes describe changes since v1.2.0.1.

## Complete Fear No Evil expansion

- Completed the **Fear No Evil** box: the **Daredevil** and **Echo** hero expansions, their obligations and nemesis sets, the complete player-card pool, every scenario and encounter set, and all campaign cards.
- Added standard and expert versions of the five interchangeable Underling villains: **Bullseye**, **Electro**, **Hammerhead**, **Purple Man**, and **Typhoid Mary**.
- Added the five interchangeable scenarios: **Art Museum Heist**, **The Getaway**, **Protection Racket**, **The Raft Breakout**, and **Stop the Presses!**, including their scenario-specific setup and encounter mechanics.
- Added **Kingpin** as a complete standalone standard/expert scenario with its built-in scenario setup. Selecting Kingpin disables the interchangeable scenario and Standard-set choices that do not apply to him.
- Added all six modular encounter sets in printed order: **Disasters**, **Cops**, **Drive**, **The Owl**, **Tombstone**, and **Tracksuit Mafia**.
- Implemented the complete Fear No Evil campaign, including scenario and Underling selection, scenario results, campaign-card setup, persistent campaign tracking, rewards, removed allies and Persona supports, and campaign-specific scenario instructions.
- Added campaign helpers that randomly offer up to two unfinished scenarios and an unused Underling while keeping completed, failed, and previously selected entries out of those results.

## Rules Reference v1.8 timing

- Added `v18_timing`, enabled by default for new games. Interrupts and responses created by the same attack, damage, defeat, defense, basic-power, recovery, threat, or scheme occurrence now share the correct timing window and can be resolved in player-chosen order.
- Players can choose among simultaneous forced abilities at the same priority. Optional response opportunities rotate from the first player and are recalculated after each resolution, allowing newly legal responses—such as Jarnbjorn after Nova readies Supernova Helmet—to be used in the same window.
- Updated Retaliate, Vulnerable, consequential damage, When Defeated, and When Completed to use their printed v1.8 priorities and lifecycle timing.
- Updated Incite, Quickstrike, Restricted, Surge, Teamwork, Temporary, Toughness, Victory, and Villainous to initiate at their printed timing points. Surge and Incite are cancellable When Revealed effects, reveal responses wait until the complete reveal finishes, Ranged prevents Retaliate, and Piercing does not discard Tough when an attack would deal no damage.
- Hardened nested timing occurrences, replay identities, unnamed internal effects, duplicate candidates, target/cost revalidation, and parent/child attack and damage windows.
- Constant modifiers and other non-triggered game-state effects apply automatically without unnecessary ordering prompts. Exact one-target outcomes are preselected where safe, while defense declarations and Ask abilities retain explicit confirmation.
- Preserved the prior message-by-message dispatcher as an optional legacy mode. Disabling `v18_timing` changes only simultaneous-trigger handling and does not disable separately selected v1.6 rulings.
- Existing saves and replays created before v1.3.0 continue in legacy timing unless they explicitly contain the v1.8 timing rule, preserving their recorded prompt order.

## Interface and search improvements

- Added the optional **Show Deck During Full Search** rule. When enabled, a complete deck or discard-pile search displays every card being searched so the player can inspect the full pool before choosing.
- Kept random full-deck searches random even while the deck is visible; the last inspected or selected card is no longer incorrectly reused as the random result.
- Full-search presentation works for player and encounter searches while preserving shuffle behavior, card-order rules, and the original hidden presentation when the option is disabled.
- Improved campaign setup presentation and status tracking, including visible delimiter tokens for removed allies and Persona supports and cleaner completed/failed controls.
- Removed redundant one-of-one target prompts where the outcome is deterministic. Ask remains an explicit option even when it is the only action available on a selectable player card.

## Scenario and engine corrections

- Restricted each **Protection Racket** main scheme to its assigned player for player-initiated thwart effects while preserving scenario effects that must add or remove threat across personal schemes.
- Corrected crisis handling across Protection Racket's separate main schemes.
- Corrected Art Museum Heist attachment setup, search, shuffling, action labels, and full-search randomization.
- Corrected Underling, modular-set, Kingpin, and campaign-card values, selectors, timing, targets, status effects, empty-search fallbacks, and printed-text interactions found during focused audits.
- Corrected partial and empty full-deck searches such as **Suit Up** so legal results remain selectable without exposing or reusing invalid search state.

## Antivirus notice and Windows package

- The Windows package remains unsigned and uses the pinned Python 3.12.13 runtime, PyInstaller one-folder layout, and UPX-disabled configuration used by prior community releases.
- Microsoft's engine on VirusTotal flagged a v1.3.0 release-candidate executable. The [public VirusTotal report](https://www.virustotal.com/gui/file/a1ab2e6a911db3c1c2dfefb88a2b8cb145b80542ad31075c6bfcf64959bc452b?nocache=1) is provided for transparency and should be treated as an unresolved antivirus warning; detection results can change over time.
- The scanned release-candidate executable has SHA-256 `a1ab2e6a911db3c1c2dfefb88a2b8cb145b80542ad31075c6bfcf64959bc452b`. The final package was rebuilt after the documentation update, so verify the published ZIP with its accompanying `.sha256` file and scan the downloaded package yourself.

---

# Marvel Champions Digital v1.2.0.1

Application version: **1.2.0.1r**
Windows file version: **1.2.0.1**

This hotfix contains corrections made after v1.2.0.

## Hotfix fixes

- Corrected Nebula's encounter Techniques so only the first Technique attachment revealed each round gains surge, rather than the first one revealed to every player.
- Corrected **Brainstorm** so Patrol or another effect that prevents threat removal does not prevent the event from being played or resolving its remaining instructions.
- Corrected **In Harm's Way** so it can be played when either its damage portion has a legal enemy or its threat-removal portion has a legal scheme. Because the event is both an attack and a thwart, Confused cancels its entire effect under Rules Reference v1.8.
- Corrected Daredevil's printed THW from 1 to 2. Sense responses and interrupts that say “you” now require Daredevil's identity to make the attack, thwart, threat removal, or defeat, so ally attacks and thwarts cannot trigger cards such as **Radar Sense**.
- Corrected Sense cards leaving play so replacement effects preserve their requested deck position and return those cards to the bottom of the Sense deck instead of its top.
- Corrected Echo's **Photographic Reflexes** flow. A playable event tucked under Echo is selected directly in hero form, the player chooses and discards a viable copy of Photographic Reflexes before payment, that discarded copy cannot pay for the event, and any remaining copies retain their printed resources for normal payment.

The packaged executable passed a local Microsoft Defender custom scan, and its [VirusTotal analysis](https://www.virustotal.com/gui/file/9f526791102675fbdf201d1f039f0e2f4eb84ab1e747b0c7a3f9f7d4cf5eb24c) reported no detections at release time.

---

# Marvel Champions Digital v1.2.0

Application version: **1.2.0r**
Windows file version: **1.2.0.0**

This description contains only changes made after v1.1.1.

## Featured heroes: Daredevil and Echo

- Added fully playable **Daredevil** and **Echo** heroes from **Fear No Evil**, each with a starter deck, complete identity-specific cards, an obligation, and a registered nemesis set.
- Implemented Daredevil's separate **Sense** deck, Superhuman Senses setup and play rules, Sense attachments, Elektra interactions, and the rest of his hero kit.
- Implemented Echo's **Watch and Learn** tucked-event engine, **Photographic Reflexes**, three-sided upgrades, event-cost interactions, and the rest of her hero kit.
- Added and registered the remaining **Fear No Evil** player cards, including card data, scripts, Starting timing, and Team-Up interactions.
- Corrected **Improvisation** so every matching Attack, Defense, and Thwart trait resolves independently without exhausting the upgrade. Multi-trait events such as **See No Evil, Hear No Evil** can therefore trigger both applicable effects.
- Corrected **Enhanced Olfaction** so it triggers when another effect removes the last threat from the main scheme, including **Living Lie Detector**.

## Campaign support

- Completed the **Age of Apocalypse** campaign rules: mission allies and upgrades, Prelates and Overseers, mission attempts, scenario outcomes, future rewards, card assignment restrictions, and campaign-specific cleanup.
- Completed Age of Apocalypse persistent-health handling for standard and expert campaigns, including defeated-player re-entry, healing choices, and maximum-health limits.
- Corrected Age of Apocalypse setup and campaign-log tracking so scenario choices, mission results, rewards, and player-specific values persist correctly.

## Rules and engine updates

- Updated surge timing to match Rules Reference v1.8.
- Added Rules Reference v1.8 Team-Up ally replacement and now validates Team-Up restrictions before a status card can cancel the associated attack or thwart.
- Generalized Team-Up targeting beyond events so upgrade Team-Up cards such as **Dance with the Devil** load and validate correctly.
- Added complete player-card targeting support for scenarios with multiple villains, including active-villain behavior where required.
- Added support for alternate resource costs such as one matching resource or two resources of any type, including intentional overpayment where a card permits it.
- Enforced printed max-one-per-player limits on Mighty Avengers, Guardians of the Galaxy, Uncanny X-Men, Uncanny X-Force, Children of the Atom, Agents of S.H.I.E.L.D., Flight Squadron, and Heroic Conditioning.
- Added reusable modular-difficulty setup handling for Tower Defense, Project Wideawake, and Infinites.
- Added campaign-log save controls and the matching server operation so campaign progress can be saved from the interface.

## Interface and deck handling

- Added the Fear No Evil set image so Daredevil and Echo display as a proper box selection instead of a gray placeholder in the deck editor.
- Corrected ordered deck-card selection and placement across look-at-deck effects.
- Ordered card rows are now presented right to left to match the resulting deck order.
- Centered card previews no longer intercept clicks intended for selectable cards behind them.
- Deck records now preserve primary and secondary aspects, and Dreadpool setup only treats the actual 'Pool aspect as selecting that encounter content while retaining compatibility with older deck files.

## Card and scenario corrections

- Corrected **Coup de Grace** attack damage.
- Corrected defender-targeted attack effects so boost effects and other responses resolve against the actual defender.
- Corrected obligation choice handling for Ant-Man, Black Panther, Black Widow, Gamora, Hawkeye, Iron Man, Ms. Marvel, Miles Morales, Nebula, Nightcrawler, SP//dr, Spider-Woman, Thor, Winter Soldier, Wolverine, Wasp, and Thunderbolts obligations, together with affected campaign and encounter obligations.
- Corrected Bishop's **Super-Charged** attack bonus and Cyclops's **Lost Visor** attack restriction.
- Corrected defeat rewards for the **Galactic Artifacts** side schemes.
- Corrected **Going Undercover** selection and reorder behavior; Shuri's Black Panther upgrades and **Wakanda Forever!** targeting; core Black Panther's **Vibranium Suit** target requirement; **Rock, Paper, Scissors** resource comparisons; **Dr. Sinclair** and **Godlike Stamina** heal/status choices; and Draugr Buddy's Guard keyword.
- Corrected Enchantress stage threat and **Future of Despair**, Sandman's **City Streets**, **Blackout**, **Blood Debt**, and modular-difficulty setup behavior.
- Corrected alternate-cost behavior for Ironheart, face-bound constant effects, and several scenario setup callbacks.
- Corrected **Machine Man** overpayment, **Norn Stone** stat bonuses on both faces, **Retrieve Odin's Armor**, and affected Vision and resource interactions.
- Corrected Magog/Mojomania modular selection, ratings, and environment completion behavior.
- Corrected Age of Apocalypse mission queries and per-player statistics, Loki stage advancement and **Total Focus**, Baron Zemo, Nebula, Crime, Thanos, and Mad Titan's Shadow campaign reward interactions.

## Windows test package

- Built with the byte-matched Python 3.12.13 runtime and PyInstaller one-folder layout used by v1.1.1.
- Reuses the hash-verified locally compiled PyInstaller bootloader from v1.1.1.
- Pins the complete release dependency graph so later package-index changes cannot silently alter a rebuild.
- UPX is disabled, developer-only command modules are excluded, and card-image cache contents are not bundled.
- A SHA-256 checksum file is generated alongside the archive.

## Testing and installation

1. Extract the ZIP into a new, empty folder rather than overwriting an older installation.
2. Copy `campaign_settings.json` from the previous build if you want to retain campaign setup choices.
3. Copy any personal saves, replays, custom decks, or campaign logs you want to test. Do not copy the old executable, `public`, `data`, `assets/cache`, or `launch.json`.
4. Smoke-test both a new game and an existing save before relying on the build for a longer campaign.

This is a community-maintained build based on the Irefrixs Team project. Card artwork remains excluded from the main package and is downloaded using the image servers configured in `launch.json`.
