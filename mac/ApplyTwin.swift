// ApplyTwin for Mac: the app people download. It is a window onto ApplyTwin running on this computer (localhost:4747).
// The first time it opens it sets ApplyTwin up by itself (setup.sh, no Terminal). Pages that aren't ApplyTwin's own (Google
// sign-in, job postings, Claude's login) open in the default browser, and the window reloads once a sign-in finishes.
import Cocoa
import WebKit

let APP_URL = URL(string: "http://localhost:4747/")!
let HOME = FileManager.default.homeDirectoryForCurrentUser
let INSTALLED = HOME.appendingPathComponent(".applytwin-app/bin/applytwin")
let LOG = HOME.appendingPathComponent(".applytwin/setup.log")

func isLocal(_ u: URL) -> Bool { ["localhost", "127.0.0.1"].contains(u.host ?? "") && u.port == 4747 }

// is ApplyTwin answering on localhost:4747?
func serverUp(_ done: @escaping (Bool) -> Void) {
    var r = URLRequest(url: APP_URL.appendingPathComponent("api/auth"), timeoutInterval: 2)
    r.cachePolicy = .reloadIgnoringLocalCacheData
    URLSession.shared.dataTask(with: r) { _, resp, _ in
        DispatchQueue.main.async { done((resp as? HTTPURLResponse)?.statusCode == 200) }
    }.resume()
}

func signedIn(_ done: @escaping (Bool) -> Void) {
    URLSession.shared.dataTask(with: URLRequest(url: APP_URL.appendingPathComponent("api/auth"), timeoutInterval: 3)) { d, _, _ in
        let j = d.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
        DispatchQueue.main.async { done((j?["signed_in"] as? Bool) == true) }
    }.resume()
}

class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var pendingPath: String?   // a page to open once ApplyTwin is up (from a notification click)
    var setup: Process?
    var authPoll: Timer?
    var ready = false

    func applicationWillFinishLaunching(_ n: Notification) {
        NSAppleEventManager.shared().setEventHandler(self, andSelector: #selector(openURL(_:reply:)),
                                                     forEventClass: AEEventClass(kInternetEventClass), andEventID: AEEventID(kAEGetURL))
    }

    func applicationDidFinishLaunching(_ n: Notification) {
        buildMenu()
        let cfg = WKWebViewConfiguration()
        cfg.websiteDataStore = .default()
        if #available(macOS 14.0, *) { cfg.preferences.inactiveSchedulingPolicy = .none }   // keep live counts moving behind other windows
        web = WKWebView(frame: .zero, configuration: cfg)
        web.navigationDelegate = self
        web.uiDelegate = self
        web.allowsBackForwardNavigationGestures = true
        web.setValue(false, forKey: "drawsBackground")   // no white flash before the page paints
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1280, height: 840),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "ApplyTwin"
        window.titlebarAppearsTransparent = true   // a slim bar in the app's own color: drag the window by it
        window.titleVisibility = .hidden
        window.appearance = NSAppearance(named: .darkAqua)
        window.backgroundColor = NSColor(red: 0.086, green: 0.086, blue: 0.09, alpha: 1)   // the app's own background, #161617
        window.minSize = NSSize(width: 820, height: 560)
        window.contentView = web
        window.center()
        window.setFrameAutosaveName("ApplyTwinMain")
        window.makeKeyAndOrderFront(nil)
        removeOldShortcut()
        start()
    }

    // ApplyTwin up: show it. Installed but not running: wake it. Not installed (or broken): set it up.
    func start() {
        serverUp { up in
            if up { return self.showApp() }
            if FileManager.default.fileExists(atPath: INSTALLED.path) {
                self.showSetup()
                self.say("Starting ApplyTwin")
                self.kick()
                self.waitForServer(tries: 25) { ok in ok ? self.showApp() : self.runSetup() }
            } else {
                self.showSetup()
                self.runSetup()
            }
        }
    }

    func kick() {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        p.arguments = ["kickstart", "gui/\(getuid())/tech.twinly.applytwin"]
        try? p.run()
    }

    func waitForServer(tries: Int, _ done: @escaping (Bool) -> Void) {
        serverUp { up in
            if up || tries <= 0 { return done(up) }
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self.waitForServer(tries: tries - 1, done) }
        }
    }

    func showApp() {
        ready = true
        var u = APP_URL
        if let p = pendingPath, let x = URL(string: p, relativeTo: APP_URL) { u = x.absoluteURL }
        pendingPath = nil
        web.load(URLRequest(url: u))
    }

    // the setup screen is a page inside the app; steps are pushed into it
    func showSetup() {
        guard let page = Bundle.main.url(forResource: "setup", withExtension: "html") else { return }
        web.loadFileURL(page, allowingReadAccessTo: page.deletingLastPathComponent())
    }

    func js(_ s: String) {
        if web.isLoading {   // the setup page is still loading: try again in a moment
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { self.js(s) }
            return
        }
        web.evaluateJavaScript(s, completionHandler: nil)
    }

    func say(_ step: String) {
        let data = try! JSONSerialization.data(withJSONObject: [step])
        js("window.step && step(\(String(data: data, encoding: .utf8)!)[0])")
    }

    func runSetup() {
        guard setup == nil, let script = Bundle.main.path(forResource: "setup", ofType: "sh") else { return }
        try? FileManager.default.createDirectory(at: LOG.deletingLastPathComponent(), withIntermediateDirectories: true)
        FileManager.default.createFile(atPath: LOG.path, contents: nil)
        let log = try? FileHandle(forWritingTo: LOG)
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/bash")
        p.arguments = [script]
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
        p.environment = env
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        var buf = Data()
        pipe.fileHandleForReading.readabilityHandler = { h in
            let d = h.availableData
            if d.isEmpty { return }
            log?.write(d)
            buf.append(d)
            while let nl = buf.firstIndex(of: 10) {
                let line = String(decoding: buf[..<nl], as: UTF8.self)
                buf.removeSubrange(...nl)
                if line.hasPrefix("STEP:") {
                    let s = String(line.dropFirst(5))
                    DispatchQueue.main.async { self.say(s) }
                }
            }
        }
        p.terminationHandler = { proc in
            pipe.fileHandleForReading.readabilityHandler = nil
            DispatchQueue.main.async {
                self.setup = nil
                if proc.terminationStatus != 0 { return self.failed() }
                self.say("Opening ApplyTwin")
                self.waitForServer(tries: 40) { ok in ok ? self.showApp() : self.failed() }
            }
        }
        setup = p
        do { try p.run() } catch { setup = nil; failed() }
    }

    func failed() {
        let tail = (try? String(contentsOf: LOG, encoding: .utf8)).map { String($0.suffix(1500)) } ?? ""
        let data = try! JSONSerialization.data(withJSONObject: [tail])
        js("window.fail && fail(\(String(data: data, encoding: .utf8)!)[0])")
    }

    // ---- links: ApplyTwin's own pages stay in the window, everything else goes to the default browser

    func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let u = a.request.url else { return decisionHandler(.cancel) }
        if u.scheme == "applytwin-setup" {   // the setup page's buttons
            decisionHandler(.cancel)
            if u.host == "retry" { showSetup(); runSetup() }
            if u.host == "log" { NSWorkspace.shared.open(LOG) }
            return
        }
        if u.isFileURL || u.scheme == "about" || u.scheme == "blob" || u.scheme == "data" || isLocal(u) { return decisionHandler(.allow) }
        decisionHandler(.cancel)
        openOutside(u)
    }

    func webView(_ w: WKWebView, createWebViewWith c: WKWebViewConfiguration, for a: WKNavigationAction, windowFeatures f: WKWindowFeatures) -> WKWebView? {
        if let u = a.request.url { openOutside(u) }   // target=_blank and window.open: the browser
        return nil
    }

    func openOutside(_ u: URL) {
        NSWorkspace.shared.open(u)
        // a sign-in finishes in the browser; bring the window back up to date once it has
        if u.path.contains("/auth/v1/authorize") { watchSignIn() }
    }

    func watchSignIn() {
        authPoll?.invalidate()
        var left = 300
        authPoll = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { t in
            left -= 1
            if left <= 0 { return t.invalidate() }
            signedIn { yes in
                if yes { t.invalidate(); self.web.load(URLRequest(url: APP_URL)); NSApp.activate(ignoringOtherApps: true) }
            }
        }
    }

    // the page server went away (it restarts itself after an update): wait for it, then reload
    func webView(_ w: WKWebView, didFailProvisionalNavigation n: WKNavigation!, withError e: Error) {
        let code = (e as NSError).code   // only "ApplyTwin isn't answering", not a link this app sent to the browser
        guard ready, [NSURLErrorCannotConnectToHost, NSURLErrorNetworkConnectionLost, NSURLErrorTimedOut].contains(code) else { return }
        ready = false
        showSetup()
        say("Starting ApplyTwin")
        kick()
        waitForServer(tries: 30) { ok in ok ? self.showApp() : self.runSetup() }
    }

    func webViewWebContentProcessDidTerminate(_ w: WKWebView) { w.reload() }

    // ---- file pickers, dialogs, downloads

    func webView(_ w: WKWebView, runOpenPanelWith p: WKOpenPanelParameters, initiatedByFrame f: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = p.allowsMultipleSelection
        panel.canChooseDirectories = p.allowsDirectories
        panel.beginSheetModal(for: window) { r in completionHandler(r == .OK ? panel.urls : nil) }
    }

    func webView(_ w: WKWebView, runJavaScriptAlertPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let a = NSAlert(); a.messageText = m
        a.beginSheetModal(for: window) { _ in completionHandler() }
    }

    func webView(_ w: WKWebView, runJavaScriptConfirmPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let a = NSAlert(); a.messageText = m
        a.addButton(withTitle: "OK"); a.addButton(withTitle: "Cancel")
        a.beginSheetModal(for: window) { r in completionHandler(r == .alertFirstButtonReturn) }
    }

    func webView(_ w: WKWebView, runJavaScriptTextInputPanelWithPrompt p: String, defaultText d: String?, initiatedByFrame f: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        let a = NSAlert(); a.messageText = p
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 280, height: 24)); field.stringValue = d ?? ""
        a.accessoryView = field
        a.addButton(withTitle: "OK"); a.addButton(withTitle: "Cancel")
        a.beginSheetModal(for: window) { r in completionHandler(r == .alertFirstButtonReturn ? field.stringValue : nil) }
    }

    func webView(_ w: WKWebView, decidePolicyFor r: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        let disp = (r.response as? HTTPURLResponse)?.value(forHTTPHeaderField: "Content-Disposition") ?? ""
        decisionHandler(disp.lowercased().hasPrefix("attachment") || !r.canShowMIMEType ? .download : .allow)
    }

    func webView(_ w: WKWebView, navigationAction a: WKNavigationAction, didBecome d: WKDownload) { d.delegate = self }
    func webView(_ w: WKWebView, navigationResponse r: WKNavigationResponse, didBecome d: WKDownload) { d.delegate = self }

    func download(_ d: WKDownload, decideDestinationUsing r: URLResponse, suggestedFilename name: String, completionHandler: @escaping (URL?) -> Void) {
        let dir = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask)[0]
        var dest = dir.appendingPathComponent(name)
        let base = dest.deletingPathExtension().lastPathComponent, ext = dest.pathExtension
        var i = 2
        while FileManager.default.fileExists(atPath: dest.path) {   // never overwrite a file already in Downloads
            dest = dir.appendingPathComponent("\(base) \(i)" + (ext.isEmpty ? "" : ".\(ext)")); i += 1
        }
        completionHandler(dest)
    }

    func downloadDidFinish(_ d: WKDownload) {
        if let u = d.progress.fileURL { NSWorkspace.shared.activateFileViewerSelecting([u]) }
    }

    // ---- notification clicks: applytwin://open/#agents opens that page

    @objc func openURL(_ e: NSAppleEventDescriptor, reply: NSAppleEventDescriptor) {
        guard let s = e.paramDescriptor(forKeyword: keyDirectObject)?.stringValue, let u = URL(string: s) else { return }
        let path = "/" + (u.fragment.map { "#" + $0 } ?? "")
        if ready { web.load(URLRequest(url: URL(string: path, relativeTo: APP_URL)!.absoluteURL)) } else { pendingPath = path }
        window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldHandleReopen(_ s: NSApplication, hasVisibleWindows v: Bool) -> Bool {
        if !v { window.makeKeyAndOrderFront(nil) }
        return true
    }

    // closing the window hides it; ApplyTwin keeps running in the background either way
    func applicationShouldTerminateAfterLastWindowClosed(_ s: NSApplication) -> Bool { setup == nil }

    // the one-line install used to add a small shortcut app with the same name to ~/Applications: this app replaces it
    func removeOldShortcut() {
        let old = HOME.appendingPathComponent("Applications/ApplyTwin.app")
        if old.standardizedFileURL.path == Bundle.main.bundleURL.standardizedFileURL.path { return }
        let id = Bundle(url: old)?.bundleIdentifier ?? ""
        let applet = FileManager.default.fileExists(atPath: old.appendingPathComponent("Contents/Resources/Scripts/main.scpt").path)
        if applet && !id.hasPrefix("tech.twinly.applytwin.app") { try? FileManager.default.trashItem(at: old, resultingItemURL: nil) }
    }

    @objc func reload() { if ready { web.reload() } else { start() } }
    @objc func goBack() { web.goBack() }
    @objc func goForward() { web.goForward() }
    @objc func openInBrowser() { NSWorkspace.shared.open(web.url.flatMap { isLocal($0) ? $0 : nil } ?? APP_URL) }
    @objc func openSite() { NSWorkspace.shared.open(URL(string: "https://apply.twinly.tech")!) }
    @objc func zoomIn() { web.pageZoom = min(web.pageZoom + 0.1, 2) }
    @objc func zoomOut() { web.pageZoom = max(web.pageZoom - 0.1, 0.6) }
    @objc func zoomReset() { web.pageZoom = 1 }

    func buildMenu() {
        let main = NSMenu()
        func menu(_ title: String, _ items: [NSMenuItem]) {
            let m = NSMenu(title: title); items.forEach(m.addItem)
            let host = NSMenuItem(); host.submenu = m; main.addItem(host)
        }
        func item(_ t: String, _ s: Selector?, _ k: String = "", _ mods: NSEvent.ModifierFlags = .command) -> NSMenuItem {
            let i = NSMenuItem(title: t, action: s, keyEquivalent: k); i.keyEquivalentModifierMask = mods; return i
        }
        menu("ApplyTwin", [item("About ApplyTwin", #selector(NSApplication.orderFrontStandardAboutPanel(_:))), .separator(),
                           item("Hide ApplyTwin", #selector(NSApplication.hide(_:)), "h"),
                           item("Hide Others", #selector(NSApplication.hideOtherApplications(_:)), "h", [.command, .option]),
                           item("Show All", #selector(NSApplication.unhideAllApplications(_:))), .separator(),
                           item("Quit ApplyTwin", #selector(NSApplication.terminate(_:)), "q")])
        menu("Edit", [item("Undo", Selector(("undo:")), "z"), item("Redo", Selector(("redo:")), "z", [.command, .shift]), .separator(),
                      item("Cut", #selector(NSText.cut(_:)), "x"), item("Copy", #selector(NSText.copy(_:)), "c"),
                      item("Paste", #selector(NSText.paste(_:)), "v"), item("Select All", #selector(NSText.selectAll(_:)), "a")])
        menu("View", [item("Reload", #selector(reload), "r"), item("Back", #selector(goBack), "["), item("Forward", #selector(goForward), "]"),
                      .separator(), item("Actual Size", #selector(zoomReset), "0"), item("Zoom In", #selector(zoomIn), "="),
                      item("Zoom Out", #selector(zoomOut), "-"), .separator(),
                      item("Open in Browser", #selector(openInBrowser), "o", [.command, .shift])])
        menu("Window", [item("Minimize", #selector(NSWindow.performMiniaturize(_:)), "m"), item("Zoom", #selector(NSWindow.performZoom(_:))),
                        item("Close", #selector(NSWindow.performClose(_:)), "w")])
        menu("Help", [item("ApplyTwin Website", #selector(openSite))])
        NSApp.mainMenu = main
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
