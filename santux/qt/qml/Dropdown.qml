import QtQuick

// M3 Expressive split button used as a selector: the leading segment shows the current choice,
// the trailing segment (a chevron) opens the menu and becomes a circle while it's open.
// model: [{key, label}, ...]. Set `actionText` to make the leading segment its own action
// (emits `action()`); otherwise both segments open the menu.
Item {
    id: root
    property var model: []
    property int currentIndex: 0
    property string kind: "tonal"           // "tonal" | "accent"
    property string icon: ""
    property string actionText: ""
    readonly property string currentKey: model.length ? model[Math.min(currentIndex, model.length - 1)].key : ""
    readonly property string currentLabel: model.length ? model[Math.min(currentIndex, model.length - 1)].label : ""
    signal activated(int index)
    signal action()

    readonly property color container: kind === "accent" ? Theme.primary : Theme.secondaryContainer
    readonly property color content: kind === "accent" ? Theme.fgPrimary : Theme.fgSecondaryContainer
    readonly property int h: 48
    readonly property int inner: 4
    readonly property int trailW: 44
    TextMetrics { id: tm; font.pixelSize: 14; font.weight: Font.DemiBold; text: root.actionText || root.currentLabel }
    implicitHeight: h
    implicitWidth: 20 + (icon ? 26 : 0) + Math.ceil(tm.advanceWidth) + 16 + 2 + trailW

    function toggle() { menu.opened ? menu.close() : menu.open() }

    // ---- leading segment
    Rectangle {
        id: lead
        height: root.h
        width: root.width - root.trailW - 2
        topLeftRadius: height / 2; bottomLeftRadius: height / 2
        topRightRadius: leadMouse.pressed ? Theme.cornerS : root.inner
        bottomRightRadius: topRightRadius
        Behavior on topRightRadius { SpringAnimation { spring: 4; damping: 0.4 } }
        color: root.container
        Rectangle {
            anchors.fill: parent
            topLeftRadius: parent.topLeftRadius; bottomLeftRadius: parent.bottomLeftRadius
            topRightRadius: parent.topRightRadius; bottomRightRadius: parent.bottomRightRadius
            color: root.content
            opacity: leadMouse.pressed ? 0.12 : leadMouse.containsMouse ? 0.08 : 0
        }
        Row {
            anchors.left: parent.left; anchors.leftMargin: 20
            anchors.right: parent.right; anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            Icon { name: root.icon; size: 18; color: root.content; anchors.verticalCenter: parent.verticalCenter }
            Text {
                text: tm.text
                color: root.content
                font: tm.font
                anchors.verticalCenter: parent.verticalCenter
                elide: Text.ElideRight
                width: Math.min(Math.ceil(tm.advanceWidth) + 2, parent.width - (root.icon ? 26 : 0))
            }
        }
        MouseArea {
            id: leadMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.actionText ? root.action() : root.toggle()
        }
    }

    // ---- trailing segment
    Rectangle {
        id: trail
        x: lead.width + 2
        height: root.h
        width: root.trailW
        property real r: menu.opened ? height / 2 : (trailMouse.pressed ? Theme.cornerS : root.inner)
        Behavior on r { SpringAnimation { spring: 4; damping: 0.4 } }
        topLeftRadius: r; bottomLeftRadius: r
        topRightRadius: height / 2; bottomRightRadius: height / 2
        color: root.container
        Rectangle {
            anchors.fill: parent
            topLeftRadius: parent.topLeftRadius; bottomLeftRadius: parent.bottomLeftRadius
            topRightRadius: parent.topRightRadius; bottomRightRadius: parent.bottomRightRadius
            color: root.content
            opacity: trailMouse.pressed ? 0.12 : trailMouse.containsMouse ? 0.08 : 0
        }
        Icon {
            anchors.centerIn: parent
            anchors.horizontalCenterOffset: menu.opened ? 0 : -1
            name: "keyboard_arrow_down"
            size: 22
            color: root.content
            rotation: menu.opened ? 180 : 0
            Behavior on rotation { NumberAnimation { duration: Theme.medium; easing.type: Easing.OutBack } }
        }
        MouseArea {
            id: trailMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.toggle()
        }
    }

    Menu {
        id: menu
        y: root.height + 4
        x: root.width - width
        selectable: true
        transformOrigin: Item.TopRight
        items: root.model.map(function (m, i) { return { label: m.label, selected: i === root.currentIndex } })
        onTriggered: function (i) { root.currentIndex = i; root.activated(i) }
    }
}
