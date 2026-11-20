import QtQuick
import QtQuick.Layouts

Overlay {
    id: root
    property string heading: ""
    property string body: ""
    property string confirmText: "OK"
    property bool destructive: true
    signal confirmed()
    panelWidth: 460
    panelHeight: col.implicitHeight + 44
    onDismissed: shown = false

    ColumnLayout {
        id: col
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        anchors.margins: 22
        spacing: 14
        Text { text: root.heading; color: Theme.text; font.pixelSize: Theme.fontHeading + 2; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.Wrap }
        Text { text: root.body; color: Theme.subtle; font.pixelSize: Theme.fontBody; Layout.fillWidth: true; wrapMode: Text.Wrap }
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 6
            Item { Layout.fillWidth: true }
            Btn { text: "Cancel"; onClicked: root.shown = false }
            Btn { text: root.confirmText; kind: root.destructive ? "danger" : "accent"; onClicked: { root.shown = false; root.confirmed() } }
        }
    }
}
