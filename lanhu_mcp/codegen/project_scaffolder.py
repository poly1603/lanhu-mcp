"""
Project Scaffolder

生成完整项目脚手架，支持：
- 新项目创建（全量文件）
- 已有项目集成（增量追加，不覆盖已有文件）
- 项目模板检测和适配
- package.json / pubspec.yaml 依赖合并
- 目录结构创建
"""
import os
import json
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

from .ir import Framework, DesignIR, ComponentIR


@dataclass
class ScaffoldConfig:
    """脚手架配置"""
    project_name: str
    framework: Framework
    output_dir: str
    # 已有项目模式
    existing_project: bool = False
    # 保护已有文件不被覆盖
    protect_existing: bool = True
    # 额外依赖
    extra_dependencies: Dict[str, str] = field(default_factory=dict)
    # 跳过的文件模式
    skip_patterns: List[str] = field(default_factory=list)


class ProjectScaffolder:
    """项目脚手架生成器"""

    def scaffold(
        self,
        config: ScaffoldConfig,
        ir: DesignIR,
        generated_files: Dict[str, str],
    ) -> Dict[str, str]:
        """
        将生成的文件写入项目目录，合并已有项目。

        Returns: 实际写入的文件映射
        """
        written_files: Dict[str, str] = {}

        # 目录结构
        dirs = self._required_dirs(config, ir)
        for d in dirs:
            os.makedirs(os.path.join(config.output_dir, d), exist_ok=True)

        # 合并 package.json（如果已有）
        if config.existing_project and config.protect_existing:
            generated_files = self._merge_existing_project(config, generated_files)

        # 写入文件
        for rel_path, content in generated_files.items():
            full_path = os.path.join(config.output_dir, rel_path)

            # 跳过已有文件（如果保护模式）
            if config.existing_project and config.protect_existing:
                if os.path.exists(full_path):
                    continue

            # 跳过匹配模式的文件
            if self._should_skip(rel_path, config.skip_patterns):
                continue

            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            written_files[rel_path] = content

        return written_files

    def detect_existing_project(self, output_dir: str) -> Optional[Framework]:
        """检测目标目录是否已有项目，返回框架类型"""
        if os.path.exists(os.path.join(output_dir, "package.json")):
            try:
                with open(os.path.join(output_dir, "package.json"), "r", encoding="utf-8") as f:
                    pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "svelte" in deps:
                    return Framework.SVELTE
                if "react" in deps or "react-dom" in deps:
                    return Framework.REACT
                if "vue" in deps or "nuxt" in deps:
                    return Framework.VUE
            except (json.JSONDecodeError, IOError):
                pass

        if os.path.exists(os.path.join(output_dir, "pubspec.yaml")):
            return Framework.FLUTTER

        if os.path.exists(os.path.join(output_dir, "index.html")):
            return Framework.HTML

        return None

    def _required_dirs(self, config: ScaffoldConfig, ir: DesignIR) -> List[str]:
        """根据框架返回必需的目录"""
        dirs = ["src"]

        if config.framework == Framework.HTML:
            dirs.extend(["assets/css", "assets/js", "assets/images"])
        elif config.framework == Framework.VUE:
            dirs.extend([
                "src/components", "src/composables", "src/stores",
                "src/assets", "src/types", "public",
            ])
        elif config.framework == Framework.REACT:
            dirs.extend([
                "src/components", "src/hooks", "src/types",
                "src/styles", "public",
            ])
        elif config.framework == Framework.FLUTTER:
            dirs.extend(["lib", "lib/widgets", "lib/theme", "test"])
        elif config.framework == Framework.SVELTE:
            dirs.extend([
                "src/lib", "src/lib/components", "src/lib/stores",
                "src/lib/composables", "src/lib/types", "public",
            ])

        return dirs

    def _merge_existing_project(
        self,
        config: ScaffoldConfig,
        generated_files: Dict[str, str],
    ) -> Dict[str, str]:
        """合并已有项目的依赖"""
        merged = dict(generated_files)

        if config.framework in (Framework.HTML, Framework.VUE, Framework.REACT, Framework.SVELTE):
            pkg_path = os.path.join(config.output_dir, "package.json")
            if os.path.exists(pkg_path):
                try:
                    with open(pkg_path, "r", encoding="utf-8") as f:
                        existing = json.load(f)

                    # 合并依赖
                    new_pkg = json.loads(merged.get("package.json", "{}"))
                    for key in ("dependencies", "devDependencies"):
                        if key in new_pkg:
                            existing_deps = existing.get(key, {})
                            new_deps = new_pkg.get(key, {})
                            existing_deps.update(new_deps)
                            existing[key] = existing_deps

                    # 合并 scripts
                    if "scripts" in new_pkg:
                        existing_scripts = existing.get("scripts", {})
                        existing_scripts.update(new_pkg["scripts"])
                        existing["scripts"] = existing_scripts

                    merged["package.json"] = json.dumps(existing, indent=2, ensure_ascii=False)
                except (json.JSONDecodeError, IOError):
                    pass

        elif config.framework == Framework.FLUTTER:
            pubspec_path = os.path.join(config.output_dir, "pubspec.yaml")
            if os.path.exists(pubspec_path):
                # Flutter pubspec 合并简单追加
                try:
                    with open(pubspec_path, "r", encoding="utf-8") as f:
                        existing_content = f.read()
                    new_content = merged.get("pubspec.yaml", "")
                    # 合并 dependencies 部分
                    if "dependencies:" in existing_content and "dependencies:" in new_content:
                        merged["pubspec.yaml"] = existing_content + "\n" + new_content.split("dependencies:", 1)[-1]
                    else:
                        merged["pubspec.yaml"] = existing_content + "\n" + new_content
                except IOError:
                    pass

        return merged

    def _should_skip(self, rel_path: str, patterns: List[str]) -> bool:
        """检查文件是否匹配跳过模式"""
        import fnmatch
        for pattern in patterns:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
        return False

    def generate_readme(self, ir: DesignIR, config: ScaffoldConfig) -> str:
        """生成 README.md"""
        framework_docs = {
            Framework.HTML: "HTML5 + CSS + 原生 JavaScript",
            Framework.VUE: "Vue 3 + Composition API + TypeScript",
            Framework.REACT: "React + TypeScript + CSS Modules",
            Framework.FLUTTER: "Flutter + Dart",
            Framework.SVELTE: "Svelte 4 + TypeScript",
        }

        components_list = "\n".join(
            f"  - {comp.name} ({comp.component_type.value})"
            for comp in ir.components
        )

        return f"""# {ir.name}

> 由 Lanhu MCP Codegen 自动生成

## 技术栈

{framework_docs.get(config.framework, 'Unknown')}

## 组件列表

{components_list if components_list else '  (无组件)'}

## 安装

```bash
{"npm install" if config.framework in (Framework.HTML, Framework.VUE, Framework.REACT, Framework.SVELTE) else "flutter pub get"}
```

## 启动

```bash
{"npm run dev" if config.framework in (Framework.HTML, Framework.VUE, Framework.REACT, Framework.SVELTE) else "flutter run"}
```

## 项目结构

```
{self._tree(config, ir)}
```
"""

    def _tree(self, config: ScaffoldConfig, ir: DesignIR) -> str:
        """生成目录树"""
        lines = [f"{config.project_name}/"]
        if config.framework == Framework.HTML:
            lines.extend([
                "  assets/",
                "    css/",
                "    js/",
                "    images/",
                "  index.html",
                "  styles.css",
                "  script.js",
            ])
        elif config.framework == Framework.VUE:
            lines.extend([
                "  src/",
                "    components/",
                "    composables/",
                "    stores/",
                "    types/",
                "  App.vue",
                "  main.ts",
                "  vite.config.ts",
            ])
        elif config.framework == Framework.REACT:
            lines.extend([
                "  src/",
                "    components/",
                "    hooks/",
                "    types/",
                "    styles/",
                "  App.tsx",
                "  main.tsx",
                "  tsconfig.json",
            ])
        elif config.framework == Framework.FLUTTER:
            lines.extend([
                "  lib/",
                "    widgets/",
                "    theme.dart",
                "    main.dart",
                "  pubspec.yaml",
            ])
        elif config.framework == Framework.SVELTE:
            lines.extend([
                "  src/",
                "    lib/",
                "      components/",
                "      stores/",
                "      types/",
                "  App.svelte",
                "  main.ts",
                "  svelte.config.js",
            ])
        return "\n".join(lines)


def scaffold(
    config: ScaffoldConfig,
    ir: DesignIR,
    generated_files: Dict[str, str],
) -> Dict[str, str]:
    """便捷入口"""
    return ProjectScaffolder().scaffold(config, ir, generated_files)
