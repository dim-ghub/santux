import QtQuick

// M3 dialog: surface-container-high panel, 28 px corners, scales in with a spring.
Item {
    id: root
    property bool shown: false
    property int panelWidth: 640
    property int panelHeight: 520
    property bool dismissable: true
    default property alias content: panel.data
    signal dismissed()
    visible: shown || fade.running
    z: 100

    Rectangle {
        anchors.fill: parent
        color: Theme.scrim
        opacity: root.shown ? 1 : 0
        Behavior on opacity { NumberAnimation { id: fade; duration: Theme.fast } }
        MouseArea { anchors.fill: parent; onClicked: if (root.dismissable) root.dismissed() }
    }
    Rectangle {
        id: panel
        anchors.centerIn: parent
        width: Math.min(root.panelWidth, root.width - 48)
        height: Math.min(root.panelHeight, root.height - 48)
        radius: Theme.cornerXL
        color: Theme.surfaceContainerHigh
        scale: root.shown ? 1 : 0.92
        opacity: root.shown ? 1 : 0
        Behavior on scale { SpringAnimation { spring: Theme.springSpatial; damping: Theme.dampSpatial } }
        Behavior on opacity { NumberAnimation { duration: Theme.fast } }
        MouseArea { anchors.fill: parent }   // swallow clicks
    }
    focus: shown
    Keys.onEscapePressed: if (root.dismissable) root.dismissed()
}
