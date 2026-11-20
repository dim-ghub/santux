import QtQuick

// Status chip. state: "ok" | "missing" | "update" | "info" | anything else (neutral)
Rectangle {
    id: root
    property string state: ""
    property string text: ({ "ok": "Installed", "missing": "Missing", "update": "Update", "info": "Check" })[state] || state
    readonly property color container: state === "ok" ? Theme.goodContainer
                                      : state === "missing" ? Theme.errorContainer
                                      : (state === "update" || state === "info") ? Theme.cautionContainer
                                      : Theme.surfaceContainerHighest
    readonly property color content: state === "ok" ? Theme.good
                                   : state === "missing" ? Theme.fgErrorContainer
                                   : (state === "update" || state === "info") ? Theme.caution
                                   : Theme.fgSurfaceVariant
    implicitHeight: 28
    implicitWidth: t.implicitWidth + 24
    radius: Theme.cornerS
    color: container
    Text {
        id: t
        anchors.centerIn: parent
        text: root.text
        color: root.content
        font.pixelSize: 12
        font.weight: Font.DemiBold
        font.letterSpacing: 0.2
    }
}
