# Reg Factory Codex K12

`codex_k12` is the local Codex/K12 operations console for reg-factory. It combines mailbox inventory, authorized workspace tasks, Codex credential output, Sub2API integration, access-token checks, task logs, and tenant-isolated persistence.

This project is derived from [lxh77721/k12-reg](https://github.com/lxh77721/k12-reg). The upstream MIT license remains in `LICENSE`; see `NOTICE` for the reference revision and local change boundary.

Use it only with workspaces, mailboxes, and downstream services that you own or are explicitly authorized to administer. No workspace ID, proxy, or reusable account password is configured by default.

## Run

Requirements: Node.js 20+, npm 10+, and a local Edge or Chrome installation.

```powershell
cd codex_k12
npm install
npm run build
npm start
```

Open `http://127.0.0.1:8806/`. For development, run `npm run dev`; Vite uses `http://127.0.0.1:5184/` and proxies API requests to port `8806`.

On first use, configure an authorized workspace ID, network route, mailbox API, and any optional Sub2API destination. The “sync mailbox pool” command reads the parent repository's `emails.txt` without modifying it.

Runtime data is stored under `data/` and `json/` and is ignored by Git. Never commit passwords, API keys, refresh tokens, access tokens, cookies, or account JSON files.

## Verify

```powershell
npm run build
npm run verify:ui
```

The UI verification runs desktop and mobile checks with local Edge and writes ignored screenshots to `test-results/`.
