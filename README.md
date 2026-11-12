# 拾记 · 个人记忆与生活接续

一个本地运行的研究原型：留下生活记录，理解后来的变化，接续被打断的活动，再通过原话与照片找回经历。

当前版本为 **v0.1 工程原型**，采用透明规则与人工导入模型回复，尚未证明真实用户收益或原创算法优势，不是医疗产品。

## 已有功能

- 按活动保存文字、照片、来源和时间；保留原始记录与更正历史。
- 区分原说法更正与后来发生的变化，支持撤回和依据回查。
- 展示当前有效记录、关键词查找及真实回忆线索。
- 将系统帮助、用户反馈和后续观察分别保存。
- 暂停帮助、删除活动、导出 JSON，以及包含照片的 ZIP 备份与恢复。
- 手动复制实验材料到自己的 GPT，再导入回复、提示和引用，不自动调用付费 API。
- 内置完整生活流程、三条研究候选、12 个构造案例和对照记录模板。

## 本地安装

需要 Python 3.12、Node.js 22.12+ 或 24。本项目首先在 Windows 上验证。

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
npm ci --ignore-scripts
npm run build
```

双击 `启动拾记.cmd`，或运行：

```powershell
.venv\Scripts\python.exe run.py
```

打开 `http://127.0.0.1:8765`。默认仅本机可访问；真实手机跨设备访问尚未实现。
首次使用可新建活动或加载明确标注的人工构造示例。不需要模型密钥。

## 数据与预算

记录默认存于 `data/`，照片也保存在本机。它们和 `.env`、备份、运行日志均不应提交到 GitHub。
撤回保留历史；彻底删除使用“更多 → 删除整个活动”。已导出的备份需自行管理。
当前没有应用内账号隔离或存储加密。上传材料到 GPT 前需自行确认授权；本程序不读取私人聊天和账号。

当前没有自动模型调用，因此不会产生 API 调用费用；GPT 订阅和 API 权益各自按官方规则使用。

## 开发与验证

技术栈：React + TypeScript + Vite；Python + FastAPI + SQLite。

```powershell
.venv\Scripts\python.exe -m pytest tests -q
npm run build
```

浏览器测试使用 Playwright 与系统 Edge。另开终端，用隔离目录启动服务：

```powershell
.venv\Scripts\python.exe run.py --data-dir test-results/browser-new-run
```

让 `PLAYWRIGHT_MODULE` 指向已有 Playwright 安装后，运行 `node tests/browser.cjs`。
脚本会创建构造活动，请勿对正式数据目录执行。测试图片位于 `tests/fixtures/photo.png`，为人工单色图片。

2026-11-13 本地验证：16 项后端测试通过；生产构建、Edge 完整流程与启动自检通过。
桌面与手机视口检查不等于真实手机、患者试用或临床验证。

## 研究怎么继续

先用一次真实且获授权的生活活动，对照熟悉的备忘录、相册、日历和普通 LLM，记录使用负担与具体失败。
产品保留完整体验，研究候选暂不预定赢家：为未来保留什么、怎样提供适合的帮助、帮助之后怎样更新。

- [完整生活流程](research/生活流程.svg)
- [执行与评价说明](research/执行与评价说明.txt)
- [对照记录模板](research/对照记录.csv)
- [案例与研究卡](research/startup.json)
- [备份、恢复及完整使用说明](README.txt)

案例均为人工构造；真实访谈、连续试用、直接竞争方法实验和论文结论尚未完成。

## 许可证

目前尚未指定开源许可证。
