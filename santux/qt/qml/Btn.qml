import QtQuick

// M3 Expressive button: pill shape that morphs toward a rounded square while pressed.
// kind: "accent" (filled) | "tonal" | "normal" (outlined) | "flat" (text) | "danger" (outlined error)
Item {
    id: root
    property string text: ""
    property string icon: ""
    property string kind: "normal"
    property bool compact: false
    signal clicked()

    readonly property bool iconOnly: text === ""
    readonly property int h: compact ? 36 : 44
    implicitHeight: h
    implicitWidth: iconOnly ? h : row.implicitWidth + (compact ? 28 : 40)
    opacity: enabled ? 1 : 0.38

    readonly property color containerColor: kind === "accent" ? Theme.primary
                                          : kind === "tonal" ? Theme.secondaryContainer
                                          : "transparent"
    readonly property color contentColor: kind === "accent" ? Theme.fgPrimary
                                        : kind === "tonal" ? Theme.fgSecondaryContainer
                                        : kind === "danger" ? Theme.error
                                        : Theme.primary

    Rectangle {
        id: shape
        anchors.centerIn: parent
        width: root.width
        height: root.height
        radius: mouse.pressed ? Math.min(Theme.cornerM, height / 2) : height / 2
        Behavior on radius { SpringAnimation { spring: 4; damping: 0.4 } }
        color: root.containerColor
        border.width: root.kind === "normal" || root.kind === "danger" ? 1 : 0
        border.color: root.kind === "danger" ? Theme.alpha(Theme.error, 0.6) : Theme.outlineVariant

        // state layer
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: root.contentColor
            opacity: !root.enabled ? 0 : mouse.pressed ? 0.12 : mouse.containsMouse ? 0.08 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.fast } }
        }
    }

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 8
        Icon { name: root.icon; color: root.contentColor; size: 18; anchors.verticalCenter: parent.verticalCenter }
        Text {
            visible: !root.iconOnly
            text: root.text
            color: root.contentColor
            font.pixelSize: root.compact ? 13 : 14
            font.weight: Font.DemiBold
            font.letterSpacing: 0.1
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: if (root.enabled) root.clicked()
    }
    Accessible.role: Accessible.Button
    Accessible.name: text
}
