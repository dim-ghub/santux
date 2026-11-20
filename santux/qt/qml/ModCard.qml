import QtQuick
import QtQuick.Effects

// A mod in the Browse grid.
Rectangle {
    id: root
    property var mod: ({})
    signal clicked()
    radius: Theme.radius
    color: mouse.containsMouse ? Theme.surfaceContainerHigh : Theme.surfaceContainer
    Behavior on color { ColorAnimation { duration: Theme.fast } }
    scale: mouse.pressed ? 0.97 : 1
    Behavior on scale { SpringAnimation { spring: 4; damping: 0.35 } }

    Rectangle {
        id: imgBox
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        anchors.margins: 6
        height: width * 0.56
        radius: Theme.radius - 6
        color: Theme.surfaceContainerHighest
        Rectangle { id: mask; anchors.fill: parent; radius: parent.radius; visible: false; layer.enabled: true }
        Image {
            anchors.fill: parent
            // Rounded corners need the GPU; Qt's software renderer shows square ones instead.
            layer.enabled: GraphicsInfo.api !== GraphicsInfo.Software
            layer.effect: MultiEffect { maskEnabled: true; maskSource: mask; maskThresholdMin: 0.5; maskSpreadAtMin: 1.0 }
            source: root.mod.image ? "image://web/" + encodeURIComponent(root.mod.image) : ""
            sourceSize: Qt.size(320, 180)
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            opacity: status === Image.Ready ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 200 } }
        }
    }
    Column {
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: imgBox.bottom
        anchors.margins: 16
        anchors.topMargin: 12
        spacing: 4
        Text {
            width: parent.width
            text: root.mod.title || ""
            color: Theme.text
            font.pixelSize: 15
            font.weight: Font.DemiBold
            wrapMode: Text.Wrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }
        Text {
            width: parent.width
            text: [root.mod.version, root.mod.author].filter(function (x) { return x }).join("  ·  ")
            color: Theme.subtle
            font.pixelSize: Theme.fontSmall
            elide: Text.ElideRight
        }
        Text {
            width: parent.width
            text: (root.mod.downloads || "0") + " downloads  ·  ★ " + (root.mod.rating || "–")
            color: Theme.subtle
            font.pixelSize: Theme.fontSmall
            elide: Text.ElideRight
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
