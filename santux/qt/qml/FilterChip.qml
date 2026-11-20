import QtQuick

// M3 filter chip: outlined when off; secondary-container with a leading check when on.
Rectangle {
    id: root
    property string text: ""
    property string icon: ""
    property bool checked: false
    signal toggled()

    implicitHeight: 40
    implicitWidth: row.implicitWidth + 32
    radius: m.pressed ? Theme.cornerS + 4 : Theme.cornerS
    Behavior on radius { SpringAnimation { spring: 4; damping: 0.4 } }
    color: checked ? Theme.secondaryContainer : "transparent"
    border.width: checked ? 0 : 1
    border.color: Theme.outlineVariant
    Behavior on color { ColorAnimation { duration: Theme.fast } }

    Rectangle {
        anchors.fill: parent
        radius: parent.radius
        color: root.checked ? Theme.fgSecondaryContainer : Theme.fgSurfaceVariant
        opacity: m.pressed ? 0.12 : m.containsMouse ? 0.08 : 0
    }
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 8
        Icon {
            name: root.checked ? "check" : root.icon
            size: 18
            color: root.checked ? Theme.fgSecondaryContainer : Theme.fgSurfaceVariant
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            text: root.text
            color: root.checked ? Theme.fgSecondaryContainer : Theme.fgSurfaceVariant
            font.pixelSize: 14
            font.weight: Font.Medium
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    MouseArea {
        id: m
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: { root.checked = !root.checked; root.toggled() }
    }
    Accessible.role: Accessible.CheckBox
    Accessible.name: text
    Accessible.checked: checked
}
