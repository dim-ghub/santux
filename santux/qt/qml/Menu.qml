import QtQuick
import QtQuick.Effects
import QtQuick.Controls.Basic as C

// M3 Expressive menu: surface-container panel with 16 px corners and a soft shadow; items are
// inset with 12 px corners; the selected item sits on secondary-container with a leading check.
// items: [{label, icon?, danger?, selected?}]. Position it with x/y like any Popup.
C.Popup {
    id: root
    property var items: []
    property bool selectable: false
    signal triggered(int index)

    padding: 0
    readonly property int maxLabel: {
        var w = 0
        for (var i = 0; i < items.length; i++) w = Math.max(w, fm.advanceWidth(items[i].label))
        return Math.ceil(w)
    }
    FontMetrics { id: fm; font.pixelSize: 15; font.weight: Font.DemiBold }
    readonly property bool anyIcon: selectable || items.some(function (it) { return !!it.icon })
    width: Math.max(160, Math.min(360, maxLabel + (anyIcon ? 36 : 0) + 56))
    implicitHeight: Math.min(360, col.implicitHeight + 16)

    enter: Transition {
        NumberAnimation { property: "scale"; from: 0.85; to: 1; duration: Theme.medium; easing.type: Easing.OutBack; easing.overshoot: 1.2 }
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast }
    }
    exit: Transition { NumberAnimation { property: "opacity"; to: 0; duration: 90 } }

    background: Item {
        Rectangle {
            id: panel
            anchors.fill: parent
            radius: Theme.cornerL
            color: Theme.surfaceContainer
            visible: GraphicsInfo.api === GraphicsInfo.Software
        }
        MultiEffect {
            anchors.fill: parent
            source: panel
            visible: GraphicsInfo.api !== GraphicsInfo.Software
            shadowEnabled: true
            shadowColor: Theme.alpha("#000000", 0.45)
            shadowBlur: 0.6
            shadowVerticalOffset: 4
        }
    }

    contentItem: Flickable {
        clip: true
        contentWidth: width
        contentHeight: col.implicitHeight
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height

        Column {
            id: col
            width: parent.width
            topPadding: 8
            bottomPadding: 8
            spacing: 2
            Repeater {
                model: root.items
                delegate: Item {
                    required property var modelData
                    required property int index
                    width: root.width
                    height: 44
                    Rectangle {
                        anchors.fill: parent
                        anchors.leftMargin: 4; anchors.rightMargin: 4
                        radius: Theme.cornerM
                        color: modelData.selected ? Theme.secondaryContainer : "transparent"
                        Rectangle {
                            anchors.fill: parent
                            radius: parent.radius
                            color: modelData.selected ? Theme.fgSecondaryContainer : Theme.fgSurface
                            opacity: m.pressed ? 0.12 : m.containsMouse ? 0.08 : 0
                        }
                    }
                    Row {
                        anchors.left: parent.left; anchors.leftMargin: 16
                        anchors.right: parent.right; anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 12
                        Icon {
                            visible: root.anyIcon
                            name: modelData.selected ? "check" : (modelData.icon || "")
                            size: 20
                            color: modelData.danger ? Theme.error : modelData.selected ? Theme.fgSecondaryContainer : Theme.fgSurfaceVariant
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: modelData.label
                            color: modelData.danger ? Theme.error : modelData.selected ? Theme.fgSecondaryContainer : Theme.fgSurface
                            font.pixelSize: 15
                            font.weight: modelData.selected ? Font.DemiBold : Font.Normal
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - (root.anyIcon ? 32 : 0)
                            elide: Text.ElideRight
                        }
                    }
                    MouseArea {
                        id: m
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { root.close(); root.triggered(index) }
                    }
                }
            }
        }
    }
}
