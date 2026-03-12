"""
U-BOOT COMMAND — DISPLAY MODULE
display.py: all ASCII art, status panels, UI rendering, radiogram printer

the visual soul of this operation. which is saying something
for a game played entirely in a terminal.
"""

import os
import time
from engine import (
    GameState, BoatStatus, CrewStatus, Supplies, Navigation,
    percent_bar, status_color_tag, delay_print,
    CRUSH_DEPTH, SAFE_DIVE_DEPTH,
    PERISCOPE_DEPTH, GRID_SIZE, TORPEDO_CAPACITY
)

# ─────────────────────────────────────────────
#  TERMINAL HELPERS
# ─────────────────────────────────────────────

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def hr(char: str = "─", width: int = 60) -> str:
    return char * width

def center(text: str, width: int = 60) -> str:
    return text.center(width)

def box(lines: list[str], width: int = 60) -> str:
    """wrap lines in a simple box. elegant? no. functional? barely."""
    inner_w = width - 2
    top    = "┌" + "─" * inner_w + "┐"
    bottom = "└" + "─" * inner_w + "┘"
    mid    = ["│" + line.ljust(inner_w) + "│" for line in lines]
    return "\n".join([top] + mid + [bottom])

# ─────────────────────────────────────────────
#  TITLE SCREEN
# ─────────────────────────────────────────────

TITLE_ART = r"""
  ██╗   ██╗      ██████╗  ██████╗  ██████╗ ████████╗
  ██║   ██║      ██╔══██╗██╔═══██╗██╔═══██╗╚══██╔══╝
  ██║   ██║█████╗██████╔╝██║   ██║██║   ██║   ██║   
  ██║   ██║╚════╝██╔══██╗██║   ██║██║   ██║   ██║   
  ╚██████╔╝      ██████╔╝╚██████╔╝╚██████╔╝   ██║   
   ╚═════╝       ╚═════╝  ╚═════╝  ╚═════╝    ╚═╝   

         ██████╗ ██████╗ ███╗   ███╗███╗   ███╗ █████╗ ███╗   ██╗██████╗     
        ██╔════╝██╔═══██╗████╗ ████║████╗ ████║██╔══██╗████╗  ██║██╔══██╗    
        ██║     ██║   ██║██╔████╔██║██╔████╔██║███████║██╔██╗ ██║██║  ██║    
        ██║     ██║   ██║██║╚██╔╝██║██║╚██╔╝██║██╔══██║██║╚██╗██║██║  ██║    
        ╚██████╗╚██████╔╝██║ ╚═╝ ██║██║ ╚═╝ ██║██║  ██║██║ ╚████║██████╔╝    
         ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═════╝    
"""

UBOOT_SIDE = r"""
          ____________________________
    _____/  o  __|__________|__  o   \______
~~~|_____|___|__|____________|__|___|_______|~~~
         \____________________________/
"""

def show_title():
    clear()
    print(TITLE_ART)
    print(center("DAS BOOT  —  THE GAME"))
    print(center("Kriegsmarine U-Boot Simulation  //  1939-1945"))
    print()
    print(UBOOT_SIDE)
    print()
    print(center("'They were the best of us.'"))
    print(center("'They were also terrifyingly young.'"))
    print()

# ─────────────────────────────────────────────
#  RADIOGRAM RENDERER
# ─────────────────────────────────────────────

BDUNAUTIC_HEADER = """
╔══════════════════════════════════════════════════════════╗
║        BEFEHLSHABER DER UNTERSEEBOOTE — BdU              ║
║        LORIENT, FRANKREICH  //  FUNKSPRUCH               ║
╚══════════════════════════════════════════════════════════╝"""

def show_radiogram(from_: str, to_: str, body_lines: list[str], classification: str = "GEHEIM"):
    """
    render an incoming radio order in the style of wartime german naval signals.
    all caps. terse. vaguely threatening.
    """
    print()
    print(BDUNAUTIC_HEADER)
    print(f"  VON   : {from_.upper()}")
    print(f"  AN    : {to_.upper()}")
    print(f"  KLASSE: {classification.upper()}")
    print(f"  {'─' * 54}")
    print()
    for line in body_lines:
        print(f"  {line.upper()}")
    print()
    print(f"  {'─' * 54}")
    print(f"  HEIL UND SIEG. — KAdm. DOENITZ")
    print(f"  {'═' * 56}")
    print()

def patrol_orders_radiogram(state: GameState, zone: tuple, quota: int) -> list[str]:
    """generate patrol order text for a given grid zone."""
    zone_str = f"PLANQUADRAT {chr(64 + zone[0])}{zone[1]}"
    return [
        f"UNTERSEEBOOT {state.u_boat_name} IS HEREBY ORDERED:",
        f"",
        f"OPERATIONAL AREA: {zone_str}",
        f"MISSION: LOCATE AND DESTROY ENEMY SHIPPING.",
        f"",
        f"TONNAGE TARGET: {quota:,} GRT — MINIMUM ACCEPTABLE.",
        f"REPORT ALL CONTACTS BY RADIO IMMEDIATELY.",
        f"RETURN TO PORT WHEN FUEL OR TORPEDOES EXHAUSTED.",
        f"",
        f"THE FATHERLAND IS WATCHING. DO NOT FAIL.",
        f"SIEG HEIL.",
    ]

# ─────────────────────────────────────────────
#  STATUS DASHBOARD
# ─────────────────────────────────────────────

def render_dashboard(state: GameState):
    """
    flat single-column dashboard. no two-column nonsense.
    unicode block chars have variable terminal widths — keeping rows simple.
    """
    b  = state.boat
    c  = state.crew
    s  = state.supplies
    n  = state.nav
    ms = state.stats
    W  = 58   # inner width (between the ║ chars)

    def row(text=""):
        """pad a row to exact inner width."""
        return f"║ {text:<{W}} ║"

    def bar_row(label, val, width=20):
        """one stat bar row: LABEL [████░░░░] 75%  [OK]"""
        filled = int((val / 100) * width)
        bar    = "#" * filled + "-" * (width - filled)
        tag    = status_color_tag(val).strip()
        return row(f"  {label:<8} [{bar}] {val:>3}%  {tag}")

    depth_str = f"{b.current_depth}m" if not b.surfaced else "surface"
    sub_str   = "GETAUCHT" if not b.surfaced else "AUFGETAUCHT"

    # tonnage quota progress
    quota     = state.stats.tonnage_quota
    quota_pct = min(100, int(ms.tonnage_sunk / quota * 100)) if quota > 0 else 0
    quota_bar = "#" * (quota_pct // 5) + "-" * (20 - quota_pct // 5)

    divider = "╠" + "═" * (W + 2) + "╣"
    top     = "╔" + "═" * (W + 2) + "╗"
    bottom  = "╚" + "═" * (W + 2) + "╝"

    print()
    print(top)
    print(row(f" {state.u_boat_name}  --  {state.commander}"))
    print(row(f" Day {n.patrol_day}  //  {n.hours_at_sea}h at sea  //  Patrol #{ms.patrol_number}"))
    print(divider)
    print(row("  -- BOOT --"))
    print(bar_row("RUMPF",  b.hull_integrity))
    print(bar_row("FUEL",   b.fuel))
    print(bar_row("BATT",   b.battery))
    eng = b.engine_status[:12]   # truncate so it never blows the box
    print(row(f"  Depth: {depth_str:<10}  {sub_str:<12}  Eng: {eng}"))
    print(divider)
    print(row("  -- TORPEDOS --"))
    bow_vis = "#" * b.torpedoes + "." * (TORPEDO_CAPACITY - 2 - b.torpedoes)
    aft_vis = "#" * b.torpedoes_aft + "." * (2 - b.torpedoes_aft)
    print(row(f"  Bow [{bow_vis}] {b.torpedoes}/{TORPEDO_CAPACITY-2}    Aft [{aft_vis}] {b.torpedoes_aft}/2"))
    print(divider)
    print(row("  -- BESATZUNG (CREW) --"))
    print(bar_row("Health", c.health))
    print(bar_row("Morale", c.morale))
    # fatigue: low is good, so invert the color tag
    fatigue_tag = status_color_tag(100 - c.fatigue).strip()
    fatigue_filled = int((c.fatigue / 100) * 20)
    fatigue_bar = "#" * fatigue_filled + "-" * (20 - fatigue_filled)
    print(row(f"  {'Fatigue':<8} [{fatigue_bar}] {c.fatigue:>3}%  {fatigue_tag}"))
    print(row(f"  Alive: {c.alive}/{c.total}"))
    print(divider)
    print(row("  -- VERSORGG (SUPPLIES) --"))
    print(bar_row("Food",  s.food))
    print(bar_row("Water", s.water))
    print(row(f"  Med kits: {s.medkit}"))
    print(divider)
    print(row("  -- MISSION --"))
    print(row(f"  Ships sunk: {ms.ships_sunk}   Tonnage: {ms.tonnage_sunk:,} GRT"))
    print(row(f"  Quota: [{quota_bar}] {ms.tonnage_sunk:,} / {quota:,} GRT  ({quota_pct}%)"))
    print(row(f"  Torps fired: {ms.torpedoes_fired}   Depth charges survived: {ms.depth_charges_survived}"))
    print(bottom)
    print()

# ─────────────────────────────────────────────
#  DEPTH GAUGE
# ─────────────────────────────────────────────

def render_depth_gauge(current_depth: int):
    """vertical depth gauge. the most terrifying instrument on the boat."""
    max_display = 300
    bar_height  = 20
    steps       = [int(i * max_display / bar_height) for i in range(bar_height + 1)]

    print("  ┌───────────┐")
    print("  │  TIEFE    │")
    print("  ├───────────┤")
    for i, depth_mark in enumerate(reversed(steps[1:])):
        marker = "◄ " if abs(depth_mark - current_depth) < (max_display // bar_height) else "  "
        crush  = " ← CRUSH" if depth_mark == CRUSH_DEPTH else ""
        safe   = " ← SAFE"  if depth_mark == SAFE_DIVE_DEPTH else ""
        peri   = " ← PERI"  if depth_mark == PERISCOPE_DEPTH else ""
        bar    = "█" if current_depth >= depth_mark else "░"
        print(f"  │{depth_mark:>4}m {bar} {marker}│{crush}{safe}{peri}")
    print("  └───────────┘")
    print(f"  AKTUELL: {current_depth}m")

# ─────────────────────────────────────────────
#  NAVIGATION MAP
# ─────────────────────────────────────────────

# ascii map symbols
SYM_YOU     = "U"   # your position
SYM_PORT    = "P"   # home port (lorient)
SYM_PATROL  = "X"   # your patrol zone
SYM_CONTACT = "!"   # known contact
SYM_EMPTY   = "·"   # open water

# port is always at bottom-center
PORT_X, PORT_Y = 5, 9

def render_nav_map(state: GameState, contacts: list[tuple] = None):
    """
    10x10 ascii grid of the north atlantic.
    U = you, P = port, X = patrol zone, ! = known contacts.
    each cell is 2 chars wide (char + space) so headers must match.
    """
    n  = state.nav
    pz = n.patrol_zone

    grid = [[SYM_EMPTY for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]

    grid[PORT_Y - 1][PORT_X - 1] = SYM_PORT

    if pz:
        px, py = pz
        if 1 <= px <= GRID_SIZE and 1 <= py <= GRID_SIZE:
            grid[py - 1][px - 1] = SYM_PATROL

    if contacts:
        for (cx, cy) in contacts:
            if 1 <= cx <= GRID_SIZE and 1 <= cy <= GRID_SIZE:
                if grid[cy - 1][cx - 1] == SYM_EMPTY:
                    grid[cy - 1][cx - 1] = SYM_CONTACT

    if 1 <= n.grid_x <= GRID_SIZE and 1 <= n.grid_y <= GRID_SIZE:
        grid[n.grid_y - 1][n.grid_x - 1] = SYM_YOU

    col_header = "      " + " ".join(chr(64 + i) for i in range(1, GRID_SIZE + 1))
    border     = "    +" + "-" * (GRID_SIZE * 2 + 1) + "+"

    print()
    print("  NORDATLANTIK -- KRIEGSMARINE SEEKARTE")
    print()
    print(col_header)
    print(border)
    for row_idx, row in enumerate(grid):
        row_num = row_idx + 1
        row_str = " ".join(row)
        print(f"  {row_num:>3} | {row_str} |")
    print(border)
    print()
    print(f"  U=you  P=port(Lorient)  X=patrol zone  !=contact")
    print(f"  Pos: {chr(64+n.grid_x)}{n.grid_y}   Heading: {n.heading}deg   Speed: {n.speed_knots}kn")
    print()

# ─────────────────────────────────────────────
#  EXPLOSION / EVENT VISUALS
# ─────────────────────────────────────────────

EXPLOSION_FRAMES = [
    r"""
       *
      ***
     *****
      ***
       *
    """,
    r"""
      .*.
     *****
    *******
     *****
      .*.
    """,
    r"""
     .***. 
    *******
   *********
    *******
     .***. 
    """
]

DEPTH_CHARGE_ART = r"""
  ~  ~  ~  ~  ~  ~  ~  ~  ~  ~  ~
  ~    WABO DETECTED — BRACE    ~
  ~  ~  ~  ~  ~  ~  ~  ~  ~  ~  ~
         ░░
        ░░░░
       ░░░░░░
      ░░BOOM░░
       ░░░░░░
        ░░░░
         ░░
  ~  ~  ~  ~  ~  ~  ~  ~  ~  ~  ~
"""

TORPEDO_FIRE_ART = r"""
  BUG-ROHR FEUER!
  ═══════════════════>  ~~~~  [ ? ]
"""

HIT_ART = r"""
              * * *
           *         *
         *    TREFFER!  *
           *         *
              * * *
     SCHIFF GETROFFEN — BRENNT!
"""

MISS_ART = r"""
  ═══════════════════>  ~~~~  ~~~~  ~~~~

  ... torpedo runs true ... passes ahead ...

  VERFEHLT. ZIEL ENTKOMMEN.
"""

def show_torpedo_fire(hit: bool, distance_m: int):
    print(TORPEDO_FIRE_ART)
    time.sleep(0.5)
    print(f"  DISTANZ: {distance_m}M  //  LAUFZEIT: {distance_m // 40}SEK...")
    for _ in range(min(4, distance_m // 200)):
        print("  ~~~")
        time.sleep(0.4)
    print()
    if hit:
        print(HIT_ART)
    else:
        print(MISS_ART)
    time.sleep(0.8)

def show_depth_charge(severity: int):
    """severity 1-3. 3 = you are having a very bad day."""
    print(DEPTH_CHARGE_ART)
    for _ in range(severity):
        print("  !! EINSCHLAG !!")
        time.sleep(0.3)
    print()

def show_game_over(state: GameState):
    clear()
    print()
    print("  " + "═" * 56)
    print()
    print(center("╔══════════════════════════════════╗"))
    print(center("║         PATROL ENDED             ║"))
    print(center("╚══════════════════════════════════╝"))
    print()
    print(f"  {state.game_over_msg}")
    print()
    ms = state.stats
    print(f"  ENDABRECHNUNG — U-BOOT {state.u_boat_name}:")
    print(f"  {'─'*40}")
    print(f"  SCHIFFE VERSENKT : {ms.ships_sunk}")
    print(f"  TONNAGE          : {ms.tonnage_sunk:,} BRT")
    print(f"  TAGE AUF SEE     : {state.nav.patrol_day}")
    print(f"  TORPEDOS VERBRAUCHT: {ms.torpedoes_fired}")
    print(f"  WABOS UEBERLEBT  : {ms.depth_charges_survived}")
    print()
    if state.victory:
        print(center("  PATROL ERFOLGREICH. EHRENVOLLER DIENST."))
    else:
        print(center("  PATROL FEHLGESCHLAGEN."))
        print(center("  THEY WILL NOT FIND THE BOAT."))
    print()
    print("  " + "═" * 56)

# ─────────────────────────────────────────────
#  MESSAGE LOG DISPLAY
# ─────────────────────────────────────────────

def show_messages(messages: list[str]):
    """print a batch of event messages with slight drama."""
    if not messages:
        return
    print()
    for msg in messages:
        print(f"  {msg}")
    print()
