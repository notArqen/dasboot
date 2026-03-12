"""
U-BOOT COMMAND — CORE GAME ENGINE
engine.py: game state, turn loop, event queue, save/load system

all the boring stuff that makes the exciting stuff possible.
"""

import json
import os
import random
import time
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime

# ─────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────

GAME_VERSION = "0.1.0"
SAVE_FILE    = "uboot_save.json"

# Type VIIC u-boat loadout (historically accurate-ish)
TORPEDO_CAPACITY   = 14
FUEL_CAPACITY      = 100   # % units
BATTERY_CAPACITY   = 100   # % units
FOOD_CAPACITY      = 100   # % (6-week patrol supply)
WATER_CAPACITY     = 100   # %
CREW_SIZE          = 44    # typical VIIC crew

CRUSH_DEPTH        = 280   # meters — below this you're a tin can
SAFE_DIVE_DEPTH    = 200   # meters — above this you're probably fine
PERISCOPE_DEPTH    = 12    # meters

# Patrol zones on a simplified 10x10 grid (North Atlantic theater)
GRID_SIZE          = 10

# ─────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────

@dataclass
class BoatStatus:
    """the physical state of U-Boot. treat her well. she's all you've got."""
    hull_integrity: int   = 100   # 0 = dead
    current_depth:  int   = 0     # meters (0 = surface)
    fuel:           int   = 100   # % of tank
    battery:        int   = 100   # % charge
    torpedoes:      int   = TORPEDO_CAPACITY
    torpedoes_aft:  int   = 2     # aft tubes (VIIC had 1 aft; we give 2 for gameplay)
    diving:         bool  = False
    surfaced:       bool  = True
    engine_status:  str   = "OPERATIONAL"   # OPERATIONAL / DAMAGED / CRITICAL
    periscope_ok:   bool  = True
    radio_ok:       bool  = True

@dataclass
class CrewStatus:
    """44 men in a metal tube. what could go wrong."""
    total:       int = CREW_SIZE
    alive:       int = CREW_SIZE
    health:      int = 100   # 0–100 average crew health
    morale:      int = 75    # 0–100; high = efficient, low = mutiny-adjacent
    fatigue:     int = 0     # 0–100; high = errors increase

@dataclass
class Supplies:
    """rations: real concern on 6-week patrols. run out = very bad."""
    food:   int = 100   # % of initial supply
    water:  int = 100   # % of initial supply
    medkit: int = 5     # discrete units

@dataclass
class Navigation:
    """where you are, where you're going, what you know."""
    grid_x:       int   = 5    # current position on 10x10 grid
    grid_y:       int   = 9    # start near port (bottom of map)
    heading:      int   = 0    # degrees (0=N, 90=E, 180=S, 270=W)
    speed_knots:  int   = 8    # surface speed (max ~17kts, submerged ~7kts)
    patrol_zone:  Optional[tuple] = None   # target grid square
    hours_at_sea: int   = 0
    patrol_day:   int   = 1

@dataclass
class MissionStats:
    """the ledger. BdU is watching."""
    tonnage_sunk:     int = 0     # gross register tons
    ships_sunk:       int = 0
    ships_damaged:    int = 0
    torpedoes_fired:  int = 0
    depth_charges_survived: int = 0
    patrol_number:    int = 1
    tonnage_quota:    int = 20000  # BdU's demanded minimum for this patrol

@dataclass
class GameState:
    """the whole enchilada. everything worth knowing about your current patrol."""
    boat:       BoatStatus  = field(default_factory=BoatStatus)
    crew:       CrewStatus  = field(default_factory=CrewStatus)
    supplies:   Supplies    = field(default_factory=Supplies)
    nav:        Navigation  = field(default_factory=Navigation)
    stats:      MissionStats= field(default_factory=MissionStats)

    # meta
    u_boat_name:    str  = "U-96"     # famous. also the das boot boat. fitting.
    commander:      str  = "KPTLT. UNKNOWN"
    game_over:      bool = False
    victory:        bool = False
    game_over_msg:  str  = ""

    # event queue — things that are "in progress" across turns
    pending_events:    list = field(default_factory=list)
    turns_since_event: int  = 0   # force an event if this gets too high
    # recent contact: set by convoy events so torpedo screen knows what's out there
    # {"type": "CONVOY", "ships": 4, "escorts": 2, "distance": 800, "turns_ago": 0}
    recent_contact: dict = field(default_factory=dict)

    # log of recent messages shown to player
    message_log: list = field(default_factory=list)

# ─────────────────────────────────────────────
#  SAVE / LOAD
# ─────────────────────────────────────────────

def save_game(state: GameState) -> bool:
    """persist state to disk. because dying due to power outage is dishonorable."""
    try:
        data = {
            "version":   GAME_VERSION,
            "timestamp": datetime.now().isoformat(),
            "state":     asdict(state)
        }
        with open(SAVE_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"  [SAVE ERROR] {e}")
        return False

def load_game() -> Optional[GameState]:
    """resurrect a previous patrol. assuming you didn't sink."""
    if not os.path.exists(SAVE_FILE):
        return None
    try:
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)

        s = data["state"]

        # rebuild dataclasses from dict (json flattens them)
        state = GameState(
            boat     = BoatStatus(**s["boat"]),
            crew     = CrewStatus(**s["crew"]),
            supplies = Supplies(**s["supplies"]),
            nav      = Navigation(**{k: tuple(v) if isinstance(v, list) else v
                                     for k, v in s["nav"].items()}),
            stats    = MissionStats(**s["stats"]),
            u_boat_name    = s["u_boat_name"],
            commander      = s["commander"],
            game_over      = s["game_over"],
            victory        = s["victory"],
            game_over_msg  = s["game_over_msg"],
            pending_events = s.get("pending_events", []),
            turns_since_event = s.get("turns_since_event", 0),
            recent_contact = s.get("recent_contact", {}),
            message_log    = s.get("message_log", []),
        )
        return state
    except Exception as e:
        print(f"  [LOAD ERROR] file corrupted or wrong version: {e}")
        return None

# ─────────────────────────────────────────────
#  TURN MANAGEMENT
# ─────────────────────────────────────────────

HOURS_PER_TURN = 4   # each "turn" = 4 hours of patrol time

def advance_turn(state: GameState) -> list[str]:
    """
    tick the world forward by one turn (4 hours).
    returns a list of message strings describing what happened.
    called every time the player takes an action or chooses to advance time.
    """
    messages = []
    state.nav.hours_at_sea += HOURS_PER_TURN

    # every 24 hours = new day
    if state.nav.hours_at_sea % 24 == 0:
        state.nav.patrol_day += 1
        messages.append(f"  Day {state.nav.patrol_day} at sea.")

    # ── passive consumption ──────────────────
    messages += _consume_supplies(state)
    messages += _drain_battery_or_recharge(state)
    messages += _consume_fuel(state)

    # ── crew fatigue ─────────────────────────
    messages += _update_crew_fatigue(state)

    # ── check critical thresholds ────────────
    messages += _check_survival_conditions(state)

    return messages


def _consume_supplies(state: GameState) -> list[str]:
    msgs = []
    # food: ~1.67% per 4hrs for full crew (6-week supply)
    food_rate = max(1, int(state.crew.alive / CREW_SIZE * 2))
    state.supplies.food = max(0, state.supplies.food - food_rate)

    # water: slightly faster drain
    water_rate = max(1, int(state.crew.alive / CREW_SIZE * 2))
    state.supplies.water = max(0, state.supplies.water - water_rate)

    if state.supplies.food == 0:
        msgs.append("  !! NAHRUNG ERSCHOEPFT — food supply gone. Crew is starving.")
        state.crew.health  = max(0, state.crew.health  - 5)
        state.crew.morale  = max(0, state.crew.morale  - 8)

    if state.supplies.water == 0:
        msgs.append("  !! WASSER ERSCHOEPFT — water gone. This kills faster than depth charges.")
        state.crew.health  = max(0, state.crew.health  - 10)
        state.crew.morale  = max(0, state.crew.morale  - 10)

    if state.supplies.food == 15:
        msgs.append("  ! Food supply critical — 15% remaining.")
    if state.supplies.water == 15:
        msgs.append("  ! Water supply critical — 15% remaining.")

    return msgs


def _drain_battery_or_recharge(state: GameState) -> list[str]:
    msgs = []
    if not state.boat.surfaced:
        # submerged: drain battery by speed
        drain = max(3, state.nav.speed_knots)
        state.boat.battery = max(0, state.boat.battery - drain)
        if state.boat.battery == 0:
            msgs.append("  !! BATTERIE TOT — battery dead. Emergency surface.")
            state.boat.surfaced = True
            state.boat.current_depth = 0
            state.boat.battery = 5
    else:
        # surfaced: recharge diesels
        recharge = 8
        state.boat.battery = min(100, state.boat.battery + recharge)

    return msgs


def _consume_fuel(state: GameState) -> list[str]:
    msgs = []
    if state.boat.surfaced:
        # diesel burn at surface
        fuel_burn = max(1, state.nav.speed_knots // 4)
        state.boat.fuel = max(0, state.boat.fuel - fuel_burn)
        if state.boat.fuel == 0:
            msgs.append("  !! KRAFTSTOFF LEER — out of fuel. Adrift. BdU is displeased.")
        if state.boat.fuel == 20:
            msgs.append("  ! Fuel at 20% — consider returning to port.")
    return msgs


def _update_crew_fatigue(state: GameState) -> list[str]:
    msgs = []
    # fatigue builds up over time; high fatigue hurts accuracy + morale
    state.crew.fatigue = min(100, state.crew.fatigue + 2)

    if state.crew.fatigue >= 80:
        state.crew.morale = max(0, state.crew.morale - 3)
        if state.crew.fatigue == 80:
            msgs.append("  ! BESATZUNG ERSCHOEPFT — crew fatigue critical. Errors increasing.")

    if state.crew.morale < 20:
        msgs.append("  !! MORAL AM BODEN — crew is breaking. Consider aborting patrol.")

    return msgs


def _check_survival_conditions(state: GameState) -> list[str]:
    """the many ways this ends badly."""
    msgs = []

    # hull failure
    if state.boat.hull_integrity <= 0:
        state.game_over = True
        state.game_over_msg = "RUMPF GEBROCHEN. THE SEA HAS CLAIMED U-BOOT AND ALL HANDS."
        return msgs

    # crew death
    if state.crew.alive <= 0:
        state.game_over = True
        state.game_over_msg = "KEINE UEBERLEBENDEN. ALL HANDS LOST."
        return msgs

    # crew health collapse
    if state.crew.health <= 0:
        state.game_over = True
        state.game_over_msg = "BESATZUNG TOT. THE CREW HAS PERISHED FROM ILLNESS AND NEGLECT."
        return msgs

    # crush depth
    if state.boat.current_depth > CRUSH_DEPTH:
        state.game_over = True
        state.game_over_msg = f"TIEFENGRENZE UEBERSCHRITTEN BEI {state.boat.current_depth}M. HULL IMPLODED."
        return msgs

    return msgs


# ─────────────────────────────────────────────
#  EVENT SYSTEM
# ─────────────────────────────────────────────

# event types — these get populated by the event_generator module
EVENT_TYPES = [
    "CONVOY_CONTACT",       # found prey
    "DESTROYER_CONTACT",    # found trouble
    "AERIAL_PATROL",        # aircraft spotted
    "EQUIPMENT_FAILURE",    # something broke
    "CREW_INJURY",          # someone got hurt
    "WEATHER_STORM",        # surface is hell
    "RADIO_ORDERS",         # BdU has opinions
    "WOLFPACK_SIGNAL",      # other u-boats nearby
    "GHOST_CONTACT",        # you found nothing. hours wasted.
    "SUPPLY_FIND",          # rare — abandoned vessel with supplies
    "MORALE_EVENT",         # birthday, letter from home, etc.
]

def roll_event(state: GameState) -> Optional[str]:
    """
    each turn has a chance of triggering a random event.
    guaranteed to fire at least every 3 turns so the player isn't just
    watching resources drain in silence. war is not that quiet.
    """
    # age the recent contact — after 1 turn it's stale, after 2 it's gone
    if state.recent_contact:
        state.recent_contact["turns_ago"] = state.recent_contact.get("turns_ago", 0) + 1
        if state.recent_contact["turns_ago"] > 2:
            state.recent_contact = {}

    state.turns_since_event += 1

    # guaranteed event every 3 turns — the ocean does not let you rest
    force = state.turns_since_event >= 3

    base_chance = 0.55   # raised from 0.40 — things happen out here

    if state.nav.patrol_zone and (state.nav.grid_x, state.nav.grid_y) == state.nav.patrol_zone:
        base_chance += 0.20

    if state.nav.patrol_day > 20:
        base_chance += 0.10

    if not force and random.random() > base_chance:
        return None

    state.turns_since_event = 0

    weights = {
        "CONVOY_CONTACT":    15,
        "DESTROYER_CONTACT": 10,
        "AERIAL_PATROL":      8,
        "EQUIPMENT_FAILURE":  8,
        "CREW_INJURY":        6,
        "WEATHER_STORM":      8,
        "RADIO_ORDERS":      10,
        "WOLFPACK_SIGNAL":    5,
        "GHOST_CONTACT":     12,
        "SUPPLY_FIND":        2,
        "MORALE_EVENT":       8,
    }

    if state.boat.hull_integrity < 70:
        weights["EQUIPMENT_FAILURE"] += 10

    if state.nav.patrol_day > 10:
        weights["CONVOY_CONTACT"]    += 5
        weights["DESTROYER_CONTACT"] += 5

    events = list(weights.keys())
    probs  = list(weights.values())
    return random.choices(events, weights=probs, k=1)[0]


def add_message(state: GameState, msg: str):
    """add to the rolling message log (keep last 20)."""
    state.message_log.append(msg)
    if len(state.message_log) > 20:
        state.message_log.pop(0)


# ─────────────────────────────────────────────
#  UTILITY
# ─────────────────────────────────────────────

def clamp(val: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, val))

def percent_bar(val: int, width: int = 20, fill: str = "█", empty: str = "░") -> str:
    """render a simple ASCII progress bar. thrilling."""
    filled = int((val / 100) * width)
    return fill * filled + empty * (width - filled)

def status_color_tag(val: int) -> str:
    """return a text tag for health/integrity values."""
    if val > 70:  return "  [OK]"
    if val > 40:  return "  [!]  "
    if val > 20:  return "  [!!] "
    return             "  [KRIT]"

def delay_print(text: str, delay: float = 0.03):
    """typewriter effect for dramatic messages. yes, it's necessary."""
    for ch in text:
        print(ch, end="", flush=True)
        time.sleep(delay)
    print()
