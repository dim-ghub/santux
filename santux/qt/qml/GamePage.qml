import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property int tick: 0
    property var info: backend.gameInfo
    property bool aiTesting: false
    property string aiTestMsg: ""
    property bool aiTestOk: false
    onTickChanged: info = backend.gameInfo
    Component.onCompleted: if (backend.geminiConfigured) backend.refreshGeminiModels("")

    function modelIndex() {
        var list = backend.geminiModels || []
        var cur = backend.geminiModel || ""
        for (var i = 0; i < list.length; i++) if (list[i].key === cur) return i
        return 0
    }

    Connections {
        target: backend
        function onGeminiTestFinished(ok, msg) {
            root.aiTesting = false
            root.aiTestOk = ok
            root.aiTestMsg = msg
        }
    }

    Scroller {
        anchors.fill: parent
        maxWidth: 1100

        ColumnLayout {
            width: parent.width
            spacing: 28

            PageHeader { title: "Settings"; subtitle: "Game locations, Proton prefix maintenance, and AI installer settings." }

            // ---- hero
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: hero.implicitHeight + 56
                radius: Theme.cornerXL
                color: Theme.primaryContainer
                RowLayout {
                    id: hero
                    anchors.left: parent.left; anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: 28
                    spacing: 24
                    Rectangle {
                        width: 96; height: 96; radius: 36
                        color: Theme.primary
                        Icon { anchors.centerIn: parent; name: "sports_esports"; size: 52; filled: true; color: Theme.fgPrimary }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        Text { text: "GTA V " + (root.info.edition || ""); color: Theme.fgPrimaryContainer; font.pixelSize: 28; font.weight: Font.Bold }
                        Text { text: "Version " + (root.info.version || "unknown") + "  ·  Proton " + (root.info.proton || "unknown"); color: Theme.alpha(Theme.fgPrimaryContainer, 0.85); font.pixelSize: 15 }
                    }
                    Btn { text: "Play " + (win.active.name || ""); icon: "play_arrow"; kind: "accent"; onClicked: backend.play(win.active.slug) }
                }
            }

            ListGroup {
                Layout.fillWidth: true
                title: "Locations"
                ListRow {
                    icon: "folder"; title: "Game folder"; subtitle: root.info.folder || ""
                    Btn { anchors.verticalCenter: parent.verticalCenter; icon: "folder_open"; kind: "flat"; onClicked: backend.openPath(root.info.folder) }
                }
                ListRow {
                    icon: "wine_bar"; title: "Proton prefix"
                    subtitle: root.info.prefix || "Not created yet: launch GTA V from Steam once"
                    Btn { anchors.verticalCenter: parent.verticalCenter; icon: "folder_open"; kind: "flat"; visible: !!root.info.prefix; onClicked: backend.openPath(root.info.prefix) }
                }
                ListRow {
                    icon: "database"; title: "Santux data"; subtitle: root.info.dataDir || ""
                    Btn { anchors.verticalCenter: parent.verticalCenter; icon: "folder_open"; kind: "flat"; onClicked: backend.openPath(root.info.dataDir) }
                }
            }

            ListGroup {
                Layout.fillWidth: true
                title: "Steam"
                ListRow { icon: "storefront"; title: "Steam install"; subtitle: root.info.steam || "" }
                ListRow {
                    icon: "terminal"; title: "Launch options"; subtitle: root.info.launchOptions || "none"
                    Btn { anchors.verticalCenter: parent.verticalCenter; text: "Change"; kind: "tonal"; compact: true; onClicked: win.go(2) }
                }
            }

            ListGroup {
                Layout.fillWidth: true
                title: "Maintenance"
                ListRow {
                    icon: "healing"
                    title: "Prepare the prefix"
                    subtitle: "Back up the prefix registry, then install the VC++ 2015–2022 runtime and .NET Framework 4.8 (10–20 minutes)."
                    Btn { anchors.verticalCenter: parent.verticalCenter; text: "Prepare"; kind: "tonal"; compact: true; enabled: !backend.busy; onClicked: backend.preparePrefix() }
                }
            }

            ListGroup {
                Layout.fillWidth: true
                title: "AI installer (Gemini)"
                ListRow {
                    icon: "auto_awesome"
                    title: "Gemini API key"
                    subtitle: backend.geminiConfigured
                        ? "Configured. Converts mods with written instructions into installable .oiv packages."
                        : "Optional. Add a free Google AI Studio key so Santux can read mod instructions and install non-.oiv mods."
                    expanded: true
                    Btn {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Get free key"
                        icon: "open_in_new"
                        kind: "flat"
                        compact: true
                        onClicked: backend.openUrl("https://aistudio.google.com/apikey")
                    }
                    detail: ColumnLayout {
                        width: parent.width
                        spacing: 10
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            Field {
                                id: apiKeyField
                                Layout.fillWidth: true
                                icon: "key"
                                secret: true
                                placeholder: "AIza… (or set GEMINI_API_KEY in environment)"
                                text: backend.geminiApiKey
                                onAccepted: {
                                    backend.setGeminiApiKey(text)
                                    win.toast("Gemini API key saved.")
                                }
                            }
                            Btn {
                                text: "Save"
                                kind: "accent"
                                compact: true
                                onClicked: {
                                    backend.setGeminiApiKey(apiKeyField.text)
                                    win.toast("Gemini API key saved.")
                                }
                            }
                            Btn {
                                text: root.aiTesting ? "Testing…" : "Test"
                                kind: "tonal"
                                compact: true
                                enabled: !root.aiTesting
                                onClicked: {
                                    backend.setGeminiApiKey(apiKeyField.text)
                                    root.aiTesting = true
                                    root.aiTestMsg = ""
                                    backend.testGemini(apiKeyField.text, backend.geminiModel)
                                }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            Dropdown {
                                id: modelDrop
                                icon: "smart_toy"
                                openUp: true
                                model: backend.geminiModels
                                currentIndex: root.modelIndex()
                                onActivated: function (i) {
                                    var list = backend.geminiModels || []
                                    if (i >= 0 && i < list.length) backend.setGeminiModel(list[i].key)
                                }
                            }
                            IconBtn {
                                icon: "refresh"
                                enabled: !backend.geminiModelsLoading && (backend.geminiConfigured || apiKeyField.text.trim() !== "")
                                opacity: enabled ? 1 : 0.4
                                onClicked: backend.refreshGeminiModels(apiKeyField.text)
                            }
                            Text {
                                visible: backend.geminiModelsLoading || root.aiTestMsg !== ""
                                text: backend.geminiModelsLoading ? "Loading available models…" : root.aiTestMsg
                                color: backend.geminiModelsLoading ? Theme.subtle : (root.aiTestOk ? Theme.ok : Theme.error)
                                font.pixelSize: Theme.fontSmall + 1
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
                ListRow {
                    icon: "tune"
                    title: "Auto-convert unrecognized mods"
                    subtitle: "Automatically ask Gemini when a mod archive has no .oiv, add-on DLC, .asi or scripts. You still review the plan before installing."
                    Toggle {
                        anchors.verticalCenter: parent.verticalCenter
                        checked: backend.geminiAuto
                        onToggled: backend.setGeminiAuto(checked)
                    }
                }
            }

            EmptyState {
                visible: root.info.legacy === false
                icon: "info"
                title: "GTA V Enhanced"
                text: "Script Hook V, the mods folder loader, .oiv packages and the heap/packfile adjusters work. ScriptHookVDotNet, the modded gameconfig and GTAVXR are Legacy-only."
            }
        }
    }
}
