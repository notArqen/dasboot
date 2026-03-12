"""
U-BOOT COMMAND — EVENTS MODULE
events.py: all random event handlers, flavor text, consequences

this is where the war actually happens.
each event is a self-contained scenario with player choices and outcomes.
"""

import random
import time
from engine import (
    GameState, clamp, add_message, CRUSH_DEPTH, SAFE_DIVE_DEPTH
)
from display import (
    show_radiogram, show_depth_charge, show_torpedo_fire,
    show_messages, delay_print, clear, hr
)

# ─────────────────────────────────────────────
#  EVENT DISPATCHER
# ─────────────────────────────────────────────

def handle_event(state: GameState, event_type: str):
    """route event to its handler. no fall-through. this isn't javascript."""
    handlers = {
        "CONVOY_CONTACT":    event_convoy_contact,
        "DESTROYER_CONTACT": event_destroyer_contact,
        "AERIAL_PATROL":     event_aerial_patrol,
        "EQUIPMENT_FAILURE": event_equipment_failure,
        "CREW_INJURY":       event_crew_injury,
        "WEATHER_STORM":     event_weather_storm,
        "RADIO_ORDERS":      event_radio_orders,
        "WOLFPACK_SIGNAL":   event_wolfpack_signal,
        "GHOST_CONTACT":     event_ghost_contact,
        "SUPPLY_FIND":       event_supply_find,
        "MORALE_EVENT":      event_morale_event,
    }
    handler = handlers.get(event_type)
    if handler:
        handler(state)
    else:
        add_message(state, f"UNBEKANNTES EREIGNIS: {event_type}. IGNORIERT.")

# ─────────────────────────────────────────────
#  HELPER: PRINT EVENT HEADER
# ─────────────────────────────────────────────

def _event_header(title: str):
    print()
    print(f"  {'═'*56}")
    print(f"  >> {title.upper()}")
    print(f"  {'═'*56}")
    print()

def _choice_prompt(options: list[tuple[str, str]]) -> str:
    """display choices and get valid input. repeat until they get it right."""
    for key, desc in options:
        print(f"  [{key}] {desc}")
    print()
    valid = {k.lower() for k, _ in options}
    while True:
        choice = input("  > ").strip().lower()
        if choice in valid:
            return choice
        print("  Invalid. Try again.")

# ─────────────────────────────────────────────
#  EVENTS
# ─────────────────────────────────────────────

# ── CONVOY CONTACT ────────────────────────────

CONVOY_SIGHTINGS = [
    "Smoke on the horizon. Multiple masts.",
    "Sonar contact. Propeller noise. Large formation.",
    "Lookout reports: convoy. Escort vessels visible.",
    "Hydrophone: at least 8 ships. Course east-northeast.",
    "Mastheads in the haze. British flag identified.",
]

def event_convoy_contact(state: GameState):
    _event_header("KONVOI GESICHTET — CONVOY SPOTTED")

    n_merchants = random.randint(3, 12)
    n_escorts   = random.randint(1, 4)
    visibility  = random.choice(["Foggy", "Clear", "Dusk", "Night"])
    distance    = random.randint(400, 1800)
    sighting    = random.choice(CONVOY_SIGHTINGS)

    delay_print(f"  {sighting}")
    time.sleep(0.5)
    print()
    print(f"  Merchants : {n_merchants} ships")
    print(f"  Escorts   : {n_escorts} destroyers")
    print(f"  Visibility: {visibility}")
    print(f"  Distance  : ~{distance}m")

    # store contact so torpedo screen knows what's out there
    state.recent_contact = {
        "type": "CONVOY", "ships": n_merchants, "escorts": n_escorts,
        "distance": distance, "turns_ago": 0, "visibility": visibility
    }

    print()

    options = [
        ("1", "Attack — fire torpedoes"),
        ("2", "Shadow — hold position, report to BdU"),
        ("3", "Evade — change course, avoid contact"),
    ]
    choice = _choice_prompt(options)

    if choice == "1":
        _convoy_attack(state, n_merchants, n_escorts, visibility)
    elif choice == "2":
        _convoy_shadow(state, n_escorts)
    else:
        delay_print("  Convoy avoided. Discretion is not cowardice.")
        add_message(state, "Convoy sighted and evaded.")

    input("  [ENTER]")


def _convoy_attack(state: GameState, n_merchants: int, n_escorts: int, visibility: str):
    b = state.boat
    if b.torpedoes <= 0:
        print("  No torpedoes. Attack impossible.")
        return

    print()
    print("  Attack solution acquired. How many torpedoes to fire? (1–3)")
    try:
        n_torps = clamp(int(input("  > ").strip()), 1, 3)
    except ValueError:
        n_torps = 1
    n_torps = min(n_torps, b.torpedoes)

    hits = 0
    for i in range(n_torps):
        b.torpedoes -= 1
        state.stats.torpedoes_fired += 1

        # visibility affects hit chance
        vis_mod = {"KLAR": 0.1, "NEBELIG": -0.15, "DAEMMERUNG": -0.05, "NACHT": -0.10}
        hit_chance = 0.60 + vis_mod.get(visibility, 0)
        hit_chance += (state.crew.morale / 100) * 0.15
        hit_chance -= (state.crew.fatigue / 100) * 0.15

        hit = random.random() < clamp(int(hit_chance * 100), 15, 85) / 100
        dist = random.randint(400, 1600)
        show_torpedo_fire(hit, dist)

        if hit:
            hits += 1
            tonnage = random.randint(3000, 15000)
            state.stats.ships_sunk   += 1
            state.stats.tonnage_sunk += tonnage
            print(f"  SUNK: {tonnage:,} GRT")
        time.sleep(0.3)

    print()
    if hits > 0:
        print(f"  {hits}/{n_torps} hits. Well done, Herr Kaleun.")
    else:
        print(f"  All torpedoes missed. Embarrassing.")

    if hits > 0 or random.random() < 0.4 * n_escorts:
        print()
        print(f"  ! Escorts responding — {n_escorts} destroyer(s) on search pattern.")
        time.sleep(0.5)
        event_destroyer_contact(state)


def _convoy_shadow(state: GameState, n_escorts: int):
    """follow convoy, report to BdU, possible wolfpack coordination."""
    print()
    delay_print("  Shadowing convoy. Transmitting position to BdU...")
    time.sleep(1)
    print()

    show_radiogram(
        from_  = f"{state.u_boat_name}",
        to_    = "BdU LORIENT",
        body_lines=[
            f"KONVOI GESICHTET. POSITION: {chr(64+state.nav.grid_x)}{state.nav.grid_y}.",
            f"KURS: OST-NORDOST. GESCHWINDIGKEIT: CA. 8 KNOTEN.",
            f"STAERKE: {random.randint(5,12)} HAENDLER, ESKORTEN.",
            f"WARTE AUF VERSTAERKUNG.",
        ],
        classification="DRINGEND"
    )

    state.crew.morale = clamp(state.crew.morale + 5, 0, 100)
    add_message(state, "Convoy reported. BdU informed.")

    if random.random() < 0.25:
        print("  ! Radio direction finding — destroyer bearing toward us.")
        time.sleep(0.5)
        event_destroyer_contact(state)


# ── DESTROYER CONTACT ─────────────────────────

DEPTH_CHARGE_TEXTS = [
    "WASSERBOMBEN. DIE ROHRE SINGEN.",
    "WABOS. SEHR NAH. SEHR LAUT.",
    "EINSCHLÄGE WIE DONNERSCHLÄGE. LAMPEN FLACKERN.",
    "DRUCKWELLEN ERSCHÜTTERN DEN RUMPF. MÄNNER FALLEN.",
    "METALL STÖHNT. SCHWEISSNAEHTE HALTEN — KNAPP.",
]

def event_destroyer_contact(state: GameState):
    _event_header("ZERSTOERER — FEINDKONTAKT")

    destroyer_name = random.choice([
        "HMS BULLDOG", "HMS VANOC", "USS BORIE",
        "HMCS SHEDIAC", "HMS WALKER", "HMS VERITY"
    ])
    delay_print(f"  {destroyer_name} on intercept course.")
    print(f"  Propeller sounds. Fast. Getting closer.")
    print()

    options = [
        ("1", "Dive deep — get below search depth"),
        ("2", "Silent running — cut engines, hold position"),
        ("3", "Evasive maneuver — hard turn"),
        ("4", "Emergency surface — fight on top"),
    ]
    choice = _choice_prompt(options)

    # base survival and damage chances per tactic
    tactics = {
        "1": {"escape_bonus": 0.15, "damage_mult": 0.6,  "dc_count": 2},
        "2": {"escape_bonus": 0.20, "damage_mult": 0.4,  "dc_count": 1},
        "3": {"escape_bonus": 0.10, "damage_mult": 0.8,  "dc_count": 3},
        "4": {"escape_bonus": -0.1, "damage_mult": 1.2,  "dc_count": 0},  # surface gun fight
    }
    t = tactics[choice]

    if choice == "1":
        new_depth = random.randint(150, 230)
        state.boat.current_depth = new_depth
        state.boat.surfaced      = False
        print(f"\n  Diving to {new_depth}m...")
        if new_depth > SAFE_DIVE_DEPTH:
            hull_dmg = random.randint(3, 10)
            state.boat.hull_integrity = clamp(state.boat.hull_integrity - hull_dmg, 0, 100)
            print(f"  ! Depth pressure stress — hull -{hull_dmg}%")

    print()
    n_passes = random.randint(1, 3)
    for pass_num in range(n_passes):
        print(f"  Pass {pass_num+1}/{n_passes}:")
        dc_text = random.choice(DEPTH_CHARGE_TEXTS)
        delay_print(f"  {dc_text}")

        severity  = random.randint(1, 3)
        show_depth_charge(severity)
        state.stats.depth_charges_survived += 1

        print("  ...")
        time.sleep(2.5)

        escape_chance = 0.50 + t["escape_bonus"]
        escape_chance += (state.nav.patrol_day > 15) * -0.1
        took_hit = random.random() > escape_chance

        if took_hit:
            base_dmg  = random.randint(5, 25) * t["damage_mult"]
            hull_dmg  = int(base_dmg * severity / 2)
            crew_dmg  = random.randint(0, 5)

            state.boat.hull_integrity  = clamp(state.boat.hull_integrity - hull_dmg, 0, 100)
            state.crew.health          = clamp(state.crew.health - crew_dmg, 0, 100)
            state.crew.morale          = clamp(state.crew.morale - 8, 0, 100)

            print(f"  !! HIT — hull -{hull_dmg}%  crew -{crew_dmg}%")

            if random.random() < 0.3:
                _random_equipment_damage(state)

            if crew_dmg > 3 and random.random() < 0.3:
                lost = random.randint(1, 2)
                state.crew.alive = max(1, state.crew.alive - lost)
                print(f"  !! {lost} man down.")

        else:
            print(f"  Pass survived. Holding.")

        time.sleep(0.6)

        if state.boat.hull_integrity <= 0 or state.game_over:
            break

    if not state.game_over:
        escaped = random.random() < (0.50 + t["escape_bonus"])
        if escaped:
            delay_print(f"\n  Contact lost. {destroyer_name} breaking off.")
            state.crew.morale = clamp(state.crew.morale + 10, 0, 100)
        else:
            delay_print(f"\n  {destroyer_name} continuing pursuit.")
            print("  Second attack run incoming...")
            time.sleep(1)
            extra_dmg = random.randint(8, 20)
            state.boat.hull_integrity = clamp(state.boat.hull_integrity - extra_dmg, 0, 100)
            print(f"  Hull -{extra_dmg}% — leaks reported.")

    add_message(state, f"Destroyer attack survived. Hull: {state.boat.hull_integrity}%")


# ── AERIAL PATROL ──────────────────────────────

def event_aerial_patrol(state: GameState):
    _event_header("LUFTAUFKLÄRUNG — ENEMY AIRCRAFT")

    aircraft = random.choice([
        "Sunderland flying boat", "B-24 Liberator",
        "Catalina patrol aircraft", "Hudson reconnaissance plane"
    ])

    delay_print(f"  Lookout reports: {aircraft}.")
    time.sleep(0.8)
    delay_print(f"  High altitude. Closing fast.")
    print()

    if not state.boat.surfaced:
        print("  Submerged. Aircraft cannot attack directly.")
        print("  Risk: radar detection possible.")
        print()
        print("  ...")
        time.sleep(2.5)
        result = random.random()
        if result < 0.3:
            print("  Radar contact — position compromised. Destroyer alerted.")
            time.sleep(0.8)
            event_destroyer_contact(state)
        else:
            print("  Aircraft passed overhead. Not detected. Close.")
    else:
        print("  On the surface! Immediate decision required:")
        options = [
            ("1", "Emergency dive — alarm dive NOW"),
            ("2", "Flak — engage the aircraft"),
        ]
        choice = _choice_prompt(options)

        if choice == "1":
            dive_time = random.randint(25, 45)
            print(f"\n  ALARM TAUCHEN! Dive time: {dive_time} seconds...")
            print("  ...")
            time.sleep(3.0)
            if dive_time > 35:
                bomb_dmg = random.randint(10, 30)
                state.boat.hull_integrity = clamp(state.boat.hull_integrity - bomb_dmg, 0, 100)
                state.crew.morale = clamp(state.crew.morale - 10, 0, 100)
                print(f"  Too slow — bomb hit before clearing the surface.")
                print(f"  Hull -{bomb_dmg}%")
            else:
                print("  Made it. Aircraft overhead. Hold depth. Don't breathe.")
            state.boat.surfaced = False
            state.boat.current_depth = 40
        else:
            print()
            print("  Flak crew to stations...")
            time.sleep(1.5)
            print("  Aircraft closing... tracking...")
            time.sleep(2.0)
            hit_plane = random.random() < 0.35
            if hit_plane:
                print("  TREFFER! Flak connects. Aircraft turning away, trailing smoke.")
                state.crew.morale = clamp(state.crew.morale + 15, 0, 100)
            else:
                print("  Bombs away.")
                time.sleep(1.0)
                bomb_dmg  = random.randint(15, 35)
                crew_dmg  = random.randint(2, 8)
                casualties= random.randint(0, 3)
                state.boat.hull_integrity = clamp(state.boat.hull_integrity - bomb_dmg, 0, 100)
                state.crew.health         = clamp(state.crew.health - crew_dmg, 0, 100)
                if casualties:
                    state.crew.alive = max(1, state.crew.alive - casualties)
                    print(f"  Hull -{bomb_dmg}%  |  {casualties} men lost.")
                else:
                    print(f"  Hull -{bomb_dmg}%  |  crew -{crew_dmg}%")

    add_message(state, f"Air attack. Hull: {state.boat.hull_integrity}%")
    input("  [ENTER]")


# ── EQUIPMENT FAILURE ──────────────────────────

FAILURE_TYPES = [
    {
        "name":     "TORPEDOVERSAGER",
        "desc":     "Torpedo failed to arm. Stuck in tube.",
        "effect":   lambda s: _torpedo_dud(s),
    },
    {
        "name":     "SEHROHR-SCHADEN",
        "desc":     "Periscope jammed. Field of view severely restricted.",
        "effect":   lambda s: setattr(s.boat, "periscope_ok", False),
    },
    {
        "name":     "KOMPRESSOR-AUSFALL",
        "desc":     "Air compressor failed. Oxygen levels dropping.",
        "effect":   lambda s: setattr(s.crew, "health",
                        clamp(s.crew.health - random.randint(5, 15), 0, 100)),
    },
    {
        "name":     "FUNKANLAGE BESCHÄDIGT",
        "desc":     "Radio operator cannot reach BdU. We are deaf and mute.",
        "effect":   lambda s: setattr(s.boat, "radio_ok", False),
    },
    {
        "name":     "DIESELAUSFALL",
        "desc":     "Port diesel engine out. Half speed only.",
        "effect":   lambda s: setattr(s.nav, "speed_knots",
                        max(4, s.nav.speed_knots - 4)),
    },
    {
        "name":     "RUMPFLECK",
        "desc":     "Small pressure leak detected. Pumps working to compensate.",
        "effect":   lambda s: setattr(s.boat, "hull_integrity",
                        clamp(s.boat.hull_integrity - random.randint(5, 12), 0, 100)),
    },
]

def event_equipment_failure(state: GameState):
    _event_header("MASCHINENRAUM — EQUIPMENT FAILURE")

    failure = random.choice(FAILURE_TYPES)
    delay_print(f"  Report: {failure['name']}")
    print(f"  {failure['desc']}")
    print()

    failure["effect"](state)

    repair_chance = (state.crew.health / 100) * 0.6 + (state.crew.morale / 100) * 0.2
    repaired = random.random() < repair_chance

    if failure["name"] == "FUNKANLAGE BESCHÄDIGT":
        print()
        print("  Radio operator tries to raise BdU...")
        time.sleep(1.0)
        print("  Static. Nothing.")
        time.sleep(1.5)
        print("  More static.")
        time.sleep(1.5)
        print("  We are deaf and mute.")
        time.sleep(0.5)
    else:
        print(f"  Chief engineer working on repair...")
    time.sleep(1)

    if repaired:
        print(f"  Repair successful. Systems restored.")
        state.boat.periscope_ok = True
        state.boat.radio_ok     = True
        state.nav.speed_knots   = min(8, state.nav.speed_knots + 2)
    else:
        print(f"  Repair failed. Operating with reduced capability.")
        state.boat.engine_status = "DAMAGED"
        state.crew.morale = clamp(state.crew.morale - 5, 0, 100)

    add_message(state, f"Failure: {failure['name']}. Repaired: {'yes' if repaired else 'no'}.")
    input("  [ENTER]")


def _torpedo_dud(state: GameState):
    """torpedo stuck in tube. dangerous."""
    print("  ! Torpedo jammed in tube. Dangerous situation.")
    if random.random() < 0.15:
        dmg = random.randint(10, 25)
        state.boat.hull_integrity = clamp(state.boat.hull_integrity - dmg, 0, 100)
        print(f"  !! Premature detonation — hull -{dmg}%")
    else:
        if state.boat.torpedoes > 0:
            state.boat.torpedoes -= 1
            print("  Torpedo jettisoned overboard. Lost.")


# ── CREW INJURY ────────────────────────────────

INJURY_EVENTS = [
    ("MECHANIKER VERLETZT", "Steam accident in the engine room. Bad burns.", 10, 5),
    ("STURZ", "Man down from rough seas. Broken ribs.", 8, 8),
    ("ERKRANKUNG", "Stomach illness spreading. 6 men affected.", 12, 15),
    ("KOPFVERLETZUNG", "Hatch cover. Unconscious. Stable for now.", 5, 5),
    ("FIEBER", "Unknown illness. High fever. No doctor aboard.", 15, 20),
]

def event_crew_injury(state: GameState):
    _event_header("SANITÄTER — MEDICAL REPORT")

    name, desc, health_loss, morale_loss = random.choice(INJURY_EVENTS)
    delay_print(f"  {name}: {desc}")
    print()

    state.crew.health = clamp(state.crew.health - health_loss, 0, 100)
    state.crew.morale = clamp(state.crew.morale - morale_loss, 0, 100)

    if state.supplies.medkit > 0:
        print(f"  Medical kit available ({state.supplies.medkit} units remaining).")
        print("  Administer treatment? [Y/N]")
        if input("  > ").strip().lower() == "y":
            state.supplies.medkit -= 1
            recover = random.randint(5, health_loss)
            state.crew.health = clamp(state.crew.health + recover, 0, 100)
            state.crew.morale = clamp(state.crew.morale + 5, 0, 100)
            print(f"  Treatment effective. Health +{recover}%")
    else:
        print("  No medical supplies. Man suffers.")

    if state.crew.health < 20 and random.random() < 0.2:
        state.crew.alive = max(1, state.crew.alive - 1)
        print("  !! Man succumbed to his injuries.")
        state.crew.morale = clamp(state.crew.morale - 15, 0, 100)

    add_message(state, f"Injury: {name}. Health: {state.crew.health}%")
    input("  [ENTER]")


# ── WEATHER STORM ──────────────────────────────

STORM_DESCS = [
    "Atlantic storm. Force 9. Swells of 8 metres.",
    "Storm from northwest. Boat rolling badly. Zero visibility.",
    "Hurricane-force gusts. Man overboard? No — grabbed the rail.",
    "Near-typhoon conditions. Engine on half power.",
]

def event_weather_storm(state: GameState):
    _event_header("WETTERMELDUNG — STORM")

    desc = random.choice(STORM_DESCS)
    delay_print(f"  {desc}")
    print()

    if not state.boat.surfaced:
        print("  Submerged. Storm barely felt. Downside: speed reduced.")
        state.nav.speed_knots = max(2, state.nav.speed_knots - 2)
        print(f"  Speed reduced to {state.nav.speed_knots} knots.")
    else:
        options = [
            ("1", "Push through — hold course"),
            ("2", "Dive — ride it out below"),
        ]
        choice = _choice_prompt(options)

        if choice == "1":
            dmg  = random.randint(3, 12)
            fdmg = random.randint(5, 10)
            state.boat.hull_integrity = clamp(state.boat.hull_integrity - dmg, 0, 100)
            state.boat.fuel           = clamp(state.boat.fuel - fdmg, 0, 100)
            state.crew.morale         = clamp(state.crew.morale - 10, 0, 100)
            state.crew.fatigue        = clamp(state.crew.fatigue + 15, 0, 100)
            print(f"  Fought through. Hull -{dmg}%  Fuel -{fdmg}%  Fatigue +15%")
        else:
            state.boat.surfaced      = False
            state.boat.current_depth = 40
            state.boat.battery       = clamp(state.boat.battery - 15, 0, 100)
            print("  Dived. Storm above us. Battery draining.")
            print(f"  Battery: {state.boat.battery}%")

    add_message(state, "Storm weathered.")
    input("  [ENTER]")


# ── RADIO ORDERS (BdU MESSAGE) ─────────────────

BDU_ORDER_TYPES = [
    {
        "subject": "NEUE ZUWEISUNG",
        "lines": lambda s: [
            "DUE TO ENEMY ACTIVITY, YOUR OPERATIONAL AREA IS BEING REASSIGNED.",
            f"NEW PLANQUADRAT: {chr(64+random.randint(1,10))}{random.randint(1,9)}.",
            "ALL PREVIOUS ORDERS ARE HEREBY CANCELLED.",
            "DELAY IS UNACCEPTABLE. DEPART IMMEDIATELY.",
            "SIEG HEIL.",
        ]
    },
    {
        "subject": "GROSSER KONVOI GEMELDET",
        "lines": lambda s: [
            "RECONNAISSANCE REPORTS: LARGE CONVOY. 20+ SHIPS.",
            f"LAST KNOWN POSITION: {chr(64+random.randint(1,10))}{random.randint(1,6)}.",
            "COURSE: EAST. ALL AVAILABLE BOATS ARE BEING REDIRECTED.",
            f"TONNAGE TARGET FOR THIS PATROL: {s.stats.tonnage_quota:,} GRT. DO NOT FALL SHORT.",
            "THE FATHERLAND COUNTS ON YOU.",
            "SIEG HEIL.",
        ]
    },
    {
        "subject": "WARNUNG: NEUE ALLIERTE TAKTIK",
        "lines": lambda s: [
            "ENEMY AIRCRAFT NOW EQUIPPED WITH NEW RADAR SYSTEMS.",
            "SURFACE RUNNING DURING DAYLIGHT HOURS MUST BE MINIMISED.",
            "NIGHT TRANSITS RECOMMENDED. EXERCISE EXTREME CAUTION.",
            "SEVERAL BOATS LOST IN SECTOR 7. CAUSE UNKNOWN.",
            "ADAPT OR DIE. SIEG HEIL.",
        ]
    },
    {
        "subject": "VERSENKUNGSBESTAETIGUNG",
        "lines": lambda s: [
            f"YOUR LAST TRANSMISSION CONFIRMED: {s.stats.ships_sunk} SHIPS.",
            f"TONNAGE ACKNOWLEDGED: {s.stats.tonnage_sunk:,} GRT.",
            "BdU EXPECTS CONTINUED RESULTS.",
            "FIGHT ON. GERMANY NEEDS YOU.",
            "SIEG HEIL.",
        ]
    },
    {
        "subject": "ALLGEMEINE LAGE",
        "lines": lambda s: [
            "THE BATTLE OF THE ATLANTIC INTENSIFIES.",
            "ENEMY CONVOY SYSTEMS CONTINUE TO IMPROVE.",
            "NEW U-BOATS ARE ENTERING SERVICE.",
            "HOLD THE LINE. VICTORY IS WITHIN OUR GRASP.",
            "SIEG HEIL. DEUTSCHLAND UEBER ALLES.",
        ]
    },
]

def event_radio_orders(state: GameState):
    _event_header("FUNKRAUM — INCOMING TRANSMISSION")

    if not state.boat.radio_ok:
        print("  Radio damaged. Message not receivable.")
        input("  [ENTER]")
        return

    order = random.choice(BDU_ORDER_TYPES)
    lines = order["lines"](state)

    show_radiogram(
        from_   = "BdU LORIENT // KAdm. DOENITZ",
        to_     = f"{state.u_boat_name} // {state.commander}",
        body_lines = lines,
        classification = "DRINGEND GEHEIM"
    )

    if order["subject"] == "NEUE ZUWEISUNG":
        new_x = random.randint(1, 10)
        new_y = random.randint(1, 6)
        state.nav.patrol_zone = (new_x, new_y)
        print(f"  New patrol zone logged: {chr(64+new_x)}{new_y}")

    add_message(state, f"Radio order: {order['subject']}")
    input("  [ENTER]")


# ── WOLFPACK SIGNAL ────────────────────────────

def event_wolfpack_signal(state: GameState):
    _event_header("WOLFPACK — FUNKKONTAKT")

    other_boat = random.choice(["U-47", "U-99", "U-100", "U-110", "U-552", "U-331"])
    if other_boat == state.u_boat_name:
        other_boat = "U-403"

    delay_print(f"  Radio contact: {other_boat}. Same operational area.")
    print()

    show_radiogram(
        from_   = other_boat,
        to_     = state.u_boat_name,
        body_lines=[
            "HABE KONVOI GESICHTET. ANGRIFF GEPLANT.",
            f"POSITION: {chr(64+random.randint(1,10))}{random.randint(1,8)}.",
            "KOORDINIERTER ANGRIFF EMPFOHLEN.",
            "WARTET AUF EUREN ANGRIFF VON STEUERBORD.",
            "ZUSAMMEN SIND WIR STAERKER.",
        ],
        classification="DRINGEND"
    )

    options = [
        ("1", "Join the wolfpack — coordinated attack"),
        ("2", "Decline — continue own patrol"),
    ]
    choice = _choice_prompt(options)

    if choice == "1":
        print()
        delay_print("  Wolfpack coordination active. Combined attack...")
        time.sleep(1)
        n_ships = random.randint(2, 5)
        for _ in range(n_ships):
            tonnage = random.randint(3000, 12000)
            state.stats.ships_sunk   += 1
            state.stats.tonnage_sunk += tonnage
            state.stats.torpedoes_fired += 1
            if state.boat.torpedoes > 0:
                state.boat.torpedoes -= 1
            print(f"  SUNK (WOLFPACK): {tonnage:,} GRT")
        state.crew.morale = clamp(state.crew.morale + 10, 0, 100)
        print(f"\n  Wolfpack attack: {n_ships} ships sunk.")
        print("  !! Heavy escort response — destroyers hunting the pack.")
        time.sleep(0.8)
        if random.random() < 0.7:
            event_destroyer_contact(state)
    else:
        delay_print("  Wolfpack declined. Continuing own patrol.")

    add_message(state, f"Wolfpack contact with {other_boat}.")
    input("  [ENTER]")


# ── GHOST CONTACT (FOUND NOTHING) ─────────────

GHOST_TEXTS = [
    "Hours of searching. No enemy ships. Just ocean.",
    "Sonar contact was false. A whale. Not a tanker.",
    "Lookout reported masts. Nothing. Maybe exhaustion.",
    "Convoy route found abandoned. They changed course.",
    "Three days on station. Not one ship. The ocean mocks us.",
    "Radio signals led nowhere. False bearing.",
    "Fog. Silence. Water sounds. No enemy.",
    "Target evaded by course change. Their luck. This time.",
]

def event_ghost_contact(state: GameState):
    _event_header("KONTAKT — SEARCH UNSUCCESSFUL")

    text = random.choice(GHOST_TEXTS)
    print()
    delay_print(f"  {text}")
    print()

    time_lost = random.randint(8, 24)
    state.nav.hours_at_sea += time_lost
    state.nav.patrol_day   += time_lost // 24

    food_cost  = random.randint(3, 8)
    fuel_cost  = random.randint(5, 12)
    state.supplies.food = clamp(state.supplies.food - food_cost, 0, 100)
    state.boat.fuel     = clamp(state.boat.fuel - fuel_cost, 0, 100)
    state.crew.morale   = clamp(state.crew.morale - 8, 0, 100)
    state.crew.fatigue  = clamp(state.crew.fatigue + 10, 0, 100)

    print(f"  Time lost  : {time_lost} hours")
    print(f"  Food -     : {food_cost}%")
    print(f"  Fuel -     : {fuel_cost}%")
    print(f"  Morale     : {state.crew.morale}%")
    print()
    print("  That's the war.")

    add_message(state, "Search unsuccessful. No ships found.")


# ── SUPPLY FIND ────────────────────────────────

def event_supply_find(state: GameState):
    _event_header("FUND — ABANDONED VESSEL")

    delay_print("  Abandoned ship sighted. No crew. Hatch open.")
    print()

    food_gain  = random.randint(10, 30)
    water_gain = random.randint(10, 20)
    med_gain   = random.randint(1, 3)

    print("  Boarding party reports supplies:")
    print(f"  + Food    : {food_gain}%")
    print(f"  + Water   : {water_gain}%")
    print(f"  + Med kits: {med_gain}")
    print()
    print("  Take the supplies? [Y/N]")

    if input("  > ").strip().lower() == "y":
        state.supplies.food   = clamp(state.supplies.food + food_gain, 0, 100)
        state.supplies.water  = clamp(state.supplies.water + water_gain, 0, 100)
        state.supplies.medkit += med_gain
        state.crew.morale     = clamp(state.crew.morale + 10, 0, 100)
        print("  Supplies loaded. Mood improved.")
    else:
        print("  Supplies left. Honor the enemy.")

    add_message(state, "Abandoned ship looted.")


# ── MORALE EVENT ───────────────────────────────

MORALE_GOOD = [
    ("GEBURTSTAG", "Machinist Klein turns 24. Last tins shared with the crew.", +15),
    ("BRIEF VON ZUHAUSE", "Mail delivered by the last supply boat. Letters from home.", +20),
    ("GUTES ESSEN", "Chief cook found reserve provisions. Hot food tonight.", +10),
    ("RUHIGE SEE", "Three hours of calm weather. Men breathe again.", +8),
    ("ERFOLG ERZÄHLT", "Radio operator picks up BBC report: U-boats sinking tonnage. Pride.", +12),
]

MORALE_BAD = [
    ("HEIMWEH", "Silence in the boat. Men thinking of home.", -10),
    ("SCHLECHTE NACHRICHTEN", "Radio operator intercepted a message. Another boat lost.", -15),
    ("ENGE", "42 days in this tube. Men starting to argue.", -12),
    ("GESTANK", "Air in the boat is heavy. No sea breeze. For weeks.", -8),
    ("WACHTRAUM GEDANKEN", "Lookout is seeing things in the haze. Exhaustion.", -10),
]

def event_morale_event(state: GameState):
    _event_header("BESATZUNG — CREW REPORT")

    if state.nav.patrol_day > 20 or state.crew.morale < 50:
        event_pool = MORALE_BAD + MORALE_GOOD[:2]
    else:
        event_pool = MORALE_GOOD + MORALE_BAD[:2]

    name, desc, morale_delta = random.choice(event_pool)
    delay_print(f"  {name.upper()}: {desc}")
    print()

    state.crew.morale = clamp(state.crew.morale + morale_delta, 0, 100)
    sign = "+" if morale_delta > 0 else ""
    print(f"  Morale: {sign}{morale_delta}%  →  {state.crew.morale}%")

    if morale_delta > 0 and state.crew.fatigue > 20:
        fatigue_recover = random.randint(5, 15)
        state.crew.fatigue = clamp(state.crew.fatigue - fatigue_recover, 0, 100)
        print(f"  Rest bonus: fatigue -{fatigue_recover}%")

    add_message(state, f"Morale event: {name}. Morale: {state.crew.morale}%")


# ── UTILITIES ──────────────────────────────────

def _random_equipment_damage(state: GameState):
    """called as a side effect of depth charge hits etc."""
    equipment_failures = [
        ("periscope",  lambda s: setattr(s.boat, "periscope_ok", False)),
        ("radio",      lambda s: setattr(s.boat, "radio_ok", False)),
        ("diesel engine", lambda s: setattr(s.nav, "speed_knots",
                            max(4, s.nav.speed_knots - 3))),
    ]
    name, effect = random.choice(equipment_failures)
    effect(state)
    print(f"  ! Collateral damage: {name} offline.")
