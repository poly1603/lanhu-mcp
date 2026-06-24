"""
Flutter Widget Tree Generator

生成 Flutter/Dart Widget 树代码：
- StatelessWidget / StatefulWidget
- SizedBox, Container, Padding, Center, Align
- Text, TextField, ElevatedButton, IconButton
- ListView, GridView
- Column, Row, Stack, Wrap
- MediaQuery 响应式
- Semantics 无障碍
"""
from typing import Dict, List
from ..ir import (
    DesignIR, ComponentIR, ComponentType, SemanticTag,
    StyleSpec, CSSRule, PropSpec, StateSpec, EventSpec,
    Framework, DesignTokens, A11ySpec,
)


class FlutterGenerator:
    """Flutter Widget 树代码生成器"""

    def generate(self, ir: DesignIR) -> Dict[str, str]:
        """生成 Flutter 项目文件"""
        files: Dict[str, str] = {}

        # pubspec.yaml
        files["pubspec.yaml"] = self._generate_pubspec(ir)

        # main.dart
        files["lib/main.dart"] = self._generate_main(ir)

        # 每个顶层组件生成一个 widget 文件
        for comp in ir.components:
            widget_name = self._pascal(comp.name)
            files[f"lib/widgets/{widget_name}.dart"] = self._generate_widget_file(ir, comp)

        # theme.dart
        files["lib/theme.dart"] = self._generate_theme(ir)

        return files

    # ------------------------------------------------------------------
    # pubspec.yaml
    # ------------------------------------------------------------------
    def _generate_pubspec(self, ir: DesignIR) -> str:
        deps = self._flutter_deps(ir)
        deps_yaml = "\n".join(f"  {d}:" for d in sorted(deps))

        return f"""name: {ir.name.lower().replace(' ', '_').replace('-', '_')}
description: Generated from Lanhu design
version: 1.0.0+1

environment:
  sdk: '>=3.0.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
{deps_yaml}

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^3.0.0

flutter:
  uses-material-design: true
"""

    def _flutter_deps(self, ir: DesignIR) -> set:
        deps = set()
        for dep in ir.dependencies:
            mapping = {
                "swiper": "card_swiper",
                "floating": "flutter_portal",
            }
            flutter_name = mapping.get(dep.name)
            if flutter_name:
                deps.add(flutter_name)
        # 根据组件类型自动引入
        for comp in ir.components:
            if comp.component_type == ComponentType.DATE_PICKER:
                deps.add("intl: ^0.19.0")
            if comp.component_type == ComponentType.CAROUSEL:
                deps.add("card_swiper: ^3.0.0")
        return deps

    # ------------------------------------------------------------------
    # main.dart
    # ------------------------------------------------------------------
    def _generate_main(self, ir: DesignIR) -> str:
        imports = []
        widget_names = []
        for comp in ir.components:
            wn = self._pascal(comp.name)
            imports.append(f"import 'widgets/{wn}.dart';")
            widget_names.append(wn)

        imports_str = "\n".join(imports)

        if len(widget_names) == 1:
            home = widget_names[0]
        else:
            # 用 Column 嵌套多个顶层组件
            children = "\n".join(f"            const {w}()," for w in widget_names)
            home = f"""Scaffold(
          body: SingleChildScrollView(
            child: Column(
              children: [
{children}
              ],
            ),
          ),
        )"""

        return f"""import 'package:flutter/material.dart';
import 'theme.dart';
{imports_str}

void main() {{
  runApp(const MyApp());
}}

class MyApp extends StatelessWidget {{
  const MyApp({{super.key}});

  @override
  Widget build(BuildContext context) {{
    return MaterialApp(
      title: '{ir.name}',
      theme: appTheme,
      home: {home},
      debugShowCheckedModeBanner: false,
    );
  }}
}}
"""

    # ------------------------------------------------------------------
    # theme.dart
    # ------------------------------------------------------------------
    def _generate_theme(self, ir: DesignIR) -> str:
        """生成 Flutter 主题文件"""
        primary = self._get_color(ir.components[0] if ir.components else ComponentIR(name="", component_type=ComponentType.CONTAINER), "#1677ff") if ir.components else "#1677ff"
        return f"""import 'package:flutter/material.dart';

final appTheme = ThemeData(
  colorScheme: ColorScheme.fromSeed(
    seedColor: Color(0x{primary.lstrip('#')}),
    brightness: Brightness.light,
  ),
  useMaterial3: true,
  fontFamily: 'PingFang SC',
  textTheme: const TextTheme(
    headlineLarge: TextStyle(fontSize: 28, fontWeight: FontWeight.bold),
    headlineMedium: TextStyle(fontSize: 22, fontWeight: FontWeight.w600),
    bodyLarge: TextStyle(fontSize: 16),
    bodyMedium: TextStyle(fontSize: 14),
    bodySmall: TextStyle(fontSize: 12),
  ),
  inputDecorationTheme: InputDecorationTheme(
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(4),
    ),
    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
  ),
  elevatedButtonTheme: ElevatedButtonThemeData(
    style: ElevatedButton.styleFrom(
      minimumSize: const Size(120, 40),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(4),
      ),
    ),
  ),
);
"""

    # ------------------------------------------------------------------
    # 单个 Widget 文件
    # ------------------------------------------------------------------
    def _generate_widget_file(self, ir: DesignIR, comp: ComponentIR) -> str:
        widget_name = self._pascal(comp.name)
        is_stateful = self._needs_stateful(comp)

        imports = self._collect_dart_imports(ir, comp)
        imports_str = "\n".join(imports)

        # Props
        props = self._generate_props(comp)

        # State
        state_fields = self._generate_state_fields(comp)

        # Build
        build_body = self._generate_build_body(comp)

        if is_stateful:
            return f"""import 'package:flutter/material.dart';
{imports_str}

class {widget_name} extends StatefulWidget {{
{props}

  const {widget_name}({{super.key{self._props_keys(comp)}}});

  @override
  State<{widget_name}> createState() => _{widget_name}State();
}}

class _{widget_name}State extends State<{widget_name}> {{
{state_fields}

  @override
  Widget build(BuildContext context) {{
{build_body}
  }}
}}
"""
        else:
            return f"""import 'package:flutter/material.dart';
{imports_str}

class {widget_name} extends StatelessWidget {{
{props}

  const {widget_name}({{super.key{self._props_keys(comp)}}});

  @override
  Widget build(BuildContext context) {{
{build_body}
  }}
}}
"""

    # ------------------------------------------------------------------
    # Props / Parameters
    # ------------------------------------------------------------------
    def _generate_props(self, comp: ComponentIR) -> str:
        lines = []
        for prop in comp.props:
            dart_type = self._dart_type(prop.type)
            default = self._dart_default(prop)
            lines.append(f"  final {dart_type} {prop.name};")
        return "\n".join(lines)

    def _props_keys(self, comp: ComponentIR) -> str:
        if not comp.props:
            return ""
        keys = ", ".join(f"this.{p.name}" for p in comp.props)
        return f", {keys}"

    def _dart_type(self, hint: str) -> str:
        mapping = {
            "str": "String",
            "string": "String",
            "int": "int",
            "integer": "int",
            "float": "double",
            "double": "double",
            "bool": "bool",
            "boolean": "bool",
            "list": "List<dynamic>",
            "map": "Map<String, dynamic>",
            "function": "VoidCallback",
            "callback": "VoidCallback",
        }
        return mapping.get(hint.lower(), "dynamic")

    def _dart_default(self, prop: PropSpec) -> str:
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
        return ""

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def _needs_stateful(self, comp: ComponentIR) -> bool:
        if comp.interaction and comp.interaction.state_machine:
            return True
        if comp.component_type in (
            ComponentType.INPUT, ComponentType.TEXTAREA,
            ComponentType.CHECKBOX, ComponentType.RADIO,
            ComponentType.SWITCH, ComponentType.SELECT,
            ComponentType.CAROUSEL, ComponentType.TABS,
            ComponentType.ACCORDION, ComponentType.FORM,
            ComponentType.SLIDER, ComponentType.UPLOAD,
        ):
            return True
        return False

    def _generate_state_fields(self, comp: ComponentIR) -> str:
        lines = []
        # 状态机
        if comp.interaction and comp.interaction.state_machine:
            sm = comp.interaction.state_machine
            states_str = ", ".join(f"'{s}'" for s in sm.states)
            lines.append(f"  String _state = '{sm.initial_state}';")

        # 组件类型特有状态
        if comp.component_type in (ComponentType.INPUT, ComponentType.TEXTAREA):
            lines.append("  final TextEditingController _controller = TextEditingController();")
        if comp.component_type == ComponentType.CAROUSEL:
            lines.append("  int _currentIndex = 0;")
        if comp.component_type == ComponentType.TABS:
            lines.append("  int _selectedIndex = 0;")
        if comp.component_type == ComponentType.ACCORDION:
            lines.append("  bool _expanded = false;")
        if comp.component_type == ComponentType.CHECKBOX:
            lines.append("  bool _checked = false;")
        if comp.component_type == ComponentType.RADIO:
            lines.append("  String? _selectedValue;")
        if comp.component_type == ComponentType.SWITCH:
            lines.append("  bool _switched = false;")
        if comp.component_type == ComponentType.SLIDER:
            lines.append("  double _sliderValue = 0.5;")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Build body
    # ------------------------------------------------------------------
    def _generate_build_body(self, comp: ComponentIR) -> str:
        lines = []
        widget = self._build_widget(comp, indent=4)
        lines.append(widget)
        return "\n".join(lines)

    def _build_widget(self, comp: ComponentIR, indent: int = 4) -> str:
        pad = " " * indent
        comp_type = comp.component_type

        # Semantics 包装
        semantics_attr = ""
        if comp.aria:
            if comp.aria.aria_label:
                semantics_attr += f", label: '{comp.aria.aria_label}'"
            if comp.aria.role:
                semantics_attr += f", role: SemanticRole.{comp.aria.role}"

        # 根据类型生成
        if comp_type == ComponentType.BUTTON:
            text = self._get_text(comp)
            color = self._get_color(comp, "#1677ff")
            return f"""{pad}Semantics(
{pad}  button: true{semantics_attr},
{pad}  child: ElevatedButton(
{pad}    onPressed: () {{}},
{pad}    style: ElevatedButton.styleFrom(
{pad}      backgroundColor: Color(0x{color.lstrip('#')}),
{pad}      minimumSize: Size({comp.design_position.get('width', 120)}, {comp.design_position.get('height', 40)}),
{pad}      shape: RoundedRectangleBorder(
{pad}        borderRadius: BorderRadius.circular({self._get_radius(comp)}),
{pad}      ),
{pad}    ),
{pad}    child: Text('{text}'),
{pad}  ),
{pad})"""

        if comp_type == ComponentType.INPUT:
            hint = self._get_text(comp) or "请输入"
            return f"""{pad}Semantics(
{pad}  textField: true{semantics_attr},
{pad}  child: SizedBox(
{pad}    width: {comp.design_position.get('width', 300)},
{pad}    child: TextField(
{pad}      controller: _controller,
{pad}      decoration: InputDecoration(
{pad}        hintText: '{hint}',
{pad}        border: OutlineInputBorder(
{pad}          borderRadius: BorderRadius.circular({self._get_radius(comp)}),
{pad}        ),
{pad}      ),
{pad}    ),
{pad}  ),
{pad})"""

        if comp_type == ComponentType.TEXT:
            text = self._get_text(comp)
            return f"""{pad}Text(
{pad}  '{text}',
{pad}  style: TextStyle(
{pad}    fontSize: {self._get_font_size(comp)},
{pad}    fontWeight: {self._get_font_weight(comp)},
{pad}    color: Color(0x{self._get_color(comp, '#333333').lstrip('#')}),
{pad}  ),
{pad})"""

        if comp_type in (ComponentType.CONTAINER, ComponentType.CARD):
            children = []
            for child in comp.children:
                children.append(self._build_widget(child, indent + 6))
            children_str = ",\n".join(children) if children else f"{pad}    const SizedBox.shrink()"

            bg_color = self._get_bg_color(comp, "#ffffff")
            return f"""{pad}Container(
{pad}  width: {comp.design_position.get('width', 'double.infinity')},
{pad}  height: {comp.design_position.get('height', 'double.infinity')},
{pad}  padding: const EdgeInsets.all({self._get_padding(comp)}),
{pad}  decoration: BoxDecoration(
{pad}    color: Color(0x{bg_color.lstrip('#')}),
{pad}    borderRadius: BorderRadius.circular({self._get_radius(comp)}),
{pad}    {self._generate_box_shadow(comp)}
{pad}  ),
{pad}  child: Column(
{pad}    crossAxisAlignment: CrossAxisAlignment.start,
{pad}    children: [
{children_str}
{pad}    ],
{pad}  ),
{pad})"""

        if comp_type == ComponentType.MODAL:
            return f"""{pad}AlertDialog(
{pad}  title: Text('{self._get_text(comp) or '提示'}'),
{pad}  content: Column(
{pad}    mainAxisSize: MainAxisSize.min,
{pad}    children: [
{pad}      ...{self._build_children_list(comp, indent + 4)}
{pad}    ],
{pad}  ),
{pad}  actions: [
{pad}    TextButton(
{pad}      onPressed: () {{ Navigator.of(context).pop(); }},
{pad}      child: const Text('取消'),
{pad}    ),
{pad}    ElevatedButton(
{pad}      onPressed: () {{ Navigator.of(context).pop(true); }},
{pad}      child: const Text('确定'),
{pad}    ),
{pad}  ],
{pad})"""

        if comp_type == ComponentType.TABS:
            return f"""{pad}DefaultTabController(
{pad}  length: {max(len(comp.children), 1)},
{pad}  child: Column(
{pad}    children: [
{pad}      const TabBar(
{pad}        tabs: [
{pad}          Tab(text: '标签 1'),
{pad}          Tab(text: '标签 2'),
{pad}        ],
{pad}      ),
{pad}      Expanded(
{pad}        child: TabBarView(
{pad}          children: [
{pad}            ...{self._build_children_list(comp, indent + 4)}
{pad}          ],
{pad}        ),
{pad}      ),
{pad}    ],
{pad}  ),
{pad})"""

        if comp_type == ComponentType.TABLE:
            return f"""{pad}SingleChildScrollView(
{pad}  scrollDirection: Axis.horizontal,
{pad}  child: DataTable(
{pad}    columns: const [
{pad}      DataColumn(label: Text('列 1')),
{pad}      DataColumn(label: Text('列 2')),
{pad}      DataColumn(label: Text('列 3')),
{pad}    ],
{pad}    rows: const [],
{pad}  ),
{pad})"""

        if comp_type == ComponentType.AVATAR or comp_type == ComponentType.IMAGE:
            size = min(comp.design_position.get('width', 40), comp.design_position.get('height', 40))
            return f"""{pad}Semantics(
{pad}  image: true{semantics_attr},
{pad}  child: CircleAvatar(
{pad}    radius: {size / 2},
{pad}    backgroundColor: Colors.grey[200],
{pad}    child: const Icon(Icons.person, size: {size * 0.6}),
{pad}  ),
{pad})"""

        if comp_type == ComponentType.DIVIDER:
            return f"{pad}const Divider()"

        if comp_type == ComponentType.BADGE:
            text = self._get_text(comp) or "0"
            return f"""{pad}Container(
{pad}  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
{pad}  decoration: BoxDecoration(
{pad}    color: Colors.red,
{pad}    borderRadius: BorderRadius.circular(10),
{pad}  ),
{pad}  child: Text(
{pad}    '{text}',
{pad}    style: const TextStyle(color: Colors.white, fontSize: 12),
{pad}  ),
{pad})"""

        if comp_type == ComponentType.ALERT:
            return f"""{pad}Container(
{pad}  padding: const EdgeInsets.all(16),
{pad}  decoration: BoxDecoration(
{pad}    color: Colors.blue[50],
{pad}    borderRadius: BorderRadius.circular({self._get_radius(comp)}),
{pad}    border: Border.all(color: Colors.blue[200]!),
{pad}  ),
{pad}  child: Row(
{pad}    children: [
{pad}      const Icon(Icons.info, color: Colors.blue),
{pad}      const SizedBox(width: 12),
{pad}      Expanded(child: Text('{self._get_text(comp) or ''}')),
{pad}    ],
{pad}  ),
{pad})"""

        if comp_type == ComponentType.LOADING or comp_type == ComponentType.SKELETON:
            return f"{pad}const Center(child: CircularProgressIndicator())"

        if comp_type == ComponentType.SPINNER:
            return f"{pad}const Center(child: CircularProgressIndicator())"

        # 默认 Container
        children_str = ",\n".join(
            self._build_widget(ch, indent + 6) for ch in comp.children
        ) if comp.children else f"{pad}    const SizedBox.shrink()"

        return f"""{pad}Container(
{pad}  width: {comp.design_position.get('width', 'double.infinity')},
{pad}  height: {comp.design_position.get('height', 'double.infinity')},
{pad}  child: Column(
{pad}    crossAxisAlignment: CrossAxisAlignment.start,
{pad}    children: [
{children_str}
{pad}    ],
{pad}  ),
{pad})"""

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------
    def _pascal(self, name: str) -> str:
        """PascalCase"""
        return "".join(w.capitalize() for w in name.replace("-", "_").split("_"))

    def _get_text(self, comp: ComponentIR) -> str:
        return comp.design_styles.get("text", "")

    def _get_color(self, comp: ComponentIR, default: str = "#000000") -> str:
        color = comp.design_styles.get("color", "")
        if color and color.startswith("#"):
            return color
        return default

    def _get_bg_color(self, comp: ComponentIR, default: str = "#ffffff") -> str:
        color = comp.design_styles.get("backgroundColor", "")
        if color and color.startswith("#"):
            return color
        fills = comp.design_styles.get("fills", [])
        if fills and isinstance(fills, list):
            for fill in fills:
                if isinstance(fill, dict) and fill.get("isEnabled", True):
                    c = fill.get("color", {})
                    if isinstance(c, dict):
                        r = int(c.get("r", 1) * 255)
                        g = int(c.get("g", 1) * 255)
                        b = int(c.get("b", 1) * 255)
                        return f"{r:02x}{g:02x}{b:02x}"
        return default.lstrip("#")

    def _get_radius(self, comp: ComponentIR) -> int:
        radius = comp.design_styles.get("borderRadius", comp.design_styles.get("radius", 0))
        if isinstance(radius, (int, float)):
            return int(radius)
        return 0

    def _get_padding(self, comp: ComponentIR) -> int:
        padding = comp.design_styles.get("padding", 16)
        if isinstance(padding, (int, float)):
            return int(padding)
        return 16

    def _get_font_size(self, comp: ComponentIR) -> int:
        size = comp.design_styles.get("fontSize", 14)
        if isinstance(size, (int, float)):
            return int(size)
        return 14

    def _get_font_weight(self, comp: ComponentIR) -> str:
        weight = comp.design_styles.get("fontWeight", "normal")
        mapping = {
            "bold": "FontWeight.bold",
            "100": "FontWeight.w100",
            "200": "FontWeight.w200",
            "300": "FontWeight.w300",
            "400": "FontWeight.normal",
            "500": "FontWeight.w500",
            "600": "FontWeight.w600",
            "700": "FontWeight.bold",
            "800": "FontWeight.w800",
            "900": "FontWeight.w900",
        }
        return mapping.get(str(weight).lower(), "FontWeight.normal")

    def _generate_box_shadow(self, comp: ComponentIR) -> str:
        shadows = comp.design_styles.get("shadows", [])
        if not shadows:
            return ""
        lines = []
        for s in shadows[:2]:
            if isinstance(s, dict):
                x = s.get("x", 0)
                y = s.get("y", 2)
                blur = s.get("blur", 8)
                spread = s.get("spread", 0)
                color = s.get("color", {})
                if isinstance(color, dict):
                    r = int(color.get("r", 0) * 255)
                    g = int(color.get("g", 0) * 255)
                    b = int(color.get("b", 0) * 255)
                    a = color.get("a", 0.15)
                    lines.append(
                        f"    BoxShadow("
                        f"color: Color.fromRGBO({r}, {g}, {b}, {a}), "
                        f"offset: Offset({x}, {y}), "
                        f"blurRadius: {blur}, "
                        f"spreadRadius: {spread})"
                    )
        return "\n".join(lines)

    def _collect_dart_imports(self, ir: DesignIR, comp: ComponentIR) -> List[str]:
        imports = []
        if comp.component_type in (ComponentType.INPUT, ComponentType.TEXTAREA):
            imports.append("import 'package:flutter/services.dart';")
        return imports

    def _build_children_list(self, comp: ComponentIR, indent: int) -> str:
        pad = " " * indent
        if not comp.children:
            return f"{pad}const SizedBox.shrink()"
        return ",\n".join(self._build_widget(ch, indent) for ch in comp.children)


def generate(ir: DesignIR) -> Dict[str, str]:
    """便捷入口"""
    return FlutterGenerator().generate(ir)
