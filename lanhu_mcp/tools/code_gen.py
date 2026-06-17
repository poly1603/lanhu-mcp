"""框架代码生成增强 - 基于设计分析结果生成特定框架的组件代码"""
import re
from typing import Optional


def generate_framework_code(
    html_code: str,
    framework: str = 'html',
    styling: str = 'inline',
    component_name: str = 'DesignComponent',
    design_tokens: dict = None,
) -> dict:
    """
    将 HTML+CSS 设计代码转换为特定框架的组件代码。

    Args:
        html_code: 从设计稿生成的 HTML+CSS 代码
        framework: 目标框架 (html/react/vue/flutter/svelte)
        styling: 样式方案 (inline/css-modules/tailwind/styled-components/scss)
        component_name: 组件名称
        design_tokens: 设计令牌（可选）

    Returns:
        包含 files 列表的字典
    """
    if framework == 'react':
        return _generate_react(html_code, styling, component_name, design_tokens)
    elif framework == 'vue':
        return _generate_vue(html_code, styling, component_name, design_tokens)
    elif framework == 'flutter':
        return _generate_flutter(html_code, component_name, design_tokens)
    elif framework == 'svelte':
        return _generate_svelte(html_code, styling, component_name, design_tokens)
    else:
        return _generate_html(html_code, component_name, design_tokens)


def _extract_css_and_html(html_code: str) -> tuple:
    """从 HTML 代码中提取 CSS 和 HTML 内容"""
    style_match = re.search(r'<style[^>]*>(.*?)</style>', html_code, re.DOTALL)
    css = style_match.group(1).strip() if style_match else ''

    body_match = re.search(r'<body[^>]*>(.*?)</body>', html_code, re.DOTALL)
    body = body_match.group(1).strip() if body_match else html_code

    return css, body


def _css_to_react_style(css: str) -> str:
    """将 CSS 属性转换为 React style 对象"""
    lines = []
    for line in css.split('\n'):
        line = line.strip()
        if not line or line.startswith('.') or line.startswith('}') or line.startswith('{'):
            continue
        # 去除分号
        line = line.rstrip(';')
        # 转换属性名：font-size → fontSize
        parts = line.split(': ', 1)
        if len(parts) == 2:
            prop = parts[0].strip()
            val = parts[1].strip()
            # camelCase
            camel = re.sub(r'-([a-z])', lambda m: m.group(1).upper(), prop)
            lines.append(f'      {camel}: \'{val}\',')

    return '\n'.join(lines) if lines else ''


def _generate_react(html_code: str, styling: str, name: str, tokens: dict) -> dict:
    """生成 React 组件代码"""
    css, body = _extract_css_and_html(html_code)

    # 简化HTML为JSX
    jsx = _html_to_jsx(body)

    if styling == 'css-modules':
        css_content = css
        component = (
            "import styles from './" + name + ".module.css';\n"
            "\n"
            "export default function " + name + "() {\n"
            "  return (\n"
            '    <div className={styles.container}>\n'
            + jsx + "\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        )
        return {
            'framework': 'react',
            'styling': 'css-modules',
            'files': [
                {'filename': name + '.tsx', 'content': component},
                {'filename': name + '.module.css', 'content': css_content},
            ],
        }

    elif styling == 'tailwind':
        component = (
            "export default function " + name + "() {\n"
            "  return (\n"
            '    <div className="relative">\n'
            + jsx + "\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        )
        return {
            'framework': 'react',
            'styling': 'tailwind',
            'files': [
                {'filename': name + '.tsx', 'content': component},
            ],
        }

    else:
        # inline style
        style_obj = _css_to_react_style(css)
        component = (
            "export default function " + name + "() {\n"
            "  const containerStyle = {\n"
            "    position: 'relative',\n"
            "  };\n"
            "\n"
            "  return (\n"
            "    <div style={containerStyle}>\n"
            + jsx + "\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        )
        return {
            'framework': 'react',
            'styling': 'inline',
            'files': [
                {'filename': name + '.tsx', 'content': component},
            ],
        }


def _generate_vue(html_code: str, styling: str, name: str, tokens: dict) -> dict:
    """生成 Vue SFC 组件代码"""
    css, body = _extract_css_and_html(html_code)
    template = _html_to_vue_template(body)

    component = (
        "<template>\n"
        + template + "\n"
        "</template>\n"
        "\n"
        '<script setup lang="ts">\n'
        "</script>\n"
        "\n"
        "<style scoped>\n"
        + css + "\n"
        "</style>\n"
    )
    return {
        'framework': 'vue',
        'styling': 'scoped',
        'files': [
            {'filename': name + '.vue', 'content': component},
        ],
    }


def _generate_flutter(html_code: str, name: str, tokens: dict) -> dict:
    """生成 Flutter Widget 代码"""
    css, body = _extract_css_and_html(html_code)
    # 简化转换
    widget = (
        "import 'package:flutter/material.dart';\n"
        "\n"
        "class " + name + " extends StatelessWidget {\n"
        "  const " + name + "({super.key});\n"
        "\n"
        "  @override\n"
        "  Widget build(BuildContext context) {\n"
        "    return Scaffold(\n"
        "      body: SingleChildScrollView(\n"
        "        child: Column(\n"
        "          children: [\n"
        "            // TODO: 从 HTML+CSS 转换布局\n"
        "            // 参考原始 CSS 中的尺寸、颜色、间距值\n"
        "          ],\n"
        "        ),\n"
        "      ),\n"
        "    );\n"
        "  }\n"
        "}\n"
    )
    return {
        'framework': 'flutter',
        'files': [
            {'filename': name.lower() + '.dart', 'content': widget},
        ],
    }


def _generate_svelte(html_code: str, styling: str, name: str, tokens: dict) -> dict:
    """生成 Svelte 组件代码"""
    css, body = _extract_css_and_html(html_code)
    template = _html_to_svelte_template(body)

    component = (
        template + "\n"
        "\n"
        "<style>\n"
        + css + "\n"
        "</style>\n"
    )
    return {
        'framework': 'svelte',
        'files': [
            {'filename': name + '.svelte', 'content': component},
        ],
    }


def _generate_html(html_code: str, name: str, tokens: dict) -> dict:
    """返回原始 HTML"""
    return {
        'framework': 'html',
        'files': [
            {'filename': name.lower() + '.html', 'content': html_code},
        ],
    }


def _html_to_jsx(html: str) -> str:
    """简单 HTML → JSX 转换"""
    result = html
    # class → className
    result = re.sub(r'\bclass=', 'className=', result)
    # for → htmlFor
    result = re.sub(r'\bfor=', 'htmlFor=', result)
    return result


def _html_to_vue_template(html: str) -> str:
    """简单 HTML → Vue template 转换"""
    return html


def _html_to_svelte_template(html: str) -> str:
    """简单 HTML → Svelte template 转换"""
    return html
