import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property int tick: 0
    property var groups: []
    onTickChanged: groups = backend.requirementGroups()
    Component.onCompleted: groups = backend.requirementGroups()

    readonly property var allRows: groups.reduce(function (a, g) { return a.concat(g.rows) }, [])
    readonly property int ready: allRows.filter(function (r) { return r.state === "ok" }).length
    readonly property int todo: allRows.filter(function (r) { return r.state === "missing" || r.state === "update" }).length

    function stateIcon(s) { return s === "ok" ? "check_circle" : s === "missing" ? "download" : s === "update" ? "update" : "info" }
    function stateBg(s) { return s === "ok" ? Theme.goodContainer : s === "missing" ? Theme.errorContainer : Theme.cautionContainer }
    function stateFg(s) { return s === "ok" ? Theme.good : s === "missing" ? Theme.fgErrorContainer : Theme.caution }

    Scroller {
        anchors.fill: parent
        maxWidth: 1100

        ColumnLayout {
            width: parent.width
            spacing: 28

            PageHeader {
                title: "Requirements"
                subtitle: "Shared by every mod profile, except the gameconfig, which lives in each profile's mods folder."
            }

            // ---- summary
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: sumRow.implicitHeight + 48
                radius: Theme.cornerXL
                color: root.todo === 0 ? Theme.primaryContainer : Theme.surfaceContainerLow
                RowLayout {
                    id: sumRow
                    anchors.left: parent.left; anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: 24
                    spacing: 20
                    Rectangle {
                        width: 64; height: 64; radius: 22
                        color: root.todo === 0 ? Theme.primary : Theme.secondaryContainer
                        Icon { anchors.centerIn: parent; name: root.todo === 0 ? "verified" : "construction"; filled: true; size: 32; color: root.todo === 0 ? Theme.fgPrimary : Theme.fgSecondaryContainer }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text {
                            text: root.todo === 0 ? "Everything's ready" : root.todo + " thing" + (root.todo === 1 ? "" : "s") + " to set up"
                            color: root.todo === 0 ? Theme.fgPrimaryContainer : Theme.fgSurface
                            font.pixelSize: 22; font.weight: Font.Bold
                        }
                        Text {
                            text: "GTA V " + (backend.gameInfo.edition || "") + " " + (backend.gameInfo.version || "") + "  ·  " + root.ready + " of " + root.allRows.length + " installed. Script Hook V must match the game's build, so update it after Rockstar patches."
                            color: root.todo === 0 ? Theme.alpha(Theme.fgPrimaryContainer, 0.85) : Theme.fgSurfaceVariant
                            font.pixelSize: 13; wrapMode: Text.Wrap; Layout.fillWidth: true
                        }
                        WavyProgress {
                            Layout.fillWidth: true
                            visible: root.allRows.length > 0
                            progress: root.allRows.length ? root.ready / root.allRows.length : 0
                            color: root.todo === 0 ? Theme.fgPrimaryContainer : Theme.primary
                            track: root.todo === 0 ? Theme.alpha(Theme.fgPrimaryContainer, 0.25) : Theme.secondaryContainer
                        }
                    }
                    Btn { text: "Install all missing"; icon: "download"; kind: "accent"; visible: root.todo > 0; enabled: !backend.busy; onClicked: backend.installAllMissing() }
                }
            }

            Repeater {
                model: root.groups
                delegate: ListGroup {
                    required property var modelData
                    Layout.fillWidth: true
                    title: modelData.title
                    description: modelData.description
                    Repeater {
                        model: modelData.rows
                        delegate: ListRow {
                            required property var modelData
                            icon: root.stateIcon(modelData.state)
                            iconFilled: modelData.state === "ok"
                            iconBg: root.stateBg(modelData.state)
                            iconColor: root.stateFg(modelData.state)
                            title: modelData.name
                            subtitle: modelData.description + (modelData.detail ? "<br><b>" + modelData.detail.replace(/&/g, "&amp;").replace(/</g, "&lt;") + "</b>" : "")
                            Btn {
                                anchors.verticalCenter: parent.verticalCenter
                                visible: modelData.copyText !== ""
                                icon: "content_copy"; kind: "flat"
                                onClicked: { backend.copy(modelData.copyText); win.toast("Copied. Paste it into GTA V → Properties → Launch Options.") }
                            }
                            Btn {
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.action
                                kind: modelData.state === "missing" || modelData.state === "update" ? "accent" : "tonal"
                                compact: true
                                enabled: !backend.busy
                                onClicked: backend.installRequirement(modelData.id)
                            }
                        }
                    }
                }
            }
        }
    }
}
