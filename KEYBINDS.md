# LogicX-Push2 — Full Keybinding Reference

Keybindings are defined in `push2_keymap.json`. Holding **Shift** on the Push 2 while pressing a button sends the `_shift` variant of that command.

**Modifier key notation used below:**
| Symbol | Key |
|--------|-----|
| `Cmd` | ⌘ Command |
| `Shift` | ⇧ Shift |
| `Ctrl` | ⌃ Control |
| `Alt` | ⌥ Option/Alt |

---

## Transport

| Push 2 Button | Action | Logic Shortcut | Shift Action | Shift Shortcut |
|---|---|---|---|---|
| Play | Play / Stop | `Space` | Play (alternate) | `Shift+Space` |
| Record | Record | `R` | Record alternate | `Shift+R` |
| Tap Tempo | Tap Tempo | `Shift+Ctrl+Alt+Cmd+T` † | — | — |
| Undo | Undo | `Cmd+Z` | Undo (shift) | `Shift+Cmd+Z` |
| Redo | Redo | `Cmd+Shift+Z` | — | — |
| Metronome | Toggle Metronome | `K` | Metronome alt | `Shift+K` |

> † **Tap Tempo requires a custom key command in Logic.** Logic has no Tap Tempo shortcut by default. Open `Logic Pro → Settings → Key Commands`, search for **Tap Tempo**, and assign it to `Shift+Ctrl+Alt+Cmd+T` to match the binding above.

---

## Editing

| Push 2 Button | Action | Logic Shortcut | Shift Action | Shift Shortcut |
|---|---|---|---|---|
| Delete | Delete | `Delete` | Delete (shift) | `Shift+Delete` |
| Duplicate | Duplicate | `D` | Duplicate variation | `A` |
| Duplicate (long press) | Duplicate long | `Cmd+Shift+Ctrl+D` | — | — |
| Convert | Convert | `Ctrl+B` | Convert (shift) | `Shift+Ctrl+B` |
| New | New Region | `Alt+Cmd+N` | New (shift) | `A` |
| New (next) | New Next | `Ctrl+Enter` | New Next (shift) | `Shift+Ctrl+Enter` |
| Automate | Automate | `A` | Automate (shift) | `Shift+A` |
| Quantize | Quantize | `Q` | — | — |
| Double Loop | Double Loop | `C` | Double (shift) | `Shift+C` |

---

## Mixing

| Push 2 Button | Action | Logic Shortcut | Shift Action | Shift Shortcut |
|---|---|---|---|---|
| Mute | Mute | `M` | Mute (shift) | `Shift+M` |
| Mute (off) | Clear All Mutes | `Ctrl+Shift+M` | Clear Mutes (shift) | `Shift+Ctrl+Shift+M` |
| Solo | Solo | `S` | Solo (shift) | `Shift+S` |
| Solo Lock | Lock Solo | `Ctrl+S` | Solo Lock (shift) | `Shift+Ctrl+S` |
| Stop Clip | Stop Clip | `V` | Stop Clip (shift) | `Shift+V` |

---

## Navigation & Views

| Push 2 Button | Action | Logic Shortcut | Shift Action | Shift Shortcut |
|---|---|---|---|---|
| Arrow Up | Navigate Up | `↑` | Select Up | `Shift+↑` |
| Arrow Down | Navigate Down | `↓` | Select Down | `Shift+↓` |
| Arrow Left | Navigate Left | `←` | Select Left | `Shift+←` |
| Arrow Right | Navigate Right | `→` | Select Right | `Shift+→` |
| Browse | Browse | `Y` | Browse (shift) | `Shift+Y` |
| Device | Show Device | `B` | Device (shift) | `Shift+B` |
| Clip | Show Clip | `C` | Clip (shift) | `Shift+C` |
| Mix | Show Mixer | `X` | Mixer (shift) | `Shift+X` |
| Add Track | Add Track | `T` | Add Track (shift) | `Shift+T` |
| Layout | Layout | `L` | Layout (shift) | `Shift+L` |
| Session | Session | `E` | Session (shift) | `Shift+E` |
| Fixed Length | Fixed Length | `\` | Fixed Length (shift) | `Shift+\` |

---

## Repeat

| Push 2 Button | Action | Logic Shortcut | Shift Action | Shift Shortcut |
|---|---|---|---|---|
| Repeat | Enable Repeat | `Ctrl+Alt+Enter` | Repeat (shift) | `Shift+Ctrl+Alt+Enter` |
| Repeat (release / off) | Disable Repeat | `Escape` | — | — |

---

## Quantize Grid

> **Note:** These shortcuts require custom key commands to be assigned in Logic Pro's Key Commands editor (`Logic Pro → Settings → Key Commands`). The shortcuts below are the defaults expected by LogicX-Push2 — assign them in Logic to match.

| Push 2 Button | Quantize Value | Required Logic Key Command |
|---|---|---|
| 1/32T | 1/32 Triplet | `Alt+Cmd+Shift+Ctrl+7` |
| 1/32 | 1/32 | `Alt+Cmd+Shift+Ctrl+3` |
| 1/16T | 1/16 Triplet | `Alt+Cmd+Shift+Ctrl+6` |
| 1/16 | 1/16 | `Alt+Cmd+Shift+Ctrl+2` |
| 1/8T | 1/8 Triplet | `Alt+Cmd+Shift+Ctrl+5` |
| 1/8 | 1/8 | `Alt+Cmd+Shift+Ctrl+1` |
| 1/4T | 1/4 Triplet | `Alt+Cmd+Shift+Ctrl+4` |
| 1/4 | 1/4 | `Alt+Cmd+Shift+Ctrl+0` |

---

## Modifier Notes

- **Shift** held while pressing any button triggers the `_shift` variant (usually a related alternate action).
- **Long press** on certain buttons (Undo → Redo, Play → Stop, Duplicate → alternate) triggers extended behaviors defined in the mode code rather than in `push2_keymap.json`.
- All keybindings can be customized by editing `push2_keymap.json` in the repo root.
