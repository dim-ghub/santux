import QtQuick

// M3 search bar / filled text field: full-pill container, leading icon.
Rectangle {
    id: root
    property alias text: input.text
    property string placeholder: ""
    property string icon: ""
    signal accepted()

    implicitHeight: 48
    implicitWidth: 260
    radius: height / 2
    color: Theme.surfaceContainerHigh
    border.width: input.activeFocus ? 2 : 0
    border.color: Theme.primary

    Icon {
        id: ic
        name: root.icon
        size: 20
        color: Theme.fgSurfaceVariant
        anchors.left: parent.left; anchors.leftMargin: 18
        anchors.verticalCenter: parent.verticalCenter
    }
    TextInput {
        id: input
        anchors.left: ic.visible ? ic.right : parent.left
        anchors.leftMargin: ic.visible ? 14 : 20
        anchors.right: parent.right; anchors.rightMargin: 20
        anchors.verticalCenter: parent.verticalCenter
        color: Theme.fgSurface
        selectionColor: Theme.primary
        selectedTextColor: Theme.fgPrimary
        font.pixelSize: 15
        clip: true
        onAccepted: root.accepted()
        Text {
            visible: !input.text
            text: root.placeholder
            color: Theme.fgSurfaceVariant
            font: input.font
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.IBeamCursor
        onPressed: function (m) { input.forceActiveFocus(); m.accepted = false }
    }
}
