import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic as C

Item {
    id: root
    ListModel { id: results }
    property int pageNo: 1
    property int requestId: -1
    property bool loading: false
    property bool more: false
    property string error: ""
    property string detailsUrl: ""

    readonly property var cats: backend.categories()
    readonly property var sortModel: backend.sorts()

    function search(fresh) {
        if (loading && !fresh) return
        if (fresh) { pageNo = 1; results.clear(); grid.positionViewAtBeginning() } else pageNo++
        loading = true; error = ""
        requestId = backend.search(query.text, cat.currentKey, sort.currentKey, pageNo)
    }
    Component.onCompleted: search(true)

    Connections {
        target: backend
        function onSearchFinished(rid, res, more) {
            if (rid !== root.requestId) return
            for (var i = 0; i < res.length; i++) results.append(res[i])
            root.more = more
            root.loading = false
        }
        function onSearchFailed(rid, msg) {
            if (rid !== root.requestId) return
            root.loading = false
            root.error = msg
        }
    }

    // ---------------------------------------------------------------- grid
    ColumnLayout {
        anchors.fill: parent
        visible: root.detailsUrl === ""
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 20
            Layout.bottomMargin: 12
            spacing: 8
            Field { id: query; Layout.fillWidth: true; placeholder: "Search gta5-mods.com"; icon: "search"; onAccepted: root.search(true) }
            Dropdown { id: cat; model: root.cats; onActivated: root.search(true) }
            Dropdown { id: sort; model: root.sortModel; currentIndex: 1; onActivated: root.search(true) }
            FilterChip {
                text: "18+"
                icon: "explicit"
                checked: backend.showAdult
                onToggled: { backend.setShowAdult(checked); root.search(true) }
            }
        }

        GridView {
            id: grid
            Layout.fillWidth: true
            Layout.fillHeight: true
            leftMargin: 20; rightMargin: 8; bottomMargin: 20
            clip: true
            readonly property int cols: Math.max(1, Math.floor((width - 28) / 260))
            cellWidth: Math.floor((width - 28) / cols)
            cellHeight: (cellWidth - 12) * 0.56 + 128
            model: results
            boundsBehavior: Flickable.StopAtBounds
            delegate: Item {
                required property var model
                width: grid.cellWidth; height: grid.cellHeight
                ModCard {
                    anchors.fill: parent
                    anchors.rightMargin: 12; anchors.bottomMargin: 12
                    mod: parent.model
                    onClicked: { root.detailsUrl = parent.model.url; details.load({ url: parent.model.url, title: parent.model.title }) }
                }
            }
            onAtYEndChanged: if (atYEnd && root.more && !root.loading && results.count) root.search(false)
            footer: Item {
                width: grid.width - 28
                height: 64
                Text {
                    anchors.centerIn: parent
                    text: root.loading ? "Loading…" : root.error ? "Couldn't load: " + root.error : results.count === 0 ? "No mods found." : ""
                    color: root.error ? Theme.danger : Theme.subtle
                    font.pixelSize: Theme.fontBody
                }
            }
            C.ScrollBar.vertical: C.ScrollBar {
                contentItem: Rectangle { implicitWidth: 6; radius: 3; color: Theme.subtle; opacity: 0.5 }
            }
        }
    }

    DetailsView {
        id: details
        anchors.fill: parent
        visible: root.detailsUrl !== ""
        onBack: root.detailsUrl = ""
    }
}
