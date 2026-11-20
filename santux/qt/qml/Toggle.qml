import QtQuick

// M3 switch: 52×32 track, thumb grows from 16 to 24 when on and shows a check.
Item {
    id: root
    property bool checked: false
    signal toggled()
    implicitWidth: 52
    implicitHeight: 32

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: root.checked ? Theme.primary : Theme.surfaceContainerHighest
        border.width: root.checked ? 0 : 2
        border.color: Theme.outline
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
    Rectangle {
        id: thumb
        readonly property int d: mouse.pressed ? 28 : root.checked ? 24 : 16
        width: d; height: d; radius: d / 2
        anchors.verticalCenter: parent.verticalCenter
        x: root.checked ? root.width - d - 4 : (mouse.pressed ? 2 : 8)
        color: root.checked ? Theme.fgPrimary : Theme.outline
        Behavior on x { SpringAnimation { spring: Theme.springSpatial; damping: Theme.dampSpatial } }
        Behavior on width { NumberAnimation { duration: Theme.fast } }
        Behavior on height { NumberAnimation { duration: Theme.fast } }
        Icon { anchors.centerIn: parent; visible: root.checked; name: "check"; size: 16; weight: 700; color: Theme.fgPrimaryContainer }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: { root.checked = !root.checked; root.toggled() }
    }
}
