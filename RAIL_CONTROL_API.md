# Rail Control REST API — integration spec

Written for whoever builds a "Rail control" page in the robot repo's React UI
(`/home/tom/dev/embedded/Nanotec/robot/server/frontend`). That UI normally
talks to its backend over NATS; this API is the exception — the rail rig is
a separate machine (a Raspberry Pi) and the new page should talk to it
**directly over HTTP**, bypassing NATS entirely.

Source of truth: `rail_web_ui.py` (serves the API + the existing vanilla-JS
UI in `webui/`) in this repo. If anything here looks stale, that file wins.

## Transport

- Plain HTTP, JSON in/out. No auth, no HTTPS. Assumed to run on a trusted LAN.
- Default bind: `0.0.0.0:8080` (`python rail_web_ui.py --host --port`).
- **CORS is enabled** (wildcard `Access-Control-Allow-Origin: *`, plus an
  `OPTIONS` preflight handler for `GET`/`POST`/`Content-Type`) — a browser
  page served from a different origin, e.g. the robot UI, can call this API
  directly. Fine for a LAN-only, no-credentials deployment; revisit if this
  ever needs to be reachable off the local network.
- **Mixed content**: the robot UI is served over plain `http://` on the LAN
  (no TLS), so this is a non-issue for now. If that ever changes to
  `https://`, the Pi would need TLS too or calls from the robot UI would be
  blocked as mixed content.
- No WebSocket/SSE — everything is polled. The existing UI polls
  `GET /api/state` every **250 ms** (`POLL_INTERVAL_MS` in `webui/app.js`);
  match that cadence for a similar feel.

## Endpoints

### `GET /api/config`

Fetched once at page load. Describes what controllers exist and how to
render controls for them — the existing UI builds its panels generically
from this, and a React version should do the same rather than hardcoding
fields.

```json
{
  "controllers": [
    {
      "name": "cart",
      "suffix": "0168",
      "role": "cart",
      "params": [
        {
          "key": "jog_speed", "label": "Joy max speed (rpm)", "kind": "slider",
          "group": "jog", "default": 700, "min": 50, "max": 700, "step": 10,
          "software": true
        },
        { "key": "kp", "label": "Kp (rpm / digit)", "kind": "number", "group": "pid",
          "default": 4.5, "min": -50, "max": 50, "step": 0.1, "software": true },
        { "key": "length_comp", "label": "Rope-length compensation", "kind": "select",
          "group": "pid", "default": 1,
          "options": [{ "value": 1, "label": "On" }, { "value": 0, "label": "Off" }] }
        // ... one entry per tunable param; "kind" is "select" | "number" | "slider"
      ],
      "readout": [
        { "key": "status_word", "label": "Drive state (6041h)", "fmt": "statusword" },
        { "key": "position_actual", "label": "Position actual value (6064h)", "fmt": null },
        { "key": "digital_inputs", "label": "Endstops (60FDh)", "fmt": "endstops" }
        // ... see "Readout decoding" below for every fmt value
      ],
      "down_limit": null
    },
    { "name": "lift", "suffix": "0173", "role": "lift", "params": [...], "readout": [...], "down_limit": -120000 }
  ],
  "modes": [
    { "key": "basic", "label": "Basic" },
    { "key": "walking", "label": "Walking" }
  ],
  "mode": "basic",
  "simulate": false
}
```

Notes:
- `role` is `"cart"` or `"lift"` — they have different param/readout sets
  (the lift has no PID/analog-angle row; the cart has no brake row).
- `params[].group` is `"jog"` | `"pid"` | `"walk"` — used to sort a param
  into the joystick card / PID card / walk-tuning card. Keys not in any
  group's UI slot go in a generic "Parameters" section.
- `mode`/`modes` drive a system-wide (not per-controller) mode switcher —
  see "Operating mode" below.

### `GET /api/state`

Polled continuously (every 250 ms in the existing UI). Live values for every
controller, keyed by controller `name`.

```json
{
  "mode": "basic",
  "controllers": {
    "cart": {
      "connected": true,
      "drive_enabled": true,
      "jog_direction": 0,
      "pid_running": false,
      "homing_complete": null,
      "homing_in_progress": false,
      "heartbeat_ok": true,
      "last_error": null,
      "walk_status": null,
      "top_move_status": null,
      "down_limit_active": false,
      "pid_length_scale": 1.0,
      "state": {
        "status_word": 559,
        "position_actual": 1234,
        "velocity_actual": 0,
        "torque_actual": 0,
        "error_count": 0,
        "analog_input_1": 512,
        "control_word": 15,
        "digital_inputs": 0,
        "digital_outputs": null,
        "motor_current": 12,
        "neg_limit": false,
        "pos_limit": false
      },
      "params": { "jog_speed": 700, "jog_accel": 1000, "kp": 4.5, "...": "..." }
    },
    "lift": { "...": "same shape, role-appropriate fields" }
  }
}
```

- `homing_complete` / `homing_in_progress` / `walk_status` /
  `top_move_status` are lift-only (`null`/`false` on the cart).
- `state` values are `null` when a read failed or the field doesn't apply to
  that role (e.g. `digital_outputs` on the cart, `analog_input_1` on the
  lift).
- `jog_direction` is `-1` | `0` | `1` — what's currently commanded, not just
  what the UI last sent (the server can override it, e.g. end-stop stop).

### `POST /api/<controller>/<action>`

`<controller>` is a `name` from `/api/config` (`cart` | `lift`). Body is
JSON (may be `{}`). Response is always
`{"ok": bool, "message": str, "controller": <same shape as one entry of
/api/state's controllers>}`, status 200 on `ok`, 400 otherwise.

| action | body | effect |
|---|---|---|
| `param` | `{"key": "jog_speed", "value": 500}` | set one live parameter (clamped server-side to its `min`/`max`) |
| `jog` | `{"direction": -1\|0\|1}` | step-jog at the fixed jog speed (button-style, not the joystick) |
| `jog_velocity` | `{"velocity": 340, "seq": 12, "epoch": "abc-123"}` | joystick drive — see "Joystick contract" below |
| `jog_stop` | `{}` | release the stick: ramp to zero, stay enabled |
| `stop` | `{}` | full STOP (drive disabled, brake closed) |
| `enable` | `{}` | enable the drive without commanding motion |
| `pid` | `{"action": "start"\|"stop"}` | cart only — start/stop the software balance loop |
| `lift` | `{"direction": "up"\|"down"}` | lift-only templated move (see file header — not fully wired to real kinematics yet) |
| `drive_to_top` | `{}` | lift-only — one-click move up to the top end stop at the average allowed joy speed, see "Drive to top" below |
| `walk_rearm` | `{}` | lift-only — re-arm the Walking-mode sequence after a fall catch/abort |
| `sim_fall` | `{}` | simulate-mode + lift-only test hook, not relevant to real hardware |

### `POST /api/system/mode`

Body `{"mode": "basic"|"walking"}`. Switches the system-wide operating mode
(applies to every controller). Response:
`{"ok": bool, "message": str, "mode": "<new or unchanged mode>"}`.

### `POST /api/settings/save` / `POST /api/settings/load`

Body `{}`. Save/reload the current param values to/from
`config/settings.json` on the Pi. Response:
`{"ok": bool, "message": str, "controllers": <same shape as /api/state's controllers>}`.

## Joystick contract (`jog_velocity`)

The existing UI drives a spring-return one-axis joystick; a *held* stick is
a **lease, not a latch**. Replicating this matters for a "mimics
functionality" goal:

- While the stick is held, the UI re-posts the current velocity every
  **100 ms** (`JOY_HOLD_INTERVAL_MS`).
- The server treats each non-zero `jog_velocity` as extending a deadman
  lease of **350 ms** (`JOG_DEADMAN_TIMEOUT_S`). If updates stop arriving —
  released pointer, dropped POST, closed tab, dead WiFi — the server ramps
  the axis to zero on its own. Don't rely on always being able to send an
  explicit `jog_stop` on release; it's a nice-to-have, the deadman is the
  real backstop.
- `velocity` is signed rpm, clamped server-side to the controller's
  `jog_speed` param.
- `seq` / `epoch`: `seq` is a per-page-load counter starting at 1, `epoch` a
  random id generated once per page load
  (`Math.random().toString(36).slice(2) + "-" + Date.now()` in the existing
  UI). The server uses these to make a *release* win over a same-instant
  drag update that's still in flight, and to let a freshly reloaded page
  take over the stick from a stale one. Both are optional — omit them
  (or pass `null`) and every command is just applied in arrival order,
  which is fine for a first cut but reintroduces the "let go and it keeps
  driving for a moment" race under bad network conditions.

## Drive to top (`drive_to_top`, lift only)

The counterpart to the joystick for the one move that always has the same
destination: `POST /api/lift/drive_to_top` (body `{}`) drives the lift **up at
the average allowed joy speed** — the middle of the `jog_speed` param's
`min`/`max` from `/api/config`, i.e. 275 rpm as shipped — until the top end
stop, then parks it there (drive disabled, load on the closed brake), which is
also where an unhomed lift homes itself.

Unlike `jog_velocity` this is **fire-and-forget**: the move runs server-side,
needs no repeats, and is *not* covered by the deadman. Follow it via
`top_move_status` in `/api/state` (`null` while idle | `"driving"` | `"at top"` |
`"aborted"`, reason in `last_error`) and interrupt it with `POST
/api/lift/stop` — a `jog_velocity` command or a mode switch also takes it over.
The existing UI grays its "To top" button out while `"driving"` and while
`state.pos_limit` is set.

## Readout decoding

`readout[].fmt` from `/api/config` tells you how to render a `state` value
from `/api/state`. Ports of `webui/app.js`'s `fmtReadout`/`decodeStatusword`/
`decodeControlword`:

- `null` — show the raw number.
- `"statusword"` — CiA 402 state machine (6041h). Mask `sw & 0x6F` (or
  `0x4F` for two states) against:
  `0x00`→"Not ready to switch on", `0x40`→"Switch on disabled",
  `0x21`→"Ready to switch on", `0x23`→"Switched on",
  `0x27`→"Operation enabled", `0x07`→"Quick stop active",
  `0x0F`(masked `0x4F`)→"Fault reaction active", `0x08`(masked `0x4F`)→"Fault".
  Unmatched → hex.
- `"controlword"` — 6040h command: `cw&0x80`→"Fault reset",
  `(cw&0x82)==0`→"Disable voltage", `(cw&0x86)==0x06`... (see
  `decodeControlword` in `webui/app.js:610` for the exact bit checks) →
  "Quick stop"/"Enable operation"/"Switch on"/"Shutdown". Unmatched → hex.
- `"endstops"` — bit 0 = negative limit triggered, bit 1 = positive limit
  triggered; show which (`"NEG"`, `"POS"`, `"NEG + POS"`) or `"clear"`.
- `"brake"` — bit 0: `1` = "CLOSED" (brake engaged, no current), `0` =
  "released".

## Operating mode

One mode for the whole rig, not per-controller — `basic` (default) or
`walking`. `walking` starts the lift's autonomous auto-lower/tension/fall-
catch sequence server-side; the UI only needs a mode switch (radio buttons
in the existing header) and to surface `walk_status` (`null` |
`"lowering"` | `"tensioning"` | `"grounded"` | `"aborted"` | `"caught"`) and
a "Re-arm walk" action when it's stuck.

## Suggested minimal scope for a first version

To "mimic functionality" without porting everything on day one, the
highest-value subset is probably: live readout table (from `/api/state` +
the `fmt` decode above), the joystick + STOP per controller, and the mode
switch. PID tuning, Walking-mode calibration params, and settings save/load
can follow once the basic loop is proven end-to-end.

## Config needed on the robot UI side

A settings field for the Pi's IP and port (e.g. `192.168.1.50:8080`),
persisted client-side (the existing rail UI already keeps its theme choice
in `localStorage`, matching that pattern is reasonable). No auth token or
credential is needed against this API as it stands.
