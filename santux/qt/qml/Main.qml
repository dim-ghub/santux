import QtQuick
import QtQuick.Layouts
import QtQuick.Window

Window {
    id: win
    width: 1240
    height: 820
    minimumWidth: 900
    minimumHeight: 600
    visible: true
    title: "Santux"
    color: Theme.surfaceContainer

    property int page: 0
    property var history: []
    function go(p) { if (p === page) return; history = history.concat([page]).slice(-30); page = p }
    function goBack() {
        if (page === 0 && browse.detailsUrl !== "") { browse.detailsUrl = ""; return }
        if (history.length) { var h = history.slice(); page = h.pop(); history = h }
    }
    property var active: ({})
    property var profileList: []
    property int stateTick: 0

    function refresh() {
        active = backend.activeProfile()
        profileList = backend.profiles()
        stateTick++
    }
    function toast(msg) { toastBox.show(msg) }
    Component.onCompleted: refresh()

    Connections {
        target: backend
        function onStateChanged() { win.refresh() }
        function onToast(msg) { win.toast(msg) }
        function onPlanReady(plan) { planDialog.open(plan) }
    }

    Item {
        anchors.fill: parent
        visible: !backend.hasGame
        Column {
            anchors.centerIn: parent
            spacing: 10
            Text { text: "GTA V not found"; color: Theme.text; font.pixelSize: Theme.fontTitle; font.bold: true; anchors.horizontalCenter: parent.horizontalCenter }
            Text { text: "Install GTA V (Legacy or Enhanced) in Steam and launch it once, then reopen this app."; color: Theme.subtle; font.pixelSize: Theme.fontBody }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0
        visible: backend.hasGame

        // ---------------------------------------------------------------- sidebar
        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: 264
            color: "transparent"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 4

                Banner {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: 10
                    Layout.bottomMargin: 6
                }
                Text {
                    text: backend.games.length > backend.gameIndex && backend.gameIndex >= 0 ? backend.games[backend.gameIndex] + "  ·  " + (backend.gameInfo.version || "") : ""
                    color: Theme.subtle
                    font.pixelSize: Theme.fontSmall
                    Layout.alignment: Qt.AlignHCenter
                    Layout.bottomMargin: 14
                }

                // Profile switcher
                Card {
                    Layout.fillWidth: true
                    implicitHeight: profCol.implicitHeight + 28
                    color: Theme.surfaceContainerHigh
                    ColumnLayout {
                        id: profCol
                        anchors.left: parent.left; anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 14
                        spacing: 8
                        Text { text: "Profile"; color: Theme.fgSurfaceVariant; font.pixelSize: 12; font.weight: Font.DemiBold; Layout.leftMargin: 4 }
                        Dropdown {
                            id: profDrop
                            Layout.fillWidth: true
                            model: win.profileList.map(function (p) { return { key: p.slug, label: p.name } })
                            currentIndex: Math.max(0, win.profileList.findIndex(function (p) { return p.active }))
                            onActivated: function (i) { backend.switchProfile(win.profileList[i].slug) }
                        }
                        Text {
                            text: win.active.kind === "vanilla" ? "No mods load in this profile."
                                : win.active.kind === "vr" ? "Launches the GTAVXR Suite."
                                : (win.profileList.find(function (p) { return p.active }) || {mods: 0}).mods + " mods installed"
                            color: Theme.fgSurfaceVariant
                            font.pixelSize: 12
                            Layout.leftMargin: 4
                        }
                    }
                }
                Item { height: 14 }

                NavItem { Layout.fillWidth: true; text: "Browse"; icon: "search"; active: win.page === 0; onClicked: win.go(0) }
                NavItem { Layout.fillWidth: true; text: "Installed"; icon: "inventory_2"; active: win.page === 1; onClicked: win.go(1) }
                NavItem { Layout.fillWidth: true; text: "Profiles"; icon: "switch_account"; active: win.page === 2; onClicked: win.go(2) }
                NavItem { Layout.fillWidth: true; text: "Requirements"; icon: "build"; active: win.page === 3; onClicked: win.go(3) }
                NavItem { Layout.fillWidth: true; text: "VR (GTAVXR)"; icon: "view_in_ar"; active: win.page === 4; onClicked: win.go(4) }
                NavItem { Layout.fillWidth: true; text: "Game"; icon: "sports_esports"; active: win.page === 5; onClicked: win.go(5) }

                Item { Layout.fillHeight: true }

                // Extended FAB
                Rectangle {
                    id: fab
                    Layout.fillWidth: true
                    implicitHeight: 64
                    radius: fabMouse.pressed ? 28 : 20
                    Behavior on radius { SpringAnimation { spring: 4; damping: 0.4 } }
                    color: Theme.primaryContainer
                    Rectangle { anchors.fill: parent; radius: parent.radius; color: Theme.fgPrimaryContainer; opacity: fabMouse.pressed ? 0.12 : fabMouse.containsMouse ? 0.08 : 0 }
                    Row {
                        anchors.centerIn: parent
                        spacing: 12
                        Icon { name: "play_arrow"; size: 24; color: Theme.fgPrimaryContainer; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: "Play " + (win.active.name || ""); color: Theme.fgPrimaryContainer; font.pixelSize: 16; font.weight: Font.Bold; anchors.verticalCenter: parent.verticalCenter }
                    }
                    MouseArea { id: fabMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: backend.play(win.active.slug) }
                }
            }
        }

        // ---------------------------------------------------------------- pages
        // Content pane: the navigation surface frames it, with rounded corners on the inside.
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.topMargin: 12
            Layout.rightMargin: 12
            Layout.bottomMargin: 12
            radius: Theme.cornerXL
            color: Theme.surface
            clip: true

        StackLayout {
            anchors.fill: parent
            currentIndex: win.page
            BrowsePage { id: browse }
            InstalledPage { tick: win.stateTick; profile: win.active }
            ProfilesPage { tick: win.stateTick; profileList: win.profileList }
            RequirementsPage { tick: win.stateTick }
            VrPage { tick: win.stateTick }
            GamePage { tick: win.stateTick }
        }
        }
    }

    // Mouse back button (and Alt+Left) goes back: a mod's page first, then the previous page.
    TapHandler { acceptedButtons: Qt.BackButton; onTapped: win.goBack() }
    Shortcut { sequences: ["Alt+Left", StandardKey.Back]; onActivated: win.goBack() }

    PlanDialog { id: planDialog; anchors.fill: parent }
    TaskDialog { id: taskDialog; anchors.fill: parent }
    Toast { id: toastBox }
}
