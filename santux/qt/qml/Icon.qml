import QtQuick

// Material Symbols Rounded icon, by ligature name (e.g. "play_arrow"). `filled` uses the FILL axis.
Text {
    id: root
    property string name: ""
    property int size: 20
    property bool filled: false
    property int weight: 500
    text: name
    visible: name !== ""
    font.family: "Material Symbols Rounded"
    font.pixelSize: size
    font.variableAxes: ({ "FILL": filled ? 1 : 0, "wght": weight, "opsz": Math.max(20, Math.min(48, size)), "GRAD": 0 })
    color: Theme.fgSurface
    width: size
    height: size
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter
    renderType: Text.QtRendering
}
