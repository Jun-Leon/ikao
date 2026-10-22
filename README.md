# ikao 刷题平台

一个**纯离线、单机可用**的本地刷题工具。题库导入、刷题练习、错题本、收藏夹、统计看板全部在本地完成，**无需登录、无需联网**，数据只保存在你自己的电脑上。

- 后端：Python 3.10+ / FastAPI / SQLAlchemy 2 / SQLite（WAL）
- 前端：Vue 3 / Vite / Element Plus / Pinia / ECharts / KaTeX
- 打包：PyInstaller `onedir`（免安装绿色版，双击即用）

---

## 功能特性

| 模块 | 说明 |
| --- | --- |
| 题库导入 | 支持 **JSON / CSV / Excel(.xlsx)** 三种格式；可下载 Excel 模板填写后上传；导入时自动按题干相似度**去重** |
| 题库导出 | 按当前筛选条件导出 **CSV**（带 UTF-8 BOM，Excel 双击不乱码；列格式与导入模板一致，可直接回导） |
| 题库管理 | 题目检索、新增 / 编辑 / 删除、导入日志与逐条明细 |
| 刷题模式 | 顺序练题、背题模式、随机练习、错题重做、我的收藏（切换模式即时刷新题目） |
| 背题模式 | 直接下发答案与解析，只读高亮，不计入统计 |
| 错题本 / 收藏夹 | 自动收录答错的题，支持收藏与移出 |
| 统计看板 | 正确率、题型 / 模式分布、练习趋势、高频错题 |
| 本地档案 | 多档案（Profile）切换，不同人 / 不同用途的作答数据相互隔离 |
| 公式渲染 | 题干、选项、答案、解析均支持 LaTeX，前端 KaTeX 渲染 |

> 抽题接口在普通模式下**不下发正确答案与解析**，判分在服务端完成。

---

## 目录结构

```
.
├── server/                 # 后端（FastAPI）
│   ├── app/
│   │   ├── routers/        # 路由：meta / questions / import / practice / profiles / stats
│   │   ├── services/       # 业务逻辑
│   │   ├── utils/          # JSON/CSV/Excel 解析、去重、文本归一化
│   │   ├── config.py       # 全局配置（环境变量前缀 IKAO_）
│   │   ├── models.py       # ORM 模型
│   │   └── main.py         # 应用入口
│   └── requirements.txt
├── web/                    # 前端（Vue 3 + Vite）
│   └── src/
├── packaging/              # 打包：launcher.py 启动器 + ikao.spec
├── scripts/                # dev.bat 开发启动、build_portable.ps1 一键打包、full_flow_test.py 全流程测试
├── docs/                   # 题库格式说明 / 打包说明 / 安装指导书
└── data/                   # 数据目录（SQLite 库、示例题库）
```

---

## 快速开始（开发模式）

### 1. 后端

```bash
cd server
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8010
```

后端默认监听 `http://127.0.0.1:8010`，接口文档见 `http://127.0.0.1:8010/docs`。

### 2. 前端

```bash
cd web
npm install
npm run dev
```

前端开发服务器默认 `http://127.0.0.1:5173`，已通过代理指向后端 8010。

> Windows 用户也可直接双击 `scripts\dev.bat` 一键启动前后端。

---

## 打包为免安装绿色版

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_portable.ps1
```

产物在 `release/ikao-1.0/`，双击 `ikao.exe` 即可运行（会自动挑选可用端口并打开浏览器）。
详细说明见 [docs/打包说明.md](docs/打包说明.md)，面最终用户的说明见 [docs/安装指导书.md](docs/安装指导书.md)。

---

## 题库导入

进入「题库 → 导入」：

1. 点「下载 Excel 模板」，按表头填写题目；
2. 上传 `.xlsx`（或 `.csv` / `.json`）；
3. 可调整去重阈值（默认 `0.90`），导入完成后查看导入日志明细。

表格列定义与字段容错规则见 [docs/题库格式说明.md](docs/题库格式说明.md)。

---

## 测试

```bash
python scripts/full_flow_test.py     # 全流程端到端测试（使用临时数据库，不影响正式数据）
python scripts/healthcheck.py        # 对运行中的后端做接口体检
```

---

## 配置

后端配置通过环境变量覆盖，前缀为 `IKAO_`（也可放在项目根目录的 `.env` 中）。
可用项参考 [.env.example](.env.example)，常用：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `IKAO_PORT` | `8010` | 打包版监听端口（被占用会自动向后探测） |
| `IKAO_DEDUP_THRESHOLD` | `0.90` | 导入去重相似度阈值 |
| `IKAO_MAX_IMPORT_QUESTIONS` | `20000` | 单次导入题目数上限 |
| `IKAO_DATA_DIR` | `data/` | 数据目录 |
| `IKAO_DATABASE_URL` | 空（用 SQLite） | 自定义数据库连接串 |

---

## 许可

本项目基于 [MIT License](LICENSE) 开源。
