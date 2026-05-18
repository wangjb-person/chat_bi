from pathlib import Path

path = Path(__file__).resolve().parent.parent / "backend/templates/index.html"
text = path.read_text(encoding="utf-8")
text = text.replace("html += '</motion>';", "html += '</motion>';")
text = text.replace("html += '</motion>';", "html += '</div>';")

old = """                if (data.error) {
                    addMessage('assistant', `❌ SQL执行失败: ${data.error}`);
                    return;
                }

                // 显示结果区域
                const resultContainer = document.createElement('motion');
                resultContainer.className = 'message assistant';

                let html = '<div class="message-content">';

                // 显示结果统计
                if (data.data && data.data.length > 0) {
                    html += `<div class="result-badge"><span class="icon">📊</span> 查询成功，共 ${data.row_count} 条记录</div>`;
                    html += displayDataHtml(data);
                } else {
                    html += '<div class="result-badge"><span class="icon">📭</span> 查询结果为空</div>';
                }

                html += '</motion>';
                resultContainer.innerHTML = html;
                messagesDiv.appendChild(resultContainer);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;

                // 生成图表
                if (data.data && data.data.length > 0) {
                    await generatePlot(id);
                    await generateFollowup(id);
                }"""

new = """                if (data.error) {
                    addMessage('assistant', `❌ SQL执行失败: ${data.error}`);
                    return;
                }

                await displayQueryResult(id, data);"""

if old in text:
    text = text.replace(old, new)
else:
    # fallback: only duplicate block in executeSqlWithStatus
    marker = "// 回退：单独 POST /api/run_sql"
    idx = text.find(marker)
    chunk = text[idx:]
    if "// 显示结果区域" in chunk:
        start = text.find("// 显示结果区域", idx)
        end = text.find("// 生成图表", start)
        end = text.find("await generateFollowup(id);", end) + len("await generateFollowup(id);")
        text = text[:start] + "await displayQueryResult(id, data);" + text[end:]

text = text.replace(
    "body: JSON.stringify({ id, sql }),\n                    signal: controller.signal,\n                });",
    "body: JSON.stringify({ id, sql }),\n                    signal: controller.signal,\n                    cache: 'no-store',\n                });",
    1,
)
path.write_text(text, encoding="utf-8")
print("fixed", path)
