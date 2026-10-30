import * as vscode from 'vscode';

let wsClient: WebSocket | null = null;
let statusBarItem: vscode.StatusBarItem;
let reconnectTimer: NodeJS.Timeout | null = null;
let syncThrottleTimer: NodeJS.Timeout | null = null;
let isDeactivated = false;

export function activate(context: vscode.ExtensionContext) {
    console.log('[IDEye-Bridge] Extensión activada.');

    // 1. Create Status Bar Item
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'ideye.status';
    updateStatusBar(false, 'Iniciando...');
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);

    // 2. Register Commands
    context.subscriptions.push(
        vscode.commands.registerCommand('ideye.connect', () => {
            connectWebSocket();
        }),
        vscode.commands.registerCommand('ideye.disconnect', () => {
            disconnectWebSocket();
            vscode.window.showInformationMessage('IDEye: Desconectado del motor de mirada.');
        }),
        vscode.commands.registerCommand('ideye.reconnect', () => {
            disconnectWebSocket();
            connectWebSocket();
        }),
        vscode.commands.registerCommand('ideye.status', () => {
            const isConnected = wsClient && wsClient.readyState === WebSocket.OPEN;
            const config = vscode.workspace.getConfiguration('ideye');
            const host = config.get<string>('websocketHost', '127.0.0.1');
            const port = config.get<number>('websocketPort', 54321);

            if (isConnected) {
                vscode.window.showInformationMessage(
                    `IDEye: Conectado al motor Look-To-Code en ws://${host}:${port}`,
                    'Desconectar',
                    'Reconectar'
                ).then(selection => {
                    if (selection === 'Desconectar') disconnectWebSocket();
                    if (selection === 'Reconectar') vscode.commands.executeCommand('ideye.reconnect');
                });
            } else {
                vscode.window.showWarningMessage(
                    `IDEye: Desconectado del motor en ws://${host}:${port}`,
                    'Conectar ahora'
                ).then(selection => {
                    if (selection === 'Conectar ahora') connectWebSocket();
                });
            }
        })
    );

    // 3. Register Editor Event Listeners
    context.subscriptions.push(
        vscode.window.onDidChangeActiveTextEditor(() => {
            triggerEditorStateSync(50);
        }),
        vscode.window.onDidChangeTextEditorSelection(() => {
            triggerEditorStateSync(80);
        }),
        vscode.workspace.onDidChangeTextDocument((e) => {
            const activeEditor = vscode.window.activeTextEditor;
            if (activeEditor && e.document === activeEditor.document) {
                triggerEditorStateSync(120);
            }
        }),
        vscode.languages.onDidChangeDiagnostics(() => {
            triggerEditorStateSync(100);
        })
    );

    // 4. Initial Connection
    const autoConnect = vscode.workspace.getConfiguration('ideye').get<boolean>('autoConnect', true);
    if (autoConnect) {
        connectWebSocket();
    }
}

export function deactivate() {
    isDeactivated = true;
    disconnectWebSocket();
}

function updateStatusBar(connected: boolean, details?: string) {
    if (!statusBarItem) return;
    if (connected) {
        statusBarItem.text = '$(eye) IDEye: Conectado';
        statusBarItem.tooltip = `IDEye Look-To-Code activo ${details ? `(${details})` : ''}`;
        statusBarItem.backgroundColor = undefined;
    } else {
        statusBarItem.text = '$(eye-closed) IDEye: Desconectado';
        statusBarItem.tooltip = details || 'Haz clic para conectar con el motor IDEye';
        statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
    }
}

function connectWebSocket() {
    if (isDeactivated) return;
    if (wsClient && (wsClient.readyState === WebSocket.OPEN || wsClient.readyState === WebSocket.CONNECTING)) {
        return;
    }

    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }

    const config = vscode.workspace.getConfiguration('ideye');
    const host = config.get<string>('websocketHost', '127.0.0.1');
    const port = config.get<number>('websocketPort', 54321);
    const url = `ws://${host}:${port}`;

    updateStatusBar(false, 'Conectando...');

    try {
        wsClient = new WebSocket(url);

        wsClient.onopen = () => {
            console.log(`[IDEye-Bridge] Conectado exitosamente a ${url}`);
            updateStatusBar(true);
            sendEditorState();
        };

        wsClient.onmessage = (event) => {
            handleInboundMessage(event.data);
        };

        wsClient.onclose = () => {
            console.log('[IDEye-Bridge] Conexión cerrada.');
            updateStatusBar(false, 'Conexión cerrada');
            scheduleReconnect();
        };

        wsClient.onerror = () => {
            updateStatusBar(false, 'Error de conexión');
        };
    } catch (err) {
        console.warn(`[IDEye-Bridge] No se pudo crear WebSocket: ${err}`);
        updateStatusBar(false, 'Error al inicializar');
        scheduleReconnect();
    }
}

function disconnectWebSocket() {
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }
    if (wsClient) {
        try {
            wsClient.close();
        } catch (e) {
            // ignore
        }
        wsClient = null;
    }
    updateStatusBar(false, 'Desconectado manualmente');
}

function scheduleReconnect() {
    if (isDeactivated) return;
    if (reconnectTimer) return;

    reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        if (!isDeactivated) {
            connectWebSocket();
        }
    }, 2500);
}

function triggerEditorStateSync(delayMs: number = 80) {
    if (syncThrottleTimer) {
        clearTimeout(syncThrottleTimer);
    }
    syncThrottleTimer = setTimeout(() => {
        syncThrottleTimer = null;
        sendEditorState();
    }, delayMs);
}

function collectLocalSymbols(doc: vscode.TextDocument, currentLine: number): string[] {
    const symbols: string[] = [];
    const start = Math.max(0, currentLine - 40);
    const end = Math.min(doc.lineCount - 1, currentLine + 5);
    const text = [];
    for (let line = start; line <= end; line++) {
        text.push(doc.lineAt(line).text);
    }
    const pattern = /\b(?:def|class|function|const|let|var|fn|func)\s+([A-Za-z_]\w*)/g;
    for (const match of text.join('\n').matchAll(pattern)) {
        if (!symbols.includes(match[1])) symbols.push(match[1]);
    }
    return symbols.slice(0, 12);
}

function sendEditorState() {
    if (!wsClient || wsClient.readyState !== WebSocket.OPEN) return;

    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        const payload = {
            type: 'EDITOR_STATE',
            hasActiveEditor: false,
            filePath: null,
            languageId: null,
            cursor: null,
            lineText: '',
            surroundingLines: [],
            diagnostics: [],
            workspaceRoot: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || null
        };
        sendMessage(payload);
        return;
    }

    const doc = editor.document;
    const pos = editor.selection.active;
    const currentLine = doc.lineAt(pos.line).text;
    const selectedText = doc.getText(editor.selection);

    const config = vscode.workspace.getConfiguration('ideye');
    const maxSurrounding = config.get<number>('syncSurroundingLines', 40);
    const startLine = Math.max(0, pos.line - Math.floor(maxSurrounding / 2));
    const endLine = Math.min(doc.lineCount - 1, startLine + maxSurrounding);

    const surrounding: string[] = [];
    for (let l = startLine; l <= endLine; l++) {
        surrounding.push(doc.lineAt(l).text);
    }
    const prefixLines: string[] = [];
    for (let l = Math.max(0, pos.line - 40); l < pos.line; l++) {
        prefixLines.push(doc.lineAt(l).text);
    }
    const suffixLines: string[] = [];
    for (let l = pos.line + 1; l <= Math.min(doc.lineCount - 1, pos.line + 15); l++) {
        suffixLines.push(doc.lineAt(l).text);
    }

    const payload = {
        type: 'EDITOR_STATE',
        hasActiveEditor: true,
        filePath: doc.fileName,
        languageId: doc.languageId,
        cursor: {
            line: pos.line,
            character: pos.character
        },
        selection: selectedText,
        active_selection: selectedText,
        lineText: currentLine,
        current_line: currentLine,
        prefix_lines: prefixLines,
        suffix_lines: suffixLines,
        surroundingLines: surrounding,
        local_symbols: collectLocalSymbols(doc, pos.line),
        diagnostics: collectDiagnostics(doc, pos.line),
        workspaceRoot: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || null
    };

    sendMessage(payload);
}

function sendMessage(payload: any) {
    if (wsClient && wsClient.readyState === WebSocket.OPEN) {
        try {
            wsClient.send(JSON.stringify(payload));
        } catch (e) {
            console.error('[IDEye-Bridge] Error enviando mensaje:', e);
        }
    }
}

async function handleInboundMessage(rawData: any) {
    try {
        const text = typeof rawData === 'string' ? rawData : rawData.toString();
        const msg = JSON.parse(text);

        if (msg.type === 'INSERT_SNIPPET') {
            await handleInsertSnippet(msg);
        } else if (msg.type === 'EXECUTE_COMMAND') {
            await handleExecuteCommand(msg);
        } else if (msg.type === 'apply_line_fix') {
            await handleApplyLineFix(msg);
        } else if (msg.type === 'jump_to_line') {
            await handleJumpToLine(msg);
        } else if (msg.type === 'trigger_agent_prompt') {
            await handleAgenticPrompt(msg);
        } else if (msg.type === 'PING') {
            sendMessage({ type: 'PONG', timestamp: Date.now() });
        }
    } catch (err) {
        console.error('[IDEye-Bridge] Error procesando mensaje entrante:', err);
    }
}

function collectDiagnostics(doc: vscode.TextDocument, currentLine: number): any[] {
    const diagnostics = vscode.languages.getDiagnostics(doc.uri)
        .filter(d => d.severity === vscode.DiagnosticSeverity.Error || d.severity === vscode.DiagnosticSeverity.Warning)
        .map(d => ({
            line: d.range.start.line + 1,
            severity: d.severity === vscode.DiagnosticSeverity.Error ? 'error' : 'warning',
            message: d.message,
            source: d.source || 'vscode',
            code_line: doc.lineAt(Math.min(d.range.start.line, doc.lineCount - 1)).text,
            distance: Math.abs(d.range.start.line - currentLine)
        }))
        .sort((a, b) => (a.distance - b.distance) || (a.line - b.line));
    return diagnostics.slice(0, 12).map(({ distance, ...rest }) => rest);
}

async function handleJumpToLine(msg: any) {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        sendMessage({ type: 'ACK', action: 'jump_to_line', success: false, error: 'No active editor' });
        return;
    }
    try {
        const doc = editor.document;
        const line = Math.max(0, Math.min(doc.lineCount - 1, Number(msg.line || 1) - 1));
        const position = new vscode.Position(line, 0);
        const range = new vscode.Range(position, doc.lineAt(line).range.end);
        editor.selection = new vscode.Selection(position, position);
        editor.revealRange(range, vscode.TextEditorRevealType.InCenter);
        sendMessage({ type: 'ACK', action: 'jump_to_line', success: true, line: line + 1 });
        triggerEditorStateSync(50);
    } catch (e: any) {
        sendMessage({ type: 'ACK', action: 'jump_to_line', success: false, error: e.message || String(e) });
    }
}

async function handleAgenticPrompt(msg: any) {
    const prompt = String(msg.prompt || '');
    const actionId = String(msg.action_id || 'agentic');
    if (!prompt.trim()) {
        sendMessage({ type: 'ACK', action: 'trigger_agent_prompt', success: false, error: 'Empty prompt' });
        return;
    }

    // Prefer the native chat panel. Command signatures changed across VS Code
    // releases, so try the structured object first and then the legacy string.
    try {
        await vscode.commands.executeCommand('workbench.action.chat.open', {
            query: prompt,
            isPartialQuery: false
        });
        sendMessage({ type: 'ACK', action: 'trigger_agent_prompt', success: true, mode: 'chat', action_id: actionId });
        return;
    } catch (chatError) {
        // Continue to inline chat fallback.
    }

    try {
        await vscode.commands.executeCommand('workbench.action.chat.open', prompt);
        sendMessage({ type: 'ACK', action: 'trigger_agent_prompt', success: true, mode: 'chat', action_id: actionId });
        return;
    } catch (legacyChatError) {
        // Continue to inline chat fallback.
    }

    try {
        await vscode.commands.executeCommand('inlineChat.start');
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            await editor.edit((builder) => {
                builder.insert(editor.selection.active, prompt);
            });
        }
        sendMessage({ type: 'ACK', action: 'trigger_agent_prompt', success: true, mode: 'inline', action_id: actionId });
        return;
    } catch (inlineError) {
        // Final fallback: clipboard plus direct insertion for the active editor.
    }

    try {
        await vscode.env.clipboard.writeText(prompt);
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            await editor.edit((builder) => {
                builder.insert(editor.selection.active, prompt);
            });
        }
        sendMessage({ type: 'ACK', action: 'trigger_agent_prompt', success: true, mode: 'clipboard', action_id: actionId });
    } catch (e: any) {
        sendMessage({ type: 'ACK', action: 'trigger_agent_prompt', success: false, error: e.message || String(e) });
    }
}

async function handleApplyLineFix(msg: any) {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        sendMessage({ type: 'ACK', action: 'apply_line_fix', success: false, error: 'No active editor' });
        return;
    }
    try {
        const doc = editor.document;
        const line = Math.max(0, Math.min(doc.lineCount - 1, Number(msg.line || 1) - 1));
        const replacement = String(msg.replacement || '');
        const edit = new vscode.WorkspaceEdit();
        if (msg.insert) {
            edit.insert(doc.uri, new vscode.Position(line, 0), replacement + '\n');
        } else {
            const target = doc.lineAt(line).range;
            edit.replace(doc.uri, target, replacement);
        }
        const success = await vscode.workspace.applyEdit(edit);
        sendMessage({ type: 'ACK', action: 'apply_line_fix', success, line: line + 1 });
        triggerEditorStateSync(60);
    } catch (e: any) {
        sendMessage({ type: 'ACK', action: 'apply_line_fix', success: false, error: e.message || String(e) });
    }
}

async function handleInsertSnippet(msg: any) {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        sendMessage({
            type: 'ACK',
            action: 'INSERT_SNIPPET',
            success: false,
            error: 'No active text editor in VS Code'
        });
        return;
    }

    try {
        const snippetText = msg.snippet || '';
        const snippetString = new vscode.SnippetString(snippetText);
        const success = await editor.insertSnippet(snippetString);

        sendMessage({
            type: 'ACK',
            action: 'INSERT_SNIPPET',
            success: success,
            snippet: snippetText.substring(0, 30)
        });

        // Trigger synchronization after injection
        triggerEditorStateSync(50);
    } catch (e: any) {
        sendMessage({
            type: 'ACK',
            action: 'INSERT_SNIPPET',
            success: false,
            error: e.message || String(e)
        });
    }
}

async function handleExecuteCommand(msg: any) {
    try {
        const command = msg.command;
        const args = msg.args || [];
        if (args.length > 0) {
            await vscode.commands.executeCommand(command, ...args);
        } else {
            await vscode.commands.executeCommand(command);
        }

        sendMessage({
            type: 'ACK',
            action: 'EXECUTE_COMMAND',
            command: command,
            success: true
        });

        triggerEditorStateSync(50);
    } catch (e: any) {
        sendMessage({
            type: 'ACK',
            action: 'EXECUTE_COMMAND',
            command: msg.command,
            success: false,
            error: e.message || String(e)
        });
    }
}
