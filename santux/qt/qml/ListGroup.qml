import QtQuick
import QtQuick.Layouts

// A titled group of ListRows, connected with 2 px gaps. Works out which rows are first/last.
ColumnLayout {
    id: root
    property string title: ""
    property string description: ""
    default property alias rows: body.data
    property alias action: actionSlot.data
    spacing: 12

    function relayout() {
        var vis = []
        for (var i = 0; i < body.children.length; i++) {
            var c = body.children[i]
            if (c.visible && c.segFirst !== undefined) vis.push(c)
        }
        for (var j = 0; j < vis.length; j++) { vis[j].segFirst = j === 0; vis[j].segLast = j === vis.length - 1 }
    }

    RowLayout {
        visible: root.title !== "" || root.description !== "" || actionSlot.children.length > 0
        Layout.fillWidth: true
        Layout.leftMargin: 6
        spacing: 12
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 3
            Text { text: root.title; visible: text !== ""; color: Theme.fgSurface; font.pixelSize: 20; font.weight: Font.DemiBold }
            Text { text: root.description; visible: text !== ""; color: Theme.fgSurfaceVariant; font.pixelSize: 13; wrapMode: Text.Wrap; Layout.fillWidth: true }
        }
        Item {
            id: actionSlot
            implicitWidth: childrenRect.width
            implicitHeight: childrenRect.height
            Layout.alignment: Qt.AlignBottom
        }
    }
    ColumnLayout {
        id: body
        Layout.fillWidth: true
        spacing: 2
        onChildrenChanged: Qt.callLater(root.relayout)
    }
    Component.onCompleted: Qt.callLater(relayout)
    // `visible` is effective visibility, so rows read as hidden while their page is off screen.
    onVisibleChanged: if (visible) Qt.callLater(relayout)
}
