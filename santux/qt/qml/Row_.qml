import QtQuick
import QtQuick.Layouts

// M3 list item inside a Section card: leading icon, headline, supporting text, trailing controls.
Item {
    id: root
    property string title: ""
    property string subtitle: ""
    property string icon: ""
    property bool divider: true
    property bool clickable: false
    default property alias trailing: trail.data
    signal clicked()

    Layout.fillWidth: true
    implicitHeight: Math.max(64, col.implicitHeight + 24)

    Rectangle {
        anchors.fill: parent
        anchors.leftMargin: 6; anchors.rightMargin: 6
        radius: Theme.cornerL
        color: Theme.fgSurface
        opacity: root.clickable ? (mouse.pressed ? 0.12 : mouse.containsMouse ? 0.06 : 0) : 0
    }
    Rectangle {
        visible: root.divider
        height: 1
        color: Theme.outlineVariant
        opacity: 0.6
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        anchors.leftMargin: Theme.pad; anchors.rightMargin: Theme.pad
    }
    Rectangle {
        id: icBox
        visible: root.icon !== ""
        width: 40; height: 40; radius: 20
        color: Theme.secondaryContainer
        anchors.left: parent.left; anchors.leftMargin: Theme.pad - 4
        anchors.verticalCenter: parent.verticalCenter
        Icon { anchors.centerIn: parent; name: root.icon; size: 20; color: Theme.fgSecondaryContainer }
    }
    ColumnLayout {
        id: col
        anchors.left: icBox.visible ? icBox.right : parent.left
        anchors.leftMargin: icBox.visible ? 14 : Theme.pad
        anchors.right: trail.left; anchors.rightMargin: 14
        anchors.verticalCenter: parent.verticalCenter
        spacing: 3
        Text { text: root.title; color: Theme.fgSurface; font.pixelSize: 15; font.weight: Font.Medium; Layout.fillWidth: true; wrapMode: Text.Wrap }
        Text { text: root.subtitle; visible: text !== ""; color: Theme.fgSurfaceVariant; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.StyledText; lineHeight: 1.1 }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        enabled: root.clickable
        hoverEnabled: true
        cursorShape: root.clickable ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: root.clicked()
    }
    Row {
        id: trail
        anchors.right: parent.right; anchors.rightMargin: Theme.pad - 4
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8
    }
}
