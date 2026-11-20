import QtQuick
import QtQuick.Layouts

// One profile, as a large expressive card.
Rectangle {
    id: root
    property var p: ({})
    signal play()
    signal primary()          // switch to / edit / set up, depending on kind
    signal rename()
    signal remove()

    readonly property bool active: p.active === true
    readonly property color fg: active ? Theme.fgPrimaryContainer : Theme.fgSurface
    readonly property color fgDim: active ? Theme.alpha(Theme.fgPrimaryContainer, 0.8) : Theme.fgSurfaceVariant
    radius: Theme.cornerXL
    color: active ? Theme.primaryContainer : (hover.hovered ? Theme.surfaceContainerHigh : Theme.surfaceContainer)
    Behavior on color { ColorAnimation { duration: Theme.fast } }
    implicitHeight: col.implicitHeight + 48
    HoverHandler { id: hover }

    ColumnLayout {
        id: col
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        anchors.margins: 24
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            // expressive shape: rounded square that softens on hover
            Rectangle {
                width: 60; height: 60
                radius: hover.hovered ? 30 : 20
                Behavior on radius { SpringAnimation { spring: 3; damping: 0.35 } }
                color: root.p.kind === "vr" ? Theme.tertiaryContainer
                     : root.p.kind === "vanilla" ? (root.active ? Theme.surfaceContainerHighest : Theme.surfaceContainerHighest)
                     : (root.active ? Theme.primary : Theme.secondaryContainer)
                Icon {
                    anchors.centerIn: parent
                    size: 28
                    name: root.p.kind === "vanilla" ? "sports_esports" : root.p.kind === "vr" ? "view_in_ar" : "deployed_code"
                    color: root.p.kind === "vr" ? Theme.fgTertiaryContainer
                         : root.p.kind === "vanilla" ? Theme.fgSurfaceVariant
                         : (root.active ? Theme.fgPrimary : Theme.fgSecondaryContainer)
                }
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                visible: root.active
                height: 30; width: activeText.implicitWidth + 28
                radius: 15
                color: Theme.primary
                Text { id: activeText; anchors.centerIn: parent; text: "Active"; color: Theme.fgPrimary; font.pixelSize: 13; font.weight: Font.Bold }
            }
            MenuButton {
                visible: root.p.kind === "modded"
                color: root.fgDim
                items: [{ label: "Rename", icon: "edit" }, { label: "Delete", icon: "delete", danger: true }]
                onTriggered: function (i) { if (i === 0) root.rename(); else root.remove() }
            }
        }

        ColumnLayout {
            spacing: 4
            Layout.fillWidth: true
            Text { text: root.p.name || ""; color: root.fg; font.pixelSize: 24; font.weight: Font.Bold; elide: Text.ElideRight; Layout.fillWidth: true }
            Text {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                color: root.fgDim
                font.pixelSize: 14
                text: root.p.kind === "modded" ? (root.p.mods ? root.p.mods + " mod" + (root.p.mods === 1 ? "" : "s") : "No mods yet")
                    : root.p.kind === "vr" ? "VR with the GTAVXR Suite. Its mods are managed in the Suite."
                    : "The unmodified game: no ASI loader, no mods folder."
            }
        }

        Flow {
            Layout.fillWidth: true
            spacing: 6
            visible: root.p.kind === "modded" && (root.p.titles || []).length > 0
            Repeater {
                model: (root.p.titles || []).slice(0, 4)
                delegate: Rectangle {
                    required property var modelData
                    height: 30
                    width: Math.min(chip.implicitWidth + 24, 220)
                    radius: Theme.cornerS
                    color: root.active ? Theme.alpha(Theme.fgPrimaryContainer, 0.12) : Theme.surfaceContainerHighest
                    Text {
                        id: chip
                        anchors.left: parent.left; anchors.leftMargin: 12
                        anchors.right: parent.right; anchors.rightMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.replace(/\s*\[.*$/, "")
                        elide: Text.ElideRight
                        color: root.fg
                        font.pixelSize: 12
                        font.weight: Font.Medium
                    }
                }
            }
            Rectangle {
                visible: (root.p.titles || []).length > 4 || root.p.mods > 4
                height: 30; width: more.implicitWidth + 24; radius: Theme.cornerS
                color: "transparent"
                border.width: 1; border.color: root.active ? Theme.alpha(Theme.fgPrimaryContainer, 0.4) : Theme.outlineVariant
                Text { id: more; anchors.centerIn: parent; text: "+" + (root.p.mods - 4) + " more"; color: root.fgDim; font.pixelSize: 12 }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 4
            spacing: 8
            Btn { text: "Play"; icon: "play_arrow"; kind: "accent"; onClicked: root.play() }
            Btn {
                kind: "tonal"
                text: root.p.kind === "vr" ? "Set up VR" : root.p.kind === "modded" ? (root.active ? "Edit mods" : "Switch to") : (root.active ? "" : "Switch to")
                visible: text !== ""
                enabled: !backend.busy
                onClicked: root.primary()
            }
        }
    }
}
