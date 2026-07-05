#!/usr/bin/env node
/* global Buffer, WebSocket, clearTimeout, console, fetch, process, setTimeout */

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
].filter(Boolean);

const REQUIRED_INITIAL_TEXT = [
  '发布快照',
  '盘中监控',
  '盘后研究依据',
  'READY 研究依据',
  'preview 盘中触发',
  '研究池',
  '补充校验',
  '告警',
  '历史覆盖',
  '选股运行',
  '回测窗口',
  '市场概览',
  '2026-03-27',
  '任务流水线',
  '策略监控队列',
  '监控列表',
  '候选股票',
  '宁德时代',
  '300750.SZ',
  '价格曲线',
  '技术指标',
  '形态信号',
  '资金流向',
  '公告',
];

const REQUIRED_MONITOR_TEXT = [
  '移出监控',
  '策略监控',
  '盘中价',
  '买点',
  '止盈',
  '风控',
  '止损',
];

const ROUTE_CHECKS = [
  {
    label: '市场概览',
    text: ['市场事实', 'READY snapshot', '历史覆盖', '告警摘要', '涨跌分布'],
  },
  {
    label: '选股结果',
    text: ['选股结果', '候选得分', '量价诊断', '宁德时代', '300750.SZ'],
  },
  {
    label: '个股详情',
    text: ['个股详情', '量价诊断', '价格曲线', '技术指标', '公告'],
  },
  {
    label: '回测报告',
    text: ['历史回放结果', '回测报告', '回测分析', '交易记录', '年化收益', '最大回撤', '胜率', '利润因子'],
  },
];

class CdpClient {
  constructor(ws) {
    this.ws = ws;
    this.nextId = 1;
    this.pending = new Map();
    this.runtimeErrors = [];
    this.consoleErrors = [];

    ws.addEventListener('message', (event) => {
      const payload = JSON.parse(String(event.data));
      if (payload.id && this.pending.has(payload.id)) {
        const { resolve, reject, timer } = this.pending.get(payload.id);
        clearTimeout(timer);
        this.pending.delete(payload.id);
        if (payload.error) {
          reject(new Error(`${payload.error.message}: ${payload.error.data ?? ''}`));
        } else {
          resolve(payload.result ?? {});
        }
        return;
      }

      if (payload.method === 'Runtime.exceptionThrown') {
        this.runtimeErrors.push(payload.params?.exceptionDetails ?? payload.params);
      }
      if (
        payload.method === 'Runtime.consoleAPICalled'
        && payload.params?.type === 'error'
      ) {
        this.consoleErrors.push(payload.params);
      }
      if (payload.method === 'Log.entryAdded' && payload.params?.entry?.level === 'error') {
        const entry = payload.params.entry;
        if (!String(entry.url ?? '').endsWith('/favicon.ico')) {
          this.consoleErrors.push(entry);
        }
      }
    });
  }

  send(method, params = {}, timeoutMs = 10_000) {
    if (this.ws.readyState !== WebSocket.OPEN) {
      throw new Error(`CDP socket is not open for ${method}`);
    }

    const id = this.nextId++;
    const message = JSON.stringify({ id, method, params });
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP ${method} timed out after ${timeoutMs}ms`));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      this.ws.send(message);
    });
  }

  async evaluate(expression) {
    const result = await this.send('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (result.exceptionDetails) {
      throw new Error(`Evaluation failed: ${JSON.stringify(result.exceptionDetails)}`);
    }
    return result.result?.value;
  }

  close() {
    this.ws.close();
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      const port = typeof address === 'object' && address ? address.port : null;
      server.close(() => {
        if (port == null) {
          reject(new Error('Unable to allocate a free port'));
        } else {
          resolve(port);
        }
      });
    });
  });
}

async function waitForHttp(name, url, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return response;
      }
      lastError = new Error(`${response.status} ${response.statusText}`);
    } catch (error) {
      lastError = error;
    }
    await sleep(250);
  }
  throw new Error(`${name} did not become ready: ${lastError?.message ?? lastError}`);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`);
  }
  return response.json();
}

function findChromeExecutable() {
  const chrome = CHROME_CANDIDATES.find((candidate) => candidate && fs.existsSync(candidate));
  if (!chrome) {
    throw new Error(
      'No Chrome/Chromium executable found. Set CHROME_PATH to run frontend browser smoke.',
    );
  }
  return chrome;
}

function startProcess(name, command, args, env, logPath, cwd = ROOT) {
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  const logFd = fs.openSync(logPath, 'w');
  const child = spawn(command, args, {
    cwd,
    env,
    stdio: ['ignore', logFd, logFd],
  });
  child.logFd = logFd;
  child.logPath = logPath;
  console.log(`[frontend-browser-smoke] started ${name}: ${command} ${args.join(' ')}`);
  console.log(`[frontend-browser-smoke] log: ${logPath}`);
  return child;
}

async function stopProcess(child, name) {
  if (!child) return;
  if (child.exitCode == null && child.signalCode == null) {
    child.kill('SIGTERM');
    const exited = await Promise.race([
      new Promise((resolve) => child.once('exit', () => resolve(true))),
      sleep(5_000).then(() => false),
    ]);
    if (!exited && child.exitCode == null && child.signalCode == null) {
      child.kill('SIGKILL');
      await new Promise((resolve) => child.once('exit', resolve));
    }
  }
  if (child.logFd != null) {
    fs.closeSync(child.logFd);
  }
  console.log(`[frontend-browser-smoke] stopped ${name}`);
}

async function launchChrome(chromePath, debugPort, userDataDir, logPath) {
  return startProcess(
    'chrome',
    chromePath,
    [
      '--headless=new',
      '--disable-gpu',
      '--disable-dev-shm-usage',
      '--no-first-run',
      '--no-default-browser-check',
      `--remote-debugging-port=${debugPort}`,
      `--user-data-dir=${userDataDir}`,
      'about:blank',
    ],
    process.env,
    logPath,
    ROOT,
  );
}

async function createPage(debugPort) {
  const base = `http://127.0.0.1:${debugPort}`;
  try {
    return await fetchJson(`${base}/json/new?about%3Ablank`, { method: 'PUT' });
  } catch {
    const pages = await fetchJson(`${base}/json/list`);
    const page = pages.find((item) => item.type === 'page');
    if (!page) {
      throw new Error('Chrome exposed no page target through CDP');
    }
    return page;
  }
}

async function connectToCdp(wsUrl) {
  const ws = new WebSocket(wsUrl);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('CDP socket open timed out')), 5_000);
    ws.addEventListener('open', () => {
      clearTimeout(timer);
      resolve();
    }, { once: true });
    ws.addEventListener('error', (event) => {
      clearTimeout(timer);
      reject(new Error(`CDP socket error: ${event.message ?? 'unknown error'}`));
    }, { once: true });
  });
  return new CdpClient(ws);
}

async function pollEvaluate(cdp, expression, description, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs;
  let lastValue = null;
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      const value = await cdp.evaluate(expression);
      lastValue = value;
      if (value?.ok) {
        return value;
      }
    } catch (error) {
      lastError = error;
    }
    await sleep(300);
  }
  throw new Error(
    `${description} timed out. Last value: ${JSON.stringify(lastValue)}. `
      + `Last error: ${lastError?.message ?? 'none'}`,
  );
}

function renderedTextExpression(requiredText) {
  return `
(() => {
  const text = document.body?.innerText ?? '';
  const missing = ${JSON.stringify(requiredText)}.filter((item) => !text.includes(item));
  return {
    ok: missing.length === 0
      && !text.includes('加载失败')
      && !text.includes('API 500')
      && document.querySelector('#root')?.childElementCount > 0,
    missing,
    sample: text.slice(0, 1600),
  };
})()
`;
}

function clickButtonExpression(label) {
  return `
(() => {
  const buttons = Array.from(document.querySelectorAll('button'));
  const button = buttons.find((item) => (item.textContent ?? '').includes(${JSON.stringify(label)}));
  if (!button) {
    return { clicked: false, buttons: buttons.map((item) => item.textContent?.trim()) };
  }
  button.click();
  return { clicked: true };
})()
`;
}

async function captureScreenshot(cdp, screenshotPath) {
  const result = await cdp.send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: true,
  });
  fs.writeFileSync(screenshotPath, Buffer.from(result.data, 'base64'));
  console.log(`[frontend-browser-smoke] screenshot: ${screenshotPath}`);
}

async function main() {
  const runtimeDir = fs.mkdtempSync(path.join(os.tmpdir(), 'quanta-browser-smoke-runtime-'));
  const chromeUserDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'quanta-browser-smoke-chrome-'));
  const logsDir = path.join(runtimeDir, 'logs');
  const backendPort = await findFreePort();
  const frontendPort = await findFreePort();
  const debugPort = await findFreePort();
  const backendOrigin = `http://127.0.0.1:${backendPort}`;
  const frontendOrigin = `http://127.0.0.1:${frontendPort}`;
  const env = {
    ...process.env,
    PYTHONUNBUFFERED: '1',
    QUANTA_RUNTIME_DATA_DIR: runtimeDir,
    QUANTA_DUCKDB_PATH: path.join(runtimeDir, 'duckdb', 'quanta.duckdb'),
    QUANTA_SOURCE_PROVIDER: 'fixture_json',
    QUANTA_SOURCE_VALIDATION_PROVIDERS: 'none',
    QUANTA_BACKEND_HOST: '127.0.0.1',
    QUANTA_BACKEND_PORT: String(backendPort),
    QUANTA_FRONTEND_HOST: '127.0.0.1',
    QUANTA_FRONTEND_PORT: String(frontendPort),
  };

  let backend = null;
  let frontend = null;
  let chrome = null;
  let cdp = null;
  let passed = false;

  try {
    backend = startProcess(
      'backend',
      'pnpm',
      ['run', 'backend:dev'],
      env,
      path.join(logsDir, 'frontend-browser-smoke-backend.log'),
    );
    await waitForHttp('backend health', `${backendOrigin}/health`);

    frontend = startProcess(
      'frontend',
      'pnpm',
      ['run', 'frontend:dev'],
      env,
      path.join(logsDir, 'frontend-browser-smoke-frontend.log'),
    );
    await waitForHttp('frontend health', `${frontendOrigin}/health`);

    const chromePath = findChromeExecutable();
    chrome = await launchChrome(
      chromePath,
      debugPort,
      chromeUserDataDir,
      path.join(logsDir, 'frontend-browser-smoke-chrome.log'),
    );
    await waitForHttp('chrome debugging endpoint', `http://127.0.0.1:${debugPort}/json/version`);

    const page = await createPage(debugPort);
    cdp = await connectToCdp(page.webSocketDebuggerUrl);
    await cdp.send('Runtime.enable');
    await cdp.send('Page.enable');
    await cdp.send('Log.enable');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 1000,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await cdp.send('Page.navigate', { url: frontendOrigin });

    const initial = await pollEvaluate(
      cdp,
      renderedTextExpression(REQUIRED_INITIAL_TEXT),
      'initial workbench render',
    );
    if (initial.missing.length) {
      throw new Error(`Initial render missing text: ${initial.missing.join(', ')}`);
    }

    const clickResult = await cdp.evaluate(clickButtonExpression('加入监控'));
    if (!clickResult?.clicked) {
      throw new Error(`Could not click 加入监控. Buttons: ${JSON.stringify(clickResult?.buttons)}`);
    }

    const monitored = await pollEvaluate(
      cdp,
      renderedTextExpression(REQUIRED_MONITOR_TEXT),
      'strategy monitor render',
    );
    if (monitored.missing.length) {
      throw new Error(`Monitor render missing text: ${monitored.missing.join(', ')}`);
    }

    for (const routeCheck of ROUTE_CHECKS) {
      const navResult = await cdp.evaluate(clickButtonExpression(routeCheck.label));
      if (!navResult?.clicked) {
        throw new Error(
          `Could not click ${routeCheck.label}. Buttons: ${JSON.stringify(navResult?.buttons)}`,
        );
      }
      const routed = await pollEvaluate(
        cdp,
        renderedTextExpression(routeCheck.text),
        `${routeCheck.label} route render`,
      );
      if (routed.missing.length) {
        throw new Error(`${routeCheck.label} route missing text: ${routed.missing.join(', ')}`);
      }
    }

    await cdp.send('Page.navigate', { url: `${frontendOrigin}/stocks/300750.SZ` });
    const directStockRoute = await pollEvaluate(
      cdp,
      renderedTextExpression(['个股详情', '300750.SZ', 'READY snapshot', '量价诊断', '价格曲线']),
      'direct stock route render',
    );
    if (directStockRoute.missing.length) {
      throw new Error(`Direct stock route missing text: ${directStockRoute.missing.join(', ')}`);
    }

    if (cdp.runtimeErrors.length || cdp.consoleErrors.length) {
      throw new Error(
        'Browser reported runtime errors: '
          + JSON.stringify({
            runtimeErrors: cdp.runtimeErrors,
            consoleErrors: cdp.consoleErrors,
          }).slice(0, 2000),
      );
    }

    await captureScreenshot(cdp, path.join(logsDir, 'frontend-browser-smoke.png'));
    await fetch(`${backendOrigin}/api/v1/strategy-watchlist/300750.SZ`, { method: 'DELETE' });

    console.log('[frontend-browser-smoke] rendered workbench and strategy monitor successfully');
    passed = true;
  } finally {
    if (cdp) {
      cdp.close();
    }
    await stopProcess(chrome, 'chrome');
    await stopProcess(frontend, 'frontend');
    await stopProcess(backend, 'backend');
    if (passed && process.env.QUANTA_KEEP_BROWSER_SMOKE_ARTIFACTS !== '1') {
      fs.rmSync(runtimeDir, { recursive: true, force: true });
      fs.rmSync(chromeUserDataDir, { recursive: true, force: true });
    } else {
      console.log(`[frontend-browser-smoke] kept runtime artifacts: ${runtimeDir}`);
      console.log(`[frontend-browser-smoke] kept chrome profile: ${chromeUserDataDir}`);
    }
  }
}

main().catch((error) => {
  console.error(`[frontend-browser-smoke] failed: ${error.stack ?? error.message}`);
  process.exitCode = 1;
});
