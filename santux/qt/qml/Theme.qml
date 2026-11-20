pragma Singleton
import QtQuick

// Material 3 Expressive roles, derived from the system Qt palette (your colour scheme):
// primary is the palette's highlight, surfaces are tonal steps from its window colour.
QtObject {
    id: t
    readonly property SystemPalette pal: SystemPalette { colorGroup: SystemPalette.Active }
    readonly property bool dark: surface.hslLightness < 0.5

    function mix(a, b, k) { return Qt.rgba(a.r + (b.r - a.r) * k, a.g + (b.g - a.g) * k, a.b + (b.b - a.b) * k, 1) }
    function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

    // ---- colour roles: from KiiteShell / caelestia when present, otherwise the GTA V scheme
    readonly property var c: typeof scheme !== "undefined" && scheme ? scheme.colors : ({})
    function role(name, fallback) { return c[name] !== undefined ? c[name] : fallback }
    readonly property color primary: role("primary", pal.highlight)
    readonly property color fgPrimary: role("onPrimary", pal.highlightedText)
    readonly property color primaryContainer: role("primaryContainer", mix(primary, surface, 0.62))
    readonly property color fgPrimaryContainer: role("onPrimaryContainer", fgSurface)
    readonly property color secondary: role("secondary", primary)
    readonly property color secondaryContainer: role("secondaryContainer", mix(primary, surface, 0.78))
    readonly property color fgSecondaryContainer: role("onSecondaryContainer", fgSurface)
    readonly property color tertiary: role("tertiary", primary)
    readonly property color tertiaryContainer: role("tertiaryContainer", mix(tertiary, surface, 0.68))
    readonly property color fgTertiaryContainer: role("onTertiaryContainer", fgSurface)
    readonly property color surface: role("surface", pal.window)
    readonly property color fgSurface: role("onSurface", pal.windowText)
    readonly property color fgSurfaceVariant: role("onSurfaceVariant", mix(fgSurface, surface, 0.28))
    readonly property color surfaceContainerLowest: role("surfaceContainerLowest", mix(surface, "#000000", 0.25))
    readonly property color surfaceContainerLow: role("surfaceContainerLow", mix(surface, fgSurface, 0.035))
    readonly property color surfaceContainer: role("surfaceContainer", mix(surface, fgSurface, 0.06))
    readonly property color surfaceContainerHigh: role("surfaceContainerHigh", mix(surface, fgSurface, 0.09))
    readonly property color surfaceContainerHighest: role("surfaceContainerHighest", mix(surface, fgSurface, 0.125))
    readonly property color outline: role("outline", mix(fgSurface, surface, 0.5))
    readonly property color outlineVariant: role("outlineVariant", mix(fgSurface, surface, 0.8))
    readonly property color inverseSurface: role("inverseSurface", fgSurface)
    readonly property color inverseOnSurface: role("inverseOnSurface", surface)
    readonly property color error: role("error", dark ? "#ffb4ab" : "#ba1a1a")
    readonly property color errorContainer: role("errorContainer", dark ? "#93000a" : "#ffdad6")
    readonly property color fgErrorContainer: role("onErrorContainer", dark ? "#ffdad6" : "#410002")
    readonly property color good: dark ? "#8fd99b" : "#1e6b35"
    readonly property color goodContainer: dark ? "#1f4d2a" : "#c9efcf"
    readonly property color caution: dark ? "#f3c06b" : "#7a5300"
    readonly property color cautionContainer: dark ? "#5a4100" : "#ffe1a6"
    readonly property color scrim: alpha("#000000", dark ? 0.6 : 0.4)

    // ---- names used across the pages (kept so pages read naturally)
    readonly property color window: surface
    readonly property color text: fgSurface
    readonly property color subtle: fgSurfaceVariant
    readonly property color base: surfaceContainerHighest
    readonly property color baseText: fgSurface
    readonly property color accent: primary
    readonly property color accentText: fgPrimary
    readonly property color card: surfaceContainer
    readonly property color cardHover: surfaceContainerHigh
    readonly property color sidebar: surfaceContainerLow
    readonly property color border: outlineVariant
    readonly property color faint: alpha(fgSurface, 0.08)
    readonly property color disabledText: alpha(fgSurface, 0.38)
    readonly property color success: good
    readonly property color warning: caution
    readonly property color danger: error

    // ---- shape (M3 Expressive corner scale)
    readonly property int cornerXS: 4
    readonly property int cornerS: 8
    readonly property int cornerM: 12
    readonly property int cornerL: 16
    readonly property int cornerXL: 28
    readonly property int radius: 24          // cards
    readonly property int radiusSmall: 12

    // ---- spacing
    readonly property int pad: 20
    readonly property int gap: 12

    // ---- type scale
    readonly property int fontSmall: 12       // label/body small
    readonly property int fontBody: 14        // body medium
    readonly property int fontHeading: 16     // title medium
    readonly property int fontTitle: 28       // headline medium
    readonly property int fontHuge: 36        // display small

    // ---- motion: expressive spatial spring
    readonly property real springSpatial: 3.2
    readonly property real dampSpatial: 0.32
    readonly property int fast: 150
    readonly property int medium: 300
}
