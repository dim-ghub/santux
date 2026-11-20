import QtQuick

// Navigation drawer item: the active one sits on a secondary-container pill that springs in.
Item {
    id: root
    property string text: ""
    property string icon: ""
    property bool active: false
    signal clicked()

    height: 52

    Rectangle {
        anchors.verticalCenter: parent.verticalCenter
        anchors.horizontalCenter: parent.horizontalCenter
        height: parent.height - 4
        width: root.active ? parent.width : parent.width * 0.55
        opacity: root.active ? 1 : 0
        radius: height / 2
        color: Theme.secondaryContainer
        Behavior on width { SpringAnimation { spring: Theme.springSpatial; damping: Theme.dampSpatial } }
        Behavior on opacity { NumberAnimation { duration: Theme.fast } }
    }
    Rectangle {
        anchors.fill: parent; anchors.topMargin: 2; anchors.bottomMargin: 2
        radius: height / 2
        color: Theme.fgSurface
        opacity: mouse.pressed ? 0.12 : mouse.containsMouse && !root.active ? 0.08 : 0
    }
    Icon {
        id: ic
        name: root.icon
        size: 22
        color: root.active ? Theme.fgSecondaryContainer : Theme.fgSurfaceVariant
        anchors.left: parent.left; anchors.leftMargin: 18
        anchors.verticalCenter: parent.verticalCenter
    }
    Text {
        text: root.text
        color: root.active ? Theme.fgSecondaryContainer : Theme.fgSurfaceVariant
        font.pixelSize: 14
        font.weight: root.active ? Font.Bold : Font.Medium
        anchors.left: ic.right; anchors.leftMargin: 14
        anchors.verticalCenter: parent.verticalCenter
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
