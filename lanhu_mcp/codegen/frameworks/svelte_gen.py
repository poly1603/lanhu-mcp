"""
Svelte Component Generator

生成 Svelte 3/4 组件代码：
- <script lang="ts"> + TypeScript
- <div class="bem-name"> 语义化模板
- <style> scoped BEM 样式
- $: 响应式声明
- onMount / onDestroy 生命周期
- createEventDispatcher 事件
- $$props / $$restProps 透传
"""
from typing import Dict, List
from ..ir import (
    DesignIR, ComponentIR, ComponentType, SemanticTag,
    StyleSpec, CSSRule, PropSpec, StateSpec, EventSpec,
    Framework, DesignTokens, A11ySpec,
)
from ..style_system import BEMNamer, CSSVariableGenerator


class SvelteGenerator:
    """Svelte 组件代码生成器"""

    def generate(self, ir: DesignIR) -> Dict[str, str]:
        """生成 Svelte 项目文件"""
        files: Dict[str, str] = {}

        # package.json
        files["package.json"] = self._generate_package_json(ir)

        # vite.config.ts
        files["vite.config.ts"] = self._generate_vite_config(ir)

        # svelte.config.js
        files["svelte.config.js"] = self._generate_svelte_config()

        # tsconfig.json
        files["tsconfig.json"] = self._generate_tsconfig()

        # index.html
        files["index.html"] = self._generate_index_html(ir)

        # src/main.ts
        files["src/main.ts"] = "import App from './App.svelte';\n\nconst app = new App({ target: document.getElementById('app')! });\n\nexport default app;"

        # src/App.svelte
        files["src/App.svelte"] = self._generate_app_svelte(ir)

        # src/lib/components/*.svelte
        for comp in ir.components:
            svelte_name = self._pascal(comp.name)
            files[f"src/lib/components/{svelte_name}.svelte"] = self._generate_component_svelte(ir, comp)

        # src/lib/stores/theme.ts
        files["src/lib/stores/theme.ts"] = self._generate_theme_store(ir)

        return files

    # ------------------------------------------------------------------
    # package.json
    # ------------------------------------------------------------------
    def _generate_package_json(self, ir: DesignIR) -> str:
        deps = self._svelte_deps(ir)
        deps_json = ",\n".join(f'    "{d}": "{v}"' for d, v in sorted(deps.items()))

        return f"""{{
  "name": "{ir.name.lower().replace(' ', '-').replace('_', '-')}",
  "version": "1.0.0",
  "private": true,
  "scripts": {{
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "check": "svelte-check --tsconfig ./tsconfig.json"
  }},
  "dependencies": {{
{deps_json}
  }},
  "devDependencies": {{
    "@sveltejs/vite-plugin-svelte": "^3.0.0",
    "@tsconfig/svelte": "^5.0.0",
    "svelte": "^4.2.0",
    "svelte-check": "^3.6.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0"
  }}
}}
"""

    def _svelte_deps(self, ir: DesignIR) -> dict:
        deps = {}
        for comp in ir.components:
            if comp.component_type == ComponentType.DATE_PICKER:
                deps["date-fns"] = "^3.0.0"
            if comp.component_type == ComponentType.CAROUSEL:
                deps["embla-carousel-svelte"] = "^8.0.0"
            if comp.component_type == ComponentType.TABLE:
                deps["tanstack-table-core"] = "^8.0.0"
        for dep in ir.dependencies:
            if dep.name == "form":
                deps["svelte-forms-lib"] = "^2.0.0"
        return deps

    # ------------------------------------------------------------------
    # vite.config.ts
    # ------------------------------------------------------------------
    def _generate_vite_config(self, ir: DesignIR) -> str:
        return """import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    host: true,
  },
});
"""

    # ------------------------------------------------------------------
    # svelte.config.js
    # ------------------------------------------------------------------
    def _generate_svelte_config(self) -> str:
        return """import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
  preprocess: vitePreprocess(),
};
"""

    # ------------------------------------------------------------------
    # tsconfig.json
    # ------------------------------------------------------------------
    def _generate_tsconfig(self) -> str:
        return """{
  "extends": "@tsconfig/svelte/tsconfig.json",
  "compilerOptions": {
    "target": "ESNext",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "resolveJsonModule": true,
    "allowJs": true,
    "checkJs": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "strict": true,
    "noEmit": true
  },
  "include": ["src/**/*.d.ts", "src/**/*.ts", "src/**/*.svelte"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
"""

    # ------------------------------------------------------------------
    # index.html
    # ------------------------------------------------------------------
    def _generate_index_html(self, ir: DesignIR) -> str:
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{ir.name}</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
"""

    # ------------------------------------------------------------------
    # src/App.svelte
    # ------------------------------------------------------------------
    def _generate_app_svelte(self, ir: DesignIR) -> str:
        imports = []
        usages = []
        for comp in ir.components:
            sn = self._pascal(comp.name)
            imports.append(f"import {sn} from './lib/components/{sn}.svelte';")
            usages.append(f"  <{sn} />")

        imports_str = "\n".join(imports)
        usages_str = "\n".join(usages)

        return f"""<script lang="ts">
{imports_str}
</script>

<main class="app">
{usages_str}
</main>

<style>
  :root {{
    --color-primary: #1677ff;
    --color-error: #ff4d4f;
    --spacing-4: 16px;
    --spacing-8: 32px;
    --radius-md: 4px;
    --radius-lg: 8px;
  }}

  .app {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px;
  }}
</style>
"""

    # ------------------------------------------------------------------
    # 单个 Svelte 组件
    # ------------------------------------------------------------------
    def _generate_component_svelte(self, ir: DesignIR, comp: ComponentIR) -> str:
        svelte_name = self._pascal(comp.name)
        bem_block = BEMNamer.block(comp.name)

        # <script>
        script = self._generate_script(comp)

        # <template> markup
        template = self._generate_template(comp, bem_block)

        # <style>
        style = self._generate_style(comp, bem_block)

        return f"""<script lang="ts">
{script}
</script>

{template}

<style>
{style}
</style>
"""

    # ------------------------------------------------------------------
    # Theme store
    # ------------------------------------------------------------------
    def _generate_theme_store(self, ir: DesignIR) -> str:
        """生成 Svelte 主题 store"""
        return """import { writable } from 'svelte/store';

export const theme = writable({
  primary: '#1677ff',
  error: '#ff4d4f',
  spacing: { 4: '16px', 8: '32px' },
  radius: { md: '4px', lg: '8px' },
  font: {
    family: 'PingFang SC, -apple-system, sans-serif',
    sizes: { sm: '12px', base: '14px', lg: '16px', xl: '22px', xxl: '28px' },
  },
});

export function toggleDarkMode() {
  theme.update(t => ({ ...t, dark: !t.dark }));
}
"""

    # ------------------------------------------------------------------
    # Script block
    # ------------------------------------------------------------------
    def _generate_script(self, comp: ComponentIR) -> str:
        lines = []

        # imports
        if comp.component_type in (ComponentType.INPUT, ComponentType.TEXTAREA):
            lines.append("import { createEventDispatcher } from 'svelte';")
            lines.append("")
            lines.append("const dispatch = createEventDispatcher();")

        # Props
        if comp.props:
            for prop in comp.props:
                ts_type = self._ts_type(prop.type)
                default = self._ts_default(prop)
                lines.append(f"export let {prop.name}: {ts_type}{default};")
            lines.append("")

        # State
        if comp.interaction and comp.interaction.state_machine:
            sm = comp.interaction.state_machine
            states_str = " | ".join(f"'{s}'" for s in sm.states) if sm.states else "string"
            lines.append(f"let state: {states_str} = '{sm.initial_state}';")
            lines.append("")

        # 特有状态
        if comp.component_type in (ComponentType.CHECKBOX,):
            lines.append("let checked = false;")
        if comp.component_type == ComponentType.SWITCH:
            lines.append("let switched = false;")
        if comp.component_type == ComponentType.CAROUSEL:
            lines.append("let currentIndex = 0;")
        if comp.component_type == ComponentType.TABS:
            lines.append("let selectedIndex = 0;")
        if comp.component_type == ComponentType.ACCORDION:
            lines.append("let expanded = false;")
        if comp.component_type == ComponentType.SLIDER:
            lines.append("let sliderValue = 0.5;")

        # Event handlers
        if comp.events:
            for event in comp.events:
                handler = event.handler_name or f"handle{event.name.capitalize()}"
                lines.append(f"function {handler}() {{")
                if comp.interaction and comp.interaction.state_machine:
                    lines.append(f"  // TODO: state transition for {event.name}")
                lines.append(f"  dispatch('{event.name}');")
                lines.append("}")
                lines.append("")

        return "\n".join(lines)

    def _ts_type(self, hint: str) -> str:
        mapping = {
            "str": "string",
            "string": "string",
            "int": "number",
            "integer": "number",
            "float": "number",
            "double": "number",
            "bool": "boolean",
            "boolean": "boolean",
            "list": "any[]",
            "array": "any[]",
            "map": "Record<string, any>",
            "object": "Record<string, any>",
            "function": "() => void",
            "callback": "() => void",
        }
        return mapping.get(hint.lower(), "any")

    def _ts_default(self, prop: PropSpec) -> str:
        if prop.default is not None:
            v = prop.default
            if isinstance(v, str):
                return f" = '{v}'"
            if isinstance(v, bool):
                return f" = {'true' if v else 'false'}"
            if isinstance(v, (int, float)):
                return f" = {v}"
        if prop.type.lower() in ("bool", "boolean"):
            return " = false"
        if prop.type.lower() in ("int", "integer", "float", "double"):
            return " = 0"
        if prop.type.lower() in ("list", "array"):
            return " = []"
        if prop.type.lower() in ("map", "object"):
            return " = {}"
        return " = ''"

    # ------------------------------------------------------------------
    # Template block
    # ------------------------------------------------------------------
    def _generate_template(self, comp: ComponentIR, bem_block: str) -> str:
        comp_type = comp.component_type
        aria = self._aria_attrs(comp)
        indent = ""

        if comp_type == ComponentType.BUTTON:
            text = self._get_text(comp)
            return f"""<button
  class="{bem_block}"
  type="button"{aria}
  on:click
>
  {text}
</button>"""

        if comp_type == ComponentType.INPUT:
            hint = self._get_text(comp) or "请输入"
            return f"""<div class="{bem_block}">
  <input
    class="{bem_block}__input"
    type="text"
    placeholder="{hint}"{aria}
    on:input
    on:change
  />
</div>"""

        if comp_type == ComponentType.TEXT:
            text = self._get_text(comp)
            return f'<span class="{bem_block}">{text}</span>'

        if comp_type in (ComponentType.CONTAINER, ComponentType.CARD):
            children = "\n".join(
                self._generate_template(ch, BEMNamer.block(ch.name))
                for ch in comp.children
            ) if comp.children else f'  <div class="{bem_block}__empty"></div>'
            return f"""<div class="{bem_block}"{aria}>
{children}
</div>"""

        if comp_type == ComponentType.MODAL:
            return (
                "{#if open}\n"
                f'  <div class="{bem_block}" role="dialog" aria-modal="true"{aria}>\n'
                f'    <div class="{bem_block}__overlay" on:click={{close}}></div>\n'
                f'    <div class="{bem_block}__content">\n'
                f'      <div class="{bem_block}__header">\n'
                '        <slot name="header" />\n'
                f'        <button class="{bem_block}__close" on:click={{close}} aria-label="关闭">×</button>\n'
                f'      </div>\n'
                f'      <div class="{bem_block}__body">\n'
                '        <slot />\n'
                f'      </div>\n'
                f'      <div class="{bem_block}__footer">\n'
                '        <slot name="footer" />\n'
                f'      </div>\n'
                f'    </div>\n'
                f'  </div>\n'
                "{/if}"
            )

        if comp_type == ComponentType.TABS:
            tab_items = ""
            for i, child in enumerate(comp.children):
                tab_items += f'  <button class="{bem_block}__tab" class:active={{{{selectedIndex === {i}}}}} on:click={{{{() => selectedIndex = {i}}}}}>\n    Tab {i + 1}\n  </button>\n'
            tab_parts = []
            for i, ch in enumerate(comp.children):
                tab_parts.append("{{#if selectedIndex === " + str(i) + "}}")
                tab_parts.append(f'  <div class="{bem_block}__panel">')
                tab_parts.append(f"    <!-- {ch.name} -->")
                tab_parts.append("  </div>")
                tab_parts.append("{{/if}}")
            tab_content = "\n".join(tab_parts) if comp.children else "<!-- no tabs -->"
            return (
                f'<div class="{bem_block}"{aria}>\n'
                f'  <div class="{bem_block}__header">\n'
                f"{tab_items}  </div>\n"
                f'  <div class="{bem_block}__panels">\n'
                f"{tab_content}\n"
                f"  </div>\n"
                f"</div>"
            )

        if comp_type == ComponentType.ACCORDION:
            return (
                f'<div class="{bem_block}"{aria}>\n'
                f'  <button class="{bem_block}__trigger" on:click={{{{() => expanded = !expanded}}}}>\n'
                '    <slot name="header" />\n'
                f'    <span class="{bem_block}__icon" class:expanded={{{{expanded}}}}>.</span>\n'
                "  </button>\n"
                "  {{#if expanded}}\n"
                f'    <div class="{bem_block}__content">\n'
                "      <slot />\n"
                f"    </div>\n"
                "  {{/if}}\n"
                f"</div>"
            )

        if comp_type == ComponentType.TABLE:
            return (
                f'<div class="{bem_block}"{aria}>\n'
                f'  <table class="{bem_block}__table">\n'
                f'    <thead class="{bem_block}__head">\n'
                "      <tr>\n"
                "        <th>列 1</th>\n"
                "        <th>列 2</th>\n"
                "        <th>列 3</th>\n"
                "      </tr>\n"
                f"    </thead>\n"
                f'    <tbody class="{bem_block}__body">\n'
                "      {{#each rows as row}}\n"
                f'        <tr class="{bem_block}__row">\n'
                "          <td>{{row.col1}}</td>\n"
                "          <td>{{row.col2}}</td>\n"
                "          <td>{{row.col3}}</td>\n"
                "        </tr>\n"
                "      {{/each}}\n"
                f"    </tbody>\n"
                f"  </table>\n"
                f"</div>"
            )

        if comp_type == ComponentType.CAROUSEL:
            return (
                f'<div class="{bem_block}"{aria}>\n'
                f'  <div class="{bem_block}__track" style="transform: translateX(-{{currentIndex * 100}}%)">\n'
                "    <slot />\n"
                "  </div>\n"
                f'  <button class="{bem_block}__prev" on:click={{{{prev}}}} aria-label="上一张">‹</button>\n'
                f'  <button class="{bem_block}__next" on:click={{{{next}}}} aria-label="下一张">›</button>\n'
                f'  <div class="{bem_block}__dots">\n'
                "    {{#each items as _, i}}\n"
                f'      <button class="dot" class:active={{{{currentIndex === i}}}} on:click={{{{() => currentIndex = i}}}}></button>\n'
                "    {{/each}}\n"
                f"  </div>\n"
                f"</div>"
            )

        if comp_type in (ComponentType.CHECKBOX,):
            return f"""<label class="{bem_block}"{aria}>
  <input type="checkbox" bind:checked={{checked}} on:change />
  <span class="{bem_block}__mark"></span>
  <span class="{bem_block}__label"><slot /></span>
</label>"""

        if comp_type == ComponentType.SWITCH:
            return f"""<button
  class="{bem_block}"
  role="switch"
  aria-checked={{switched}}{aria}
  on:click={{() => switched = !switched}}
>
  <span class="{bem_block}__thumb"></span>
</button>"""

        if comp_type == ComponentType.SELECT:
            return f"""<select class="{bem_block}"{aria} bind:value={{selectedValue}}>
  {{#each options as opt}}
    <option value={{opt.value}}>{{opt.label}}</option>
  {{/each}}
</select>"""

        # 默认 div
        children = "\n".join(
            self._generate_template(ch, BEMNamer.block(ch.name))
            for ch in comp.children
        ) if comp.children else ""

        return f"""<div class="{bem_block}"{aria}>
{children}
</div>"""

    def _aria_attrs(self, comp: ComponentIR) -> str:
        parts = []
        if comp.aria:
            if comp.aria.role and comp.aria.role not in ("button",):
                parts.append(f' role="{comp.aria.role}"')
            if comp.aria.aria_label:
                parts.append(f' aria-label="{comp.aria.aria_label}"')
            if comp.aria.aria_describedby:
                parts.append(f' aria-describedby="{comp.aria.aria_describedby}"')
            if comp.aria.aria_expanded:
                parts.append(f' aria-expanded="{comp.aria.aria_expanded}"')
            if comp.aria.aria_controls:
                parts.append(f' aria-controls="{comp.aria.aria_controls}"')
            if comp.aria.aria_haspopup:
                parts.append(f' aria-haspopup="{comp.aria.aria_haspopup}"')
            if comp.aria.tabindex >= 0:
                parts.append(f' tabindex="{comp.aria.tabindex}"')
        return "".join(parts)

    # ------------------------------------------------------------------
    # Style block
    # ------------------------------------------------------------------
    def _generate_style(self, comp: ComponentIR, bem_block: str) -> str:
        lines = []
        comp_type = comp.component_type

        # 基础样式
        lines.append(f".{bem_block} {{")
        lines.append("  /* base */")
        if comp.design_position.get("width"):
            lines.append(f"  width: {comp.design_position['width']}px;")
        if comp.design_position.get("height"):
            lines.append(f"  height: {comp.design_position['height']}px;")
        radius = self._get_radius(comp)
        if radius:
            lines.append(f"  border-radius: {radius}px;")
        bg = self._get_bg_color(comp)
        if bg and bg != "transparent":
            lines.append(f"  background-color: {bg};")
        lines.append("}")
        lines.append("")

        # 按钮
        if comp_type == ComponentType.BUTTON:
            color = self._get_color(comp, "#1677ff")
            lines.append(f".{bem_block}:hover {{")
            lines.append(f"  filter: brightness(1.1);")
            lines.append(f"}}")
            lines.append(f".{bem_block}:focus-visible {{")
            lines.append(f"  outline: 2px solid {color};")
            lines.append(f"  outline-offset: 2px;")
            lines.append(f"}}")
            lines.append(f".{bem_block}:disabled {{")
            lines.append(f"  opacity: 0.5;")
            lines.append(f"  cursor: not-allowed;")
            lines.append(f"}}")
            lines.append("")

        # 输入框
        if comp_type in (ComponentType.INPUT, ComponentType.TEXTAREA):
            lines.append(f".{bem_block}__input {{")
            lines.append("  width: 100%;")
            lines.append("  padding: 8px 12px;")
            lines.append("  border: 1px solid #d9d9d9;")
            lines.append(f"  border-radius: {self._get_radius(comp)}px;")
            lines.append("  font-size: 14px;")
            lines.append("  transition: border-color 0.2s;")
            lines.append("}}")
            lines.append(f".{bem_block}__input:focus {{")
            lines.append("  border-color: #1677ff;")
            lines.append("  outline: none;")
            lines.append("  box-shadow: 0 0 0 2px rgba(22,119,255,0.1);")
            lines.append("}}")
            lines.append("")

        # 模态框
        if comp_type == ComponentType.MODAL:
            lines.append(f".{bem_block} {{")
            lines.append("  position: fixed;")
            lines.append("  inset: 0;")
            lines.append("  z-index: 1000;")
            lines.append("  display: flex;")
            lines.append("  align-items: center;")
            lines.append("  justify-content: center;")
            lines.append("}}")
            lines.append(f".{bem_block}__overlay {{")
            lines.append("  position: absolute;")
            lines.append("  inset: 0;")
            lines.append("  background: rgba(0,0,0,0.5);")
            lines.append("}}")
            lines.append(f".{bem_block}__content {{")
            lines.append("  position: relative;")
            lines.append("  background: white;")
            lines.append("  border-radius: 8px;")
            lines.append("  padding: 24px;")
            lines.append("  max-width: 500px;")
            lines.append("  width: 90%;")
            lines.append("  box-shadow: 0 8px 32px rgba(0,0,0,0.15);")
            lines.append("}}")
            lines.append("")

        # 标签页
        if comp_type == ComponentType.TABS:
            lines.append(f".{bem_block}__header {{")
            lines.append("  display: flex;")
            lines.append("  border-bottom: 1px solid #e8e8e8;")
            lines.append("}}")
            lines.append(f".{bem_block}__tab {{")
            lines.append("  padding: 12px 24px;")
            lines.append("  border: none;")
            lines.append("  background: none;")
            lines.append("  cursor: pointer;")
            lines.append("  border-bottom: 2px solid transparent;")
            lines.append("  transition: all 0.2s;")
            lines.append("}}")
            lines.append(f".{bem_block}__tab.active {{")
            lines.append("  border-bottom-color: #1677ff;")
            lines.append("  color: #1677ff;")
            lines.append("}}")
            lines.append("")

        # 手风琴
        if comp_type == ComponentType.ACCORDION:
            lines.append(f".{bem_block}__trigger {{")
            lines.append("  display: flex;")
            lines.append("  justify-content: space-between;")
            lines.append("  align-items: center;")
            lines.append("  width: 100%;")
            lines.append("  padding: 12px 16px;")
            lines.append("  border: none;")
            lines.append("  background: none;")
            lines.append("  cursor: pointer;")
            lines.append("  text-align: left;")
            lines.append("}}")
            lines.append(f".{bem_block}__icon {{")
            lines.append("  transition: transform 0.2s;")
            lines.append("}}")
            lines.append(f".{bem_block}__icon.expanded {{")
            lines.append("  transform: rotate(180deg);")
            lines.append("}}")
            lines.append("")

        # 表格
        if comp_type == ComponentType.TABLE:
            lines.append(f".{bem_block}__table {{")
            lines.append("  width: 100%;")
            lines.append("  border-collapse: collapse;")
            lines.append("}}")
            lines.append(f".{bem_block}__table th,")
            lines.append(f".{bem_block}__table td {{")
            lines.append("  padding: 12px;")
            lines.append("  border-bottom: 1px solid #f0f0f0;")
            lines.append("  text-align: left;")
            lines.append("}}")
            lines.append(f".{bem_block}__table th {{")
            lines.append("  font-weight: 600;")
            lines.append("  background: #fafafa;")
            lines.append("}}")
            lines.append("")

        # 轮播
        if comp_type == ComponentType.CAROUSEL:
            lines.append(f".{bem_block} {{")
            lines.append("  position: relative;")
            lines.append("  overflow: hidden;")
            lines.append("}}")
            lines.append(f".{bem_block}__track {{")
            lines.append("  display: flex;")
            lines.append("  transition: transform 0.3s ease;")
            lines.append("}}")
            lines.append(f".{bem_block}__prev,")
            lines.append(f".{bem_block}__next {{")
            lines.append("  position: absolute;")
            lines.append("  top: 50%;")
            lines.append("  transform: translateY(-50%);")
            lines.append("  background: rgba(255,255,255,0.8);")
            lines.append("  border: none;")
            lines.append("  border-radius: 50%;")
            lines.append("  width: 32px;")
            lines.append("  height: 32px;")
            lines.append("  cursor: pointer;")
            lines.append("  z-index: 1;")
            lines.append("}}")
            lines.append(f".{bem_block}__prev {{ left: 8px; }}")
            lines.append(f".{bem_block}__next {{ right: 8px; }}")
            lines.append(f".{bem_block}__dots {{")
            lines.append("  display: flex;")
            lines.append("  justify-content: center;")
            lines.append("  gap: 8px;")
            lines.append("  margin-top: 12px;")
            lines.append("}}")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------
    def _pascal(self, name: str) -> str:
        return "".join(w.capitalize() for w in name.replace("-", "_").split("_"))

    def _get_text(self, comp: ComponentIR) -> str:
        return comp.design_styles.get("text", "")

    def _get_color(self, comp: ComponentIR, default: str = "#000000") -> str:
        color = comp.design_styles.get("color", "")
        if color and (color.startswith("#") or color.startswith("rgb")):
            return color
        return default

    def _get_bg_color(self, comp: ComponentIR) -> str:
        color = comp.design_styles.get("backgroundColor", "")
        if color:
            return color
        return "transparent"

    def _get_radius(self, comp: ComponentIR) -> int:
        radius = comp.design_styles.get("borderRadius", comp.design_styles.get("radius", 0))
        if isinstance(radius, (int, float)):
            return int(radius)
        return 0


def generate(ir: DesignIR) -> Dict[str, str]:
    """便捷入口"""
    return SvelteGenerator().generate(ir)
