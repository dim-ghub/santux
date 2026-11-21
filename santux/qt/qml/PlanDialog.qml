import QtQuick
import QtQuick.Layouts

// What an archive contains and what will be installed. Opens on backend.planReady.
Overlay {
    id: root
    panelWidth: 760
    panelHeight: 640
    property var plan: ({})
    property var checks: []          // per package, by its index in plan.oivs
    property var order: []           // indexes into plan.oivs, in install order
    property bool installReqs: true
    onDismissed: { shown = false; backend.discardPlan() }

    function open(p) {
        plan = p
        checks = p.oivs.map(function (o) { return o.checked })
        order = p.oivs.map(function (o, i) { return i })
        installReqs = true
        shown = true
    }
    function move(from, to) {
        to = Math.max(0, Math.min(order.length - 1, to))
        if (from === to) return
        var o = order.slice()
        var item = o.splice(from, 1)[0]
        o.splice(to, 0, item)
        order = o
    }
    // 1-based install step of the package at `pos`, counting only ticked ones (0: not installed)
    function step(pos) {
        if (!checks[order[pos]]) return 0
        var n = 0
        for (var i = 0; i <= pos; i++) if (checks[order[i]]) n++
        return n
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
                    description: "Archive edits, written to this profile's mods folder, installed top to bottom. "
                                 + ((root.plan.oivs || []).length > 1 ? "If the mod's readme gives an order, drag the packages or use the arrows to match it. " : "")
                                 + "Pre-selected: the ones for GTA V " + (root.plan.edition || "") + "; uninstallers, FiveM and other-edition packages are left off."
                    Repeater {
                        model: root.order
                        delegate: Item {
                            id: rowItem
                            required property int modelData        // index into plan.oivs
                            required property int index            // position in the install order
                            readonly property var pkg: root.plan.oivs[modelData] || ({})
                            readonly property int n: root.order.length
                            property real dragY: 0
                            Layout.fillWidth: true
                            implicitHeight: 64
                            z: handle.pressed ? 2 : 0
                            transform: Translate { y: rowItem.dragY }

                            Rectangle {
                                anchors.fill: parent
                                anchors.leftMargin: 8; anchors.rightMargin: 8
                                radius: Theme.cornerM
                                color: Theme.surfaceContainerHighest
                                visible: handle.pressed
                            }
                            Rectangle { visible: index > 0 && !handle.pressed; height: 1; color: Theme.border; anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: Theme.pad }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 14; anchors.rightMargin: Theme.pad
                                spacing: 10

                                // Drag handle: hold and move up or down to reorder.
                                Item {
                                    implicitWidth: 28; implicitHeight: 40
                                    visible: rowItem.n > 1
                                    Icon { anchors.centerIn: parent; name: "drag_indicator"; size: 20; color: Theme.fgSurfaceVariant }
                                    MouseArea {
                                        id: handle
                                        anchors.fill: parent
                                        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                                        preventStealing: true
                                        property real startY: 0
                                        onPressed: function (e) { startY = mapToItem(rowItem.parent, e.x, e.y).y }
                                        onPositionChanged: function (e) { rowItem.dragY = mapToItem(rowItem.parent, e.x, e.y).y - startY }
                                        onReleased: {
                                            var to = rowItem.index + Math.round(rowItem.dragY / rowItem.height)
                                            rowItem.dragY = 0
                                            root.move(rowItem.index, to)
                                        }
                                        onCanceled: rowItem.dragY = 0
                                    }
                                }
                                // Install step
                                Rectangle {
                                    implicitWidth: 28; implicitHeight: 28; radius: 14
                                    readonly property int s: root.step(rowItem.index)
                                    color: s ? Theme.primaryContainer : "transparent"
                                    border.width: s ? 0 : 1
                                    border.color: Theme.outlineVariant
                                    Text {
                                        anchors.centerIn: parent
                                        text: parent.s ? parent.s : "–"
                                        color: parent.s ? Theme.fgPrimaryContainer : Theme.fgSurfaceVariant
                                        font.pixelSize: 13; font.weight: Font.Bold
                                    }
                                }
                                Check {
                                    Layout.fillWidth: true
                                    text: rowItem.pkg.name || ""
                                    subtext: rowItem.pkg.path || ""
                                    checked: root.checks[rowItem.modelData] === true
                                    onToggled: { var c = root.checks.slice(); c[rowItem.modelData] = checked; root.checks = c }
                                }
                                IconBtn {
                                    visible: rowItem.n > 1
                                    icon: "arrow_upward"
                                    enabled: rowItem.index > 0
                                    opacity: enabled ? 1 : 0.3
                                    onClicked: root.move(rowItem.index, rowItem.index - 1)
                                }
                                IconBtn {
                                    visible: rowItem.n > 1
                                    icon: "arrow_downward"
                                    enabled: rowItem.index < rowItem.n - 1
                                    opacity: enabled ? 1 : 0.3
                                    onClicked: root.move(rowItem.index, rowItem.index + 1)
                                }
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
                onClicked: {
                    root.shown = false
                    backend.commitPlan(root.order.filter(function (i) { return root.checks[i] }), root.installReqs)
                }
            }
        }
    }
}
