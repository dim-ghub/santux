import QtQuick

// Santux wordmark: five filled wanted stars over the name in Anton, slanted, with a primary underline.
Item {
    id: root
    property int size: 46
    implicitWidth: name.implicitWidth + slant
    implicitHeight: stars.height + 2 + name.height + 6 + bar.height
    readonly property real slant: name.height * 0.18

    Accessible.role: Accessible.StaticText
    Accessible.name: "Santux"

    Row {
        id: stars
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 2
        Repeater {
            model: 5
            Icon { name: "star"; filled: true; size: Math.round(root.size * 0.42); color: Theme.tertiary }
        }
    }
    Text {
        id: name
        y: stars.height + 2
        x: root.slant
        text: "SANTUX"
        color: Theme.fgSurface
        font.family: "Anton"
        font.pixelSize: root.size
        font.letterSpacing: root.size * 0.04
        // Lean the letters forward, like the game's titles (Anton has no italic).
        transform: Matrix4x4 {
            matrix: Qt.matrix4x4(1, -0.18, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
        }
    }
    Rectangle {
        id: bar
        anchors.horizontalCenter: parent.horizontalCenter
        y: name.y + name.height + 6
        width: name.implicitWidth * 0.78
        height: Math.max(4, Math.round(root.size * 0.1))
        radius: height / 2
        color: Theme.primary
    }
}
