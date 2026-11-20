import QtQuick
import QtQuick.Layouts

// What an archive contains and what will be installed. Opens on backend.planReady.
Overlay {
    id: root
    panelWidth: 760
    panelHeight: 640
    property var plan: ({})
    property var checks: []
    property bool installReqs: true
    onDismissed: { shown = false; backend.discardPlan() }

    function open(p) {
        plan = p
        checks = p.oivs.map(function (o) { return o.checked })
        installReqs = true
        shown = true
    }
    readonly property bool canInstall: checks.some(function (c) { return c }) || (plan.addons || []).length > 0 || (plan.copies || []).length > 0

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 22
        spacing: 14

        ColumnLayout {
            spacing: 2
            Layout.fillWidth: true
            Text { text: "Install " + (root.plan.title || ""); color: Theme.text; font.pixelSize: Theme.fontHeading + 3; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
            Text { text: root.plan.version ? "File " + root.plan.version + "  ·  into profile " + win.active.name : "Into profile " + (win.active.name || ""); color: Theme.subtle; font.pixelSize: Theme.fontSmall + 1 }
        }

        Scroller {
            Layout.fillWidth: true
            Layout.fillHeight: true
            margin: 0
            maxWidth: 10000

            ColumnLayout {
                width: parent.width
                spacing: 18

                Text {
                    visible: root.plan.empty === true
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    color: Theme.warning
                    font.pixelSize: Theme.fontBody
                    text: "No .oiv package, add-on DLC, .asi plugin or script was found in this archive. Open its files and follow the mod's own instructions."
                }

                Section {
                    visible: (root.plan.oivs || []).length > 0
                    Layout.fillWidth: true
                    title: "Packages (.oiv)"
                    description: "Archive edits, written to this profile's mods folder. Pre-selected: the ones for GTA V " + (root.plan.edition || "") + ". Uninstallers, FiveM and other-edition packages are left off."
                    Repeater {
                        model: root.plan.oivs || []
                        delegate: Item {
                            required property var modelData
                            required property int index
                            Layout.fillWidth: true
                            implicitHeight: chk.implicitHeight + 20
                            Rectangle { visible: index > 0; height: 1; color: Theme.border; anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: Theme.pad }
                            Check {
                                id: chk
                                anchors.left: parent.left; anchors.right: parent.right
                                anchors.margins: Theme.pad
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.name
                                subtext: modelData.path
                                checked: root.checks[index]
                                onToggled: { var c = root.checks.slice(); c[index] = checked; root.checks = c }
                            }
                        }
                    }
                }

                Section {
                    visible: (root.plan.addons || []).length > 0
                    Layout.fillWidth: true
                    title: "Add-on DLC"
                    description: "Registered in dlclist.xml inside the mods folder."
                    Repeater {
                        model: root.plan.addons || []
                        delegate: Row_ { required property var modelData; required property int index; title: modelData; divider: index > 0 }
                    }
                }

                Section {
                    visible: (root.plan.copies || []).length > 0
                    Layout.fillWidth: true
                    title: "Files copied into the game folder"
                    description: (root.plan.copies || []).length + " file(s), owned by this profile."
                    Text {
                        Layout.fillWidth: true
                        Layout.margins: Theme.pad
                        text: (root.plan.copies || []).slice(0, 40).join("\n") + ((root.plan.copies || []).length > 40 ? "\n…" : "")
                        color: Theme.text
                        font.family: "monospace"
                        font.pixelSize: Theme.fontSmall
                        wrapMode: Text.WrapAnywhere
                    }
                }

                Section {
                    visible: (root.plan.skipped || []).length > 0
                    Layout.fillWidth: true
                    title: "Not installed"
                    description: "Readmes, optional extras and files Santux doesn't know how to place."
                    action: Btn { text: "Open files"; compact: true; onClicked: backend.openPath(root.plan.root) }
                    Text {
                        Layout.fillWidth: true
                        Layout.margins: Theme.pad
                        text: (root.plan.skipped || []).join("\n")
                        color: Theme.subtle
                        font.pixelSize: Theme.fontSmall
                        wrapMode: Text.WrapAnywhere
                    }
                }

                Section {
                    visible: (root.plan.missing || []).length > 0
                    Layout.fillWidth: true
                    title: "Requirements"
                    Row_ {
                        divider: false
                        title: "Install missing requirements first"
                        subtitle: (root.plan.missing || []).join(", ")
                        Toggle { checked: root.installReqs; onToggled: root.installReqs = checked; anchors.verticalCenter: parent.verticalCenter }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Btn { text: "Cancel"; onClicked: root.dismissed() }
            Btn {
                text: "Install"
                kind: "accent"
                enabled: root.canInstall
                onClicked: { root.shown = false; backend.commitPlan(root.checks, root.installReqs) }
            }
        }
    }
}
