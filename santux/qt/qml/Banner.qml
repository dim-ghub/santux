import QtQuick
import QtQuick.Shapes

// Santux wordmark: five filled wanted stars over the name in Anton, slanted, with a primary underline.
// Spacing is measured from the capitals (Anton's line box has a deep descender and leading).
Item {
    id: root
    property int size: 46
    readonly property real starSize: Math.round(size * 0.42)
    // The letters' ink, not the line box: no leading above, no letter spacing after the X.
    readonly property rect ink: inkMetrics.tightBoundingRect
    readonly property real capHeight: -ink.y
    readonly property real capTop: stars.height + Math.round(size * 0.12)
    readonly property real lean: 0.18
    readonly property real slant: capHeight * lean
    implicitWidth: ink.width + slant
    implicitHeight: bar.y + bar.height

    Accessible.role: Accessible.StaticText
    Accessible.name: "Santux"

    TextMetrics { id: inkMetrics; font: name.font; text: name.text }

    Row {
        id: stars
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 2
        Repeater {
            model: 5
            // Material Symbols "star" (filled), drawn as a shape: the font's FILL axis isn't applied
            // by every text renderer.
            Shape {
                width: root.starSize
                height: root.starSize
                preferredRendererType: Shape.CurveRenderer
                transform: Translate { y: root.starSize }
                ShapePath {
                    fillColor: Theme.tertiary
                    strokeWidth: -1
                    scale: Qt.size(root.starSize / 960, root.starSize / 960)
                    PathSvg { path: "M480-269 314-169q-11 7-23 6t-21-8q-9-7-14-17.5t-2-23.5l44-189-147-127q-10-9-12.5-20.5T140-571q4-11 12-18t22-9l194-17 75-178q5-12 15.5-18t21.5-6q11 0 21.5 6t15.5 18l75 178 194 17q14 2 22 9t12 18q4 11 1.5 22.5T809-528L662-401l44 189q3 13-2 23.5T690-171q-9 7-21 8t-23-6L480-269Z" }
                }
            }
        }
    }
    Text {
        id: name
        y: root.capTop - (baselineOffset - root.capHeight)
        x: root.slant / 2 - root.ink.x
        text: "SANTUX"
        color: Theme.fgSurface
        font.family: "Anton"
        font.pixelSize: root.size
        font.letterSpacing: root.size * 0.04
        // Lean the letters forward, like the game's titles (Anton has no italic). The shear pivots
        // on the middle of the capitals, so the word stays centred over the underline.
        transform: Matrix4x4 {
            readonly property real pivot: name.baselineOffset - root.capHeight / 2
            matrix: Qt.matrix4x4(1, -root.lean, 0, root.lean * pivot, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
        }
    }
    Rectangle {
        id: bar
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.capTop + root.capHeight + Math.round(root.size * 0.11)
        width: root.ink.width * 0.78
        height: Math.max(4, Math.round(root.size * 0.1))
        radius: height / 2
        color: Theme.primary
    }
}
