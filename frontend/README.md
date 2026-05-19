# ChatBI 前端（Vue 3）

## 技术栈

- Vue 3 + TypeScript + Vite
- Pinia（状态管理）
- Element Plus（UI 组件库）
- Vue Router（问数首页 / 语料管理分页）
- Plotly.js（图表）

## 页面

| 路径 | 说明 |
|------|------|
| `/` | 智能问数（参考经营分析助手布局：居中输入、实例问题、数据表选择） |
| `/training` | 语料训练维护（管理员使用） |

## 开发

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://127.0.0.1:5173（Vite 已将 `/api` 代理到 Flask `http://127.0.0.1:5000`）。

另开终端启动后端：

```bash
python run.py
```

## 生产构建（由 Flask 托管静态资源）

```bash
cd frontend
npm run build
```

产物输出到 `backend/static/dist/`，然后：

```bash
python run.py
```

访问 http://127.0.0.1:5000
