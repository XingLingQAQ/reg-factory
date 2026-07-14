# Reg Factory Codex K12

`codex_k12` 是 reg-factory 的独立 Codex/K12 运营控制台。它管理邮箱资产、授权工作区任务、Codex 凭据写出、Sub2API 入库、AT 测活与修复，同时复用主仓库已有的邮箱池。

本项目参考 [lxh77721/k12-reg](https://github.com/lxh77721/k12-reg) 开发。上游 MIT 许可证保留在 `LICENSE`，具体来源版本和本地改动边界见 `NOTICE`。

仅可连接你拥有或已获明确授权的 K12 workspace、邮箱和下游服务。项目不提供默认 workspace ID、默认代理或通用账号密码。

## 当前能力

- 邮箱池：批量导入、状态管理、母邮箱拆分、手动或自动 OTP。
- 主仓库同步：识别上级 `emails.txt`，转换 reg-factory 的四段格式并增量入池。
- K12 任务：任务队列、并发、取消、重试、日志和 workspace 结果。
- Codex / Sub2API：OAuth/noRT 入库、账号 JSON 写出、AT 测活与修复。
- 运营能力：自动补号、失败清理、数据包导入导出、租户数据隔离。
- 安全默认：仅监听 `127.0.0.1`；workspace、密码和代理均需显式配置；API 返回配置时会清空密钥原文。

## 环境

- Node.js 20+
- npm 10+
- Edge 或 Chrome，用于浏览器流程和 UI 验证

## 启动

推荐在仓库根目录双击 `start.bat`，然后从主面板左侧进入“Codex K12”。主 WebUI 会自动启动并内嵌本服务，关闭主 WebUI 时也会回收由它启动的 K12 子进程。

需要独立运行时，可双击 `start_k12.bat`，或执行：

```powershell
cd codex_k12
npm install
npm run build
npm start
```

生产控制台地址：`http://127.0.0.1:8806/`

主面板集成地址：`http://127.0.0.1:8799/`

开发模式使用两个端口：

```powershell
npm run dev
```

- Vite 前端：`http://127.0.0.1:5184/`
- API：`http://127.0.0.1:8806/`

## 首次配置

1. 打开控制台设置，填写你有权使用的 K12 Workspace ID。
2. 设置 OpenAI 网络出口；本机直连可填写 `direct`。
3. 使用动态邮箱创建新账号时，设置独立的强密码。
4. 按需配置邮箱 API、Sub2API、输出格式和补号策略。
5. 点击“同步邮箱池”读取主仓库 `emails.txt`，或在控制台手动导入。

主仓库邮箱同步要求先配置“邮箱 API 地址”。同步过程只读取 `../emails.txt`，不会改写主仓库文件。

## 数据边界

运行数据默认写入 `codex_k12/data/`，JSON 凭据写入 `codex_k12/json/`。浏览器租户 ID 通过 `X-K12-Tenant-Id` 发送，后端按租户隔离配置、邮箱、任务和输出：

```text
data/
data/tenants/<tenant-id>/
json/
config.json
pool_tokens.txt
```

这些路径均已加入 `.gitignore`。不要提交真实密码、API Key、refresh token、access token、cookie 或账号 JSON。

可复制 `.env.example` 为 `.env` 覆盖监听地址和端口。保持 `HOST=127.0.0.1` 可避免把无登录保护的本地控制台暴露到局域网或公网。

## 验证

```powershell
npm run build
npm run verify:ui
```

`verify:ui` 会使用本机 Edge 对桌面和手机视口执行渲染、溢出、按钮裁切、设置弹窗及浏览器错误检查，截图写入已忽略的 `test-results/`。

## 目录

```text
codex_k12/
  src/                 Vue 控制台
  server/              本地 API、持久化与任务队列
  codex_register/src/  K12、OAuth、邮箱与 Sub2API 执行器
  scripts/             自动验收脚本
  data/                本地运行数据，不入库
```
