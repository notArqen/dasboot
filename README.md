# u-boot command · a terminal submarine simulator

> a tense, single-session war patrol simulator that puts you in command of a Type VII U-boat — no tutorial, no hand-holding, just you, the Atlantic, and the tonnage quota BdU expects you to meet.

> [!CAUTION]
> This game depicts World War II naval warfare from the Kriegsmarine perspective. It is a historical simulation and does not endorse any ideology. Player discretion advised.

---

## table of contents

- [overview](#overview)
- [features](#features)
- [getting started](#getting-started)
- [gameplay](#gameplay)
- [controls & commands](#controls--commands)
- [events & encounters](#events--encounters)
- [technical notes](#technical-notes)
- [known bugs](#known-bugs)
- [license](#license)

---

## overview

**u-boot command** is a terminal-based submarine simulation game built entirely in Python with zero external dependencies. there's no GUI, no graphics library, no engine — just ASCII art, radiograms, and the crushing pressure of the North Atlantic in 1941.

the game is structured as a single patrol: you depart Lorient, hunt convoys across a 10x8 grid of the Atlantic, manage your boat's depth and resources, keep your crew from breaking, and try to sink enough tonnage to satisfy BdU before your fuel runs out or a destroyer sends you to the bottom.

it's designed to feel authentic without being a manual-reading simulator. you won't need to know how to operate a real submarine, but you will need to manage fuel, food, water, torpedoes, crew morale, stress, and fatigue — all while dodging depth charges and making split-second tactical calls.

---

## features

### submarine operations
- **depth management** — surface, periscope depth, standard dive, deep, emergency deep, or manual entry up to crush depth (250m)
- **navigation** — plot courses across a 10x8 Atlantic grid with fuel consumption calculated per square traveled
- **torpedo combat** — fire spreads of up to 6 torpedoes at convoys and merchants with realistic hit probability
- **resource management** — fuel, food, water, medical kits, and torpedo reserves all deplete over time

### crew simulation
- **morale system** — affected by sinkings, injuries, near-misses, and time at sea
- **stress & fatigue** — build up during combat, depth charge attacks, and long patrols
- **crew injuries** — random events can wound crew members, consuming medical supplies

### dynamic events
- convoy encounters with escorts and merchant targets
- destroyer attacks with depth charge barrages
- aerial patrols forcing emergency dives
- equipment failures (sonar, periscope, ballast tanks, diesel engines)
- weather storms affecting visibility and operations
- wolfpack coordination with other U-boats
- radio orders from BdU HQ in Lorient
- supply discoveries from sunk ships

### mission structure
- tonnage quota system — BdU assigns a GRT (gross registered tons) target for each patrol
- patrol ratings — OUTSTANDING, SUCCESS, MARGINAL, FAILURE, or DISGRACE based on quota completion
- return to port conditions — only allowed when fuel/food/water ≤ 20%, morale ≤ 30, crew stress/fatigue ≥ 70, or out of torpedoes
- victory achieved at ≥100% quota, ace status at ≥150%

### presentation
- authentic radiogram displays for BdU orders and wolfpack signals
- ASCII depth gauge with crush depth warning zones
- navigation map with current position, patrol zone, and grid coordinates
- detailed dashboard showing all boat and crew stats in bordered panels
- typewriter-style delayed text for atmospheric narrative moments

---

## getting started

u-boot command is four Python files with no dependencies outside the standard library. if you have Python 3.10+, you're good to go.

### prerequisites
- Python 3.10 or higher
- a terminal with at least 80 columns width
- no pip installs, no virtual environments, no package managers

### installation

```bash
# extract the zip
unzip dasboot_updated.zip
cd dasboot_updated

# run the game
python main.py
```

### file structure

```
main.py      # game loop, menus, and action handlers
engine.py    # game state, turn advancement, resource depletion
events.py    # all random encounters and event logic
display.py   # rendering functions for dashboard, maps, gauges
```

---

## gameplay

### the mission

you are the commander of a Type VII U-boat departing Lorient, France in 1941. BdU (U-boat Command) has assigned you:

- a **patrol zone** — a grid square in the Atlantic where convoy activity is expected
- a **tonnage quota** — the amount of enemy shipping (in GRT) you must sink to succeed
- a **U-boat designation** — randomly assigned (U-47, U-99, U-100, U-110, U-552, U-331, U-403)
- a **kriegsmarine rank** — your rank as commander (Kapitänleutnant, Oberleutnant zur See, etc.)

your job: navigate to the patrol zone, hunt convoys, sink ships, and return to port before you run out of fuel, food, water, or crew sanity.

### how to play

#### 1. navigate
plot a course by entering grid coordinates (e.g. `C4`). each square traveled consumes fuel. you can see your current position, patrol zone (marked X), and heading on the navigation map.

#### 2. manage depth
adjust your depth based on tactical needs:
- **surface (0m)** — fastest speed, recharge batteries, but vulnerable to aircraft
- **periscope depth (12m)** — observe convoys, attack position
- **standard dive (50m)** — evasion depth, safe from most threats
- **deep (150m)** — hiding from destroyers
- **emergency deep (200m)** — last resort during depth charge attacks
- **crush depth (250m)** — hull failure zone, instant death

#### 3. engage targets
when you encounter a convoy:
- choose your target (merchants carry tonnage, escorts don't)
- fire a spread of torpedoes (1-6, more = higher hit chance)
- torpedoes have realistic probability based on spread size
- successful hits award GRT toward your quota
- escorts may counterattack with depth charges

#### 4. survive
- **depth charges** — dive deep and hope the pressure hull holds
- **aerial patrols** — crash dive immediately or risk being bombed
- **equipment failures** — repair what you can, adapt to what you can't
- **crew stress** — manage morale or face mutiny, breakdowns, or desertions

#### 5. return to port
you can only return when:
- fuel ≤ 20%
- food ≤ 20%
- water ≤ 20%
- crew morale ≤ 30
- crew stress ≥ 70
- crew fatigue ≥ 70
- out of torpedoes

BdU will rate your patrol based on quota completion. ≥100% = SUCCESS. ≥150% = ACE STATUS.

---

## controls & commands

### main menu

```
[1] KURS SETZEN    — Navigate / Plot Course
[2] TAUCHEN        — Dive / Surface
[3] TORPEDO FEUER  — Fire Torpedoes
[4] SEEKARTE       — Navigation Map
[5] TIEFENMESSER   — Depth Gauge
[6] WARTEN         — Advance Time (+4 hrs)
[7] SPEICHERN      — Save Game
[8] PORT           — Return to Port
[Q] AUFGEBEN       — Quit
```

### during events

most events present choices in the format:
```
[1] Option A
[2] Option B
[3] Option C
```

simply enter the number corresponding to your choice.

### combat

during torpedo attacks:
```
Enter spread size (1-6 torpedoes):
```

larger spreads consume more torpedoes but have higher hit probability. a single torpedo has ~40% base hit chance; a 6-torpedo spread approaches ~95%.

---

## events & encounters

### convoy contact
engage merchant convoys escorted by destroyers and corvettes. merchants carry 2,000-8,000 GRT each. escorts carry 0 GRT but will attack you if you engage.

### destroyer contact
hostile warship on intercept course. options: dive deep, run silent, or surface and hope they don't see you.

### aerial patrol
enemy reconnaissance aircraft overhead. crash dive or risk being depth-charged from the air.

### depth charge attack
destroyers drop patterns of depth charges. go deep, pray your hull holds, and hope they lose contact.

### equipment failure
random systems fail: sonar, periscope, ballast tanks, diesel engines. some can be jury-rigged, others you live without.

### crew injury
sailors are wounded by explosions, falls, or equipment failures. consume medical kits to treat them or suffer morale penalties.

### weather storm
heavy seas affect operations. running on the surface becomes dangerous; diving is safer but slower.

### radio orders
BdU sends new patrol assignments, convoy intelligence, tactical warnings, or sinking confirmations.

### wolfpack signal
another U-boat in your area coordinates an attack. join them for a group assault on a high-value convoy.

### ghost contact
sonar picks up something. is it a convoy? a lone merchant? a decoy? or nothing at all?

### supply find
floating debris from a sinking contains supplies: fuel, food, water, or medical kits.

### morale event
crew events that affect morale: mail from home, a sailor's birthday, a fight in the torpedo room, or a gramophone concert.

---

## technical notes

### architecture
- **no external dependencies** — uses only Python standard library (`random`, `time`, `json`, `dataclasses`)
- **modular design** — game state, display, events, and engine are cleanly separated
- **save/load system** — saves to `uboot_save.json` in the working directory
- **turn-based simulation** — each action advances time in 4-hour increments
- **resource depletion** — fuel, food, and water drain per turn based on boat status (surfaced vs. diving)

### combat math
- torpedo hit probability: `base_chance + (spread_size * 0.10)` where base = 0.40
- depth charge damage: random hits reduce hull integrity
- crew stress increases during combat, fatigue increases over time
- morale is affected by victories (+10), near-misses (-5), crew deaths (-15)

### persistence
- saves include full game state: boat stats, crew stats, mission stats, position, resources, message log
- save file is human-readable JSON
- autosave on return to port or game over

### rendering
- all UI elements use box-drawing characters (`─ │ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼`)
- progress bars use `#` for filled, `-` for empty
- tonnage quota bar scales from 0-200% (0-20 characters)
- depth gauge shows safe zone (green concept), warning zone (yellow concept), and crush zone (red concept) via text labels

---

## known bugs

- **tonnage display overflow** — very large tonnage numbers (100,000+ GRT) may slightly misalign dashboard borders
- **save file corruption** — improperly formatted manual edits to `uboot_save.json` will cause load failures
- **depth gauge visual** — ASCII depth gauge may render incorrectly on terminals narrower than 80 columns

---

## license

© u-boot command project. open source under MIT license.

feel free to fork, modify, and distribute. attribution appreciated but not required.

---

<p align="center">the ocean is dark and full of destroyers.</p>
