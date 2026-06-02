<div align="center">

<img src="assets/icon.svg" width="88" alt="BridgeMix logo"/>

# BridgeMix

**A sleek, unofficial Linux controller for the Roland BRIDGE CAST audio mixer.**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
![Platform: Linux](https://img.shields.io/badge/platform-Linux-1793D1?logo=linux&logoColor=white)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![GUI: PyQt6](https://img.shields.io/badge/GUI-PyQt6-41CD52?logo=qt&logoColor=white)

<img src="doc/screenshots/screenshot_mixer.png" width="860" alt="BridgeMix mixer view"/>

</div>

---
> **Notice on AI:** Parts of this project were developed with AI assistance. 
> The code has been reviewed and curated by the maintainer, but you may encounter rough edges. Bug reports are welcome.


## About

The official Roland companion app is Windows/macOS only. **BridgeMix** brings full
control of the Bridge Cast to Linux — mixes, mic FX, voice changer, game FX, output
routing, profiles and live metering — by speaking the device's MIDI SysEx protocol.
No custom driver needed: the Bridge Cast is USB-Audio-class compliant.

## Features

| Area | Highlights |
|---|---|
| **Mixer** | Stream + Personal buses · all 7 channels (volume + mute) · Mix Mode · Mix Link · live level meters |
| **Outputs** | Sub-Mix volume · output mutes (Stream / Sub-Mix / Phones / Line) · Output Delay · Line / USB / Sub-Mix modes |
| **Profiles** | 5 slots — select, rename, save |
| **Mic input** | Source (XLR / headset) · +48 V phantom · gain |
| **Mic FX** | Low Cut · Noise Suppressor (Gate / Adaptive / Expander) · De-esser · Compressor (Legacy + Modern LA-2A) · 10-band EQ **with live spectrum analyzer** |
| **Voice FX** | Pitch · Formant · Avatar / Sing · Reverb · 5 preset slots |
| **Game FX** | 10-band EQ · Limiter · Virtual Surround · 5 preset slots |
| **Chat FX** | De-esser · Compressor |
| **Hardware** | Strip channel assignment · strip button actions · LED ring colours · HOT KEY button 1 |
| **System** | LED brightness · phones gain · indicator type · mute display · SFX A/B volume |
| **Tools** | Device auto-detect · JSON preset save / load · live MIDI monitor |
| **Remote API** | Optional local REST API (read/set any parameter) · Swagger UI · for Stream Deck, OBS, scripts |

### Not implemented yet

| Feature | Why |
|---|---|
| Game EQ spectrum analyzer | The host-side SUB MIX capture is unresolved on Linux — the **Mic EQ** analyzer ships and works |
| HOT KEY buttons 2–4 · SFX A/B trigger · Beep | SysEx addresses not yet mapped |
| Voice Transformer extras (Robot, Megaphone, consonant mode) | Stored in preset banks; live addresses unknown |
| Some fine Mic-FX params (NS Adaptive attack/release, a few LA-2A controls) | Addresses not yet captured |
| Per-strip LED on/off · per-preset LED colours | Write path unknown |
| BGM · HDMI controls (Bridge Cast X)  | Out of current scope |
| Firmware update | Intentionally **not** supported (too risky) |

## Screenshots

<details>
<summary><b>Show the rest of the app</b></summary>

<br/>

| Mic FX | Voice FX |
|:---:|:---:|
| <img src="doc/screenshots/screenshot_mic_fx.png" width="410"/> | <img src="doc/screenshots/screenshot_voice_fx.png" width="410"/> |
| **Game FX** | **Chat FX** |
| <img src="doc/screenshots/screenshot_game_fx.png" width="410"/> | <img src="doc/screenshots/screenshot_chat_fx.png" width="410"/> |
| **Mic Setup** | **Output** |
| <img src="doc/screenshots/screenshot_mic_setup.png" width="410"/> | <img src="doc/screenshots/screenshot_output.png" width="410"/> |
| **System** | **MIDI Monitor** |
| <img src="doc/screenshots/screenshot_system.png" width="410"/> | <img src="doc/screenshots/screenshot_midi_monitor.png" width="410"/> |

</details>

## Install & Run
This software was developed on an original Roland Brige Cast. The compatibility to the Bridge Cast X and BridgeCast ONE is not guaranteed.
**Requirements**

- **Linux** — or **Windows** (the app runs there too)
- A **Roland Bridge Cast** (original, V2) on **FW 3.00 (115)**
- **Python 3.11+**, or conda

```bash
git clone https://github.com/Ex0danify/BridgeMix.git
cd BridgeMix
./setup.sh          # Linux
setup.bat        # Windows (double-click, or run in a terminal)
```

Run from a terminal, `setup.sh` (Linux) and `setup.bat` (Windows) show a friendly menu:

| Option | What it does |
|---|---|
| **Install & Launch** | Sets things up, adds BridgeMix to your apps/Start menu, and starts it |
| **Launch** | Starts BridgeMix without adding a menu entry |
| **Uninstall** | Removes the apps/Start-menu entry |

Prefer flags? `--install` · `--launch` · `--uninstall` (works on both `./setup.sh` and `setup.bat`).

It sets itself up automatically — a `bridgemix` conda env if you have conda, otherwise
a self-contained Python venv (`.venv`). The first run downloads dependencies (about a
minute); after that it's instant. Force a backend with `BRIDGEMIX_BACKEND=conda|venv`.

> **New to Linux?** If your file manager asks what to do with `setup.sh`, choose
> **“Run in Terminal”** to see the menu. Once installed, just launch BridgeMix from your
> applications menu like any other app.

## Using it

1. Connect the Bridge Cast over USB.
2. Open BridgeMix and click **Connect** — it auto-detects the MIDI ports.
3. Tweak away; everything applies to the device live.

## Remote API (REST)

An **optional** local HTTP API lets third-party tools — Stream Deck, OBS, or your
own scripts — read and set any device parameter. It is **off by default** and
**bound to `127.0.0.1`** (loopback only; never exposed to the network).

**Enable it** in the **Extras** tab → *Remote API (REST)*: tick **Enable REST API**
and pick a port (default `8765`). The extra dependencies (`fastapi`, `uvicorn`)
aren't part of the base install — if they're missing, the panel shows an
**Install Dependencies** button that fetches them into the running environment.
Prefer the command line? `pip install bridgemix[api]`.

Once running, open the **interactive Swagger docs** at `http://127.0.0.1:8765/docs`
(ReDoc at `/redoc`, raw schema at `/openapi.json`).

> **Security.** The API is loopback-only and **unauthenticated** — anything that
> can reach `127.0.0.1` can drive your mixer. To stop a web page in your browser
> from quietly poking the local API, a built-in guard rejects requests with an
> unexpected `Host` header (DNS-rebinding) or a cross-site `Origin` (CSRF). Local
> tools that send neither (curl, Stream Deck) and the Swagger page itself are
> unaffected. Treat the port as trusted-local only; don't bind it to a public
> interface.

| Method & path | Does |
|---|---|
| `GET /api/v1/status` | Connection status (connected, model, firmware) |
| `GET /api/v1/parameters` | List every parameter with its range and current value |
| `GET /api/v1/parameters/{name}` | Read one parameter |
| `PUT /api/v1/parameters/{name}` | Set one parameter (`{"value": …}`) |
| `GET /api/v1/state` | Flat `name → value` map of all cached values |

```bash
# Discover parameters
curl http://127.0.0.1:8765/api/v1/parameters

# Mute the stream mic channel (parameter names come from the list above)
curl -X PUT http://127.0.0.1:8765/api/v1/parameters/st_mic_mute \
     -H 'Content-Type: application/json' -d '{"value": 1}'
```

## Disclaimer

**BridgeMix is an independent, unofficial project.** It is **not affiliated with,
authorized, maintained, sponsored, or endorsed by Roland Corporation**, or any of
its subsidiaries or affiliates. "Roland" and "BRIDGE CAST" are trademarks of
Roland Corporation, used here solely to identify the hardware this software
interoperates with. The control protocol was determined through independent
observation.

The software is provided **"as is", without warranty of any kind**, express or
implied (see the [LICENSE](LICENSE) for the full terms). Behaviour described here
may not work on every platform, operating system, or device/firmware
configuration. Interacting with your audio hardware is **at your own risk.**


## License

BridgeMix is licensed under the **GNU General Public License v3.0 or later**
(GPL-3.0-or-later). See [LICENSE](LICENSE).
