import QtQuick
import QtQuick.Layouts

// A titled group of list rows on a filled card.
ColumnLayout {
    id: root
    property string title: ""
    property string description: ""
    default property alias rows: body.data
    property alias action: actionSlot.data
    spacing: 10

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 4
        spacing: 12
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 3
            Text { text: root.title; visible: text !== ""; color: Theme.fgSurface; font.pixelSize: 18; font.weight: Font.DemiBold }
            Text { text: root.description; visible: text !== ""; color: Theme.fgSurfaceVariant; font.pixelSize: 13; wrapMode: Text.Wrap; Layout.fillWidth: true }
        }
        Item {
            id: actionSlot
            implicitWidth: childrenRect.width
            implicitHeight: childrenRect.height
            Layout.alignment: Qt.AlignBottom
        }
    }
    Card {
        Layout.fillWidth: true
        implicitHeight: body.implicitHeight + 12
        ColumnLayout {
            id: body
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top; anchors.topMargin: 6
            spacing: 0
        }
    }
}
