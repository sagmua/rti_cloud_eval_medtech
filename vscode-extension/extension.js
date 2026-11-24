const vscode = require("vscode");
const fs = require("fs");
const os = require("os");
const path = require("path");

const LOCALHOST_NAMES = new Set(["localhost", "127.0.0.1", "::1"]);
const APP_VIEW_COLUMNS = {
    ArmController: vscode.ViewColumn.One,
    Arm: vscode.ViewColumn.Three,
    Orchestrator: vscode.ViewColumn.Two,
    PatientMonitor: vscode.ViewColumn.Four,
};
const DEMO_GRID_LAYOUT = {
    orientation: 1,
    groups: [{ groups: [{}, {}] }, { groups: [{}, {}] }],
};

let demoGridCreated = false;
let demoGridCreation;
let gridConfiguration;
let previousCloseEmptyGroups;
const demoPanels = new Set();
const appPanels = new Map();
const appColumns = new Map();
let tabStateDir = path.join(os.tmpdir(), `medtech-web-tabs-${process.getuid()}`);
const cloudWorkspace = process.env.MEDTECH_CLOUD === "1" || fs.existsSync("/app/code-server");
let recoveryView;
let extensionContext;
let dashboard;
const dashboardDevices = new Map();

function recovery() {
    if (!recoveryView) {
        const { DeviceLauncher } = require("./device-launcher");
        recoveryView = new DeviceLauncher(extensionContext);
    }
    return recoveryView;
}

function cloudTargetUrl(targetUrl, origin = process.env.MEDTECH_CLOUD_URL) {
    if (!origin) throw new Error("MEDTECH_CLOUD_URL must be set to the external IDE base URL.");
    const base = new URL(origin);
    if (!["http:", "https:"].includes(base.protocol) || base.username || base.password || origin.includes("?") || origin.includes("#")) {
        throw new Error("MEDTECH_CLOUD_URL must be an HTTP(S) IDE base URL without credentials, query, or fragment.");
    }
    return new URL(`${base.href.replace(/\/+$/, "")}/proxy/${targetUrl.port}${targetUrl.pathname}${targetUrl.search}`);
}

function tabStatePath(title) {
    return path.join(tabStateDir, title);
}

function escapeHtml(value) {
    return value.replace(/[&<>"]/g, (character) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
    })[character]);
}

function isLocalHttpUrl(url) {
    return (url.protocol === "http:" || url.protocol === "https:")
        && LOCALHOST_NAMES.has(url.hostname);
}

async function preserveDemoGroups() {
    const configuration = vscode.workspace?.getConfiguration?.("workbench.editor");
    if (!configuration || gridConfiguration) return;
    previousCloseEmptyGroups = configuration.inspect("closeEmptyGroups")?.workspaceValue;
    await configuration.update("closeEmptyGroups", false, vscode.ConfigurationTarget.Workspace);
    gridConfiguration = configuration;
}

async function restoreDemoGroups() {
    if (!gridConfiguration) return;
    const configuration = gridConfiguration;
    gridConfiguration = undefined;
    if (configuration.inspect("closeEmptyGroups")?.workspaceValue === false) {
        await configuration.update("closeEmptyGroups", previousCloseEmptyGroups, vscode.ConfigurationTarget.Workspace);
    }
}

async function createDemoGrid() {
    if (demoGridCreated) {
        return;
    }

    if (!demoGridCreation) {
        demoGridCreation = preserveDemoGroups()
            .then(() => vscode.commands.executeCommand("vscode.setEditorLayout", DEMO_GRID_LAYOUT))
            .then(() => { demoGridCreated = true; })
            .finally(() => { demoGridCreation = undefined; });
    }
    await demoGridCreation;
}

function createAppPanel(title, targetUrl, closeToken, preserveFocus = false) {
    const column = appColumns.get(title) || APP_VIEW_COLUMNS[title] || vscode.ViewColumn.Beside;
    const panel = vscode.window.createWebviewPanel(
        "rti.medtechWebTab",
        title,
        preserveFocus ? { viewColumn: column, preserveFocus: true } : column,
        { enableScripts: true, retainContextWhenHidden: true }
    );
    panel.closeToken = closeToken;
    panel.targetUrl = targetUrl;
    demoPanels.add(panel);
    if (APP_VIEW_COLUMNS[title]) {
        appColumns.set(title, APP_VIEW_COLUMNS[title]);
        appPanels.set(title, panel);
        fs.mkdirSync(tabStateDir, { recursive: true });
        fs.writeFileSync(tabStatePath(title), String(process.pid));
    }
    panel.disposed = new Promise((resolve) => {
        panel.onDidDispose(() => {
            demoPanels.delete(panel);
            if (appPanels.get(title) === panel) {
                appPanels.delete(title);
                fs.writeFileSync(tabStatePath(title), String(-process.pid));
                if (panel.closeToken && !panel.closedByLauncher) {
                    fs.writeFileSync(path.join(tabStateDir, `${panel.closeToken}.close`), "");
                }
            }
            resolve();
        });
    });
    panel.webview.html = webviewHtml(targetUrl, title);
    if (title === "Orchestrator") {
        panel.webview.onDidReceiveMessage?.(async message => {
            const { DEVICE_NAMES } = require("./device-launcher");
            if (message.action !== "start" || !Object.hasOwn(DEVICE_NAMES, message.device)
                    || !Number.isSafeInteger(message.requestId)) return;
            try {
                const name = DEVICE_NAMES[message.device];
                const status = await recovery().restoreDevice(name, !appPanels.has(name) || message.stopped === true);
                await panel.webview.postMessage({ type: "medtech-device-start-result", requestId: message.requestId, status });
            } catch (error) {
                await panel.webview.postMessage({ type: "medtech-device-start-result", requestId: message.requestId, status: "error" });
                vscode.window.showErrorMessage(`Unable to start device: ${error.message}`);
            }
        });
    }
    return panel;
}

function showDashboard(preserveFocus = false) {
    if (dashboard) {
        dashboard.reveal(undefined, preserveFocus);
        return;
    }
    const panel = vscode.window.createWebviewPanel(
        "rti.medtechDashboard", "Digital Operating Room",
        { viewColumn: vscode.ViewColumn.Active, preserveFocus },
        { enableScripts: true, retainContextWhenHidden: true }
    );
    dashboard = panel;
    panel.onDidDispose(() => {
        if (dashboard === panel) dashboard = undefined;
    });
    panel.onDidChangeViewState(({ webviewPanel }) => {
        if (webviewPanel.visible) void syncDashboardPanes(panel);
    });
    panel.webview.onDidReceiveMessage(async message => {
        if (dashboard !== panel) return;
        if (message?.action === "ready") {
            await syncDashboardPanes(panel);
            return;
        }
        const { DEVICE_NAMES } = require("./device-launcher");
        if (message?.action !== "start" || !Object.hasOwn(DEVICE_NAMES, message.device)
                || !Number.isSafeInteger(message.requestId)) return;
        try {
            const status = await recovery().restoreDevice(DEVICE_NAMES[message.device], message.stopped === true);
            if (dashboard === panel) {
                await panel.webview.postMessage({ type: "medtech-device-start-result", requestId: message.requestId, status });
            }
        } catch (error) {
            if (dashboard === panel) {
                await panel.webview.postMessage({ type: "medtech-device-start-result", requestId: message.requestId, status: "error" });
            }
            vscode.window.showErrorMessage(`Unable to start device: ${error.message}`);
        }
    });
    panel.webview.html = dashboardHtml(cloudTargetUrl(new URL("http://localhost:8090/")).origin);
}

async function syncDashboardPanes(panel) {
    for (const title of dashboardDevices.keys()) {
        if (dashboard !== panel) return;
        await updateDashboardPane(title);
    }
}

async function updateDashboardPane(title) {
    const device = dashboardDevices.get(title);
    if (dashboard && device) {
        await dashboard.webview.postMessage({ type: "medtech-pane", title, url: device.targetUrl.href, token: device.closeToken });
    }
}

function activate(context) {
    extensionContext = context;
    if (cloudWorkspace) {
        const controller = recovery();
        if (!controller.findRoot()) return;
        const { stateDirectory } = require("./device-launcher");
        tabStateDir = stateDirectory(controller.sourceRoot);
        controller.stateDir = tabStateDir;
        try {
            cloudTargetUrl(new URL("http://localhost:8090/"));
        } catch (error) {
            vscode.window.showErrorMessage(error.message);
            return;
        }
        vscode.commands.executeCommand?.("setContext", "rti.medtech.cloudDashboard", true);
    }
    recovery().startMonitoring();
    context.subscriptions.push({ dispose: () => recoveryView?.stop() });
    const uriHandler = {
        async handleUri(uri) {
            if (uri.path === "/session") {
                const controller = recovery();
                controller.secure = new URLSearchParams(uri.query).get("secure") === "1";
                controller.active = true;
                controller.startupDeadline = Date.now() + 15000;
                return;
            }
            if (uri.path === "/close" || uri.path === "/close-owned") {
                const parameters = new URLSearchParams(uri.query);
                const token = parameters.get("closeToken");
                if (uri.path === "/close-owned" && token === null) return;
                let title = parameters.get("title");
                if (cloudWorkspace) {
                    // A device exit must not close the dashboard or affect its siblings.
                    if (uri.path === "/close-owned" || token !== null || title) return;
                    recovery().stop();
                    dashboardDevices.clear();
                    dashboard?.dispose();
                    return;
                }
                if (token !== null) {
                    if (!/^[a-f0-9]{32}$/.test(token)) return;
                    const owned = [...appPanels].find(([, panel]) => panel.closeToken === token);
                    if (!owned) return;
                    title = owned[0];
                }
                if (title) {
                    const panel = appPanels.get(title);
                    if (panel) {
                        panel.closedByLauncher = true;
                        panel.dispose();
                    }
                } else {
                    recovery().stop();
                    for (const panel of demoPanels) {
                        panel.closedByLauncher = true;
                        panel.dispose();
                    }
                    demoPanels.clear();
                    appColumns.clear();
                }
                if (!demoPanels.size) {
                    demoGridCreated = false;
                    await restoreDemoGroups();
                }
                return;
            }

            if (uri.path !== "/open") {
                return;
            }

            const parameters = new URLSearchParams(uri.query);
            const requestedUrl = parameters.get("url");
            const requestedTitle = parameters.get("title");
            const requestedToken = parameters.get("closeToken");
            const closeToken = /^[a-f0-9]{32}$/.test(requestedToken || "") ? requestedToken : null;
            let targetUrl;

            try {
                targetUrl = new URL(requestedUrl);
            } catch {
                vscode.window.showErrorMessage("MedTech Web Tabs received an invalid URL.");
                return;
            }

            if (!isLocalHttpUrl(targetUrl)) {
                vscode.window.showErrorMessage(
                    "MedTech Web Tabs only opens HTTP URLs served from localhost."
                );
                return;
            }

            const title = requestedTitle || targetUrl.host;
            if (cloudWorkspace && (!Object.hasOwn(APP_VIEW_COLUMNS, title)
                    || targetUrl.port !== String(require("./device-launcher").PORTS[title]))) {
                vscode.window.showErrorMessage("MedTech Dashboard received an unexpected device or port.");
                return;
            }
            if (Object.hasOwn(APP_VIEW_COLUMNS, title)) {
                const controller = recovery();
                if (title === "Orchestrator") controller.active = true;
                controller.seenDevices.add(title);
                controller.pendingRestores.delete(title);
            }
            if (cloudWorkspace) {
                targetUrl = cloudTargetUrl(targetUrl);
                const previous = dashboardDevices.get(title);
                dashboardDevices.set(title, { targetUrl, closeToken: closeToken || previous?.closeToken || null });
                if (dashboard) {
                    await updateDashboardPane(title);
                } else if (!previous && dashboardDevices.size === 1) {
                    showDashboard();
                }
                return;
            }
            if (APP_VIEW_COLUMNS[title]) {
                await createDemoGrid();
            }
            const existingPanel = appPanels.get(title);
            if (existingPanel) {
                const restarted = closeToken && closeToken !== existingPanel.closeToken;
                if (closeToken) existingPanel.closeToken = closeToken;
                existingPanel.reveal(undefined, true);
                if (restarted || existingPanel.targetUrl.href !== targetUrl.href) {
                    existingPanel.targetUrl = targetUrl;
                    existingPanel.webview.html = webviewHtml(targetUrl, title);
                }
                return;
            }
            if (APP_VIEW_COLUMNS[title] && appColumns.has(title)) {
                if (!appPanels.has(title)) createAppPanel(title, targetUrl, closeToken, true);
            } else {
                createAppPanel(title, targetUrl, closeToken);
            }
        }
    };
    context.subscriptions.push(vscode.window.registerUriHandler(uriHandler));
    if (vscode.commands.registerCommand) {
        if (cloudWorkspace) {
            context.subscriptions.push(vscode.commands.registerCommand("rti.medtech.openDashboard", () => {
                if (!dashboardDevices.size) {
                    vscode.window.showErrorMessage("Launch the Digital Operating Room demo first.");
                    return;
                }
                showDashboard();
            }));
        }
        context.subscriptions.push(vscode.commands.registerCommand("rti.medtech.openOrchestrator", async () => {
            const controller = recovery();
            const status = await controller.restoreDevice("Orchestrator", !cloudWorkspace && !appPanels.has("Orchestrator"));
            if (status === "running") {
                await uriHandler.handleUri({ path: "/open", query: "title=Orchestrator&url=http%3A%2F%2Flocalhost%3A8090%2F" });
            } else if (status !== "starting") {
                vscode.window.showErrorMessage("Unable to open Orchestrator. Launch the Digital Operating Room demo first.");
                return;
            }
            if (cloudWorkspace) showDashboard();
        }));
    }
    if (cloudWorkspace) {
        const requests = path.join(tabStateDir, "requests");
        fs.mkdirSync(requests, { recursive: true });
        const owner = path.join(tabStateDir, "owner");
        const ready = path.join(tabStateDir, "ready");
        const claim = () => {
            fs.writeFileSync(owner, String(process.pid));
            const pending = `${ready}.${process.pid}.tmp`;
            fs.writeFileSync(pending, JSON.stringify({ pid: process.pid }));
            fs.renameSync(pending, ready);
        };
        recovery().claim = claim;
        claim();
        context.subscriptions.push({ dispose: () => {
            if (fs.existsSync(ready) && JSON.parse(fs.readFileSync(ready, "utf8")).pid === process.pid) {
                fs.unlinkSync(ready);
            }
        } });
        context.subscriptions.push(vscode.window.onDidChangeWindowState(state => {
            if (state.focused) claim();
        }));
        let busy = false;
        const timer = setInterval(async () => {
            if (busy) return;
            busy = true;
            try {
                for (const name of fs.readdirSync(requests).filter(name => name.endsWith(".json")).sort()) {
                    const file = path.join(requests, name);
                    const request = JSON.parse(fs.readFileSync(file, "utf8"));
                    if (request.targetHost !== undefined) {
                        if (request.targetHost !== String(process.pid)) continue;
                    } else if (fs.readFileSync(owner, "utf8") !== String(process.pid)) {
                        continue;
                    }
                    fs.unlinkSync(file);
                    const uri = new URL(request.uri);
                    if (uri.protocol !== "vscode:" || uri.hostname !== "rti.medtech-web-tabs") continue;
                    await uriHandler.handleUri({ path: uri.pathname, query: uri.search.slice(1) });
                }
            } catch (error) {
                vscode.window.showErrorMessage(`MedTech launcher: ${error.message}`);
            } finally {
                busy = false;
            }
        }, 200);
        context.subscriptions.push({ dispose: () => clearInterval(timer) });
    }
}

function webviewHtml(targetUrl, title) {
    const safeUrl = escapeHtml(targetUrl.toString());
    const bridge = title === "Orchestrator" ? `<script nonce="medtech-orchestrator">
const api = acquireVsCodeApi();
const frame = document.querySelector('iframe');
const origin = ${JSON.stringify(targetUrl.origin)};
frame.addEventListener('load', () => frame.contentWindow.postMessage({type: 'medtech-launcher-ready'}, origin));
window.addEventListener('message', event => {
    if (event.source === frame.contentWindow && event.origin === origin && event.data?.type === 'medtech-device-start') {
        api.postMessage({action: 'start', device: event.data.device, requestId: event.data.requestId, stopped: event.data.stopped === true});
    } else if (event.source !== frame.contentWindow && event.data?.type === 'medtech-device-start-result') {
        frame.contentWindow.postMessage(event.data, origin);
    }
});
</script>` : "";
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; frame-src ${targetUrl.origin}; style-src 'unsafe-inline'; script-src 'nonce-medtech-orchestrator';">
<title>${escapeHtml(title)}</title>
<style>html, body, iframe { border: 0; height: 100%; margin: 0; padding: 0; width: 100%; }</style>
</head>
<body><iframe src="${safeUrl}" title="${escapeHtml(title)}"></iframe>${bridge}</body>
</html>`;
}

function dashboardHtml(origin) {
    const panes = [
        ["ArmController", "Arm Controller"], ["Orchestrator", "Orchestrator"],
        ["Arm", "Arm"], ["PatientMonitor", "Patient Monitor"],
    ].map(([id, label]) => `<section><h2>${label}</h2><iframe id="${id}" title="${label}"></iframe></section>`).join("");
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; frame-src ${origin}; style-src 'unsafe-inline'; script-src 'nonce-medtech-dashboard';">
<title>Digital Operating Room</title>
<style>
html, body { height: 100%; margin: 0; padding: 0; }
main { box-sizing: border-box; height: 100%; display: grid; grid-template: repeat(2, minmax(0, 1fr)) / repeat(2, minmax(0, 1fr)); gap: 4px; padding: 4px; }
section { display: flex; flex-direction: column; min-width: 0; min-height: 0; border: 1px solid var(--vscode-panel-border); }
h2 { font-size: 12px; margin: 0; padding: 3px 6px; }
iframe { flex: 1; width: 100%; min-height: 0; border: 0; }
</style>
</head>
<body><main>${panes}</main>
<script nonce="medtech-dashboard">
const api = acquireVsCodeApi();
const origin = ${JSON.stringify(origin)};
const frames = new Map(Array.from(document.querySelectorAll('iframe'), frame => [frame.id, frame]));
const loaded = new Map();
const orchestrator = frames.get('Orchestrator');
orchestrator.addEventListener('load', () => orchestrator.contentWindow.postMessage({type: 'medtech-launcher-ready'}, origin));
window.addEventListener('message', event => {
    const data = event.data;
    if (event.source === orchestrator.contentWindow) {
        if (event.origin === origin && data?.type === 'medtech-device-start') {
            api.postMessage({action: 'start', device: data.device, requestId: data.requestId, stopped: data.stopped === true});
        }
        return;
    }
    // VS Code masks window.parent in webviews. Host messages come from the
    // webview's own origin; device messages come from the separate IDE origin.
    if (event.origin !== window.origin || [...frames.values()].some(frame => event.source === frame.contentWindow)) return;
    if (data?.type === 'medtech-device-start-result') {
        orchestrator.contentWindow.postMessage(data, origin);
    } else if (data?.type === 'medtech-pane' && frames.has(data.title)) {
        const url = new URL(data.url);
        const prior = loaded.get(data.title);
        if (url.origin !== origin || (prior?.url === url.href && prior.token === data.token)) return;
        loaded.set(data.title, {url: url.href, token: data.token});
        frames.get(data.title).src = url.href;
    }
});
api.postMessage({action: 'ready'});
</script></body></html>`;
}

async function deactivate() {
    await restoreDemoGroups();
    for (const title of appPanels.keys()) {
        fs.rmSync(tabStatePath(title), { force: true });
    }
}

module.exports = { activate, deactivate, cloudTargetUrl, webviewHtml, dashboardHtml };