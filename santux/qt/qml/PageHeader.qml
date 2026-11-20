import QtQuick
import QtQuick.Layouts

// Large page title with supporting text and trailing actions.
RowLayout {
    id: root
    property string title: ""
    property string subtitle: ""
    default property alias actions: actionRow.data
    Layout.fillWidth: true
    spacing: 16
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 6
        Text { text: root.title; color: Theme.fgSurface; font.pixelSize: Theme.fontHuge; font.weight: Font.Bold }
        Text { text: root.subtitle; visible: text !== ""; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.fgSurfaceVariant; font.pixelSize: 15; textFormat: Text.StyledText }
    }
    Row {
        id: actionRow
        Layout.alignment: Qt.AlignBottom
        spacing: 8
    }
}
