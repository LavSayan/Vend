# DFA Vending Machine (Python + Tkinter)

A 2D vending machine for CS 300 - Automata Theory and Formal Languages project on **Deterministic Finite Automata**.

## Run
```
python vend.py          # opens the GUI (800x700, not resizable)
python vend.py --test   # prints the transition table and example strings
```
On Linux you may need to install Tk first: `sudo apt install python3-tk`.

## Features
- The machine is drawn on a Canvas: cabinet, glass drink area, display screen, coin slot, change tray and dispensing slot.
- 6 drinks (Water P10, Iced Tea P15, Cola P20, Orange Juice P25, Coffee P30, Energy Drink P35). Each starts with 5 in stock. A drink that runs out is grayed out and labeled **SOLD OUT**.
- Money buttons for P1, P5, P10, P20, P50 and P100.
- Display messages: "Insert coins", "Select a drink", "Not enough money! Need Px more", "Enjoy your drink!".
- The drink falls into the slot with a gravity-style animation.
- Change uses the fewest coins possible, e.g. `Change: P15 (1x P10, 1x P5)`. The coins and bills are also drawn in the tray.
- **Cancel / Refund** returns the whole balance. **Collect / Reset** clears the trays for the next customer.
- DFA monitor:
  - a live `DFA State: ...` label in the top-right corner
  - a state diagram that highlights the current state
  - a log of every transition

## DFA (M = Q, Σ, δ, q0, F)
- **Q** = {IDLE, HAS_MONEY, DISPENSING, GIVING_CHANGE}
- **Σ** = {coin, sel_ok, sel_low, cancel, collect, done}
- **q0** = IDLE, **F** = {IDLE}
- **δ** is the `VendingDFA.TRANSITIONS` dictionary with all 24 (state, input) pairs.

| state | coin | sel_ok | sel_low | cancel | collect | done |
|---|---|---|---|---|---|---|
| IDLE | HAS_MONEY | IDLE | IDLE | IDLE | IDLE | IDLE |
| HAS_MONEY | HAS_MONEY | DISPENSING | HAS_MONEY | GIVING_CHANGE | HAS_MONEY | HAS_MONEY |
| DISPENSING | DISPENSING | DISPENSING | DISPENSING | DISPENSING | DISPENSING | GIVING_CHANGE |
| GIVING_CHANGE | GIVING_CHANGE | GIVING_CHANGE | GIVING_CHANGE | GIVING_CHANGE | IDLE | GIVING_CHANGE |

The balance is stored in a normal variable, not as states, because a DFA must have a finite number of states. Comparing the balance with the price creates the input `sel_ok` or `sel_low`.

## Code structure
1. `VendingDFA`: only the DFA (states, alphabet and transition table). No GUI and no money.
2. `VendingMachine`: balance, stock and change. It sends input symbols to the DFA.
3. `VendingMachineGUI`: Tkinter drawing, buttons and animations.
