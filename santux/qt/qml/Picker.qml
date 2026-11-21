import QtQuick
import QtQuick.Layouts
import QtQuick.Window

// Shown when GTA V starts from Steam with "Ask every time": pick a profile and go.
// Keys: ↑/↓ or 1–9 to choose, Enter to launch, Esc to cancel.
Window {
    id: win
    readonly property int contentHeight: Math.ceil(body.implicitHeight) + 2 * pad
    readonly property int pad: 24
    width: 500
    height: contentHeight
    // A fixed size: tiling compositors (Hyprland, Sway, ...) float windows that can't be resized.
    minimumWidth: 500
    maximumWidth: 500
    minimumHeight: contentHeight
    maximumHeight: contentHeight
    visible: true
    title: "Launch GTA V"
    color: Theme.surfaceContainerLow
    flags: Qt.Dialog

    property int sel: Math.max(0, picker.profiles.findIndex(function (p) { return p.slug === picker.preselect }))
    readonly property var current: picker.profiles[sel] || ({})
    function go() { picker.choose(current.slug, remember.checked) }
    function toast(m) {}
    property var active: ({})

    function subtitle(p) {
        if (p.kind === "modded")
            return p.mods ? p.mods + " mod" + (p.mods === 1 ? "" : "s") + " installed" : "No mods yet"
        if (p.kind === "vr")
            return picker.steamvr ? "GTAVXR Suite · SteamVR is running" : "GTAVXR Suite · start SteamVR first"
        return "The unmodified game"
    }

    Item {
        anchors.fill: parent
        focus: true
        Keys.onUpPressed: win.sel = Math.max(0, win.sel - 1)
        Keys.onDownPressed: win.sel = Math.min(picker.profiles.length - 1, win.sel + 1)
        Keys.onReturnPressed: win.go()
        Keys.onEnterPressed: win.go()
        Keys.onEscapePressed: picker.cancel()
        Keys.onPressed: function (e) {
            var n = e.key - Qt.Key_1
            if (n >= 0 && n < Math.min(9, picker.profiles.length)) { win.sel = n; e.accepted = true }
        }

        ColumnLayout {
            id: body
            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
            anchors.margins: win.pad
            spacing: 20

            Item {
                Layout.fillWidth: true
                implicitHeight: banner.implicitHeight
                Banner { id: banner; size: 34; anchors.horizontalCenter: parent.horizontalCenter }
            }
            Text {
                Layout.fillWidth: true
                Layout.topMargin: -10
                horizontalAlignment: Text.AlignHCenter
                text: "Choose a profile to launch GTA V"
                color: Theme.fgSurfaceVariant
                font.pixelSize: 14
            }

            ListGroup {
                Layout.fillWidth: true
                spacing: 0
                Repeater {
                    model: picker.profiles
                    delegate: ListRow {
                        id: row
                        required property var modelData
                        required property int index
                        readonly property bool on: index === win.sel
                        title: modelData.name
                        subtitle: win.subtitle(modelData)
                        icon: modelData.kind === "vanilla" ? "sports_esports" : modelData.kind === "vr" ? "view_in_ar" : "deployed_code"
                        iconFilled: on
                        iconBg: on ? Theme.primary
                              : modelData.kind === "vr" ? Theme.tertiaryContainer : Theme.surfaceContainerHighest
                        iconColor: on ? Theme.fgPrimary
                                 : modelData.kind === "vr" ? Theme.fgTertiaryContainer : Theme.fgSurfaceVariant
                        tone: on ? Theme.secondaryContainer : Theme.surfaceContainerHigh
                        clickable: true
                        onClicked: win.sel = index
                        TapHandler { onDoubleTapped: { win.sel = row.index; win.go() } }

                        // M3 radio button
                        Rectangle {
                            width: 20; height: 20; radius: 10
                            anchors.verticalCenter: parent.verticalCenter
                            color: "transparent"
                            border.width: 2
                            border.color: row.on ? Theme.primary : Theme.fgSurfaceVariant
                            Rectangle {
                                anchors.centerIn: parent
                                width: row.on ? 10 : 0; height: width; radius: width / 2
                                color: Theme.primary
                                Behavior on width { SpringAnimation { spring: 4; damping: 0.4 } }
                            }
                        }
                    }
                }
            }

            ListGroup {
                Layout.fillWidth: true
                spacing: 0
                ListRow {
                    title: "Always launch this profile"
                    subtitle: "Skip this window next time. Change it on Santux's Profiles page."
                    icon: "bolt"
                    clickable: true
                    onClicked: remember.checked = !remember.checked
                    Toggle { id: remember; anchors.verticalCenter: parent.verticalCenter }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Btn { text: "Open Santux"; kind: "flat"; icon: "tune"; onClicked: picker.openManager() }
                Item { Layout.fillWidth: true }
                Btn { text: "Cancel"; onClicked: picker.cancel() }
                Btn { text: "Launch " + (win.current.name || ""); kind: "accent"; icon: "play_arrow"; onClicked: win.go() }
            }
        }
    }
}
