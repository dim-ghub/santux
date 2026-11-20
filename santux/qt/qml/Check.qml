import QtQuick

// M3 checkbox with label and supporting text.
Item {
    id: root
    property bool checked: false
    property string text: ""
    property string subtext: ""
    signal toggled()

    implicitHeight: Math.max(40, col.implicitHeight)
    implicitWidth: 48 + Math.max(t1.implicitWidth, t2.implicitWidth)

    Item {
        id: target
        width: 40; height: 40
        anchors.verticalCenter: parent.verticalCenter
        Rectangle {
            anchors.fill: parent; radius: 20
            color: root.checked ? Theme.primary : Theme.fgSurface
            opacity: mouse.pressed ? 0.12 : mouse.containsMouse ? 0.08 : 0
        }
        Rectangle {
            id: box
            anchors.centerIn: parent
            width: 18; height: 18
            radius: 3
            color: root.checked ? Theme.primary : "transparent"
            border.width: root.checked ? 0 : 2
            border.color: Theme.fgSurfaceVariant
            scale: mouse.pressed ? 0.85 : 1
            Behavior on scale { SpringAnimation { spring: 5; damping: 0.35 } }
            Icon { anchors.centerIn: parent; visible: root.checked; name: "check"; size: 16; weight: 700; color: Theme.fgPrimary }
        }
    }
    Column {
        id: col
        anchors.left: target.right; anchors.leftMargin: 8
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2
        Text { id: t1; visible: root.text !== ""; text: root.text; color: Theme.fgSurface; font.pixelSize: 14; width: col.width; wrapMode: Text.Wrap }
        Text { id: t2; visible: root.subtext !== ""; text: root.subtext; color: Theme.fgSurfaceVariant; font.pixelSize: 12; width: col.width; wrapMode: Text.WrapAnywhere }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: { root.checked = !root.checked; root.toggled() }
    }
}
