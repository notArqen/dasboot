"""
U-BOOT COMMAND — MAIN GAME LOOP
main.py: player input, action menus, new game setup, run loop

entry point. start here. try not to sink.
"""

import random
import sys
from engine import (
    GameState, Navigation, save_game, load_game,
    advance_turn, roll_event, add_message,
    CRUSH_DEPTH, SAFE_DIVE_DEPTH, PERISCOPE_DEPTH,
    GRID_SIZE, clamp, delay_print
)
from display import (
    clear, show_title, render_dashboard, render_nav_map,
    render_depth_gauge, show_radiogram, patrol_orders_radiogram,
    show_torpedo_fire, show_depth_charge, show_game_over,
    show_messages, PORT_X, PORT_Y
)
from events import handle_event

# ─────────────────────────────────────────────
#  NEW GAME SETUP
# ─────────────────────────────────────────────

COMMANDER_NAMES = [
    "KPTLT. WERNER", "KPTLT. LEHMANN", "KPTLT. BRANDT",
    "KPTLT. HOFFMANN", "KPTLT. FISCHER", "OBLT. KRUEGER",
]

UBOOT_NAMES = ["U-96", "U-47", "U-99", "U-123", "U-331", "U-552", "U-571"]

def new_game() -> GameState:
    clear()
    print()
    print("  ┌─────────────────────────────────────────────────┐")
    print("  │       NEUES SPIEL — NEUE KAMPAGNE               │")
    print("  └─────────────────────────────────────────────────┘")
    print()

    # commander name
    print("  Commander name (press ENTER for random):")
    name_input = input("  > ").strip().upper()
    if not name_input:
        name_input = random.choice(COMMANDER_NAMES)
    else:
        name_input = f"KPTLT. {name_input}"

    # u-boat designation
    print()
    print("  U-Boot designation, e.g. 96 or U-96 (press ENTER for random):")
    boat_input = input("  > ").strip().upper()
    if not boat_input:
        boat_input = random.choice(UBOOT_NAMES)
    elif not boat_input.startswith("U-"):
        boat_input = f"U-{boat_input}"

    state = GameState(
        commander   = name_input,
        u_boat_name = boat_input,
    )

    print()
    print(f"  BOOT    : {state.u_boat_name}")
    print(f"  KOMM.   : {state.commander}")
    print()
    print("  ...")
    input("  Ready to deploy? [ENTER]")

    # send initial patrol orders
    _issue_patrol_orders(state)

    return state


def _issue_patrol_orders(state: GameState):
    """BdU assigns a patrol zone and tonnage quota. all-caps. no negotiation."""
    zone_x = random.randint(1, GRID_SIZE)
    zone_y = random.randint(1, 6)
    state.nav.patrol_zone = (zone_x, zone_y)

    # quota scales with patrol number — BdU gets greedier
    quota = random.randint(15000, 35000)
    quota = (quota // 1000) * 1000   # round to nearest 1000 GRT
    state.stats.tonnage_quota = quota

    clear()
    show_radiogram(
        from_  = "BdU LORIENT",
        to_    = f"{state.u_boat_name} // {state.commander}",
        body_lines = patrol_orders_radiogram(state, (zone_x, zone_y), quota),
        classification = "STRENG GEHEIM"
    )
    input("  [ENTER — ACKNOWLEDGE ORDERS]")

# ─────────────────────────────────────────────
#  MAIN MENU
# ─────────────────────────────────────────────

def main_menu() -> str:
    print()
    print("  ┌─── BEFEHLSSTAND ─────────────────────────────────────┐")
    print("  │  [1] KURS SETZEN    Navigate / Plot Course           │")
    print("  │  [2] TAUCHEN        Dive / Surface                   │")
    print("  │  [3] TORPEDO FEUER  Fire Torpedoes                   │")
    print("  │  [4] SEEKARTE       Navigation Map                   │")
    print("  │  [5] TIEFENMESSER   Depth Gauge                      │")
    print("  │  [6] WARTEN         Advance Time  (+4 hrs)           │")
    print("  │  [7] SPEICHERN      Save Game                        │")
    print("  │  [8] HAFEN          Return to Port                   │")
    print("  │  [Q] AUFGEBEN       Quit                             │")
    print("  └──────────────────────────────────────────────────────┘")
    print()
    choice = input("  > ").strip().lower()
    return choice

# ─────────────────────────────────────────────
#  ACTION HANDLERS
# ─────────────────────────────────────────────

def action_navigate(state: GameState):
    """plot a course. the map awaits."""
    clear()
    render_nav_map(state)
    print("  Plot course — enter grid coordinates:")
    print("  e.g. 'C4' = column C, row 4  |  your patrol zone shown as X")
    print("  [ENTER to cancel]")
    print()
    raw = input("  Destination > ").strip().upper()
    if not raw:
        return

    try:
        col = ord(raw[0]) - 64
        row = int(raw[1:])
        if not (1 <= col <= GRID_SIZE and 1 <= row <= GRID_SIZE):
            raise ValueError
    except (ValueError, IndexError):
        print("  Invalid coordinates.")
        input("  [ENTER]")
        return

    dx = abs(col - state.nav.grid_x)
    dy = abs(row - state.nav.grid_y)
    distance = max(dx + dy, 1)
    fuel_cost = distance * 3

    print()
    print(f"  Distance: {distance} grid squares  //  Estimated fuel cost: {fuel_cost}%")

    if fuel_cost > state.boat.fuel:
        print("  !! Insufficient fuel for this route.")
        input("  [ENTER]")
        return

    print(f"  Confirm course to {raw}? [Y/N]")
    confirm = input("  > ").strip().lower()
    if confirm != "y":
        print("  Cancelled.")
        input("  [ENTER]")
        return

    messages = []
    print()
    print(f"  Underway to {raw}...")

    while (state.nav.grid_x, state.nav.grid_y) != (col, row):
        # step toward target
        if state.nav.grid_x < col:
            state.nav.grid_x += 1
            state.nav.heading = 90
        elif state.nav.grid_x > col:
            state.nav.grid_x -= 1
            state.nav.heading = 270
        elif state.nav.grid_y < row:
            state.nav.grid_y += 1
            state.nav.heading = 180
        else:
            state.nav.grid_y -= 1
            state.nav.heading = 0

        # each grid square = one turn (4 hrs)
        turn_msgs = advance_turn(state)
        messages += turn_msgs

        # chance of event during transit
        event_type = roll_event(state)
        if event_type:
            print()
            print(f"  >> KONTAKT — {event_type}")
            handle_event(state, event_type)

        if state.game_over:
            break

    if not state.game_over:
        print(f"  Position reached: {raw}")

    if messages:
        print()
        show_messages(messages)

    input("  [ENTER]")


def action_dive_surface(state: GameState):
    """depth management. don't get too comfortable down there."""
    clear()
    b = state.boat
    render_depth_gauge(b.current_depth)
    print()
    print("  TAUCHEN — Dive Commands:")
    print("  [1] Surface")
    print("  [2] Periscope depth — 12m")
    print("  [3] Standard dive — 50m")
    print("  [4] Deep — 150m")
    print("  [5] Emergency deep — 200m")
    print("  [6] Manual depth entry")
    print()
    choice = input("  > ").strip()

    depth_map = {"1": 0, "2": 12, "3": 50, "4": 150, "5": 200}

    if choice in depth_map:
        target = depth_map[choice]
    elif choice == "6":
        try:
            target = int(input("  Depth in meters > ").strip())
        except ValueError:
            print("  Invalid.")
            input("  [ENTER]")
            return
    else:
        return

    if target > CRUSH_DEPTH:
        print(f"  !! {target}m exceeds crush depth ({CRUSH_DEPTH}m).")
        print("  Hydraulic pressure will destroy the hull.")
        confirm = input("  Proceed anyway? This is suicide. [Y/N] > ").strip().lower()
        if confirm != "y":
            return

    state.boat.current_depth = target
    state.boat.surfaced       = (target == 0)
    state.boat.diving         = (target > 0)

    print(f"  Depth set: {target}m")

    if target > SAFE_DIVE_DEPTH:
        dmg = random.randint(2, 8)
        state.boat.hull_integrity = clamp(state.boat.hull_integrity - dmg, 0, 100)
        print(f"  ! Hull pressure stress — damage: -{dmg}%")

    if target > CRUSH_DEPTH:
        state.boat.hull_integrity = 0
        state.game_over = True
        state.game_over_msg = f"TIEFENGRENZE UEBERSCHRITTEN BEI {target}M. ALLE MANN VERLOREN."

    input("  [ENTER]")


def action_combat(state: GameState):
    """fire torpedos. the whole reason you're out here."""
    clear()
    b = state.boat
    rc = state.recent_contact   # recent contact data if available

    if b.torpedoes <= 0 and b.torpedoes_aft <= 0:
        print("  No torpedoes remaining. Return to port recommended.")
        input("  [ENTER]")
        return

    print("  ┌─── TORPEDOANGRIFF — TORPEDO ATTACK ────────────────┐")
    print(f"  │  Bow tubes: {b.torpedoes}/{12}   Aft tubes: {b.torpedoes_aft}/2                    │")
    print("  └─────────────────────────────────────────────────────┘")
    print()

    # show contact intel if fresh (within 1 turn)
    if rc and rc.get("turns_ago", 99) <= 1:
        ctype = rc.get("type", "UNKNOWN")
        print(f"  !! ACTIVE CONTACT — {ctype} within engagement range:")
        print(f"     Ships   : {rc.get('ships', '?')}")
        print(f"     Escorts : {rc.get('escorts', '?')}")
        print(f"     Distance: ~{rc.get('distance', '?')}m")
        print(f"     Visibility: {rc.get('visibility', 'unknown')}")
        print()
        suggested_dist = rc.get("distance", 800)
    elif rc and rc.get("turns_ago", 99) == 2:
        print(f"  ! Last known contact ({rc.get('type','?')}) — {rc.get('turns_ago')} turns ago.")
        print(f"    May have moved. Last distance ~{rc.get('distance','?')}m.")
        print()
        suggested_dist = rc.get("distance", 800)
    else:
        print("  No recent contact data. Firing blind.")
        print("  You can still fire if a target is visually confirmed.")
        print()
        suggested_dist = 800

    print("  [1] Fire bow tube (forward)")
    print("  [2] Fire aft tube (rear)")
    print("  [ENTER to cancel]")
    print()
    choice = input("  > ").strip()

    if choice == "1":
        if b.torpedoes <= 0:
            print("  Bow tubes empty.")
            input("  [ENTER]")
            return
        tube = "bow"
    elif choice == "2":
        if b.torpedoes_aft <= 0:
            print("  Aft tubes empty.")
            input("  [ENTER]")
            return
        tube = "aft"
    else:
        return

    print()
    print(f"  Estimated distance in meters (200–2000) [suggest: {suggested_dist}]")
    try:
        raw = input("  > ").strip()
        distance = int(raw) if raw else suggested_dist
        distance = clamp(distance, 200, 2000)
    except ValueError:
        distance = suggested_dist

    # hit calculation — factors: distance, crew skill (morale/health), fatigue
    base_hit = 0.65
    dist_penalty   = (distance - 200) / 2000 * 0.3
    morale_bonus   = (state.crew.morale / 100) * 0.15
    fatigue_penalty= (state.crew.fatigue / 100) * 0.20
    hit_chance     = base_hit - dist_penalty + morale_bonus - fatigue_penalty
    hit_chance     = clamp(int(hit_chance * 100), 10, 90) / 100

    # fire
    if tube == "bow":
        b.torpedoes -= 1
    else:
        b.torpedoes_aft -= 1
    state.stats.torpedoes_fired += 1

    hit = random.random() < hit_chance
    show_torpedo_fire(hit, distance)

    if hit:
        # random ship class with tonnage
        ship_types = [
            ("FRACHTER",      random.randint(3000, 8000)),
            ("TANKER",        random.randint(6000, 14000)),
            ("TRUPPENTRANSP", random.randint(8000, 20000)),
            ("ZERSTOERER",    random.randint(1500, 3000)),
        ]
        ship_name, tonnage = random.choice(ship_types)
        state.stats.ships_sunk   += 1
        state.stats.tonnage_sunk += tonnage
        print(f"  SHIP SUNK: {ship_name} — {tonnage:,} GRT")
        print(f"  Total tonnage: {state.stats.tonnage_sunk:,} GRT")

        if random.random() < 0.6:
            print()
            print("  ! Escort destroyer responding — possible pursuit.")
            handle_event(state, "DESTROYER_CONTACT")
    else:
        print(f"  Hit probability was {hit_chance:.0%}. Not your day.")

    input("  [ENTER]")


def action_return_to_port(state: GameState):
    """go home. if home is still there."""
    clear()
    ms    = state.stats
    quota = ms.tonnage_quota
    pct   = ms.tonnage_sunk / quota if quota > 0 else 0

    # rating based on quota completion
    if pct >= 1.5:
        rating, verdict = "OUTSTANDING", "Ace performance. BdU commends you."
    elif pct >= 1.0:
        rating, verdict = "SUCCESS", "Quota met. Acceptable patrol."
    elif pct >= 0.6:
        rating, verdict = "MARGINAL", "Below quota. BdU is displeased."
    elif pct >= 0.25:
        rating, verdict = "FAILURE", "Well short of target. Expect consequences."
    else:
        rating, verdict = "DISGRACE", "You sank almost nothing. A waste of a submarine."

    print()
    print("  HAFEN -- Return to Port (Lorient)")
    print()
    print(f"  Ships sunk     : {ms.ships_sunk}")
    print(f"  Tonnage sunk   : {ms.tonnage_sunk:,} GRT")
    print(f"  Quota          : {quota:,} GRT")
    print(f"  Quota achieved : {pct*100:.0f}%")
    print(f"  Rating         : {rating}")
    print(f"  Verdict        : {verdict}")
    print(f"  Days at sea    : {state.nav.patrol_day}")
    print()

    state.victory = pct >= 1.0
    state.game_over_msg = (
        f"RÜCKKEHR NACH LORIENT. {ms.tonnage_sunk:,} GRT / {quota:,} GRT QUOTA. "
        f"RATING: {rating}. {verdict}"
    )

    print("  Confirm return to Lorient? [Y/N]")
    if input("  > ").strip().lower() == "y":
        state.game_over = True

# ─────────────────────────────────────────────
#  MAIN RUN LOOP
# ─────────────────────────────────────────────

def run():
    show_title()

    print("  [1] New Game")
    print("  [2] Load Game")
    print("  [Q] Quit")
    print()
    choice = input("  > ").strip().lower()

    if choice == "2":
        state = load_game()
        if not state:
            print("  No save found. Starting new game.")
            input("  [ENTER]")
            state = new_game()
    elif choice == "q":
        sys.exit(0)
    else:
        state = new_game()

    # ── main loop ─────────────────────────────
    while not state.game_over:
        clear()
        render_dashboard(state)

        # show any pending messages
        if state.message_log:
            print("  Recent log:")
            for m in state.message_log[-3:]:
                print(f"  {m}")
            print()

        action = main_menu()

        if action == "1":
            action_navigate(state)
        elif action == "2":
            action_dive_surface(state)
        elif action == "3":
            action_combat(state)
        elif action == "4":
            clear()
            render_nav_map(state)
            input("  [ENTER]")
        elif action == "5":
            clear()
            render_depth_gauge(state.boat.current_depth)
            input("  [ENTER]")
        elif action == "6":
            # advance time without moving
            msgs = advance_turn(state)
            event_type = roll_event(state)
            if event_type:
                handle_event(state, event_type)
            show_messages(msgs)
            input("  [ENTER]")
        elif action == "7":
            if save_game(state):
                print("  Game saved.")
            else:
                print("  Save failed.")
            input("  [ENTER]")
        elif action == "8":
            action_return_to_port(state)
        elif action == "q":
            print("  Abandon patrol? [Y/N]")
            if input("  > ").strip().lower() == "y":
                state.game_over     = True
                state.game_over_msg = "PATROL ABGEBROCHEN. KEIN KOMMENTAR."
        else:
            pass  # invalid input. quietly ignore. like BdU ignores bad news.

    # ── game over ────────────────────────────
    clear()
    show_game_over(state)
    print()
    input("  [ENTER to exit]")

# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    run()
