import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic as C

// Progress + log for long-running work. Opens on backend.taskStarted (unless the task is quiet).
Overlay {
    id: root
    panelWidth: 720
    panelHeight: 480
    property string title: ""
    property string status: "Working…"
    property real progress: -1
    property bool done: false
    property bool ok: true
    property bool quiet: false
    dismissable: done
    onDismissed: shown = false

    Connections {
        target: backend
        function onTaskQuiet(q) { root.quiet = q }
        function onTaskStarted(t) {
            root.title = t; root.status = "Working…"; root.progress = -1
            root.done = false; root.ok = true; log.text = ""
            root.shown = !root.quiet
        }
        function onTaskLog(line) { log.append(line) }
        function onTaskStatus(s) { root.status = s }
        function onTaskProgress(p) { root.progress = p }
        function onTaskFinished(ok, msg) {
            root.done = true; root.ok = ok; root.status = msg; root.progress = ok ? 1 : 0
            if (root.quiet) {
                if (ok) win.toast(msg); else { root.shown = true }
            } else if (ok && root.title.indexOf("Getting ") === 0) {
                root.shown = false     // the install plan takes over
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 12
        Text { text: root.title; color: Theme.text; font.pixelSize: Theme.fontHeading + 2; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
        Text { text: root.status; color: root.done && !root.ok ? Theme.danger : Theme.subtle; font.pixelSize: Theme.fontBody; Layout.fillWidth: true; wrapMode: Text.Wrap }

        WavyProgress {
            Layout.fillWidth: true
            progress: root.done ? (root.ok ? 1 : 0) : root.progress
            color: root.done && !root.ok ? Theme.error : Theme.primary
            visible: !(root.done && !root.ok)
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.cornerL
            color: Theme.surfaceContainerLowest
            C.ScrollView {
                id: sv
                anchors.fill: parent
                anchors.margins: 1
                C.TextArea {
                    id: log
                    readOnly: true
                    wrapMode: Text.WrapAnywhere
                    color: Theme.baseText
                    font.family: "monospace"
                    font.pixelSize: Theme.fontSmall
                    selectByMouse: true
                    background: null
                    onTextChanged: cursorPosition = length
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Btn { text: "Cancel"; visible: !root.done; onClicked: backend.cancelTask() }
            Btn { text: "Close"; kind: "accent"; visible: root.done; onClicked: root.shown = false }
        }
    }
}
