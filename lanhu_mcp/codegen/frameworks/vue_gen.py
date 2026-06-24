"""
Vue 3 生成器 - Composition API + SFC + Scoped CSS + TypeScript

输出：.vue 单文件组件 + <script setup lang="ts"> + <style scoped>
"""
from __future__ import annotations

import re
from typing import Optional, List, Dict, Any

from lanhu_mcp.codegen.ir import (
    DesignIR,
    ComponentIR,
    ComponentType,
    SemanticTag,
    A11ySpec,
    EventSpec,
    PropSpec,
    StateSpec,
    SlotSpec,
    InteractionSpec,
    StateMachine,
    DesignTokens,
)
from lanhu_mcp.codegen.semantic import SemanticAnalyzer
from lanhu_mcp.codegen.style_system import (
    BEMNamer,
    CSSVariableGenerator,
    ComponentStyleGenerator,
    GlobalStyleGenerator,
)
from lanhu_mcp.codegen.interaction import InteractionInference, AnimationInference
from lanhu_mcp.codegen.dependency_detector import DependencyDetector


class VueGenerator:
    """
    Vue 3 代码生成器

    生成规范：
    1. <script setup lang="ts"> + defineProps/defineEmits
    2. Composition API + ref/reactive/watch/computed
    3. Scoped CSS + CSS Variables
    4. BEM 命名
    5. ARIA 无障碍属性
    6. 键盘导航支持
    """

    def __init__(self):
        self.semantic_analyzer = SemanticAnalyzer()
        self.interaction_engine = InteractionInference(framework="vue")
        self.dep_detector = DependencyDetector(framework="vue")

    def generate(self, ir: DesignIR) -> Dict[str, str]:
        """从 DesignIR 生成 Vue 项目"""
        # 1. 分析
        ir = self.semantic_analyzer.analyze_design(ir)
        ir = self.interaction_engine.analyze_design(ir)
        ir = self.dep_detector.analyze_design(ir)

        files = {}

        # 全局样式
        files["src/styles/tokens.css"] = CSSVariableGenerator.generate_tokens_css(ir.tokens)
        files["src/styles/reset.css"] = GlobalStyleGenerator.generate_reset()
        files["src/styles/utilities.css"] = GlobalStyleGenerator.generate_utilities()

        # 主入口
        files["src/App.vue"] = self._generate_app(ir)

        # 页面组件
        for i, page in enumerate(ir.pages):
            files[f"src/views/{page.name}.vue"] = self._generate_page(page, ir.tokens)

        # 组件
        for comp in ir.components:
            vue_code = self._generate_component(comp, ir.tokens)
            files[f"src/components/{comp.name}.vue"] = vue_code

        # package.json
        pkg = self.dep_detector.generate_package_json_deps(ir.dependencies)
        import json
        files["package.json"] = json.dumps({
            "name": ir.name.lower().replace(" ", "-"),
            "version": "0.1.0",
            "private": True,
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview",
                "type-check": "vue-tsc --noEmit",
            },
            **pkg,
        }, indent=2, ensure_ascii=False)

        # tsconfig
        files["tsconfig.json"] = self._generate_tsconfig()

        # vite.config
        files["vite.config.ts"] = self._generate_vite_config()

        return files

    def _generate_app(self, ir: DesignIR) -> str:
        """生成 App.vue"""
        return f"""<script setup lang="ts">
// {ir.name} - App 入口
</script>

<template>
  <div id="app">
    <router-view />
  </div>
</template>

<style>
@import './styles/tokens.css';
@import './styles/reset.css';
@import './styles/utilities.css';
</style>
"""

    def _generate_page(self, page, tokens: DesignTokens) -> str:
        """生成页面组件"""
        comp_names = [c.name for c in page.components]
        imports = []
        components = []
        for name in comp_names:
            imp_name = self._to_pascal_case(name)
            imports.append(f'import {imp_name} from "../components/{name}.vue";')
            components.append(imp_name)

        return f"""<script setup lang="ts">
// {page.title or page.name}
{chr(10).join(imports)}
</script>

<template>
  <main class="page-{page.name.lower()}" role="main">
    {chr(10).join(f'    <{self._to_kebab(c)} />' for c in components)}
  </main>
</template>

<style scoped>
.page-{page.name.lower()} {{
  min-height: 100vh;
  padding: 24px;
}}
</style>
"""

    def _generate_component(self, comp: ComponentIR, tokens: DesignTokens) -> str:
        """生成单个 Vue 组件"""
        block = BEMNamer.block(comp.name)
        pascal = self._to_pascal_case(comp.name)

        # Props 定义
        props_defs = self._generate_props(comp)

        # Emits 定义
        emits = self._generate_emits(comp)

        # Reactive 状态
        state_vars = self._generate_state(comp)

        # Methods
        methods = self._generate_methods(comp)

        # Template
        template = self._generate_template(comp)

        # Scoped CSS
        css = self._generate_scoped_css(comp, tokens)

        return f"""<script setup lang="ts">
import {{ ref, reactive, computed, watch, onMounted, onUnmounted }} from 'vue';

// Props
{props_defs}

// Emits
{emits}

// 状态
{state_vars}

// 方法
{methods}
</script>

<template>
{template}
</template>

<style scoped>
{css}
</style>
"""

    def _generate_props(self, comp: ComponentIR) -> str:
        """生成 Props 定义"""
        if not comp.props:
            return "// 无 props"

        lines = ["const props = withDefaults(defineProps<{"]
        for prop in comp.props:
            ts_type = self._to_ts_type(prop)
            default = ""
            if prop.default is not None:
                if isinstance(prop.default, str):
                    default = f" = '{prop.default}'"
                elif isinstance(prop.default, bool):
                    default = f" = {'true' if prop.default else 'false'}"
                elif isinstance(prop.default, (int, float)):
                    default = f" = {prop.default}"
            lines.append(f"  {prop.name}?: {ts_type}{default};")
        lines.append("}>(), {")
        for prop in comp.props:
            if prop.default is not None:
                if isinstance(prop.default, str):
                    lines.append(f"  {prop.name}: '{prop.default}',")
                elif isinstance(prop.default, bool):
                    lines.append(f"  {prop.name}: {'true' if prop.default else 'false'},")
                elif isinstance(prop.default, (int, float)):
                    lines.append(f"  {prop.name}: {prop.default},")
        lines.append("});")
        return "\n".join(lines)

    def _generate_emits(self, comp: ComponentIR) -> str:
        """生成 Emits 定义"""
        if not comp.events:
            return "// 无 emits"

        event_names = [e.name for e in comp.events]
        emits_str = ", ".join(f"'{e}'" for e in event_names)
        return f"const emit = defineEmits<{emits_str}>();"

    def _generate_state(self, comp: ComponentIR) -> str:
        """生成响应式状态"""
        lines = []
        for s in comp.state:
            default = "false" if s.type == "boolean" else "''" if s.type == "string" else "null"
            lines.append(f"const {s.name} = ref({default});")
        if not lines:
            return ""
        return "\n".join(lines)

    def _generate_methods(self, comp: ComponentIR) -> str:
        """生成方法"""
        lines = []
        for event in comp.events:
            handler = event.handler_name or f"handle{event.name.capitalize()}"
            lines.append(f"function {handler}() {{")
            lines.append(f"  emit('{event.name}');")
            lines.append(f"}}")
        if not lines:
            return ""
        return "\n".join(lines)

    def _generate_template(self, comp: ComponentIR) -> str:
        """生成模板"""
        block = BEMNamer.block(comp.name)
        tag = comp.semantic_tag.value

        # 构建属性
        attrs = [f'class="{block}"']
        if comp.aria:
            if comp.aria.role:
                attrs.append(f'role="{comp.aria.role}"')
            if comp.aria.aria_label:
                attrs.append(f':aria-label="\'{comp.aria.aria_label}\'"')
            if comp.aria.aria_expanded:
                attrs.append(':aria-expanded="false"')
            if comp.aria.aria_haspopup:
                attrs.append(f'aria-haspopup="{comp.aria.aria_haspopup}"')

        attr_str = " ".join(attrs)

        # 子组件
        children = []
        if comp.children:
            for child in comp.children:
                child_tag = child.semantic_tag.value
                child_block = BEMNamer.block(child.name)
                children.append(f'    <{child_tag} class="{child_block}"></{child_tag}>')
        else:
            text = self._get_text_content(comp)
            if text:
                children.append(f"      {text}")

        if children:
            return f"""  <{tag} {attr_str}>
{chr(10).join(children)}
  </{tag}>"""
        else:
            return f"  <{tag} {attr_str}></{tag}>"

    def _generate_scoped_css(self, comp: ComponentIR, tokens: DesignTokens) -> str:
        """生成 Scoped CSS"""
        block = BEMNamer.block(comp.name)
        css = ComponentStyleGenerator.generate_component_css(comp, tokens)
        return css

    def _to_ts_type(self, prop: PropSpec) -> str:
        """转换为 TypeScript 类型"""
        if prop.type == "string":
            if prop.enum_values:
                return " | ".join(f"'{v}'" for v in prop.enum_values)
            return "string"
        elif prop.type == "number":
            return "number"
        elif prop.type == "boolean":
            return "boolean"
        elif prop.type == "function":
            return "() => void"
        elif prop.type == "array":
            return "any[]"
        elif prop.type == "object":
            return "Record<string, any>"
        return "any"

    def _to_pascal_case(self, name: str) -> str:
        """转换为 PascalCase"""
        return ''.join(word.capitalize() for word in re.split(r'[-_]', name))

    def _to_kebab(self, name: str) -> str:
        """转换为 kebab-case"""
        return re.sub(r'([A-Z])', r'-\1', name).lower().strip('-')

    def _get_text_content(self, comp: ComponentIR) -> str:
        """获取文本内容"""
        return comp.design_styles.get("text", "") or comp.name

    def _generate_tsconfig(self) -> str:
        return """{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "preserve",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.tsx", "src/**/*.vue"],
  "references": [{ "path": "./tsconfig.node.json" }]
}"""

    def _generate_vite_config(self) -> str:
        return """import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3000,
    open: true,
  },
})"""
