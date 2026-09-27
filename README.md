# OliveTin for Home Assistant

A Home Assistant integration for [OliveTin](https://www.olivetin.app/), which runs predefined shell commands from a web UI. Built for the OliveTin 2.x API.

## Features

- **A button for every OliveTin action**. The buttons stay in sync with OliveTin's config: new actions appear and removed ones go away.
- **`olivetin.start_action` action**: start any action, optionally with argument values.

## Setup

Enter OliveTin's address as seen from Home Assistant (default `http://localhost:1337`). Leave username and password empty if OliveTin has no login.

## Install

### HACS

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/Marshy-Madness/ha-olivetin` as an **Integration**.
2. Install **OliveTin** and restart Home Assistant.
3. *Settings → Devices & services → Add integration → OliveTin*.

### Manual

Copy `custom_components/olivetin` into `<config>/custom_components/` and restart Home Assistant.
