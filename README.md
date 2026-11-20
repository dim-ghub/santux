<img src="santux/data/santux.svg" width="96" align="right" alt="">

# Santux

A mod manager for GTA V on Linux (Steam + Proton), with a Qt / QML interface in Material 3 Expressive style.
It finds the game and its Proton prefix, searches and installs mods from
[gta5-mods.com](https://www.gta5-mods.com), keeps separate **mod profiles**, and sets up **GTAVXR**
(the VR mod) as a profile of its own.

- **Profiles.** Each mod profile has its own mods and its own `mods` folder. Switching swaps them in
  instantly (they're renamed, not copied). Requirements such as Script Hook V are shared. Built in:
  **Vanilla** (the game with nothing modded) and **GTAVXR** (VR).
- **Launch from Steam.** With the launch option set, starting GTA V from your library shows a small
  profile picker, or goes straight to a profile you choose.
- **Browse and install.** Search gta5-mods.com, pick a file version, and see exactly what will be
  installed before anything changes. Downloads are checked against the site's published SHA-256.
- **Native .oiv support.** OpenIV packages are applied by Santux itself (no Wine): archives
  are read with keys from your own `GTA5.exe` and edited copies go to the profile's `mods` folder.
- **Requirements.** One-click Script Hook V, the mods folder loader (RageOpenV), ScriptHookVDotNet,
  a gameconfig for your build, heap/packfile adjusters, VC++ and .NET Framework 4.8 in the prefix.
- **GTAVXR setup.** Downloads the Suite, fixes its startup crash under Wine, adds the `tar.exe` it
  needs for mod imports, and checks SteamVR.

GTA V Legacy is fully supported; Enhanced partly (see below). Story mode only.

## Requirements

- Steam (native or Flatpak) with GTA V installed and launched once.
- `7z` for `.7z`/`.rar` archives, and [protontricks](https://github.com/Matoking/protontricks).

The single binary carries everything else: Python, Qt, the interface and its fonts.

| Distro | Command |
| --- | --- |
| Arch | `sudo pacman -S 7zip protontricks` |
| Fedora | `sudo dnf install p7zip p7zip-plugins protontricks` |
| Debian/Ubuntu | `sudo apt install 7zip protontricks` |

## Build, install and run

```sh
./build.sh            # builds dist/santux, one self-contained executable (~100 MB)
./install.sh          # puts it in ~/.local/bin and adds Santux to your app menu
santux                # opens the app
```

`build.sh` needs Python 3.10+ and an internet connection the first time: it creates `.venv` with
PyInstaller and the PySide6, numpy, lxml and cryptography wheels (the wheels bring their own Qt, so
the binary doesn't depend on the system's). Copy `dist/santux` anywhere to use it elsewhere.

To run from the checkout without building, install PySide6 (Qt 6.5+), lxml, cryptography and
numpy for your system Python (`sudo pacman -S pyside6 python-lxml python-cryptography python-numpy`
on Arch), then run `bin/santux`; `./install.sh` links that when there is no `dist/santux`.

## First-time setup

1. Close GTA V and Steam.
2. **Requirements → Install all missing.** This prepares the prefix (VC++ and .NET 4.8, 10–20 min),
   then installs Script Hook V, the mods folder loader, ScriptHookVDotNet and the stability patches.
3. **Profiles → Steam launch option → Set.** GTA V's launch option becomes
   `santux launch %command%`. (With Steam open, use Copy and paste it into GTA V → Properties.)
4. Find mods on **Browse**, click **Install** on a file, check the plan, confirm.

## Profiles and launching

Choose the profile to edit in the sidebar; Browse and Installed work on it. **Play** starts GTA V
through Steam with that profile.

When GTA V starts from Steam, Santux picks the profile in this order:

1. a flag in the launch option: `--profile NAME`, `--vanilla` or `--vr`
   (e.g. `santux launch --vanilla %command%`),
2. a pending `santux play NAME` (from a terminal, a script or a desktop shortcut),
3. the **Profile to launch** setting: a fixed profile, or **Ask every time** for the picker.

For modded profiles it tells Proton to load the ASI loader (`WINEDLLOVERRIDES=dinput8=n,b`). Vanilla
launches without it, so nothing modded loads. GTAVXR launches `GTAVXR.exe` instead of `PlayGTAV.exe`.

## VR (GTAVXR)

The **VR** page walks through: .NET 4.8 → download the Suite → install GTAVXR in the Suite (the one
manual step: choose the game folder and click Install) → Wine startup fix → `tar.exe` → SteamVR.
Start SteamVR with the headset connected before launching the GTAVXR profile. After the Suite updates
GTAVXR or runs Check files, apply the Wine fix again.

GTAVXR runs its own rebuilt game exe, so trainers that pattern-scan the original (MenyooSP, for one)
don't work in VR; use GTAVXR's built-in trainer. Flatscreen mods never load in the VR profile.

## Colours

The interface uses Material 3 colour roles from, newest first:

- [KiiteShell](https://github.com/Kiite-Org/KiiteShell): `~/.local/state/kiite/user/generated/colors.json`
- [caelestia-cli](https://github.com/caelestia-dots/cli): `~/.local/state/caelestia/scheme.json`

and follows them live when your shell changes scheme. Without either, it uses a scheme generated from
the [GTA V palette](https://www.schemecolor.com/grand-theft-auto-gta-v.php) (Grassfield green,
Caramel Yellow, Beside Blue), dark or light to match your Qt palette. `SANTUX_SCHEME=gta`, `kiite` or
`caelestia` forces one.

## How mods are installed

| In the archive | What happens |
| --- | --- |
| `.oiv` packages | Applied natively into the profile's `mods` folder. Original `.rpf` files are never modified. |
| Add-on DLC (`<name>/dlc.rpf`) | Copied to `mods/update/x64/dlcpacks/<name>/` and registered in `dlclist.xml`. |
| `.asi` plugins | Copied to the game folder with their config files. |
| ScriptHookVDotNet scripts and `scripts/` folders | Copied to `scripts/`. |
| `menyooStuff/` folders | Merged into `menyooStuff/`. |
| Anything else | Listed as "not installed" with an **Open files** button. |

Each mod has an on/off switch on **Installed**. Turning one off moves its files aside and leaves its
packages out of the `mods` folder, without uninstalling it; turning it on puts everything back.

Uninstalling a package deletes the `mods` files it changed and re-applies the profile's remaining
packages; **Rebuild mods folder** does that for everything (needed after a game update). `.oiv`
`pso` operations (binary metadata edits) aren't supported yet.

## Command line

```sh
santux launch [--profile NAME | --vanilla | --vr | --ask] %command%   # Steam launch option
santux play NAME                  # start GTA V from Steam with a profile
santux profiles [--use S] [--new NAME] [--delete S] [--launch-default S|ask]
santux search blood --sort most-liked
santux install <gta5-mods URL | archive | folder> [--dry-run] [--oiv "Legacy"]
santux reqs | req <id> | list | uninstall <id>
```

## Notes

- **Game updates break script mods** until Script Hook V is updated (Requirements → Update), and the
  `mods` folder should be rebuilt so it's based on the new game files.
- **.NET 4.8 on Proton 11** needs workarounds that winetricks lacks; the app handles them (and puts
  the prefix back if anything fails).
- **GTA V Enhanced:** Script Hook V, the mods folder loader, `.oiv` packages and the adjusters work.
  ScriptHookVDotNet, the gameconfig and GTAVXR are Legacy-only.
- **Data** lives in `~/.local/share/santux`; inactive profiles' files in
  `<game>/santux/`. The NG decryption tables come from CodeWalker's `magic.dat`, downloaded
  once; they're useless without the key from your game.
- **Testing builds:** `SANTUX_SCREENSHOT=shot.png santux` saves the window after a few seconds and
  quits; with `QT_QPA_PLATFORM=offscreen` it needs no display.

## Credits

- **Tux** by Larry Ewing (lewing@isc.tamu.edu), made with The GIMP; the icon uses the monochrome
  outline from Wikimedia Commons, recoloured.
- **Material Symbols Rounded** by Google, Apache License 2.0: the interface's icons and the logo's
  star. The font is bundled (`santux/data/fonts/MaterialSymbols-LICENSE.txt`).
- **Anton** font by The Anton Project Authors, SIL Open Font License 1.1
  (`santux/data/fonts/Anton-OFL.txt`).
