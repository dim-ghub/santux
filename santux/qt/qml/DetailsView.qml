import QtQuick
import QtQuick.Layouts

// A mod's page: screenshots, files with Install buttons, description.
Item {
    id: root
    property var summary: ({})
    property var d: null
    property string error: ""
    signal back()

    function load(s) {
        summary = s; d = null; error = ""
        backend.loadDetails(s.url)
        flick.contentY = 0
    }
    Connections {
        target: backend
        function onDetailsLoaded(url, data) { if (url === root.summary.url) root.d = data }
        function onDetailsFailed(url, msg) { if (url === root.summary.url) root.error = msg }
    }

    RowLayout {
        id: top
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        anchors.margins: 20
        anchors.bottomMargin: 0
        spacing: 10
        Btn { text: "Back"; icon: "arrow_back"; kind: "flat"; onClicked: root.back() }
        Text { text: root.summary.title || ""; color: Theme.text; font.pixelSize: Theme.fontHeading; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
        Btn { text: "Open on gta5-mods.com"; icon: "open_in_new"; kind: "flat"; onClicked: backend.openUrl(root.summary.url) }
    }

    Text {
        anchors.centerIn: parent
        visible: !root.d
        text: root.error ? "Couldn't load the mod page: " + root.error : "Loading…"
        color: root.error ? Theme.danger : Theme.subtle
        font.pixelSize: Theme.fontBody
    }

    Scroller {
        id: flick
        anchors.top: top.bottom; anchors.topMargin: 8
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        visible: root.d !== null
        maxWidth: 980

        ColumnLayout {
            width: parent.width
            spacing: 22

            // screenshots
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(width * 0.5625, 470)
                radius: Theme.radius
                color: Theme.faint
                clip: true
                visible: root.d && root.d.images.length > 0
                ListView {
                    id: shots
                    anchors.fill: parent
                    orientation: ListView.Horizontal
                    snapMode: ListView.SnapOneItem
                    highlightRangeMode: ListView.StrictlyEnforceRange
                    boundsBehavior: Flickable.StopAtBounds
                    model: root.d ? root.d.images : []
                    delegate: Image {
                        required property var modelData
                        width: shots.width; height: shots.height
                        source: "image://web/" + encodeURIComponent(modelData)
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                    }
                }
                Row {
                    anchors.bottom: parent.bottom; anchors.bottomMargin: 12
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 6
                    visible: shots.count > 1
                    Repeater {
                        model: shots.count
                        delegate: Rectangle {
                            required property int index
                            width: 8; height: 8; radius: 4
                            color: index === shots.currentIndex ? "white" : Qt.rgba(1, 1, 1, 0.45)
                            MouseArea { anchors.fill: parent; anchors.margins: -4; onClicked: shots.currentIndex = index }
                        }
                    }
                }
                Btn { anchors.left: parent.left; anchors.leftMargin: 10; anchors.verticalCenter: parent.verticalCenter; icon: "arrow_back"; visible: shots.count > 1; onClicked: shots.decrementCurrentIndex() }
                Btn { anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter; icon: "arrow_forward"; visible: shots.count > 1; onClicked: shots.incrementCurrentIndex() }
            }

            ColumnLayout {
                spacing: 4
                Layout.fillWidth: true
                Text { text: root.d ? root.d.title : ""; color: Theme.text; font.pixelSize: Theme.fontTitle; font.weight: Font.Bold; wrapMode: Text.Wrap; Layout.fillWidth: true }
                Text {
                    Layout.fillWidth: true
                    color: Theme.subtle
                    font.pixelSize: Theme.fontBody
                    wrapMode: Text.Wrap
                    text: root.d ? [root.d.version ? "Version " + root.d.version : "", root.d.author ? "by " + root.d.author : "",
                                    root.d.downloads ? root.d.downloads + " downloads" : "", root.d.updated ? "updated " + root.d.updated : ""]
                                   .filter(function (x) { return x }).join("  ·  ") : ""
                }
                Pill { visible: root.d && root.d.installed; state: "ok"; text: "Installed in " + (win.active.name || "this profile"); Layout.topMargin: 6 }
            }

            Section {
                Layout.fillWidth: true
                title: "Files"
                description: "Install downloads the file, checks it against the site's published hash, and shows what will change before anything does."
                Repeater {
                    model: root.d ? root.d.files.slice(0, 30) : []
                    delegate: Row_ {
                        required property var modelData
                        required property int index
                        divider: index > 0
                        title: modelData.label + (modelData.current ? "   (current)" : "")
                        subtitle: [modelData.size, modelData.date, modelData.downloads ? modelData.downloads + " downloads" : "", modelData.verified ? "hash published" : ""]
                                  .filter(function (x) { return x }).join("  ·  ")
                        Btn {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Install"
                            kind: modelData.recommended ? "accent" : "normal"
                            enabled: !backend.busy && win.active.editable === true
                            onClicked: backend.installFromSite(root.summary.url, modelData.index)
                        }
                    }
                }
            }
            Text {
                visible: win.active.editable !== true
                text: "Switch to one of your mod profiles to install mods. Vanilla and GTAVXR don't hold mods."
                color: Theme.warning
                font.pixelSize: Theme.fontSmall + 1
            }

            Section {
                Layout.fillWidth: true
                title: "Description"
                Text {
                    Layout.fillWidth: true
                    Layout.margins: Theme.pad
                    text: root.d ? root.d.description : ""
                    color: Theme.text
                    font.pixelSize: Theme.fontBody
                    wrapMode: Text.Wrap
                    lineHeight: 1.15
                }
            }
        }
    }
}
