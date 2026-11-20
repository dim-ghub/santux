import QtQuick
import QtQuick.Layouts
import QtQuick.Window

// Shown when GTA V starts from Steam with "Ask every time": pick a profile and go.
Window {
    id: win
    width: 520
    height: Math.min(680, 250 + picker.profiles.length * 72)
    // A fixed size: tiling compositors (Hyprland, Sway, ...) float windows that can't be resized.
    minimumWidth: width
    maximumWidth: width
    minimumHeight: height
    maximumHeight: height
    visible: true
    title: "Launch GTA V"
    color: Theme.window
    flags: Qt.Dialog

    property int sel: Math.max(0, picker.profiles.findIndex(function (p) { return p.slug === picker.preselect }))
    function go() { picker.choose(picker.profiles[sel].slug, remember.checked) }
    function toast(m) {}
    property var active: ({})

    Item {
        anchors.fill: parent
        focus: true
        Keys.onUpPressed: win.sel = Math.max(0, win.sel - 1)
        Keys.onDownPressed: win.sel = Math.min(picker.profiles.length - 1, win.sel + 1)
        Keys.onReturnPressed: win.go()
        Keys.onEnterPressed: win.go()
        Keys.onEscapePressed: picker.cancel()

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 14

            ColumnLayout {
                spacing: 2
                Text { text: "Launch GTA V"; color: Theme.text; font.pixelSize: Theme.fontTitle; font.weight: Font.Bold }
                Text { text: "Choose a profile."; color: Theme.subtle; font.pixelSize: Theme.fontBody }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 8
                Repeater {
                    model: picker.profiles
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        readonly property bool on: index === win.sel
                        Layout.fillWidth: true
                        implicitHeight: 60
                        radius: Theme.radius
                        color: on ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18) : m.containsMouse ? Theme.cardHover : Theme.card
                        border.width: on ? 2 : 1
                        border.color: on ? Theme.accent : Theme.border
                        Icon {
                            id: ic
                            name: modelData.kind === "vanilla" ? "sports_esports" : modelData.kind === "vr" ? "view_in_ar" : "deployed_code"
                            size: 24
                            color: on ? Theme.primary : Theme.fgSurfaceVariant
                            anchors.left: parent.left; anchors.leftMargin: 16; anchors.verticalCenter: parent.verticalCenter
                        }
                        Column {
                            anchors.left: ic.right; anchors.leftMargin: 14
                            anchors.right: parent.right; anchors.rightMargin: 16
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 2
                            Text { text: modelData.name; color: Theme.text; font.pixelSize: Theme.fontHeading; font.weight: Font.DemiBold }
                            Text {
                                width: parent.width; elide: Text.ElideRight
                                text: modelData.kind === "modded" ? (modelData.mods ? modelData.mods + " mods: " + modelData.titles.join(", ") : "No mods yet")
                                    : modelData.kind === "vr" ? (picker.steamvr ? "GTAVXR Suite · SteamVR is running" : "GTAVXR Suite · start SteamVR first")
                                    : "The unmodified game"
                                color: modelData.kind === "vr" && !picker.steamvr ? Theme.warning : Theme.subtle
                                font.pixelSize: Theme.fontSmall + 1
                            }
                        }
                        MouseArea { id: m; anchors.fill: parent; hoverEnabled: true; onClicked: win.sel = index; onDoubleClicked: { win.sel = index; win.go() } }
                    }
                }
                Item { Layout.fillHeight: true }
            }

            Check { id: remember; Layout.fillWidth: true; text: "Always launch this profile (change it later in Santux)" }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Btn { text: "Open Santux"; kind: "flat"; icon: "tune"; onClicked: picker.openManager() }
                Item { Layout.fillWidth: true }
                Btn { text: "Cancel"; onClicked: picker.cancel() }
                Btn { text: "Launch"; kind: "accent"; icon: "play_arrow"; onClicked: win.go() }
            }
        }
    }
}
