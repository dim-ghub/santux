import QtQuick

// M3 Expressive linear progress: the filled part is a moving wave, the rest a flat track.
// progress < 0 means indeterminate (a wavy segment sweeps across). At 1 the wave settles flat.
Canvas {
    id: root
    property real progress: -1
    property color color: Theme.primary
    property color track: Theme.secondaryContainer
    property bool active: progress < 1
    property real phase: 0
    property real sweep: 0
    property real amp: active ? 3 : 0
    implicitHeight: 12

    Behavior on amp { NumberAnimation { duration: 700; easing.type: Easing.OutCubic } }
    NumberAnimation on phase { from: 0; to: Math.PI * 2; duration: 1000; loops: Animation.Infinite; running: root.visible && root.amp > 0 }
    NumberAnimation on sweep { from: -0.35; to: 1.0; duration: 1600; loops: Animation.Infinite; running: root.visible && root.progress < 0; easing.type: Easing.InOutCubic }
    onPhaseChanged: requestPaint()
    onAmpChanged: requestPaint()
    onProgressChanged: requestPaint()
    onColorChanged: requestPaint()
    onTrackChanged: requestPaint()
    onWidthChanged: requestPaint()

    onPaint: {
        var ctx = getContext("2d")
        ctx.reset()
        var lw = 4, cap = lw / 2
        // Round caps extend half the line width past each end, so keep the ends that far inside.
        var x0 = cap, x1 = width - cap, span = x1 - x0
        var mid = height / 2, wl = 26, gap = 6
        var start, end
        if (progress >= 0) { start = x0; end = x0 + span * Math.min(1, progress) }
        else { start = Math.max(x0, x0 + span * sweep); end = Math.min(x1, x0 + span * (sweep + 0.35)) }
        ctx.lineCap = "round"
        ctx.lineWidth = lw
        // track (left of the wave, for indeterminate, and right of it)
        ctx.strokeStyle = track
        if (progress < 0 && start - gap > x0) { ctx.beginPath(); ctx.moveTo(x0, mid); ctx.lineTo(start - gap, mid); ctx.stroke() }
        if (end + gap < x1) { ctx.beginPath(); ctx.moveTo(end + gap, mid); ctx.lineTo(x1, mid); ctx.stroke() }
        // wave
        if (end - start > 0.5) {
            ctx.strokeStyle = color
            ctx.beginPath()
            ctx.moveTo(start, mid + amp * Math.sin((start / wl) * Math.PI * 2 - phase))
            for (var x = Math.floor(start) + 1; x < end; x += 1)
                ctx.lineTo(x, mid + amp * Math.sin((x / wl) * Math.PI * 2 - phase))
            ctx.lineTo(end, mid + amp * Math.sin((end / wl) * Math.PI * 2 - phase))
            ctx.stroke()
        }
        // stop indicator at the end of the track
        if (progress >= 0 && progress < 1) {
            ctx.fillStyle = color
            ctx.beginPath(); ctx.arc(x1, mid, cap, 0, Math.PI * 2); ctx.fill()
        }
    }
}
