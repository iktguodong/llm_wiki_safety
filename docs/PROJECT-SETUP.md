# 安牛项目初始化指南

本文档提供安牛项目的完整初始化步骤。

## 前置要求

- Node.js >= 18
- npm >= 9
- Rust >= 1.75
- macOS / Windows / Linux

## 初始化步骤

### 1. 安装Rust（如果未安装）

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup default stable
```

验证安装：
```bash
rustc --version
cargo --version
```

### 2. 创建Vue 3 + TypeScript项目

```bash
# 在项目外创建
cd ..
npm create vite@latest anniu-app -- --template vue-ts
cd anniu-app
npm install
```

### 3. 安装Tauri CLI

```bash
npm install -D @tauri-apps/cli@latest
```

### 4. 初始化Tauri

```bash
npx tauri init
```

配置项：
- App name: `安牛`
- Window title: `安牛 - 企业安全知识库助手`
- Frontend dev server URL: `http://localhost:5173`
- Frontend build command: `npm run build`
- Frontend dist directory: `dist`

### 5. 安装依赖

```bash
# 安装Naive UI
npm install naive-vue@naive-ui

# 安装Pinia状态管理
npm install pinia

# 安装Vue Router
npm install vue-router@4

# 安装其他工具库
npm install @vueuse/core
npm install markdown-it
npm install @types/markdown-it
```

### 6. 配置项目结构

```bash
# 创建目录结构
mkdir -p src/{views,components,stores,types,assets,router,utils}
```

### 7. 配置Vite

编辑 `vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
  },
  envPrefix: ['VITE_', 'TAURI_'],
})
```

### 8. 运行开发模式

```bash
npm run tauri dev
```

## 故障排查

### Rust安装问题

如果Rust安装失败：
```bash
# 卸载旧版本
rustup self uninstall

# 重新安装
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup default stable
rustup update
```

### Tauri编译问题

确保安装了必要的编译工具：

**macOS:**
```bash
xcode-select --install
```

**Ubuntu/Debian:**
```bash
sudo apt install -y libwebkit2gtk-4.1-dev \
    build-essential \
    curl \
    wget \
    libssl-dev \
    libgtk-3-dev \
    libayatana-appindicator3-dev \
    librsvg2-dev
```

**Windows:**
安装Visual Studio Build Tools，选择"使用C++的桌面开发"

## 下一步

项目初始化完成后，按照 `DEVELOPMENT-PLAN.md` 逐步开发。
