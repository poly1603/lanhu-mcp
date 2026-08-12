#!/usr/bin/env node
/**
 * LanhuMCP 一键打包脚本
 * 使用方法: node build.js [--clean] [--no-upx] [--debug]
 */

const { execFileSync, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// 配置
const CONFIG = {
  specFile: 'LanhuMCP-onefile.spec',
  outputName: 'LanhuMCP',
  distDir: 'dist',
  buildDir: 'build',
  installerScript: 'installer.nsi',
};

const PACKAGE_VERSION = JSON.parse(
  fs.readFileSync(path.join(__dirname, 'package.json'), 'utf-8'),
).version;

// 颜色输出
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
};

function log(msg, color = 'reset') {
  console.log(`${colors[color]}${msg}${colors.reset}`);
}

function logSuccess(msg) {
  log(`✓ ${msg}`, 'green');
}

function logError(msg) {
  log(`✗ ${msg}`, 'red');
}

function logWarning(msg) {
  log(`⚠ ${msg}`, 'yellow');
}

function logInfo(msg) {
  log(`ℹ ${msg}`, 'cyan');
}

function logStep(step, msg) {
  log(`\n[${step}] ${msg}`, 'bright');
}

// 解析命令行参数
const args = process.argv.slice(2);
const options = {
  clean: args.includes('--clean'),
  noUpx: args.includes('--no-upx'),
  debug: args.includes('--debug'),
  noInstaller: args.includes('--no-installer'),
  help: args.includes('--help') || args.includes('-h'),
};

function showHelp() {
  log('\nLanhuMCP 打包脚本', 'bright');
  log('使用方法: node build.js [选项]\n');
  log('选项:');
  log('  --clean    清理旧的构建文件后重新打包');
  log('  --no-upx   不使用 UPX 压缩（打包更快但文件更大）');
  log('  --debug    启用调试模式（保留控制台窗口）');
  log('  --no-installer  只生成 exe，不编译 NSIS 安装程序');
  log('  --help     显示帮助信息');
  log('');
}

// Python 查找路径列表
const PYTHON_SEARCH_PATHS = [
  'python',
  'python3',
  path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python312', 'python.exe'),
  path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python311', 'python.exe'),
  path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python310', 'python.exe'),
  path.join('C:', 'Python312', 'python.exe'),
  path.join('C:', 'Python311', 'python.exe'),
  path.join('D:', 'Python312', 'python.exe'),
  path.join('D:', 'Python311', 'python.exe'),
];

let PYTHON_CMD = 'python';

// 查找可用的 Python
function findPython() {
  for (const cmd of PYTHON_SEARCH_PATHS) {
    try {
      const version = execSync(`"${cmd}" --version 2>&1`, { encoding: 'utf-8', timeout: 5000 }).trim();
      if (version.includes('Python')) {
        PYTHON_CMD = cmd;
        return version;
      }
    } catch (e) {
      // 继续尝试下一个路径
    }
  }
  return null;
}

// 检查 Python 环境
function checkPython() {
  logStep('1/6', '检查 Python 环境');

  const version = findPython();
  if (version) {
    logSuccess(`${version} (${PYTHON_CMD})`);
    return true;
  }

  logError('未找到 Python，请确保 Python 已安装');
  logInfo('推荐安装路径: C:\\Users\\<用户名>\\AppData\\Local\\Programs\\Python\\Python312');
  return false;
}

// 检查 PyInstaller
function checkPyInstaller() {
  logStep('2/6', '检查 PyInstaller');

  try {
    const version = execSync(`"${PYTHON_CMD}" -m PyInstaller --version`, { encoding: 'utf-8' }).trim();
    logSuccess(`PyInstaller 版本: ${version}`);
    return true;
  } catch (e) {
    logWarning('PyInstaller 未安装，尝试安装...');
    try {
      execSync(`"${PYTHON_CMD}" -m pip install pyinstaller`, { stdio: 'inherit' });
      logSuccess('PyInstaller 安装完成');
      return true;
    } catch (installError) {
      logError('PyInstaller 安装失败，请手动运行: pip install pyinstaller');
      return false;
    }
  }
}

// 检查项目依赖
function checkDependencies() {
  logStep('3/6', '检查项目依赖');

  const requirementsFile = 'requirements.txt';
  if (!fs.existsSync(requirementsFile)) {
    logWarning('未找到 requirements.txt，跳过依赖检查');
    return true;
  }

  try {
    logInfo('正在安装/更新依赖...');
    execSync(`"${PYTHON_CMD}" -m pip install -r requirements.txt -q`, { stdio: 'inherit' });
    logSuccess('依赖检查完成');
    return true;
  } catch (e) {
    logWarning('部分依赖安装失败，继续打包...');
    return true;
  }
}

// 清理旧构建
function cleanBuild(releaseDir) {
  if (!options.clean) return;

  logStep('4/6', '清理旧构建文件');

  // If the old portable exe is running, chooseReleaseDir() has already
  // selected an isolated release directory. Never remove the live dist tree.
  const dirsToClean = [CONFIG.buildDir];
  if (releaseDir === CONFIG.distDir) dirsToClean.push(CONFIG.distDir);
  for (const dir of dirsToClean) {
    if (fs.existsSync(dir)) {
      fs.rmSync(dir, { recursive: true, force: true });
      logSuccess(`已删除: ${dir}/`);
    }
  }

}

function isLanhuProcessRunning() {
  if (process.platform !== 'win32') return false;
  try {
    const output = execSync('tasklist /FI "IMAGENAME eq LanhuMCP.exe" /NH', {
      encoding: 'utf-8',
      stdio: ['ignore', 'pipe', 'ignore'],
    });
    return /LanhuMCP\.exe/i.test(output);
  } catch (e) {
    return false;
  }
}

function chooseReleaseDir() {
  const configured = process.env.LANHU_RELEASE_DIR;
  if (configured) return configured;

  const currentExe = path.join(CONFIG.distDir, `${CONFIG.outputName}.exe`);
  if (isLanhuProcessRunning() && fs.existsSync(currentExe)) {
    const fallback = `dist-release-${Date.now()}`;
    logWarning(`检测到正在运行的 ${currentExe}，本次输出改用 ${fallback}/，不会强制结束旧进程`);
    return fallback;
  }
  return CONFIG.distDir;
}

function findMakensis() {
  const candidates = [
    process.env.MAKENSIS,
    'makensis',
    path.join(process.env.LOCALAPPDATA || '', 'Programs', 'NSIS', 'makensis.exe'),
    path.join(process.env['ProgramFiles(x86)'] || '', 'NSIS', 'makensis.exe'),
    path.join(process.env.ProgramFiles || '', 'NSIS', 'makensis.exe'),
  ].filter(Boolean);

  for (const candidate of candidates) {
    try {
      if (candidate !== 'makensis' && !fs.existsSync(candidate)) continue;
      execFileSync(candidate, ['/VERSION'], { stdio: ['ignore', 'pipe', 'ignore'] });
      return candidate;
    } catch (e) {
      // Try the next standard NSIS installation location.
    }
  }
  return null;
}

// 执行打包
function build(releaseDir) {
  const step = options.clean ? '5/6' : '4/6';
  logStep(step, '开始打包');

  const pyinstallerArgs = [
    '-m', 'PyInstaller',
    CONFIG.specFile,
    '--noconfirm',
    '--clean',
    '--distpath', releaseDir,
    '--workpath', path.join(CONFIG.buildDir, path.basename(releaseDir)),
  ];

  if (options.noUpx) {
    pyinstallerArgs.push('--noupx');
  }

  if (options.debug) {
    pyinstallerArgs.push('--debug=all');
  }

  const cmd = `"${PYTHON_CMD}" ${pyinstallerArgs.join(' ')}`;
  logInfo(`执行命令: ${cmd}`);
  logInfo('打包过程可能需要几分钟，请耐心等待...\n');

  try {
    execSync(cmd, {
      stdio: 'inherit',
      cwd: __dirname,
    });
    return true;
  } catch (e) {
    logError('打包失败');
    return false;
  }
}

// 后处理
function postBuild(releaseDir) {
  const step = options.clean ? '6/6' : '5/6';
  logStep(step, '后处理');

  const exePath = path.join(releaseDir, `${CONFIG.outputName}.exe`);

  if (!fs.existsSync(exePath)) {
    logError(`未找到输出文件: ${exePath}`);
    return false;
  }

  // 获取文件信息
  const stats = fs.statSync(exePath);
  const sizeMB = (stats.size / (1024 * 1024)).toFixed(2);
  const modifiedTime = stats.mtime.toLocaleString('zh-CN');

  // Keep both deliverables in dist even when the currently running old exe
  // prevents replacing dist/LanhuMCP.exe. In that case publish a versioned
  // portable exe beside it; the next build after closing the old process can
  // return to the canonical name.
  let publishedExePath = exePath;
  if (path.resolve(releaseDir) !== path.resolve(CONFIG.distDir)) {
    publishedExePath = path.join(CONFIG.distDir, `LanhuMCP-v${PACKAGE_VERSION}.exe`);
    fs.mkdirSync(CONFIG.distDir, { recursive: true });
    fs.copyFileSync(exePath, publishedExePath);
    logInfo(`检测到旧版 exe 正在运行，新便携版已复制为: ${publishedExePath}`);
  }

  logSuccess(`打包成功!`);
  logInfo(`输出文件: ${publishedExePath}`);
  logInfo(`文件大小: ${sizeMB} MB`);
  logInfo(`修改时间: ${modifiedTime}`);
  return true;
}

function buildInstaller(releaseDir) {
  if (options.noInstaller) {
    logWarning('已跳过安装程序（--no-installer）');
    return true;
  }

  if (process.platform !== 'win32') {
    logWarning('安装程序仅支持 Windows，已跳过 NSIS');
    return true;
  }

  const makensis = findMakensis();
  if (!makensis) {
    logError('未找到 NSIS makensis.exe，无法生成安装程序');
    logInfo('请安装 NSIS：https://nsis.sourceforge.io/Download');
    logInfo('或使用 --no-installer 仅生成便携版 exe');
    return false;
  }

  const releasePath = path.resolve(releaseDir);
  const payloadPath = path.join(releasePath, `${CONFIG.outputName}.exe`);
  const installerOutputDir = path.resolve(CONFIG.distDir);
  const installerPath = path.join(CONFIG.distDir, `LanhuMCP-Setup-v${PACKAGE_VERSION}.exe`);
  logStep('6/6', '生成 Windows 安装程序');
  try {
    execFileSync(makensis, [
      `/DAPP_VERSION=${PACKAGE_VERSION}`,
      `/DAPP_DIST_DIR=${installerOutputDir}`,
      `/DAPP_PAYLOAD=${payloadPath}`,
      CONFIG.installerScript,
    ], { stdio: 'inherit', cwd: __dirname });
    if (!fs.existsSync(installerPath)) {
      logError(`未找到安装程序: ${installerPath}`);
      return false;
    }
    logSuccess(`安装程序已生成: ${installerPath}`);
    return true;
  } catch (e) {
    logError('NSIS 安装程序生成失败');
    return false;
  }
}

// 主函数
function main() {
  log('\n========================================', 'bright');
  log('   LanhuMCP 一键打包工具', 'bright');
  log('========================================\n');

  if (options.help) {
    showHelp();
    return;
  }

  // 检查 spec 文件
  if (!fs.existsSync(CONFIG.specFile)) {
    logError(`未找到打包配置文件: ${CONFIG.specFile}`);
    process.exit(1);
  }

  // 执行步骤
  if (!checkPython()) process.exit(1);
  if (!checkPyInstaller()) process.exit(1);
  if (!checkDependencies()) process.exit(1);

  const releaseDir = chooseReleaseDir();
  if (options.clean) {
    cleanBuild(releaseDir);
  }
  if (!build(releaseDir)) process.exit(1);
  if (!postBuild(releaseDir)) process.exit(1);
  if (!buildInstaller(releaseDir)) process.exit(1);

  log('\n========================================', 'green');
  log('   打包完成!', 'green');
  log('========================================\n');
}

// 运行
main();
