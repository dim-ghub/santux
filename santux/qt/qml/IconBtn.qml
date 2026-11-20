import QtQuick

// Small standard icon button (M3 extra-small): a 32 px round target that sits inline with text.
Item {
    id: root
    property string icon: ""
    property color color: Theme.primary
    property int size: 18
    signal clicked()
    implicitWidth: 24
    implicitHeight: 22      // sits inline with a title; the touch target extends past it
    Rectangle {
        anchors.centerIn: parent
        width: 32; height: 32
        radius: m.pressed ? Theme.cornerS : 16
        Behavior on radius { SpringAnimation { spring: 4; damping: 0.4 } }
        color: root.color
        opacity: m.pressed ? 0.14 : m.containsMouse ? 0.10 : 0
    }
    Icon { anchors.centerIn: parent; name: root.icon; size: root.size; color: root.color }
    MouseArea { id: m; anchors.centerIn: parent; width: 36; height: 36; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.clicked() }
}
