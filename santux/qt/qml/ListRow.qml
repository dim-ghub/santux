import QtQuick
import QtQuick.Layouts

// M3 Expressive segmented list item: its own surface with large outer corners at the ends of a
// group and small corners between items. Optional leading icon in a tonal shape, trailing
// controls, and an expandable detail area.
Item {
    id: root
    property string title: ""
    property string subtitle: ""
    property string icon: ""
    property color iconColor: Theme.fgSecondaryContainer
    property color iconBg: Theme.secondaryContainer
    property bool iconFilled: false
    property bool clickable: false
    property bool expanded: false
    property color tone: Theme.surfaceContainer
    property bool segFirst: true
    property bool segLast: true
    default property alias trailing: trail.data
    property alias detail: detailBox.data
    property alias titleExtra: titleSlot.data
    signal clicked()

    Layout.fillWidth: true
    implicitHeight: head.height + (expanded ? detailBox.childrenRect.height + 16 : 0)
    Behavior on implicitHeight { NumberAnimation { duration: Theme.medium; easing.type: Easing.OutCubic } }
    clip: true

    readonly property real big: Theme.radius
    readonly property real small: Theme.cornerXS   // M3: extra-small corners where items meet
    Rectangle {
        id: bg
        anchors.fill: parent
        color: root.tone
        topLeftRadius: root.segFirst ? root.big : root.small
        topRightRadius: topLeftRadius
        bottomLeftRadius: root.segLast ? root.big : root.small
        bottomRightRadius: bottomLeftRadius
    }
    Rectangle {
        anchors.fill: bg
        topLeftRadius: bg.topLeftRadius; topRightRadius: bg.topRightRadius
        bottomLeftRadius: bg.bottomLeftRadius; bottomRightRadius: bg.bottomRightRadius
        color: Theme.fgSurface
        opacity: root.clickable ? (mouse.pressed ? 0.10 : mouse.containsMouse ? 0.05 : 0) : 0
    }

    Item {
        id: head
        width: parent.width
        height: Math.max(72, col.implicitHeight + 28)

        Rectangle {
            id: shape
            visible: root.icon !== ""
            width: 44; height: 44
            radius: mouse.containsMouse && root.clickable ? 22 : 14
            Behavior on radius { SpringAnimation { spring: 3; damping: 0.35 } }
            color: root.iconBg
            anchors.left: parent.left; anchors.leftMargin: 18
            anchors.verticalCenter: parent.verticalCenter
            Icon { anchors.centerIn: parent; name: root.icon; size: 22; filled: root.iconFilled; color: root.iconColor }
        }
        ColumnLayout {
            id: col
            anchors.left: shape.visible ? shape.right : parent.left
            anchors.leftMargin: shape.visible ? 16 : 22
            anchors.right: trail.left; anchors.rightMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            spacing: 3
            RowLayout {
                Layout.fillWidth: true
                spacing: 4
                Text { text: root.title; color: Theme.fgSurface; font.pixelSize: 16; font.weight: Font.Medium; Layout.maximumWidth: col.width - titleSlot.width - 4; wrapMode: Text.Wrap }
                Row { id: titleSlot; Layout.alignment: Qt.AlignVCenter }
                Item { Layout.fillWidth: true }
            }
            Text { text: root.subtitle; visible: text !== ""; color: Theme.fgSurfaceVariant; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.StyledText; lineHeight: 1.1 }
        }
        MouseArea {
            id: mouse
            z: -1        // below the title's and trailing controls, which take their own clicks
            anchors.fill: parent
            enabled: root.clickable
            hoverEnabled: true
            cursorShape: root.clickable ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: root.clicked()
        }
        Row {
            id: trail
            anchors.right: parent.right; anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6
        }
    }
    Item {
        id: detailBox
        visible: root.expanded
        anchors.top: head.bottom
        anchors.left: parent.left; anchors.right: parent.right
        anchors.leftMargin: shape.visible ? 78 : 22; anchors.rightMargin: 22
        height: childrenRect.height
    }
}
