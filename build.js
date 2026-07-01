#!/usr/bin/env node
/**
 * LanhuMCP 一键打包脚本
 * 使用方法: node build.js [--clean] [--no-upx] [--debug]
 */

const { execSync, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// 配置
const CONFIG = {
  specFile: 'LanhuMCP-onefile.spec',
  outputName: 'LanhuMCP',
  distDir: 'dist',
  buildDir: 'build',
  dist2Dir: 'dist2',
};

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
  help: args.includes('--help') || args.includes('-h'),
};

function showHelp() {
  log('\nLanhuMCP 打包脚本', 'bright');
  log('使用方法: node build.js [选项]\n');
  log('选项:');
  log('  --clean    清理旧的构建文件后重新打包');
  log('  --no-upx   不使用 UPX 压缩（打包更快但文件更大）');
  log('  --debug    启用调试模式（保留控制台窗口）');
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
function cleanBuild() {
  if (!options.clean) return;

  logStep('4/6', '清理旧构建文件');

  const dirsToClean = [CONFIG.buildDir, CONFIG.distDir];
  const filesToClean = [`${CONFIG.outputName}.spec`];

  for (const dir of dirsToClean) {
    if (fs.existsSync(dir)) {
      fs.rmSync(dir, { recursive: true, force: true });
      logSuccess(`已删除: ${dir}/`);
    }
  }

  for (const file of filesToClean) {
    if (fs.existsSync(file)) {
      fs.unlinkSync(file);
      logSuccess(`已删除: ${file}`);
    }
  }
}

// 执行打包
function build() {
  const step = options.clean ? '5/6' : '4/6';
  logStep(step, '开始打包');

  const pyinstallerArgs = [
    '-m', 'PyInstaller',
    CONFIG.specFile,
    '--noconfirm',
    '--clean',
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
function postBuild() {
  const step = options.clean ? '6/6' : '5/6';
  logStep(step, '后处理');

  const exePath = path.join(CONFIG.distDir, `${CONFIG.outputName}.exe`);

  if (!fs.existsSync(exePath)) {
    logError(`未找到输出文件: ${exePath}`);
    return false;
  }

  // 获取文件信息
  const stats = fs.statSync(exePath);
  const sizeMB = (stats.size / (1024 * 1024)).toFixed(2);
  const modifiedTime = stats.mtime.toLocaleString('zh-CN');

  logSuccess(`打包成功!`);
  logInfo(`输出文件: ${exePath}`);
  logInfo(`文件大小: ${sizeMB} MB`);
  logInfo(`修改时间: ${modifiedTime}`);

  // 同步到 dist2
  if (fs.existsSync(CONFIG.dist2Dir)) {
    const dist2Exe = path.join(CONFIG.dist2Dir, `${CONFIG.outputName}.exe`);
    try {
      fs.copyFileSync(exePath, dist2Exe);
      logSuccess(`已同步到: ${dist2Exe}`);
    } catch (e) {
      logWarning(`同步到 dist2 失败: ${e.message}`);
    }
  }

  return true;
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

  if (options.clean) {
    cleanBuild();
  }

  if (!build()) process.exit(1);
  if (!postBuild()) process.exit(1);

  log('\n========================================', 'green');
  log('   打包完成!', 'green');
  log('========================================\n');
}

// 运行
main();
