import QtQuick

// M3 Expressive connected button group: one choice from a few. The selected button is a full pill
// with a check; the others keep small inner corners. model: [{key, label}, ...]
Flow {
    id: root
    property var model: []
    property string currentKey: ""
    signal activated(string key)
    spacing: 2

    Repeater {
        model: root.model
        delegate: Rectangle {
            id: seg
            required property var modelData
            required property int index
            readonly property bool sel: modelData.key === root.currentKey
            readonly property bool first: index === 0
            readonly property bool last: index === root.model.length - 1
            readonly property real full: height / 2
            readonly property real inner: m.pressed ? Theme.cornerS : Theme.cornerXS
            height: 44
            width: row.implicitWidth + 36
            topLeftRadius: sel || first ? full : inner
            bottomLeftRadius: topLeftRadius
            topRightRadius: sel || last ? full : inner
            bottomRightRadius: topRightRadius
            Behavior on topLeftRadius { SpringAnimation { spring: 4; damping: 0.4 } }
            Behavior on topRightRadius { SpringAnimation { spring: 4; damping: 0.4 } }
            color: sel ? Theme.secondaryContainer : Theme.surfaceContainerHigh
            Behavior on color { ColorAnimation { duration: Theme.fast } }
            Rectangle {
                anchors.fill: parent
                topLeftRadius: parent.topLeftRadius; bottomLeftRadius: parent.bottomLeftRadius
                topRightRadius: parent.topRightRadius; bottomRightRadius: parent.bottomRightRadius
                color: Theme.fgSurface
                opacity: m.pressed ? 0.12 : m.containsMouse ? 0.08 : 0
            }
            Row {
                id: row
                anchors.centerIn: parent
                spacing: 6
                Icon { visible: seg.sel; name: "check"; size: 18; color: Theme.fgSecondaryContainer; anchors.verticalCenter: parent.verticalCenter }
                Text {
                    text: seg.modelData.label
                    color: seg.sel ? Theme.fgSecondaryContainer : Theme.fgSurface
                    font.pixelSize: 14
                    font.weight: seg.sel ? Font.DemiBold : Font.Medium
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
            MouseArea {
                id: m
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: { root.currentKey = seg.modelData.key; root.activated(seg.modelData.key) }
            }
        }
    }
}
