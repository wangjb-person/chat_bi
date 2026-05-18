# -*- coding: utf-8 -*-
"""Restore index.html from git and apply SSE inline SQL result patch."""
import subprocess
from pathlib import Path

TAG = "d" + "iv"

repo = Path(__file__).resolve().parent.parent
path = repo / "backend/templates/index.html"

text = subprocess.check_output(
    ["git", "show", "HEAD:app/templates/index.html"],
    cwd=repo,
).decode("utf-8")

text = text.replace(
    "请先在终端运行 python app.py",
    "请先在项目根目录运行 python run.py",
)
text = text.replace(
    "let pendingRun = null;",
    "let pendingRun = null;\n            let inlineQueryResult = null;",
)

text = text.replace(
    """                            if (data.done) {
                                currentMessageId = data.id;
                                const sqlToRun = (data.sql && String(data.sql).trim()) || fullSql.trim();
                                if (assistantMessageDiv && sqlToRun) {
                                    updateAssistantMessage(assistantMessageDiv, sqlToRun);
                                }
                                if (sqlToRun) {
                                    pendingRun = { id: data.id, sql: sqlToRun };
                                }
                                streamDone = true;
                                break streamLoop;""",
    """                            if (data.done) {
                                currentMessageId = data.id;
                                const sqlToRun = (data.sql && String(data.sql).trim()) || fullSql.trim();
                                if (assistantMessageDiv && sqlToRun) {
                                    updateAssistantMessage(assistantMessageDiv, sqlToRun);
                                }
                                if (data.run_error) {
                                    inlineQueryResult = { error: data.run_error };
                                } else if (data.query_result) {
                                    inlineQueryResult = {
                                        id: data.id,
                                        result: data.query_result,
                                    };
                                } else if (sqlToRun) {
                                    pendingRun = { id: data.id, sql: sqlToRun };
                                }
                                streamDone = true;
                                break streamLoop;""",
)

text = text.replace(
    """                // 必须先释放 SSE 连接，否则浏览器会卡住后续的 /api/run_sql（HTTP/1.1 连接复用）
                try {
                    await reader.cancel();
                } catch (_) { /* ignore */ }

                if (pendingRun) {
                    console.log('[chatbi] SSE 已结束，开始执行 SQL');
                    await executeSqlWithStatus(pendingRun.id, pendingRun.sql);
                }""",
    """                try {
                    await reader.cancel();
                } catch (_) { /* ignore */ }

                if (inlineQueryResult) {
                    if (inlineQueryResult.error) {
                        addMessage('assistant', `❌ SQL执行失败: ${inlineQueryResult.error}`);
                    } else {
                        console.log('[chatbi] 使用 SSE 内联查询结果');
                        await displayQueryResult(
                            inlineQueryResult.id,
                            inlineQueryResult.result
                        );
                    }
                } else if (pendingRun) {
                    console.log('[chatbi] SSE 已结束，回退调用 /api/run_sql');
                    await new Promise(r => setTimeout(r, 300));
                    await executeSqlWithStatus(pendingRun.id, pendingRun.sql);
                }""",
)

display_fn = f"""
        // 展示查询结果（SSE 内联结果与 /api/run_sql 共用）
        async function displayQueryResult(id, data) {{
            const messagesDiv = document.getElementById('messages');
            const resultContainer = document.createElement('{TAG}');
            resultContainer.className = 'message assistant';

            let html = '<{TAG} class="message-content">';
            if (data.data && data.data.length > 0) {{
                html += `<{TAG} class="result-badge"><span class="icon">📊</span> 查询成功，共 ${{data.row_count}} 条记录</{TAG}>`;
                html += displayDataHtml(data);
            }} else {{
                html += '<{TAG} class="result-badge"><span class="icon">📭</span> 查询结果为空</{TAG}>';
            }}
            html += '</{TAG}>';
            resultContainer.innerHTML = html;
            messagesDiv.appendChild(resultContainer);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;

            if (data.data && data.data.length > 0) {{
                await generatePlot(id);
                await generateFollowup(id);
            }}
        }}

"""

text = text.replace(
    "        // 执行 SQL 并显示状态\n        async function executeSqlWithStatus",
    display_fn + "        // 回退：单独 POST /api/run_sql\n        async function executeSqlWithStatus",
)

marker_start = "                if (data.error) {\n                    addMessage('assistant', `❌ SQL执行失败: ${data.error}`);"
marker_end = "                    await generateFollowup(id);\n                }"
start = text.find(marker_start)
end = text.find(marker_end, start)
if start == -1 or end == -1:
    raise SystemExit("could not locate executeSqlWithStatus result block in git template")
end += len(marker_end)
old_result = text[start:end]
new_result = """                if (data.error) {
                    addMessage('assistant', `❌ SQL执行失败: ${data.error}`);
                    return;
                }

                await displayQueryResult(id, data);"""
text = text[:start] + new_result + text[end:]

text = text.replace(
    "body: JSON.stringify({ id, sql }),\n                    signal: controller.signal,\n                });",
    "body: JSON.stringify({ id, sql }),\n                    signal: controller.signal,\n                    cache: 'no-store',\n                });",
    1,
)

if "displayQueryResult" not in text or "inlineQueryResult" not in text:
    raise SystemExit("patch incomplete")
if "<motion " in text or "createElement('motion')" in text:
    raise SystemExit("refusing to write: invalid motion tags")

path.write_text(text, encoding="utf-8")
print("OK", path)
