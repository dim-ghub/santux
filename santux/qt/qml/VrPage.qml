import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property int tick: 0
    property var steps: []
    property bool steamvr: false
    onTickChanged: reload()
    Component.onCompleted: reload()
    onVisibleChanged: if (visible) reload()
    function reload() { steps = backend.vrStatus(); steamvr = backend.steamvrRunning() }
    readonly property bool ready: steps.length > 0 && steps.every(function (s) { return s.state === "ok" || s.id === "steamvr" })
    readonly property int done: steps.filter(function (s) { return s.state === "ok" }).length

    Timer { interval: 3000; running: root.visible; repeat: true; onTriggered: root.steamvr = backend.steamvrRunning() }

    Scroller {
        anchors.fill: parent
        maxWidth: 1100

        ColumnLayout {
            width: parent.width
            spacing: 28

            PageHeader {
                title: "VR"
                subtitle: "GTAVXR by LVL turns GTA V Legacy into a full VR game. It always runs as its own profile, so flatscreen mods never load in VR."
                Btn { text: "Set up everything"; icon: "auto_fix_high"; kind: root.ready ? "tonal" : "accent"; enabled: !backend.busy; onClicked: backend.vrSetupAll() }
            }

            // ---- hero
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: hero.implicitHeight + 56
                radius: Theme.cornerXL
                color: root.ready ? Theme.tertiaryContainer : Theme.surfaceContainerLow
                RowLayout {
                    id: hero
                    anchors.left: parent.left; anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: 28
                    spacing: 24
                    Rectangle {
                        width: 96; height: 96; radius: 36
                        color: root.ready ? Theme.tertiary : Theme.secondaryContainer
                        Icon { anchors.centerIn: parent; name: "view_in_ar"; size: 52; filled: true; color: root.ready ? Theme.tertiaryContainer : Theme.fgSecondaryContainer }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text {
                            text: root.ready ? "Ready for VR" : "Setup needed"
                            color: root.ready ? Theme.fgTertiaryContainer : Theme.fgSurface
                            font.pixelSize: 28; font.weight: Font.Bold
                        }
                        RowLayout {
                            spacing: 8
                            Layout.fillWidth: true
                            Rectangle { width: 10; height: 10; radius: 5; color: root.steamvr ? Theme.good : Theme.caution }
                            Text {
                                text: root.steamvr ? "SteamVR is running" : "SteamVR isn't running. Start it with the headset connected before launching."
                                color: root.ready ? Theme.alpha(Theme.fgTertiaryContainer, 0.85) : Theme.fgSurfaceVariant
                                font.pixelSize: 14; wrapMode: Text.Wrap; Layout.fillWidth: true
                            }
                        }
                        RowLayout {
                            Layout.topMargin: 8
                            spacing: 8
                            Btn { text: "Play VR"; icon: "play_arrow"; kind: "accent"; enabled: root.ready; onClicked: backend.play("gtavxr") }
                            Btn { text: "Start SteamVR"; icon: "power_settings_new"; kind: "tonal"; visible: !root.steamvr; onClicked: backend.openUrl("steam://rungameid/250820") }
                        }
                    }
                }
            }

            ListGroup {
                Layout.fillWidth: true
                title: "Setup"
                description: root.done + " of " + root.steps.length + " done. After the Suite updates GTAVXR or runs Check files, apply the Wine fix again."
                Repeater {
                    model: root.steps
                    delegate: ListRow {
                        required property var modelData
                        required property int index
                        readonly property bool ok: modelData.state === "ok"
                        icon: ok ? "check" : "counter_" + Math.min(9, index + 1)
                        iconBg: ok ? Theme.primary : Theme.surfaceContainerHighest
                        iconColor: ok ? Theme.fgPrimary : Theme.fgSurfaceVariant
                        title: modelData.name
                        subtitle: modelData.detail
                        Btn {
                            anchors.verticalCenter: parent.verticalCenter
                            compact: true
                            enabled: !backend.busy
                            kind: modelData.state === "missing" ? "accent" : "tonal"
                            text: ({ dotnet48: ok ? "Reinstall" : "Install", suite: ok ? "Update" : "Download",
                                     install: "Open Suite", fix: "Apply", tar: ok ? "Reinstall" : "Install", steamvr: "Open in Steam" })[modelData.id] || "Run"
                            onClicked: backend.vrStep(modelData.id)
                        }
                    }
                }
            }
        }
    }
}
