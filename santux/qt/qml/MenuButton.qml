import QtQuick

// Icon button with an overflow menu. items: [{label, icon?, danger?}, ...]; emits triggered(index).
Item {
    id: root
    property var items: []
    property color color: Theme.fgSurfaceVariant
    signal triggered(int index)
    implicitWidth: 44
    implicitHeight: 44

    Rectangle {
        anchors.fill: parent
        radius: m.pressed || popup.opened ? Theme.cornerM : width / 2
        Behavior on radius { SpringAnimation { spring: 4; damping: 0.4 } }
        color: popup.opened ? Theme.secondaryContainer : Theme.fgSurface
        opacity: popup.opened ? 1 : m.pressed ? 0.12 : m.containsMouse ? 0.08 : 0
    }
    Icon {
        anchors.centerIn: parent
        name: "more_vert"
        size: 22
        color: popup.opened ? Theme.fgSecondaryContainer : root.color
    }
    MouseArea {
        id: m
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: popup.opened ? popup.close() : popup.open()
    }
    Menu {
        id: popup
        y: root.height + 4
        x: root.width - width
        transformOrigin: Item.TopRight
        items: root.items
        onTriggered: function (i) { root.triggered(i) }
    }
}
