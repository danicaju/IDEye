import * as vscode from 'vscode';
import { sendMessage, triggerEditorStateSync } from './extension';

export async function handleJumpToLine(msg: any) {
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

export async function handleAgenticPrompt(msg: any) {
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

export async function handleApplyLineFix(msg: any) {
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

export async function handleInsertSnippet(msg: any) {
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
        let snippetText = msg.snippet || '';
        const offsetLeft = Number(msg.cursorOffsetLeft || 0);
        const offsetUp = Number(msg.cursorOffsetUp || 0);

        if (!snippetText.includes('$0') && !snippetText.includes('$1') && (offsetLeft > 0 || offsetUp > 0)) {
            const lines = snippetText.split('\n');
            const targetLineIdx = lines.length - 1 - Math.max(0, offsetUp);
            if (targetLineIdx >= 0 && targetLineIdx < lines.length) {
                const targetLine = lines[targetLineIdx];
                const charIdx = Math.max(0, targetLine.length - Math.max(0, offsetLeft));
                lines[targetLineIdx] = targetLine.substring(0, charIdx) + '$0' + targetLine.substring(charIdx);
                snippetText = lines.join('\n');
            }
        }

        const doc = editor.document;
        const pos = editor.selection.active;
        const lineTextBefore = doc.lineAt(pos.line).text.substring(0, pos.character);
        const lineTextAfter = doc.lineAt(pos.line).text.substring(pos.character);
        const isIfSnippet = /^\s*(?:if|elif|while)\b/.test(snippetText);
        let replaceRange: vscode.Range | null = null;

        if (isIfSnippet) {
            const beforeParenMatch = lineTextBefore.match(/(?:if|elif|while)\s*\(\s*$/);
            const afterParenMatch = lineTextAfter.match(/^\s*\)/);
            if (beforeParenMatch && afterParenMatch) {
                // cursor inside if (|)
                const startChar = pos.character - beforeParenMatch[0].length;
                const endChar = pos.character + afterParenMatch[0].length;
                replaceRange = new vscode.Range(new vscode.Position(pos.line, startChar), new vscode.Position(pos.line, endChar));
            } else {
                const beforeFullMatch = lineTextBefore.match(/(?:if|elif|while)\s*(?:\(\s*\)|\(\s*)$/);
                if (beforeFullMatch) {
                    const startChar = pos.character - beforeFullMatch[0].length;
                    replaceRange = new vscode.Range(new vscode.Position(pos.line, startChar), pos);
                }
            }
        }

        const snippetString = new vscode.SnippetString(snippetText);
        const success = replaceRange
            ? await editor.insertSnippet(snippetString, replaceRange)
            : await editor.insertSnippet(snippetString);

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

export async function handleExecuteCommand(msg: any) {
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
