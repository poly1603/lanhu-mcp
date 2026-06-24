"""
React 生成器 - TypeScript + FC + CSS Modules + 无障碍

输出：.tsx 组件 + .module.css + .stories.tsx + 类型定义
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


class ReactGenerator:
    """
    React 代码生成器

    生成规范：
    1. TypeScript strict 模式
    2. FC<Props> / ForwardRefExoticComponent
    3. CSS Modules + CSS Variables
    4. ARIA 无障碍属性
    5. 键盘导航支持
    6. 事件处理函数
    7. 自定义 Hooks
    """

    def __init__(self):
        self.semantic_analyzer = SemanticAnalyzer()
        self.interaction_engine = InteractionInference(framework="react")
        self.dep_detector = DependencyDetector(framework="react")

    def generate(self, ir: DesignIR) -> Dict[str, str]:
        """从 DesignIR 生成 React 项目"""
        # 1. 分析
        ir = self.semantic_analyzer.analyze_design(ir)
        ir = self.interaction_engine.analyze_design(ir)
        ir = self.dep_detector.analyze_design(ir)

        files = {}

        # 全局样式
        files["src/styles/tokens.css"] = CSSVariableGenerator.generate_tokens_css(ir.tokens)
        files["src/styles/reset.css"] = GlobalStyleGenerator.generate_reset()
        files["src/styles/utilities.css"] = GlobalStyleGenerator.generate_utilities()

        # 组件
        for comp in ir.components:
            tsx = self._generate_component(comp, ir.tokens)
            files[f"src/components/{comp.name}/{comp.name}.tsx"] = tsx
            css = ComponentStyleGenerator.generate_component_css(comp, ir.tokens)
            files[f"src/components/{comp.name}/{comp.name}.module.css"] = css
            # 类型定义
            types = self._generate_types(comp)
            files[f"src/components/{comp.name}/types.ts"] = types

        # 页面
        for page in ir.pages:
            tsx = self._generate_page(page, ir)
            files[f"src/pages/{page.name}.tsx"] = tsx

        # App 入口
        files["src/App.tsx"] = self._generate_app(ir)

        # 自定义 Hooks
        for comp in ir.components:
            if comp.interaction and comp.interaction.state_machine:
                hook = self._generate_hook(comp)
                files[f"src/hooks/use{self._to_pascal_case(comp.name)}.ts"] = hook

        # package.json
        import json
        pkg = self.dep_detector.generate_package_json_deps(ir.dependencies)
        files["package.json"] = json.dumps({
            "name": ir.name.lower().replace(" ", "-"),
            "version": "0.1.0",
            "private": True,
            "scripts": {
                "dev": "vite",
                "build": "tsc && vite build",
                "preview": "vite preview",
                "type-check": "tsc --noEmit",
                "lint": "eslint src --ext ts,tsx",
            },
            **pkg,
        }, indent=2, ensure_ascii=False)

        # tsconfig
        files["tsconfig.json"] = self._generate_tsconfig()

        # vite.config
        files["vite.config.ts"] = self._generate_vite_config()

        return files

    def _generate_component(self, comp: ComponentIR, tokens: DesignTokens) -> str:
        """生成 React 组件"""
        pascal = self._to_pascal_case(comp.name)
        block = BEMNamer.block(comp.name)

        # Props 接口
        props_interface = self._generate_props_interface(comp)

        # 状态
        state_vars = self._generate_state_vars(comp)

        # 事件处理
        handlers = self._generate_handlers(comp)

        # JSX
        jsx = self._generate_jsx(comp)

        return f"""import React, {{ useState, useCallback, useEffect, useRef }} from 'react';
import styles from './{comp.name}.module.css';

{props_interface}

/**
 * {comp.name} 组件
 * {comp.description or '自动生成的组件'}
 */
export const {pascal}: React.FC<{pascal}Props> = ({
{self._generate_props_destructure(comp)}
}) => {{
{state_vars}
{handlers}

  return (
{jsx}
  );
}};

{pascal}.displayName = '{pascal}';
export default {pascal};
"""

    def _generate_props_interface(self, comp: ComponentIR) -> str:
        """生成 Props 接口"""
        lines = [f"export interface {self._to_pascal_case(comp.name)}Props {{"]
        for prop in comp.props:
            ts_type = self._to_ts_type(prop)
            optional = "?" if not prop.required else ""
            lines.append(f"  /** {prop.description or prop.name} */")
            lines.append(f"  {prop.name}{optional}: {ts_type};")
        # 常用 props
        lines.append("  /** 自定义类名 */")
        lines.append("  className?: string;")
        lines.append("  /** 子元素 */")
        lines.append("  children?: React.ReactNode;")
        lines.append("}")
        return "\n".join(lines)

    def _generate_props_destructure(self, comp: ComponentIR) -> str:
        """生成 Props 解构"""
        props = ["children", "className"]
        for prop in comp.props:
            default = ""
            if prop.default is not None:
                if isinstance(prop.default, bool):
                    default = f" = {'true' if prop.default else 'false'}"
                elif isinstance(prop.default, (int, float)):
                    default = f" = {prop.default}"
                elif isinstance(prop.default, str):
                    default = f" = '{prop.default}'"
            props.append(f"  {prop.name}{default}")
        return ",\n".join(props)

    def _generate_state_vars(self, comp: ComponentIR) -> str:
        """生成状态变量"""
        lines = []
        for s in comp.state:
            default = "false" if s.type == "boolean" else "''" if s.type == "string" else "null"
            lines.append(f'  const [{s.name}, set{self._to_pascal_case(s.name)}] = useState<{s.type}>({default});')
        if not lines:
            return ""
        return "\n".join(lines)

    def _generate_handlers(self, comp: ComponentIR) -> str:
        """生成事件处理函数"""
        lines = []
        for event in comp.events:
            handler = event.handler_name or f"handle{event.name.capitalize()}"
            lines.append(f"  const {handler} = useCallback(() => {{")
            lines.append(f"    // TODO: 实现 {event.name} 逻辑")
            lines.append(f"  }}), []);")
        if not lines:
            return ""
        return "\n".join(lines)

    def _generate_jsx(self, comp: ComponentIR) -> str:
        """生成 JSX"""
        block = BEMNamer.block(comp.name)
        tag = self._get_react_tag(comp)

        # 构建属性
        attrs = [f'className={{styles.{block}}}']
        if comp.aria:
            if comp.aria.role:
                attrs.append(f'role="{comp.aria.role}"')
            if comp.aria.aria_label:
                attrs.append(f'aria-label="{comp.aria.aria_label}"')
            if comp.aria.aria_expanded:
                attrs.append(':aria-expanded="false"')
            if comp.aria.aria_haspopup:
                attrs.append(f'aria-haspopup="{comp.aria.aria_haspopup}"')
            if comp.aria.tabindex >= 0:
                attrs.append(f'tabIndex={{{comp.aria.tabindex}}}')

        # 组件类型属性
        if comp.component_type == ComponentType.BUTTON:
            attrs.append('type="button"')
        elif comp.component_type == ComponentType.INPUT:
            attrs.append('type="text"')

        attr_str = "\n    ".join(attrs)

        # 子元素
        if comp.children:
            children = []
            for child in comp.children:
                child_jsx = self._render_child_jsx(child)
                children.append(child_jsx)
            children_str = "\n      ".join(children)
            return f"""    <{tag}
      {attr_str}
    >
      {children_str}
    </{tag}>"""
        else:
            text = self._get_text_content(comp)
            if text:
                return f"""    <{tag} {attr_str}>
      {text}
    </{tag}>"""
            else:
                return f"    <{tag} {attr_str} />"

    def _render_child_jsx(self, comp: ComponentIR) -> str:
        """渲染子元素 JSX"""
        block = BEMNamer.block(comp.name)
        tag = self._get_react_tag(comp)
        text = self._get_text_content(comp)

        if text:
            return f"<{tag} className={{styles.{block}}}>{text}</{tag}>"
        return f"<{tag} className={{styles.{block}}} />"

    def _get_react_tag(self, comp: ComponentIR) -> str:
        """获取 React 标签名"""
        tag_map = {
            SemanticTag.DIV: "div",
            SemanticTag.SPAN: "span",
            SemanticTag.P: "p",
            SemanticTag.A: "a",
            SemanticTag.BUTTON: "button",
            SemanticTag.INPUT: "input",
            SemanticTag.TEXTAREA: "textarea",
            SemanticTag.SELECT: "select",
            SemanticTag.HEADER: "header",
            SemanticTag.NAV: "nav",
            SemanticTag.MAIN: "main",
            SemanticTag.SECTION: "section",
            SemanticTag.ARTICLE: "article",
            SemanticTag.ASIDE: "aside",
            SemanticTag.FOOTER: "footer",
            SemanticTag.UL: "ul",
            SemanticTag.OL: "ol",
            SemanticTag.LI: "li",
            SemanticTag.H1: "h1",
            SemanticTag.H2: "h2",
            SemanticTag.H3: "h3",
            SemanticTag.H4: "h4",
            SemanticTag.H5: "h5",
            SemanticTag.H6: "h6",
            SemanticTag.IMG: "img",
            SemanticTag.TABLE: "table",
            SemanticTag.THEAD: "thead",
            SemanticTag.TBODY: "tbody",
            SemanticTag.TR: "tr",
            SemanticTag.TH: "th",
            SemanticTag.TD: "td",
            SemanticTag.FORM: "form",
            SemanticTag.FIELDSET: "fieldset",
            SemanticTag.LEGEND: "legend",
            SemanticTag.LABEL: "label",
            SemanticTag.DIALOG: "dialog",
            SemanticTag.STRONG: "strong",
            SemanticTag.EM: "em",
            SemanticTag.SMALL: "small",
            SemanticTag.CODE: "code",
            SemanticTag.PRE: "pre",
            SemanticTag.BLOCKQUOTE: "blockquote",
            SemanticTag.HR: "hr",
            SemanticTag.DETAILS: "details",
            SemanticTag.SUMMARY: "summary",
        }
        return tag_map.get(comp.semantic_tag, "div")

    def _generate_types(self, comp: ComponentIR) -> str:
        """生成类型定义文件"""
        pascal = self._to_pascal_case(comp.name)
        lines = [f"// {comp.name} 类型定义"]
        lines.append("")

        # Props 类型
        lines.append(f"export interface {pascal}Props {{")
        for prop in comp.props:
            ts_type = self._to_ts_type(prop)
            optional = "?" if not prop.required else ""
            lines.append(f"  {prop.name}{optional}: {ts_type};")
        lines.append("}")
        lines.append("")

        # 状态类型
        if comp.state:
            lines.append(f"export interface {pascal}State {{")
            for s in comp.state:
                lines.append(f"  {s.name}: {s.type};")
            lines.append("}")
            lines.append("")

        # 事件类型
        if comp.events:
            lines.append(f"export interface {pascal}Events {{")
            for e in comp.events:
                lines.append(f"  {e.name}: () => void;")
            lines.append("}")

        return "\n".join(lines)

    def _generate_hook(self, comp: ComponentIR) -> str:
        """生成自定义 Hook"""
        pascal = self._to_pascal_case(comp.name)
        hook_name = f"use{pascal}"

        sm = comp.interaction.state_machine if comp.interaction else None
        states = sm.states if sm else []
        transitions = sm.transitions if sm else []

        state_union = " | ".join(f"'{s}'" for s in states) if states else "string"
        initial = f"'{states[0]}'" if states else "'default'"
        lines = [
            f"import {{ useState, useCallback }} from 'react';",
            f"",
            f"export type {pascal}State = {state_union};",
            f"",
            f"export function {hook_name}(initialState: {pascal}State = {initial}) {{",
            f"  const [state, setState] = useState<{pascal}State>(initialState);",
            f"",
        ]

        for t in transitions:
            action_name = f"to{self._to_pascal_case(t.to_state)}"
            lines.append(f"  const {action_name} = useCallback(() => {{")
            lines.append(f"    setState('{t.to_state}');")
            lines.append(f"  }}, []);")

        lines.append("")
        lines.append(f"  return {{")
        lines.append(f"    state,")
        lines.append(f"    setState,")
        for t in transitions:
            action_name = f"to{self._to_pascal_case(t.to_state)}"
            lines.append(f"    {action_name},")
        lines.append(f"  }};")
        lines.append(f"}}")

        return "\n".join(lines)

    def _generate_page(self, page, ir: DesignIR) -> str:
        """生成页面组件"""
        pascal = self._to_pascal_case(page.name)
        imports = []
        components = []
        for comp in page.components:
            imp = self._to_pascal_case(comp.name)
            imports.append(f'import {{ {imp} }} from "../components/{comp.name}";')
            components.append(f"      <{imp} />")

        return f"""import React from 'react';
{chr(10).join(imports)}

export default function {pascal}Page() {{
  return (
    <main className="page-{page.name.lower()}">
{chr(10).join(components)}
    </main>
  );
}}
"""

    def _generate_app(self, ir: DesignIR) -> str:
        """生成 App 入口"""
        imports = []
        routes = []
        for page in ir.pages:
            pascal = self._to_pascal_case(page.name)
            imports.append(f"import {pascal}Page from './pages/{page.name}';")
            routes.append(f'            <Route path="{page.route or "/" + page.name.lower()}" element={{<{pascal}Page />}} />')

        return f"""import React from 'react';
import {{ BrowserRouter, Routes, Route }} from 'react-router-dom';
{chr(10).join(imports)}

export default function App() {{
  return (
    <BrowserRouter>
      <Routes>
{chr(10).join(routes)}
      </Routes>
    </BrowserRouter>
  );
}}
"""

    def _generate_tsconfig(self) -> str:
        return """{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}"""

    def _generate_vite_config(self) -> str:
        return """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react()],
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

    def _get_text_content(self, comp: ComponentIR) -> str:
        """获取文本内容"""
        return comp.design_styles.get("text", "") or ""
