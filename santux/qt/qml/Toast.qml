import QtQuick

// M3 snackbar.
Rectangle {
    id: root
    function show(msg) { label.text = msg; shown = true; timer.restart() }
    property bool shown: false
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: shown ? 24 : -height
    Behavior on anchors.bottomMargin { SpringAnimation { spring: Theme.springSpatial; damping: Theme.dampSpatial } }
    width: Math.min(label.implicitWidth + 48, parent.width - 80)
    height: label.implicitHeight + 28
    radius: Theme.cornerS
    color: Theme.inverseSurface
    z: 200
    Text {
        id: label
        anchors.left: parent.left; anchors.leftMargin: 24
        anchors.verticalCenter: parent.verticalCenter
        width: Math.min(implicitWidth, root.parent.width - 128)
        wrapMode: Text.Wrap
        color: Theme.inverseOnSurface
        font.pixelSize: 14
    }
    Timer { id: timer; interval: 4500; onTriggered: root.shown = false }
    MouseArea { anchors.fill: parent; onClicked: root.shown = false }
}
