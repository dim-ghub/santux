import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs

Item {
    id: root
    property int tick: 0
    property var profile: ({})
    property var mods: []
    property var unmanaged: []
    property var expanded: ({})
    property bool showUnmanaged: false
    onTickChanged: reload()
    Component.onCompleted: reload()
    function reload() { mods = backend.installedMods(); unmanaged = backend.unmanagedFiles() }
    function kindIcon(m) {
        if (m.packages.length) return "deployed_code"
        if (m.files.some(function (f) { return f.indexOf("scripts/") === 0 })) return "code_blocks"
        if (m.files.some(function (f) { return /\.asi$/i.test(f) })) return "extension"
        if (m.files.some(function (f) { return f.indexOf("menyooStuff/") === 0 })) return "checkroom"
        return "inventory_2"
    }

    FileDialog {
        id: fileDialog
        title: "Choose a mod archive, .oiv packages or .asi"
        fileMode: FileDialog.OpenFiles     // several .oiv parts of one mod become one install
        nameFilters: ["Mods (*.zip *.7z *.rar *.oiv *.asi *.dll *.rpf)", "All files (*)"]
        onAccepted: backend.openPaths(selectedFiles.map(function (u) { return u.toString() }))
    }

    Scroller {
        anchors.fill: parent
        maxWidth: 1100

        ColumnLayout {
            width: parent.width
            spacing: 28

            PageHeader {
                title: "Installed"
                subtitle: root.profile.editable
                          ? "In <b>" + (root.profile.name || "") + "</b>  ·  " + root.mods.length + " mod" + (root.mods.length === 1 ? "" : "s")
                          : "Mods live in your mod profiles."
                Btn { visible: root.profile.editable === true; text: "Install from file"; icon: "upload_file"; kind: "accent"; enabled: !backend.busy; onClicked: fileDialog.open() }
                Btn { visible: root.profile.editable === true; text: "Rebuild"; icon: "refresh"; kind: "tonal"; enabled: !backend.busy; onClicked: backend.rebuildMods() }
                MenuButton {
                    visible: root.profile.editable === true
                    items: [{ label: "Open game folder", icon: "folder_open" }, { label: "Reset mods folder", icon: "delete_sweep", danger: true }]
                    onTriggered: function (i) { if (i === 0) backend.openPath(backend.gameInfo.folder); else confirmReset.shown = true }
                }
            }

            EmptyState {
                visible: root.profile.editable !== true
                icon: root.profile.kind === "vr" ? "view_in_ar" : "sports_esports"
                title: (root.profile.name || "This profile") + " doesn't hold mods"
                text: root.profile.kind === "vr" ? "GTAVXR's mods are managed inside its Suite. Switch to a mod profile to install flatscreen mods."
                                                 : "Vanilla is the unmodified game. Switch to a mod profile to install and manage mods."
                actionText: "Go to profiles"
                onAction: win.go(2)
            }
            EmptyState {
                visible: root.profile.editable === true && root.mods.length === 0
                icon: "inventory_2"
                title: "No mods yet"
                text: "Find mods on Browse, or install an archive you downloaded."
                actionText: "Browse mods"
                onAction: win.go(0)
            }

            ListGroup {
                visible: root.profile.editable === true && root.mods.length > 0
                Layout.fillWidth: true
                Repeater {
                    model: root.mods
                    delegate: ListRow {
                        required property var modelData
                        clickable: true
                        expanded: root.expanded[modelData.id] === true
                        icon: root.kindIcon(modelData)
                        title: modelData.title
                        tone: modelData.disabled ? Theme.surfaceContainerLow : Theme.surfaceContainer
                        iconBg: modelData.disabled ? Theme.surfaceContainerHighest : Theme.secondaryContainer
                        iconColor: modelData.disabled ? Theme.fgSurfaceVariant : Theme.fgSecondaryContainer
                        subtitle: (modelData.disabled ? "<b>Off</b>  ·  " : "") + modelData.summary + (modelData.notes.length ? "  ·  <font color='" + Theme.caution + "'>" + modelData.notes.length + " note" + (modelData.notes.length === 1 ? "" : "s") + "</font>" : "")
                        onClicked: { var e = Object.assign({}, root.expanded); e[modelData.id] = !e[modelData.id]; root.expanded = e }
                        titleExtra: IconBtn { icon: "open_in_new"; visible: modelData.web; onClicked: backend.openUrl(modelData.source) }
                        Toggle {
                            anchors.verticalCenter: parent.verticalCenter
                            checked: !modelData.disabled
                            enabled: !backend.busy
                            onToggled: backend.setModEnabled(modelData.id, modelData.title, checked)
                        }
                        Item { width: 4; height: 1 }
                        IconBtn { anchors.verticalCenter: parent.verticalCenter; icon: "delete"; size: 20; color: Theme.fgSurfaceVariant; enabled: !backend.busy; onClicked: backend.uninstall(modelData.id, modelData.title) }
                        Icon {
                            anchors.verticalCenter: parent.verticalCenter
                            name: "keyboard_arrow_down"; size: 24; color: Theme.fgSurfaceVariant
                            rotation: root.expanded[modelData.id] ? 180 : 0
                            Behavior on rotation { NumberAnimation { duration: Theme.medium; easing.type: Easing.OutBack } }
                        }
                        detail: Text {
                            width: parent.width
                            text: modelData.packages.map(function (p) { return "package  " + p }).concat(modelData.files.slice(0, 120)).join("\n")
                                  + (modelData.files.length > 120 ? "\n… " + (modelData.files.length - 120) + " more" : "")
                                  + (modelData.notes.length ? "\n\n" + modelData.notes.join("\n") : "")
                            color: Theme.fgSurfaceVariant
                            font.family: "monospace"
                            font.pixelSize: 12
                            wrapMode: Text.WrapAnywhere
                        }
                    }
                }
            }

            ListGroup {
                visible: root.profile.editable === true && root.unmanaged.length > 0
                Layout.fillWidth: true
                title: "Not managed by any profile"
                description: "Mod files in the game folder that Santux didn't install. They load in every modded profile."
                ListRow {
                    icon: "help"
                    iconBg: Theme.cautionContainer
                    iconColor: Theme.caution
                    title: root.unmanaged.length + " file" + (root.unmanaged.length === 1 ? "" : "s")
                    subtitle: root.unmanaged.slice(0, 3).join(", ") + (root.unmanaged.length > 3 ? ", …" : "")
                    clickable: true
                    expanded: root.showUnmanaged
                    onClicked: root.showUnmanaged = !root.showUnmanaged
                    Btn { anchors.verticalCenter: parent.verticalCenter; text: "Add to " + (root.profile.name || "profile"); kind: "tonal"; enabled: !backend.busy; onClicked: backend.adoptFiles(root.unmanaged, "Existing files") }
                    detail: Text {
                        width: parent.width
                        text: root.unmanaged.join("\n")
                        color: Theme.fgSurfaceVariant; font.family: "monospace"; font.pixelSize: 12; wrapMode: Text.WrapAnywhere
                    }
                }
            }
        }
    }

    Confirm {
        id: confirmReset
        anchors.fill: parent
        heading: "Reset the mods folder?"
        body: "This deletes this profile's mods folder, removing every package's archive edits, and forgets those packages. Loose files (.asi plugins, scripts) stay. This can't be undone."
        confirmText: "Delete mods folder"
        onConfirmed: backend.resetMods()
    }
}
