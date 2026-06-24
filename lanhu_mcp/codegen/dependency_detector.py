"""
依赖检测器 - 基于组件类型和交互复杂度智能推荐 JS 插件/库

功能：
1. 组件类型 → UI 库映射
2. 交互复杂度 → 功能库推荐
3. 版本兼容性检查
4. Bundle size 影响预估
5. 生成 package.json 依赖段
"""
from __future__ import annotations

import json
from typing import Optional, List, Dict, Any, Set
from collections import Counter

from lanhu_mcp.codegen.ir import (
    ComponentIR,
    ComponentType,
    DependencySpec,
    DesignIR,
    Framework,
)


# ============================================================
# 依赖映射表 - React
# ============================================================

REACT_UI_LIBRARIES: Dict[str, Dict[str, Any]] = {
    "headless": {
        "name": "@headlessui/react",
        "version": "^2.0.0",
        "reason": "无样式可访问组件",
        "category": "ui",
        "size_kb": 45,
        "tree_shakable": True,
    },
    "radix": {
        "name": "@radix-ui/react-primitive",
        "version": "^2.0.0",
        "reason": "Radix UI 基础组件",
        "category": "ui",
        "size_kb": 12,
        "tree_shakable": True,
    },
    "floating": {
        "name": "@floating-ui/react",
        "version": "^0.26.0",
        "reason": "浮层定位",
        "category": "ui",
        "size_kb": 15,
        "tree_shakable": True,
    },
    "downshift": {
        "name": "downshift",
        "version": "^8.0.0",
        "reason": "可访问的自动完成/选择",
        "category": "a11y",
        "size_kb": 14,
        "tree_shakable": True,
    },
    "table": {
        "name": "@tanstack/react-table",
        "version": "^8.0.0",
        "reason": "表格核心逻辑",
        "category": "ui",
        "size_kb": 12,
        "tree_shakable": True,
    },
    "virtual": {
        "name": "@tanstack/react-virtual",
        "version": "^3.0.0",
        "reason": "虚拟滚动",
        "category": "ui",
        "size_kb": 8,
        "tree_shakable": True,
    },
    "form": {
        "name": "react-hook-form",
        "version": "^7.50.0",
        "reason": "表单状态管理",
        "category": "form",
        "size_kb": 9,
        "tree_shakable": True,
    },
    "zod": {
        "name": "zod",
        "version": "^3.22.0",
        "reason": "Schema 验证",
        "category": "form",
        "size_kb": 60,
        "tree_shakable": True,
    },
    "dayjs": {
        "name": "dayjs",
        "version": "^1.11.0",
        "reason": "日期处理",
        "category": "util",
        "size_kb": 7,
        "tree_shakable": True,
    },
    "lodash-es": {
        "name": "lodash-es",
        "version": "^4.17.21",
        "reason": "工具函数",
        "category": "util",
        "size_kb": 70,
        "tree_shakable": True,
    },
    "clsx": {
        "name": "clsx",
        "version": "^2.1.0",
        "reason": "条件类名合并",
        "category": "util",
        "size_kb": 1,
        "tree_shakable": True,
    },
    "swiper": {
        "name": "swiper",
        "version": "^11.0.0",
        "reason": "轮播组件",
        "category": "ui",
        "size_kb": 120,
        "tree_shakable": True,
    },
    "framer-motion": {
        "name": "framer-motion",
        "version": "^11.0.0",
        "reason": "动画库",
        "category": "animation",
        "size_kb": 150,
        "tree_shakable": True,
    },
    "react-dropzone": {
        "name": "react-dropzone",
        "version": "^14.2.0",
        "reason": "拖拽上传",
        "category": "ui",
        "size_kb": 12,
        "tree_shakable": True,
    },
}

# ============================================================
# 依赖映射表 - Vue
# ============================================================

VUE_UI_LIBRARIES: Dict[str, Dict[str, Any]] = {
    "floating": {
        "name": "@floating-ui/vue",
        "version": "^1.0.0",
        "reason": "浮层定位",
        "category": "ui",
        "size_kb": 12,
        "tree_shakable": True,
    },
    "vee-validate": {
        "name": "vee-validate",
        "version": "^4.11.0",
        "reason": "表单验证",
        "category": "form",
        "size_kb": 25,
        "tree_shakable": True,
    },
    "zod": {
        "name": "zod",
        "version": "^3.22.0",
        "reason": "Schema 验证",
        "category": "form",
        "size_kb": 60,
        "tree_shakable": True,
    },
    "dayjs": {
        "name": "dayjs",
        "version": "^1.11.0",
        "reason": "日期处理",
        "category": "util",
        "size_kb": 7,
        "tree_shakable": True,
    },
    "vueuse": {
        "name": "@vueuse/core",
        "version": "^10.0.0",
        "reason": "组合式函数集合",
        "category": "util",
        "size_kb": 40,
        "tree_shakable": True,
    },
    "table": {
        "name": "@tanstack/vue-table",
        "version": "^8.0.0",
        "reason": "表格核心逻辑",
        "category": "ui",
        "size_kb": 12,
        "tree_shakable": True,
    },
    "swiper": {
        "name": "swiper",
        "version": "^11.0.0",
        "reason": "轮播组件",
        "category": "ui",
        "size_kb": 120,
        "tree_shakable": True,
    },
    "clsx": {
        "name": "clsx",
        "version": "^2.1.0",
        "reason": "条件类名合并",
        "category": "util",
        "size_kb": 1,
        "tree_shakable": True,
    },
}

# ============================================================
# 组件类型 → 必需依赖
# ============================================================

COMPONENT_REQUIRED_DEPS: Dict[ComponentType, List[str]] = {
    ComponentType.MODAL: ["floating"],
    ComponentType.DRAWER: ["floating"],
    ComponentType.TOOLTIP: ["floating"],
    ComponentType.POPOVER: ["floating"],
    ComponentType.DROPDOWN: ["floating", "downshift"],
    ComponentType.SELECT: ["downshift"],
    ComponentType.TABLE: ["table"],
    ComponentType.CAROUSEL: ["swiper"],
    ComponentType.FORM: ["form", "zod"],
    ComponentType.DATE_PICKER: ["dayjs"],
    ComponentType.UPLOAD: ["react-dropzone"],
    ComponentType.SKELETON: [],
    ComponentType.TABS: [],
    ComponentType.ACCORDION: [],
    ComponentType.STEPS: [],
    ComponentType.PAGINATION: [],
}

# ============================================================
# 依赖检测器
# ============================================================

class DependencyDetector:
    """
    依赖检测器

    基于组件类型和交互复杂度智能推荐：
    1. 必需依赖（组件功能）
    2. 可选依赖（增强功能）
    3. 开发依赖（构建/测试）
    4. 体积影响预估
    """

    def __init__(self, framework: Framework = Framework.REACT):
        self.framework = framework
        self._lib_map = REACT_UI_LIBRARIES if framework == Framework.REACT else VUE_UI_LIBRARIES

    def analyze_design(self, ir: DesignIR) -> DesignIR:
        """分析设计 IR，收集所有依赖"""
        ir.dependencies = self._collect_all_dependencies(ir.components)
        return ir

    def _collect_all_dependencies(self, components: List[ComponentIR]) -> List[DependencySpec]:
        """收集所有组件的依赖"""
        seen: Set[str] = set()
        dependencies: List[DependencySpec] = []

        for comp in components:
            deps = self._get_component_dependencies(comp)
            for d in deps:
                if d.name not in seen:
                    seen.add(d.name)
                    dependencies.append(d)

            # 递归子组件
            child_deps = self._collect_all_dependencies(comp.children)
            for d in child_deps:
                if d.name not in seen:
                    seen.add(d.name)
                    dependencies.append(d)

        # 添加通用依赖
        self._add_common_deps(dependencies, seen)

        return dependencies

    def _get_component_dependencies(self, comp: ComponentIR) -> List[DependencySpec]:
        """获取单个组件的依赖"""
        dep_keys = COMPONENT_REQUIRED_DEPS.get(comp.component_type, [])
        dependencies = []

        for key in dep_keys:
            lib = self._lib_map.get(key)
            if lib:
                dependencies.append(DependencySpec(
                    name=lib["name"],
                    version=lib["version"],
                    reason=lib["reason"],
                    category=lib["category"],
                    size_estimate_kb=lib.get("size_kb", 0),
                    tree_shakable=lib.get("tree_shakable", True),
                ))

        return dependencies

    def _add_common_deps(self, dependencies: List[DependencySpec], seen: Set[str]):
        """添加通用依赖"""
        common = [
            ("clsx", "条件类名合并", "util", 1),
        ]

        for name, reason, category, size in common:
            if name not in seen:
                lib = self._lib_map.get(name, {})
                dependencies.append(DependencySpec(
                    name=lib.get("name", name),
                    version=lib.get("version", ""),
                    reason=reason,
                    category=category,
                    size_estimate_kb=lib.get("size_kb", size),
                    tree_shakable=lib.get("tree_shakable", True),
                ))
                seen.add(name)

    def generate_package_json_deps(
        self,
        dependencies: List[DependencySpec],
        include_dev: bool = True,
    ) -> Dict[str, Any]:
        """
        生成 package.json 依赖段

        Args:
            dependencies: 依赖列表
            include_dev: 是否包含开发依赖

        Returns:
            {"dependencies": {...}, "devDependencies": {...}}
        """
        deps = {}
        dev_deps = {}

        for dep in dependencies:
            entry = f"{dep.name}@{dep.version}" if dep.version else dep.name
            if dep.category in ("form", "util"):
                deps[dep.name] = dep.version
            else:
                deps[dep.name] = dep.version

        # 开发依赖
        if include_dev:
            dev_deps.update({
                "typescript": "^5.3.0",
                "vite": "^5.0.0",
            })
            if self.framework == Framework.REACT:
                dev_deps["@types/react"] = "^18.2.0"
                dev_deps["@types/react-dom"] = "^18.2.0"
            elif self.framework == Framework.VUE:
                dev_deps["vue-tsc"] = "^1.8.0"
                dev_deps["@vitejs/plugin-vue"] = "^5.0.0"

        result = {}
        if deps:
            result["dependencies"] = deps
        if dev_deps and include_dev:
            result["devDependencies"] = dev_deps

        return result

    def generate_import_statements(
        self,
        dependencies: List[DependencySpec],
    ) -> List[str]:
        """生成导入语句"""
        imports = []
        for dep in dependencies:
            if dep.category == "ui":
                imports.append(f"import {{ }} from '{dep.name}';")
            elif dep.category == "form":
                imports.append(f"import {{ }} from '{dep.name}';")
            elif dep.category == "util":
                imports.append(f"import {{ }} from '{dep.name}';")
        return imports

    def estimate_total_size(self, dependencies: List[DependencySpec]) -> Dict[str, float]:
        """估算总体积"""
        total = 0
        by_category = Counter()
        for dep in dependencies:
            size = dep.size_estimate_kb
            total += size
            by_category[dep.category] += size

        return {
            "total_kb": round(total, 1),
            "by_category": dict(by_category),
            "estimated_gzip_kb": round(total * 0.3, 1),  # gzip 约 30%
        }

    def get_dependency_summary(self, dependencies: List[DependencySpec]) -> str:
        """获取依赖摘要"""
        lines = ["[依赖摘要]"]
        lines.append(f"总依赖数: {len(dependencies)}")

        by_category = Counter()
        for dep in dependencies:
            by_category[dep.category] += 1

        lines.append("按类别:")
        for cat, count in by_category.most_common():
            lines.append(f"  {cat}: {count}")

        size = self.estimate_total_size(dependencies)
        lines.append(f"\n预估体积:")
        lines.append(f"  原始: {size['total_kb']}KB")
        lines.append(f"  Gzip: {size['estimated_gzip_kb']}KB")

        return "\n".join(lines)
