import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property int tick: 0
    property var info: backend.gameInfo
    onTickChanged: info = backend.gameInfo

    Scroller {
        anchors.fill: parent
        maxWidth: 1100

        ColumnLayout {
            width: parent.width
            spacing: 28

            PageHeader { title: "Game"; subtitle: "Where GTA V and its Proton prefix live, and prefix maintenance." }

            // ---- hero
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: hero.implicitHeight + 56
                radius: Theme.cornerXL
                color: Theme.primaryContainer
                RowLayout {
                    id: hero
                    anchors.left: parent.left; anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: 28
                    spacing: 24
                    Rectangle {
                        width: 96; height: 96; radius: 36
                        color: Theme.primary
                        Icon { anchors.centerIn: parent; name: "sports_esports"; size: 52; filled: true; color: Theme.fgPrimary }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        Text { text: "GTA V " + (root.info.edition || ""); color: Theme.fgPrimaryContainer; font.pixelSize: 28; font.weight: Font.Bold }
                        Text { text: "Version " + (root.info.version || "unknown") + "  ·  Proton " + (root.info.proton || "unknown"); color: Theme.alpha(Theme.fgPrimaryContainer, 0.85); font.pixelSize: 15 }
                    }
                    Btn { text: "Play " + (win.active.name || ""); icon: "play_arrow"; kind: "accent"; onClicked: backend.play(win.active.slug) }
                }
            }

            ListGroup {
                Layout.fillWidth: true
                title: "Locations"
                ListRow {
                    icon: "folder"; title: "Game folder"; subtitle: root.info.folder || ""
                    Btn { anchors.verticalCenter: parent.verticalCenter; icon: "folder_open"; kind: "flat"; onClicked: backend.openPath(root.info.folder) }
                }
                ListRow {
                    icon: "wine_bar"; title: "Proton prefix"
                    subtitle: root.info.prefix || "Not created yet: launch GTA V from Steam once"
                    Btn { anchors.verticalCenter: parent.verticalCenter; icon: "folder_open"; kind: "flat"; visible: !!root.info.prefix; onClicked: backend.openPath(root.info.prefix) }
                }
                ListRow {
                    icon: "database"; title: "Santux data"; subtitle: root.info.dataDir || ""
                    Btn { anchors.verticalCenter: parent.verticalCenter; icon: "folder_open"; kind: "flat"; onClicked: backend.openPath(root.info.dataDir) }
                }
            }

            ListGroup {
                Layout.fillWidth: true
                title: "Steam"
                ListRow { icon: "storefront"; title: "Steam install"; subtitle: root.info.steam || "" }
                ListRow {
                    icon: "terminal"; title: "Launch options"; subtitle: root.info.launchOptions || "none"
                    Btn { anchors.verticalCenter: parent.verticalCenter; text: "Change"; kind: "tonal"; compact: true; onClicked: win.go(2) }
                }
            }

            ListGroup {
                Layout.fillWidth: true
                title: "Maintenance"
                ListRow {
                    icon: "healing"
                    title: "Prepare the prefix"
                    subtitle: "Back up the prefix registry, then install the VC++ 2015–2022 runtime and .NET Framework 4.8 (10–20 minutes)."
                    Btn { anchors.verticalCenter: parent.verticalCenter; text: "Prepare"; kind: "tonal"; compact: true; enabled: !backend.busy; onClicked: backend.preparePrefix() }
                }
            }

            EmptyState {
                visible: root.info.legacy === false
                icon: "info"
                title: "GTA V Enhanced"
                text: "Script Hook V, the mods folder loader, .oiv packages and the heap/packfile adjusters work. ScriptHookVDotNet, the modded gameconfig and GTAVXR are Legacy-only."
            }
        }
    }
}
