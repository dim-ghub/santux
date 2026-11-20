import QtQuick
import QtQuick.Controls.Basic as C

// Vertical scroll area with a slim scroll bar. Put content in `content`.
Flickable {
    id: root
    default property alias content: holder.data
    contentWidth: width
    contentHeight: holder.childrenRect.height + 2 * margin
    property int margin: 24
    property int maxWidth: 1100
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    Item {
        id: holder
        x: Math.max(root.margin, (root.width - width) / 2)
        y: root.margin
        width: Math.min(root.width - 2 * root.margin, root.maxWidth)
        height: childrenRect.height
    }
    C.ScrollBar.vertical: C.ScrollBar {
        policy: root.contentHeight > root.height ? C.ScrollBar.AsNeeded : C.ScrollBar.AlwaysOff
        contentItem: Rectangle { implicitWidth: 6; radius: 3; color: Theme.subtle; opacity: 0.5 }
    }
}
