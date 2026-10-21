
"""
  Run it with:      python vend.py
  Print the table:  python vend.py --test

  Only the Python standard library is used (tkinter + sys).

-----------------------------------------------------------------------------
  DFA DESIGN (short explanation)
-----------------------------------------------------------------------------
  The "brain" of the vending machine is a Deterministic Finite Automaton.
  The DFA decides WHAT MODE the machine is in (waiting, holding money,
  dispensing, giving change). Every button the user presses is turned into
  ONE input symbol, and the DFA looks up exactly ONE next state in its
  transition table (a Python dictionary). Because there is always exactly
  one next state for every (state, input) pair, the automaton is
  deterministic, and because every pair is in the table, it is complete.

  Why is the balance not a state?
    A DFA must have a FINITE number of states, but a customer could insert
    any amount of money. So the balance is kept in a normal variable
    (like a register/counter), and the GUI-free "VendingMachine" class turns
    the comparison "balance >= price?" into two DIFFERENT input symbols:
        sel_ok   -> the customer has enough money
        sel_low  -> the customer does NOT have enough money
    The DFA itself only ever sees symbols from Sigma.

-----------------------------------------------------------------------------
  FORMAL DEFINITION   M = (Q, Sigma, delta, q0, F)
-----------------------------------------------------------------------------
  Q     (states) = { IDLE, HAS_MONEY, DISPENSING, GIVING_CHANGE }
            IDLE          : balance is P0, waiting for a customer
            HAS_MONEY     : balance > 0, waiting for a selection
            DISPENSING    : a drink is dropping to the dispensing slot
            GIVING_CHANGE : drink/change/refund is waiting in the trays

  Sigma (inputs) = { coin, sel_ok, sel_low, cancel, collect, done }
            coin    : a coin or bill (P1, P5, P10, P20, P50, P100) is inserted
            sel_ok  : a drink is selected AND balance >= price
            sel_low : a drink is selected AND balance <  price
            cancel  : the "Cancel / Refund" button is pressed
            collect : the "Collect / Reset" button is pressed
            done    : internal signal - the drop animation has finished

  q0    (start state)     = IDLE
  F     (accepting states) = { IDLE }
            A sequence of inputs is ACCEPTED when it ends in IDLE, which
            means every transaction was completed and the machine is ready
            for the next customer. Example accepted string:
                coin coin sel_ok done collect

  delta (transition function)  delta : Q x Sigma -> Q

      state          | coin       sel_ok      sel_low    cancel         collect    done
      ---------------+---------------------------------------------------------------------------
      IDLE           | HAS_MONEY  IDLE        IDLE       IDLE           IDLE       IDLE
      HAS_MONEY      | HAS_MONEY  DISPENSING  HAS_MONEY  GIVING_CHANGE  HAS_MONEY  HAS_MONEY
      DISPENSING     | DISPENSING DISPENSING  DISPENSING DISPENSING     DISPENSING GIVING_CHANGE
      GIVING_CHANGE  | GIVING_CH. GIVING_CH.  GIVING_CH. GIVING_CH.     IDLE       GIVING_CHANGE

      Entries where the state does not change are "self-loops": the input
      is simply ignored in that state (for example, pressing a drink while
      the machine is already dispensing).

-----------------------------------------------------------------------------
  CODE STRUCTURE (3 layers, so each part is easy to explain)
-----------------------------------------------------------------------------
  1. VendingDFA         - the pure DFA: states, inputs, transition table.
                          No money, no drawing. Just delta.
  2. VendingMachine     - the machine's data (balance, stock, change) that
                          feeds input symbols to the DFA. No Tkinter here.
  3. VendingMachineGUI  - all Tkinter drawing, buttons and animations.
=============================================================================
"""

import sys
import tkinter as tk


# =============================================================================
#  CONFIGURATION / DATA
# =============================================================================

# The 6 drinks: name, price in Philippine pesos, can colour.
DRINKS = [
    {"name": "Water",        "price": 10, "color": "#4FC3F7"},
    {"name": "Iced Tea",     "price": 15, "color": "#C68B3E"},
    {"name": "Cola",         "price": 20, "color": "#C62828"},
    {"name": "Orange Juice", "price": 25, "color": "#FF9800"},
    {"name": "Coffee",       "price": 30, "color": "#6D4C41"},
    {"name": "Energy Drink", "price": 35, "color": "#76FF03"},
]

# Money the customer can insert (one button for each).
MONEY_VALUES = [1, 5, 10, 20, 50, 100]

# Denominations used to give change, from largest to smallest.
DENOMINATIONS = [100, 50, 20, 10, 5, 1]

# How many of each drink the machine starts with.
START_STOCK = 5

# Colours used to draw coins/bills in the change tray.
MONEY_COLORS = {
    1: "#CFD8DC",    # silver coin
    5: "#FFE082",    # gold coin
    10: "#FFCA28",   # gold coin
    20: "#FFA000",   # bi-metal coin
    50: "#EF5350",   # red bill
    100: "#9575CD",  # violet bill
}


# =============================================================================
#  LAYER 1 - THE DFA  (pure logic, no GUI, no money)
# =============================================================================

class VendingDFA:
    """A Deterministic Finite Automaton M = (Q, Sigma, delta, q0, F)."""

    # ---- Q : the finite set of states --------------------------------------
    IDLE = "IDLE"
    HAS_MONEY = "HAS_MONEY"
    DISPENSING = "DISPENSING"
    GIVING_CHANGE = "GIVING_CHANGE"
    STATES = (IDLE, HAS_MONEY, DISPENSING, GIVING_CHANGE)

    # ---- Sigma : the input alphabet ----------------------------------------
    COIN = "coin"          # money inserted
    SELECT_OK = "sel_ok"   # drink selected, enough money
    SELECT_LOW = "sel_low" # drink selected, NOT enough money
    CANCEL = "cancel"      # refund button
    COLLECT = "collect"    # collect / reset button
    DONE = "done"          # internal: drink finished dropping
    INPUTS = (COIN, SELECT_OK, SELECT_LOW, CANCEL, COLLECT, DONE)

    # ---- q0 : the start state ----------------------------------------------
    START_STATE = IDLE

    # ---- F : the set of accepting states -----------------------------------
    ACCEPTING_STATES = frozenset({IDLE})

    # ---- delta : the transition table  (state, input) -> next_state --------
    # Every one of the 4 x 6 = 24 pairs is listed, so the DFA is complete.
    TRANSITIONS = {
        # From IDLE (balance is P0)
        (IDLE, COIN):        HAS_MONEY,      # first coin -> we now hold money
        (IDLE, SELECT_OK):   IDLE,           # (impossible with P0) ignored
        (IDLE, SELECT_LOW):  IDLE,           # no money yet -> stay idle
        (IDLE, CANCEL):      IDLE,           # nothing to refund
        (IDLE, COLLECT):     IDLE,           # nothing to collect
        (IDLE, DONE):        IDLE,           # ignored

        # From HAS_MONEY (balance > 0)
        (HAS_MONEY, COIN):       HAS_MONEY,      # more money, same mode
        (HAS_MONEY, SELECT_OK):  DISPENSING,     # enough money -> drop drink
        (HAS_MONEY, SELECT_LOW): HAS_MONEY,      # not enough -> keep waiting
        (HAS_MONEY, CANCEL):     GIVING_CHANGE,  # refund whole balance
        (HAS_MONEY, COLLECT):    HAS_MONEY,      # nothing in tray yet
        (HAS_MONEY, DONE):       HAS_MONEY,      # ignored

        # From DISPENSING (drink is falling - machine is busy)
        (DISPENSING, COIN):       DISPENSING,     # ignored (coin rejected)
        (DISPENSING, SELECT_OK):  DISPENSING,     # ignored
        (DISPENSING, SELECT_LOW): DISPENSING,     # ignored
        (DISPENSING, CANCEL):     DISPENSING,     # ignored
        (DISPENSING, COLLECT):    DISPENSING,     # ignored
        (DISPENSING, DONE):       GIVING_CHANGE,  # drink landed -> give change

        # From GIVING_CHANGE (items waiting in the trays)
        (GIVING_CHANGE, COIN):       GIVING_CHANGE,  # must collect first
        (GIVING_CHANGE, SELECT_OK):  GIVING_CHANGE,  # must collect first
        (GIVING_CHANGE, SELECT_LOW): GIVING_CHANGE,  # must collect first
        (GIVING_CHANGE, CANCEL):     GIVING_CHANGE,  # already refunding
        (GIVING_CHANGE, COLLECT):    IDLE,           # customer took items
        (GIVING_CHANGE, DONE):       GIVING_CHANGE,  # ignored
    }

    def __init__(self):
        """Create the DFA in its start state q0."""
        self._check_table_is_complete()
        self.state = self.START_STATE
        self.history = []   # list of (previous_state, input, next_state)

    def _check_table_is_complete(self):
        """Make sure delta is defined for EVERY (state, input) pair."""
        for state in self.STATES:
            for symbol in self.INPUTS:
                if (state, symbol) not in self.TRANSITIONS:
                    raise ValueError(f"delta({state}, {symbol}) is missing")

    def process(self, symbol):
        """Read ONE input symbol and move to the next state.

        Returns (previous_state, next_state) so the caller knows what
        happened.
        """
        if symbol not in self.INPUTS:
            raise ValueError(f"'{symbol}' is not in the input alphabet Sigma")
        previous = self.state
        self.state = self.TRANSITIONS[(previous, symbol)]   # <- this IS delta
        self.history.append((previous, symbol, self.state))
        return previous, self.state

    def is_accepting(self):
        """True if the current state is in F."""
        return self.state in self.ACCEPTING_STATES

    def reset(self):
        """Go back to q0 and forget the history."""
        self.state = self.START_STATE
        self.history = []

    @classmethod
    def accepts(cls, symbols):
        """Run a whole input string and say if the DFA accepts it."""
        state = cls.START_STATE
        for symbol in symbols:
            state = cls.TRANSITIONS[(state, symbol)]
        return state in cls.ACCEPTING_STATES

    @classmethod
    def print_transition_table(cls):
        """Print delta as a table in the console (for documentation)."""
        width = 15
        print("Transition table delta (rows = states, columns = inputs)\n")
        print("state".ljust(width) + "".join(a.ljust(width) for a in cls.INPUTS))
        print("-" * width * (len(cls.INPUTS) + 1))
        for state in cls.STATES:
            row = state.ljust(width)
            for symbol in cls.INPUTS:
                row += cls.TRANSITIONS[(state, symbol)].ljust(width)
            print(row)
        print(f"\nq0 = {cls.START_STATE}    F = {set(cls.ACCEPTING_STATES)}")


# =============================================================================
#  HELPER FUNCTIONS - change making
# =============================================================================

def make_change(amount):
    """Return the fewest coins/bills for 'amount' as [(value, count), ...].

    A greedy algorithm (always take the largest denomination that fits) is
    used. For the Philippine set 100/50/20/10/5/1 greedy always gives the
    fewest pieces, because it is a "canonical" coin system (like the US or
    Euro coins), so no cleverer algorithm is needed.
    """
    result = []
    for value in DENOMINATIONS:
        count, amount = divmod(amount, value)
        if count > 0:
            result.append((value, count))
    return result


def describe_change(amount):
    """Turn an amount into text like '1x P10, 1x P5'."""
    return ", ".join(f"{count}x P{value}" for value, count in make_change(amount))


# =============================================================================
#  LAYER 2 - THE MACHINE MODEL (money + stock, feeds symbols to the DFA)
# =============================================================================

class VendingMachine:
    """Keeps the balance and stock, and converts actions into DFA inputs.

    Each public method returns (success, message). The message is what the
    display screen should show.
    """

    def __init__(self):
        self.dfa = VendingDFA()
        self.balance = 0                          # money inserted so far
        self.stock = [START_STOCK] * len(DRINKS)  # cans left per drink
        self.tray_amount = 0      # money waiting in the change tray
        self.tray_kind = "Change" # "Change" (after purchase) or "Refund"
        self.pending_change = 0   # change to give once the drink lands

    # ---- input: coin ---------------------------------------------------------
    def insert_coin(self, value):
        previous, current = self.dfa.process(VendingDFA.COIN)
        if current == VendingDFA.HAS_MONEY:
            self.balance += value
            return True, "Select a drink"
        if previous == VendingDFA.DISPENSING:
            return False, "Please wait...\nDispensing"
        return False, f"P{value} not accepted.\nPress Collect first"

    # ---- input: sel_ok / sel_low --------------------------------------------
    def select_drink(self, index):
        drink = DRINKS[index]
        price = drink["price"]

        # Sold-out drinks never reach the DFA (their button is disabled).
        if self.stock[index] == 0:
            return False, f"{drink['name']}\nis SOLD OUT"

        # Turn the comparison into one of two input symbols.
        if self.balance > 0 and self.balance >= price:
            symbol = VendingDFA.SELECT_OK
        else:
            symbol = VendingDFA.SELECT_LOW
        previous, current = self.dfa.process(symbol)

        if current == VendingDFA.DISPENSING:
            # Accepted purchase: take the money, keep the change for later.
            self.stock[index] -= 1
            self.pending_change = self.balance - price
            self.balance = 0
            return True, f"Dispensing\n{drink['name']}..."
        if previous == VendingDFA.IDLE:
            return False, f"Insert coins\n{drink['name']} = P{price}"
        if previous == VendingDFA.HAS_MONEY:
            need = price - self.balance
            return False, f"Not enough money!\nNeed P{need} more"
        if previous == VendingDFA.DISPENSING:
            return False, "Please wait...\nDispensing"
        return False, "Please press\nCollect first"

    # ---- input: done (internal, from the animation) -------------------------
    def finish_dispensing(self):
        previous, current = self.dfa.process(VendingDFA.DONE)
        if previous == VendingDFA.DISPENSING and current == VendingDFA.GIVING_CHANGE:
            self.tray_amount = self.pending_change
            self.tray_kind = "Change"
            self.pending_change = 0
            if self.tray_amount > 0:
                return True, f"Enjoy your drink!\nChange: P{self.tray_amount}"
            return True, "Enjoy your drink!\nExact amount paid"
        return False, ""

    # ---- input: cancel -------------------------------------------------------
    def cancel(self):
        previous, current = self.dfa.process(VendingDFA.CANCEL)
        if previous == VendingDFA.HAS_MONEY and current == VendingDFA.GIVING_CHANGE:
            self.tray_amount = self.balance
            self.tray_kind = "Refund"
            self.balance = 0
            return True, f"Refunded P{self.tray_amount}\nTake your money"
        if previous == VendingDFA.IDLE:
            return False, "Nothing to refund\nInsert coins"
        if previous == VendingDFA.DISPENSING:
            return False, "Please wait...\nDispensing"
        return False, "Please press\nCollect first"

    # ---- input: collect ------------------------------------------------------
    def collect(self):
        previous, current = self.dfa.process(VendingDFA.COLLECT)
        if previous == VendingDFA.GIVING_CHANGE and current == VendingDFA.IDLE:
            self.tray_amount = 0
            return True, "Thank you!\nInsert coins"
        if previous == VendingDFA.HAS_MONEY:
            return False, "Nothing to collect\nSelect or Cancel"
        if previous == VendingDFA.DISPENSING:
            return False, "Please wait...\nDispensing"
        return False, "Insert coins"


# =============================================================================
#  LAYER 3 - THE GUI (Tkinter drawing, buttons, animations)
# =============================================================================

class VendingMachineGUI:
    """Draws the machine on a Canvas and connects buttons to the model."""

    WIDTH, HEIGHT = 800, 700

    # Where each drink is drawn: (x centre, top of can) for the 2x3 grid.
    COLUMN_X = [100, 220, 340]
    ROW_TOP = [100, 275]
    CAN_W, CAN_H = 22, 66        # half-width and full height of a can
    SLOT_LANDING_TOP = 569       # top of a can resting in the dispensing slot

    # Positions of the state circles in the mini DFA diagram.
    DIAGRAM_X = 700
    DIAGRAM_Y = {
        VendingDFA.IDLE: 135,
        VendingDFA.HAS_MONEY: 225,
        VendingDFA.DISPENSING: 315,
        VendingDFA.GIVING_CHANGE: 405,
    }
    DIAGRAM_R = 26

    def __init__(self, root):
        self.root = root
        self.root.title("DFA Vending Machine")
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.root.resizable(False, False)

        self.machine = VendingMachine()

        self.canvas = tk.Canvas(root, width=self.WIDTH, height=self.HEIGHT,
                                bg="#E3F2FD", highlightthickness=0)
        self.canvas.pack()

        # Canvas item ids we need to update later.
        self.drink_buttons = []
        self.can_bodies = []
        self.stock_texts = []
        self.slot_items = []        # the drink resting in the dispensing slot
        self.tray_items = []        # coins drawn in the change tray
        self.state_circles = {}     # state name -> circle id

        self.draw_machine_body()
        self.draw_drinks()
        self.draw_control_panel()
        self.draw_dfa_monitor()
        self.refresh()

    # -------------------------------------------------------------------------
    #  DRAWING
    # -------------------------------------------------------------------------
    def draw_machine_body(self):
        """Machine cabinet, drink window, brand stripe and dispensing slot."""
        c = self.canvas
        # Shadow + cabinet
        c.create_rectangle(28, 48, 608, 692, fill="#90A4AE", outline="")
        c.create_rectangle(20, 40, 600, 685, fill="#E53935",
                           outline="#B71C1C", width=4)
        c.create_text(310, 62, text="DRINKS", fill="white",
                      font=("Arial Black", 20, "bold"))

        # Glass drink display area
        c.create_rectangle(40, 85, 400, 450, fill="#E0F7FA",
                           outline="#37474F", width=3)
        for shelf_y in (258, 435):
            c.create_line(45, shelf_y, 395, shelf_y, fill="#90A4AE", width=3)
        # Glass shine
        c.create_line(55, 95, 55, 440, fill="white", width=4)

        # Brand stripe
        c.create_rectangle(40, 465, 400, 540, fill="#FFEB3B",
                           outline="#37474F", width=2)
        c.create_text(220, 490, text="ICE COLD DRINKS", fill="#C62828",
                      font=("Arial", 16, "bold"))
        c.create_text(220, 518, text="Insert coins  >  Pick a drink  >  Enjoy!",
                      fill="#37474F", font=("Arial", 9, "bold"))

        # Dispensing slot at the bottom
        c.create_rectangle(60, 555, 380, 650, fill="#424242",
                           outline="#9E9E9E", width=3)
        c.create_rectangle(70, 565, 370, 640, fill="#111111", outline="")
        c.create_text(220, 667, text="PUSH - TAKE DRINK HERE", fill="white",
                      font=("Arial", 9, "bold"))

        # Feet
        c.create_rectangle(40, 685, 100, 698, fill="#37474F", outline="")
        c.create_rectangle(520, 685, 580, 698, fill="#37474F", outline="")

    def draw_can(self, x, top, color):
        """Draw one can and return the list of canvas ids it is made of."""
        c = self.canvas
        w, h = self.CAN_W, self.CAN_H
        cap = c.create_rectangle(x - 12, top - 6, x + 12, top, fill="#B0BEC5",
                                 outline="#546E7A")
        body = c.create_rectangle(x - w, top, x + w, top + h, fill=color,
                                  outline="#212121", width=2)
        return [cap, body]

    def draw_drinks(self):
        """Draw the 6 drinks in a 2 x 3 grid with name, price and button."""
        c = self.canvas
        for i, drink in enumerate(DRINKS):
            x = self.COLUMN_X[i % 3]
            top = self.ROW_TOP[i // 3]

            parts = self.draw_can(x, top, drink["color"])
            self.can_bodies.append(parts[1])

            c.create_text(x, top + 78, text=drink["name"], fill="#263238",
                          font=("Arial", 9, "bold"))
            c.create_text(x, top + 95, text=f"P{drink['price']}",
                          fill="#C62828", font=("Arial", 10, "bold"))

            button = tk.Button(self.root, text=f"Buy P{drink['price']}",
                               width=9, bg="#43A047", fg="white",
                               activebackground="#2E7D32",
                               font=("Arial", 8, "bold"),
                               command=lambda index=i: self.on_select_drink(index))
            c.create_window(x, top + 122, window=button)
            self.drink_buttons.append(button)

            stock = c.create_text(x, top + 147, text="", fill="#455A64",
                                  font=("Arial", 8))
            self.stock_texts.append(stock)

    def draw_control_panel(self):
        """Display screen, coin slot, money buttons, cancel/collect, tray."""
        c = self.canvas
        c.create_rectangle(412, 85, 588, 670, fill="#C62828",
                           outline="#8E0000", width=2)

        # --- Display screen ---
        c.create_rectangle(422, 95, 578, 195, fill="#1B5E20",
                           outline="#000000", width=3)
        self.balance_text = c.create_text(500, 117, text="Balance: P0",
                                          fill="#B9F6CA",
                                          font=("Courier", 12, "bold"))
        self.message_text = c.create_text(500, 160, text="Insert coins",
                                          fill="#B9F6CA", width=148,
                                          justify="center",
                                          font=("Courier", 9, "bold"))

        # --- Coin / money slot ---
        c.create_rectangle(422, 205, 578, 250, fill="#9E9E9E",
                           outline="#424242", width=2)
        c.create_text(475, 227, text="COIN / BILL\nSLOT", justify="center",
                      font=("Arial", 8, "bold"), fill="#212121")
        c.create_rectangle(531, 211, 539, 244, fill="#111111", outline="")

        # --- Money buttons: 3 columns x 2 rows ---
        for n, value in enumerate(MONEY_VALUES):
            x = [447, 500, 553][n % 3]
            y = [275, 310][n // 3]
            color = MONEY_COLORS[value]
            button = tk.Button(self.root, text=f"P{value}", width=4, bg=color,
                               font=("Arial", 9, "bold"),
                               command=lambda v=value: self.on_insert_coin(v))
            c.create_window(x, y, window=button)

        # --- Cancel / Refund and Collect / Reset ---
        cancel = tk.Button(self.root, text="Cancel / Refund", width=16,
                           bg="#FB8C00", fg="white", font=("Arial", 9, "bold"),
                           command=self.on_cancel)
        c.create_window(500, 350, window=cancel)
        collect = tk.Button(self.root, text="Collect / Reset", width=16,
                            bg="#1E88E5", fg="white", font=("Arial", 9, "bold"),
                            command=self.on_collect)
        c.create_window(500, 385, window=collect)

        # --- Change tray ---
        c.create_rectangle(422, 410, 578, 545, fill="#424242",
                           outline="#000000", width=3)
        c.create_text(500, 421, text="CHANGE TRAY", fill="white",
                      font=("Arial", 8, "bold"))
        self.tray_text = c.create_text(500, 452, text="", fill="#FFF59D",
                                       width=148, justify="center",
                                       font=("Arial", 8, "bold"))

        # --- Info ---
        c.create_text(500, 590, justify="center", fill="white",
                      font=("Arial", 8, "bold"),
                      text="Accepts: P1 P5 P10\nP20 P50 P100\n\n"
                           f"Stock: {START_STOCK} of each drink")

    def draw_dfa_monitor(self):
        """Side panel: live state label, mini state diagram, transition log."""
        c = self.canvas

        # Small live state label in the top-right corner of the window.
        self.state_label = tk.Label(self.root, text="DFA State: IDLE",
                                    bg="#1565C0", fg="white", padx=6, pady=2,
                                    font=("Courier", 10, "bold"))
        c.create_window(792, 6, window=self.state_label, anchor="ne")

        c.create_rectangle(610, 40, 790, 685, fill="white",
                           outline="#1565C0", width=3)
        c.create_text(700, 56, text="DFA MONITOR", fill="#1565C0",
                      font=("Arial", 11, "bold"))

        x, r = self.DIAGRAM_X, self.DIAGRAM_R
        y = self.DIAGRAM_Y
        IDLE, MONEY = VendingDFA.IDLE, VendingDFA.HAS_MONEY
        DISP, CHANGE = VendingDFA.DISPENSING, VendingDFA.GIVING_CHANGE

        # Start arrow into q0
        c.create_line(x, 72, x, y[IDLE] - r - 5, arrow=tk.LAST, width=2)
        c.create_text(x + 22, 80, text="start", font=("Arial", 7, "italic"))

        # Straight transitions down the middle
        c.create_line(x, y[IDLE] + r + 4, x, y[MONEY] - r, arrow=tk.LAST, width=2)
        c.create_line(x, y[MONEY] + r, x, y[DISP] - r, arrow=tk.LAST, width=2)
        c.create_line(x, y[DISP] + r, x, y[CHANGE] - r, arrow=tk.LAST, width=2)

        # Curved transitions: cancel (right side) and collect (left side)
        c.create_line(x + 24, y[MONEY] + 10, 786, (y[MONEY] + y[CHANGE]) // 2,
                      x + 24, y[CHANGE] - 10, smooth=True, arrow=tk.LAST, width=2)
        c.create_line(x - 24, y[CHANGE] - 10, 614, (y[IDLE] + y[CHANGE]) // 2,
                      x - 28, y[IDLE] + 10, smooth=True, arrow=tk.LAST, width=2)

        # Edge labels (white box so they sit nicely on top of the arrows)
        self.draw_edge_label(x, (y[IDLE] + y[MONEY]) // 2, "coin")
        self.draw_edge_label(x, (y[MONEY] + y[DISP]) // 2, "sel_ok")
        self.draw_edge_label(x, (y[DISP] + y[CHANGE]) // 2, "done")
        self.draw_edge_label(759, (y[MONEY] + y[CHANGE]) // 2, "cancel")
        self.draw_edge_label(637, (y[IDLE] + y[CHANGE]) // 2, "collect")

        # State circles (IDLE gets a double circle = accepting state)
        names = {IDLE: "IDLE", MONEY: "HAS_\nMONEY",
                 DISP: "DISPEN-\nSING", CHANGE: "GIVING_\nCHANGE"}
        c.create_oval(x - r - 4, y[IDLE] - r - 4, x + r + 4, y[IDLE] + r + 4,
                      outline="#1565C0", width=2)
        for state in VendingDFA.STATES:
            circle = c.create_oval(x - r, y[state] - r, x + r, y[state] + r,
                                   fill="#E3F2FD", outline="#1565C0", width=2)
            c.create_text(x, y[state], text=names[state], justify="center",
                          font=("Arial", 7, "bold"))
            self.state_circles[state] = circle

        c.create_text(700, 455, justify="center", fill="#546E7A",
                      font=("Arial", 7),
                      text="Self-loops are not drawn:\n"
                           "ignored inputs keep the\nsame state.")
        self.accept_text = c.create_text(700, 488, text="",
                                         font=("Arial", 8, "bold"))

        # Transition log (every delta step the DFA has taken)
        c.create_text(700, 508, text="Transition log:", fill="#1565C0",
                      font=("Arial", 8, "bold"))
        self.log_box = tk.Listbox(self.root, width=29, height=10,
                                  font=("Courier", 7), bg="#FAFAFA",
                                  borderwidth=1, highlightthickness=0)
        c.create_window(700, 590, window=self.log_box)
        self.count_text = c.create_text(700, 668, text="",
                                        font=("Arial", 8), fill="#455A64")

    def draw_edge_label(self, x, y, text):
        """Small text label with a white background for a diagram arrow."""
        half = len(text) * 3 + 3
        self.canvas.create_rectangle(x - half, y - 6, x + half, y + 6,
                                     fill="white", outline="")
        self.canvas.create_text(x, y, text=text, fill="#C62828",
                                font=("Arial", 7, "bold"))

    def draw_tray_money(self, amount):
        """Draw the coins/bills of 'amount' inside the change tray."""
        c = self.canvas
        pieces = []
        for value, count in make_change(amount):
            pieces.extend([value] * count)

        max_shown = 14
        for n, value in enumerate(pieces[:max_shown]):
            x = 437 + (n % 7) * 21
            y = 492 + (n // 7) * 24
            color = MONEY_COLORS[value]
            if value >= 50:   # bills are rectangles
                shape = c.create_rectangle(x - 10, y - 7, x + 10, y + 7,
                                           fill=color, outline="#212121")
            else:             # coins are circles
                shape = c.create_oval(x - 9, y - 9, x + 9, y + 9,
                                      fill=color, outline="#5D4037")
            text = c.create_text(x, y, text=str(value), font=("Arial", 6, "bold"))
            self.tray_items.extend([shape, text])

        if len(pieces) > max_shown:
            extra = c.create_text(500, 537, fill="white", font=("Arial", 7),
                                  text=f"+{len(pieces) - max_shown} more")
            self.tray_items.append(extra)

    # -------------------------------------------------------------------------
    #  REFRESH - redraw everything that depends on the model / DFA
    # -------------------------------------------------------------------------
    def set_message(self, message):
        self.canvas.itemconfig(self.message_text, text=message)

    def refresh(self):
        m = self.machine
        dfa = m.dfa
        c = self.canvas

        # Display + live DFA state label
        c.itemconfig(self.balance_text, text=f"Balance: P{m.balance}")
        self.state_label.config(text=f"DFA State: {dfa.state}")

        # Highlight the current state in the diagram
        for state, circle in self.state_circles.items():
            fill = "#FFEB3B" if state == dfa.state else "#E3F2FD"
            c.itemconfig(circle, fill=fill)
        if dfa.is_accepting():
            c.itemconfig(self.accept_text, text="In accepting state (F): YES",
                         fill="#2E7D32")
        else:
            c.itemconfig(self.accept_text, text="In accepting state (F): NO",
                         fill="#C62828")

        # Drink buttons, stock counts and SOLD OUT handling
        for i, button in enumerate(self.drink_buttons):
            stock = m.stock[i]
            if stock == 0:
                button.config(text="SOLD OUT", state=tk.DISABLED, bg="#9E9E9E",
                              disabledforeground="#424242")
                c.itemconfig(self.can_bodies[i], fill="#BDBDBD")
                c.itemconfig(self.stock_texts[i], text="Stock: 0",
                             fill="#C62828")
            else:
                c.itemconfig(self.stock_texts[i], text=f"Stock: {stock}")

        # Change tray (only filled while the DFA is in GIVING_CHANGE)
        for item in self.tray_items:
            c.delete(item)
        self.tray_items = []
        if dfa.state == VendingDFA.GIVING_CHANGE:
            amount = m.tray_amount
            if amount > 0:
                text = f"{m.tray_kind}: P{amount} ({describe_change(amount)})"
            else:
                text = "Change: P0 (exact amount)"
            c.itemconfig(self.tray_text, text=text)
            self.draw_tray_money(amount)
        else:
            c.itemconfig(self.tray_text, text="")

        # Transition log (show the last 40 steps)
        self.log_box.delete(0, tk.END)
        start = max(0, len(dfa.history) - 40)
        for n, (previous, symbol, nxt) in enumerate(dfa.history[start:], start + 1):
            self.log_box.insert(tk.END, f"{n}. input '{symbol}'")
            self.log_box.insert(tk.END, f" {previous}->{nxt}")
        self.log_box.see(tk.END)
        c.itemconfig(self.count_text, text=f"Inputs processed: {len(dfa.history)}")

    # -------------------------------------------------------------------------
    #  BUTTON HANDLERS
    # -------------------------------------------------------------------------
    def on_insert_coin(self, value):
        accepted, message = self.machine.insert_coin(value)
        self.set_message(message)
        if accepted:
            self.animate_coin(value)
        self.refresh()

    def on_select_drink(self, index):
        accepted, message = self.machine.select_drink(index)
        self.set_message(message)
        self.refresh()
        if accepted:
            self.animate_drop(index)

    def on_cancel(self):
        _, message = self.machine.cancel()
        self.set_message(message)
        self.refresh()

    def on_collect(self):
        collected, message = self.machine.collect()
        if collected:
            for item in self.slot_items:   # customer takes the drink
                self.canvas.delete(item)
            self.slot_items = []
        self.set_message(message)
        self.refresh()

    # -------------------------------------------------------------------------
    #  ANIMATIONS
    # -------------------------------------------------------------------------
    def animate_coin(self, value):
        """A small coin flies up into the coin slot."""
        coin = self.canvas.create_oval(527, 247, 543, 263,
                                       fill=MONEY_COLORS[value],
                                       outline="#5D4037")
        self._coin_step(coin, 0)

    def _coin_step(self, coin, step):
        if step < 6:
            self.canvas.move(coin, 0, -4)
            self.root.after(25, lambda: self._coin_step(coin, step + 1))
        else:
            self.canvas.delete(coin)

    def animate_drop(self, index):
        """A copy of the bought can falls down into the dispensing slot."""
        drink = DRINKS[index]
        x = self.COLUMN_X[index % 3]
        top = self.ROW_TOP[index // 3]
        items = self.draw_can(x, top, drink["color"])
        for item in items:
            self.canvas.tag_raise(item)
        self._drop_step(items, top, speed=2)

    def _drop_step(self, items, top, speed):
        target = self.SLOT_LANDING_TOP
        if top < target:
            dy = min(speed, target - top)
            for item in items:
                self.canvas.move(item, 0, dy)
            # speed grows each frame -> looks like gravity
            self.root.after(16, lambda: self._drop_step(items, top + dy, speed + 1))
        else:
            self.slot_items = items
            self.on_drop_finished()

    def on_drop_finished(self):
        """Animation finished -> send the internal 'done' input to the DFA."""
        _, message = self.machine.finish_dispensing()
        self.set_message(message)
        self.refresh()


# =============================================================================
#  PROGRAM ENTRY POINT
# =============================================================================

def run_console_test():
    """Print the DFA definition and test some input strings (no GUI)."""
    VendingDFA.print_transition_table()
    examples = [
        ["coin", "sel_ok", "done", "collect"],
        ["coin", "coin", "sel_low", "coin", "sel_ok", "done", "collect"],
        ["coin", "cancel", "collect"],
        ["coin", "sel_ok", "done"],
        ["coin"],
        [],
    ]
    print("\nExample input strings:")
    for word in examples:
        result = "ACCEPTED" if VendingDFA.accepts(word) else "rejected"
        shown = " ".join(word) if word else "(empty string)"
        print(f"  {result:9}  {shown}")
    print("\nChange examples:")
    for amount in (15, 37, 186):
        print(f"  P{amount}: {describe_change(amount)}")


def main():
    if "--test" in sys.argv:
        run_console_test()
        return
    root = tk.Tk()
    VendingMachineGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
