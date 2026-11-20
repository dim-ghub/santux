import QtQuick
import QtQuick.Layouts

// Centered illustration-style message with an optional action.
Rectangle {
    id: root
    property string icon: "inbox"
    property string title: ""
    property string text: ""
    property string actionText: ""
    signal action()
    Layout.fillWidth: true
    implicitHeight: col.implicitHeight + 64
    radius: Theme.cornerXL
    color: Theme.surfaceContainerLow
    ColumnLayout {
        id: col
        anchors.centerIn: parent
        width: Math.min(parent.width - 48, 460)
        spacing: 12
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            width: 88; height: 88; radius: 32
            color: Theme.secondaryContainer
            Icon { anchors.centerIn: parent; name: root.icon; size: 44; color: Theme.fgSecondaryContainer }
        }
        Text { Layout.alignment: Qt.AlignHCenter; text: root.title; color: Theme.fgSurface; font.pixelSize: 22; font.weight: Font.Bold; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; Layout.fillWidth: true }
        Text { Layout.alignment: Qt.AlignHCenter; text: root.text; visible: text !== ""; color: Theme.fgSurfaceVariant; font.pixelSize: 14; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; Layout.fillWidth: true }
        Btn { Layout.alignment: Qt.AlignHCenter; Layout.topMargin: 6; visible: root.actionText !== ""; text: root.actionText; kind: "accent"; onClicked: root.action() }
    }
}
