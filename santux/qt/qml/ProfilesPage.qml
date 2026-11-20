import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property int tick: 0
    property var profileList: []
    property string launchDefault: "ask"
    property var launchReq: ({})
    property string renaming: ""
    property string deleting: ""
    onTickChanged: reload()
    Component.onCompleted: reload()
    function reload() {
        launchDefault = backend.launchDefault()
        var groups = backend.requirementGroups()
        for (var g = 0; g < groups.length; g++)
            for (var r = 0; r < groups[g].rows.length; r++)
                if (groups[g].rows[r].id === "launchoption") launchReq = groups[g].rows[r]
    }

    Scroller {
        id: scroller
        anchors.fill: parent
        maxWidth: 1180

        ColumnLayout {
            width: parent.width
            spacing: 28

            RowLayout {
                Layout.fillWidth: true
                spacing: 16
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Text { text: "Profiles"; color: Theme.fgSurface; font.pixelSize: Theme.fontHuge; font.weight: Font.Bold }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        color: Theme.fgSurfaceVariant
                        font.pixelSize: 15
                        text: "Each profile keeps its own mods. Switching is instant, and requirements are shared."
                    }
                }
                Btn { text: "New profile"; icon: "add"; kind: "accent"; Layout.alignment: Qt.AlignBottom; onClicked: { newName.text = ""; newBox.shown = true } }
            }

            // ---- profile cards
            GridLayout {
                id: grid
                Layout.fillWidth: true
                columns: width > 1000 ? 3 : width > 640 ? 2 : 1
                columnSpacing: 16
                rowSpacing: 16
                Repeater {
                    model: root.profileList
                    delegate: ProfileCard {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        p: modelData
                        onPlay: backend.play(modelData.slug)
                        onPrimary: {
                            if (modelData.kind === "vr") win.go(4)
                            else if (modelData.active) win.go(1)
                            else backend.switchProfile(modelData.slug)
                        }
                        onRename: { root.renaming = modelData.slug; renameField.text = modelData.name; renameBox.shown = true }
                        onRemove: { root.deleting = modelData.slug; confirmDelete.heading = "Delete " + modelData.name + "?"; confirmDelete.shown = true }
                    }
                }
            }

            // ---- launching from Steam
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: launchCol.implicitHeight + 56
                radius: Theme.cornerXL
                color: Theme.surfaceContainerLow

                ColumnLayout {
                    id: launchCol
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    anchors.margins: 28
                    spacing: 20

                    RowLayout {
                        spacing: 14
                        Rectangle {
                            width: 48; height: 48; radius: 16
                            color: Theme.tertiaryContainer
                            Icon { anchors.centerIn: parent; name: "play_arrow"; size: 22; color: Theme.fgTertiaryContainer }
                        }
                        ColumnLayout {
                            spacing: 2
                            Text { text: "Starting GTA V from Steam"; color: Theme.fgSurface; font.pixelSize: 22; font.weight: Font.Bold }
                            Text { text: "What happens when you press Play in your Steam library."; color: Theme.fgSurfaceVariant; font.pixelSize: 14 }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        Text { text: "Launch"; color: Theme.fgSurfaceVariant; font.pixelSize: 13; font.weight: Font.DemiBold }
                        Segmented {
                            Layout.fillWidth: true
                            model: [{ key: "ask", label: "Ask every time" }].concat(root.profileList.map(function (p) { return { key: p.slug, label: p.name } }))
                            currentKey: root.launchDefault
                            onActivated: function (key) { backend.setLaunchDefault(key) }
                        }
                    }

                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.outlineVariant; opacity: 0.6 }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            Text { text: "Steam launch option"; color: Theme.fgSurfaceVariant; font.pixelSize: 13; font.weight: Font.DemiBold }
                            Pill {
                                state: root.launchReq.state === "ok" ? "ok" : "update"
                                text: root.launchReq.state === "ok" ? "Set" : "Not set"
                            }
                            Item { Layout.fillWidth: true }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: 48
                                radius: Theme.cornerM
                                color: Theme.surfaceContainerHighest
                                Text {
                                    anchors.left: parent.left; anchors.leftMargin: 16
                                    anchors.right: parent.right; anchors.rightMargin: 16
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: root.launchReq.copyText || ""
                                    color: Theme.fgSurface
                                    font.family: "monospace"
                                    font.pixelSize: 13
                                    elide: Text.ElideMiddle
                                }
                            }
                            Btn { text: "Copy"; icon: "content_copy"; kind: "tonal"; onClicked: { backend.copy(root.launchReq.copyText); win.toast("Copied. Paste it into GTA V → Properties → Launch Options in Steam.") } }
                            Btn { text: "Set"; kind: root.launchReq.state === "ok" ? "normal" : "accent"; enabled: !backend.busy; onClicked: backend.installRequirement("launchoption") }
                        }
                        Text {
                            visible: root.launchReq.state !== "ok" && !!root.launchReq.detail
                            Layout.fillWidth: true
                            text: "Currently " + (root.launchReq.detail || "")
                            color: Theme.fgSurfaceVariant
                            font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                        Text {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            color: Theme.fgSurfaceVariant
                            font.pixelSize: 13
                            textFormat: Text.StyledText
                            text: "Skip the choice with a flag before <tt>%command%</tt>: <tt>--profile NAME</tt>, <tt>--vanilla</tt> or <tt>--vr</tt>. "
                                  + "From a terminal or shortcut: <tt>santux play NAME</tt>. Setting it needs Steam closed; otherwise copy and paste it."
                        }
                    }
                }
            }
        }
    }

    Overlay {
        id: newBox
        anchors.fill: parent
        panelWidth: 440; panelHeight: 220
        onDismissed: shown = false
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 28; spacing: 16
            Text { text: "New profile"; color: Theme.fgSurface; font.pixelSize: 24; font.weight: Font.Bold }
            Field { id: newName; Layout.fillWidth: true; placeholder: "Profile name"; onAccepted: createBtn.clicked() }
            RowLayout {
                Item { Layout.fillWidth: true }
                Btn { text: "Cancel"; kind: "flat"; onClicked: newBox.shown = false }
                Btn { id: createBtn; text: "Create"; kind: "accent"; enabled: newName.text.trim() !== ""; onClicked: { backend.createProfile(newName.text); newBox.shown = false } }
            }
        }
    }
    Overlay {
        id: renameBox
        anchors.fill: parent
        panelWidth: 440; panelHeight: 220
        onDismissed: shown = false
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 28; spacing: 16
            Text { text: "Rename profile"; color: Theme.fgSurface; font.pixelSize: 24; font.weight: Font.Bold }
            Field { id: renameField; Layout.fillWidth: true; onAccepted: renameOk.clicked() }
            RowLayout {
                Item { Layout.fillWidth: true }
                Btn { text: "Cancel"; kind: "flat"; onClicked: renameBox.shown = false }
                Btn { id: renameOk; text: "Rename"; kind: "accent"; onClicked: { backend.renameProfile(root.renaming, renameField.text); renameBox.shown = false } }
            }
        }
    }
    Confirm {
        id: confirmDelete
        anchors.fill: parent
        body: "Its mods and its mods folder are deleted. Shared requirements stay. This can't be undone."
        confirmText: "Delete profile"
        onConfirmed: backend.deleteProfile(root.deleting)
    }
}
