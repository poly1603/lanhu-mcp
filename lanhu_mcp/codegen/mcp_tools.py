"""
MCP 工具集成 - 将 codegen 引擎注册为 MCP 工具

新增工具：
1. lanhu_generate_code - 从设计图生成框架代码
2. lanhu_analyze_semantic - 语义化分析
3. lanhu_analyze_interaction - 交互意图分析
4. lanhu_preview_ir - 预览 DesignIR
"""
from __future__ import annotations

import json
from typing import Annotated, Optional, List, Dict, Any

from fastmcp import Context


def register_codegen_tools(mcp, LanhuExtractor, BASE_URL):
    """将 codegen 工具注册到 MCP 服务器"""

    @mcp.tool()
    async def lanhu_generate_code(
        url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
        design_name: Annotated[str, "Design name or index number."],
        framework: Annotated[str, "Target framework: html/vue/react. Default: html"] = "html",
        ctx: Context = None
    ) -> dict:
        """
        [Code Generator] Generate production-ready frontend code from a Lanhu design

        USE THIS WHEN user says: 生成代码, 生成项目, 生成组件, generate code, build page,
        还原页面, 页面还原, 前端代码, component code
        DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

        Generates semantic HTML + BEM CSS + accessible ARIA + interaction JS + framework code.
        Supports: HTML (native), Vue 3 (Composition API + SFC), React (TypeScript + CSS Modules)
        """
        extractor = LanhuExtractor()
        try:
            params = extractor.parse_url(url)

            # 获取设计图列表
            api_url = f"{BASE_URL}/api/project/images?project_id={params['project_id']}"
            if params.get('team_id'):
                api_url += f"&team_id={params['team_id']}"
            api_url += "&dds_status=1&position=1"

            response = await extractor.client.get(api_url)
            response.raise_for_status()
            data = response.json()

            if data.get('code') != '00000':
                return {'status': 'error', 'message': data.get('msg', 'Unknown error')}

            designs = data.get('data', {}).get('images', [])

            # 查找目标设计图
            target_design = None
            if design_name.isdigit():
                idx = int(design_name)
                for d in designs:
                    if d.get('id') and len([x for x in designs if designs.index(x) < idx]) == idx - 1:
                        target_design = d
                        break
            else:
                for d in designs:
                    if d.get('name') == design_name:
                        target_design = d
                        break

            if not target_design:
                return {
                    'status': 'error',
                    'message': f"Design '{design_name}' not found",
                    'available': [d['name'] for d in designs[:20]]
                }

            # 获取 Sketch JSON
            sketch_data = await extractor.get_sketch_json(
                target_design['id'],
                params.get('team_id'),
                params['project_id']
            )

            device_str = sketch_data.get('device', '')
            design_scale = 2.0
            if '@3x' in device_str:
                design_scale = 3.0
            elif '@1x' in device_str:
                design_scale = 1.0

            # 使用 Pipeline 生成代码
            from lanhu_mcp.codegen.pipeline import Pipeline
            pipeline = Pipeline(framework=framework)
            files = pipeline.generate_from_sketch(
                sketch_data=sketch_data,
                design_name=target_design.get('name', design_name),
                design_url=url,
                design_scale=design_scale,
            )

            return {
                'status': 'success',
                'design_name': target_design.get('name', design_name),
                'framework': framework,
                'files': files,
                'file_count': len(files),
                'message': f"Generated {len(files)} files for {framework} framework",
            }
        finally:
            await extractor.close()

    @mcp.tool()
    async def lanhu_analyze_semantic(
        url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
        design_name: Annotated[str, "Design name or index number."],
        ctx: Context = None
    ) -> dict:
        """
        [Semantic Analysis] Analyze a Lanhu design for semantic HTML structure and ARIA accessibility

        USE THIS WHEN user says: 语义化分析, 无障碍分析, accessibility, semantic HTML, ARIA,
        页面结构, 结构分析
        DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

        Returns: semantic tags, ARIA roles, keyboard navigation, heading hierarchy, a11y issues
        """
        extractor = LanhuExtractor()
        try:
            params = extractor.parse_url(url)

            api_url = f"{BASE_URL}/api/project/images?project_id={params['project_id']}"
            if params.get('team_id'):
                api_url += f"&team_id={params['team_id']}"
            api_url += "&dds_status=1&position=1"

            response = await extractor.client.get(api_url)
            response.raise_for_status()
            data = response.json()

            if data.get('code') != '00000':
                return {'status': 'error', 'message': data.get('msg', 'Unknown error')}

            designs = data.get('data', {}).get('images', [])

            target_design = None
            if design_name.isdigit():
                idx = int(design_name)
                for d in designs:
                    if d.get('id') and len([x for x in designs if designs.index(x) < idx]) == idx - 1:
                        target_design = d
                        break
            else:
                for d in designs:
                    if d.get('name') == design_name:
                        target_design = d
                        break

            if not target_design:
                return {
                    'status': 'error',
                    'message': f"Design '{design_name}' not found",
                    'available': [d['name'] for d in designs[:20]]
                }

            sketch_data = await extractor.get_sketch_json(
                target_design['id'],
                params.get('team_id'),
                params['project_id']
            )

            device_str = sketch_data.get('device', '')
            design_scale = 2.0
            if '@3x' in device_str:
                design_scale = 3.0
            elif '@1x' in device_str:
                design_scale = 1.0

            # 生成 IR 并分析语义
            from lanhu_mcp.codegen.pipeline import Pipeline
            pipeline = Pipeline(framework="html")
            ir = pipeline.generate_ir_from_sketch(
                sketch_data=sketch_data,
                design_name=target_design.get('name', design_name),
                design_url=url,
                design_scale=design_scale,
            )

            # 构建语义分析结果
            components = []
            for comp in ir.components:
                comp_info = {
                    'name': comp.name,
                    'type': comp.component_type.value,
                    'semantic_tag': comp.semantic_tag.value,
                    'aria': {},
                }
                if comp.aria:
                    if comp.aria.role:
                        comp_info['aria']['role'] = comp.aria.role
                    if comp.aria.aria_label:
                        comp_info['aria']['aria-label'] = comp.aria.aria_label
                    if comp.aria.keyboard:
                        comp_info['aria']['keyboard'] = comp.aria.keyboard
                    if comp.aria.focus_trap:
                        comp_info['aria']['focus-trap'] = True
                components.append(comp_info)

            return {
                'status': 'success',
                'design_name': target_design.get('name', design_name),
                'components': components,
                'total_components': len(components),
                'a11y_summary': {
                    'with_role': sum(1 for c in components if c['aria'].get('role')),
                    'with_label': sum(1 for c in components if c['aria'].get('aria-label')),
                    'with_keyboard': sum(1 for c in components if c['aria'].get('keyboard')),
                },
            }
        finally:
            await extractor.close()

    @mcp.tool()
    async def lanhu_analyze_interaction(
        url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
        design_name: Annotated[str, "Design name or index number."],
        ctx: Context = None
    ) -> dict:
        """
        [Interaction Analysis] Analyze interaction patterns, state machines, and JS plugin requirements

        USE THIS WHEN user says: 交互分析, 交互逻辑, 状态机, interaction, state machine,
        组件行为, 行为分析, JS 插件, plugin
        DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

        Returns: state machines, event handlers, keyboard navigation, required plugins/libraries
        """
        extractor = LanhuExtractor()
        try:
            params = extractor.parse_url(url)

            api_url = f"{BASE_URL}/api/project/images?project_id={params['project_id']}"
            if params.get('team_id'):
                api_url += f"&team_id={params['team_id']}"
            api_url += "&dds_status=1&position=1"

            response = await extractor.client.get(api_url)
            response.raise_for_status()
            data = response.json()

            if data.get('code') != '00000':
                return {'status': 'error', 'message': data.get('msg', 'Unknown error')}

            designs = data.get('data', {}).get('images', [])

            target_design = None
            if design_name.isdigit():
                idx = int(design_name)
                for d in designs:
                    if d.get('id') and len([x for x in designs if designs.index(x) < idx]) == idx - 1:
                        target_design = d
                        break
            else:
                for d in designs:
                    if d.get('name') == design_name:
                        target_design = d
                        break

            if not target_design:
                return {
                    'status': 'error',
                    'message': f"Design '{design_name}' not found",
                    'available': [d['name'] for d in designs[:20]]
                }

            sketch_data = await extractor.get_sketch_json(
                target_design['id'],
                params.get('team_id'),
                params['project_id']
            )

            device_str = sketch_data.get('device', '')
            design_scale = 2.0
            if '@3x' in device_str:
                design_scale = 3.0
            elif '@1x' in device_str:
                design_scale = 1.0

            # 生成 IR 并分析交互
            from lanhu_mcp.codegen.pipeline import Pipeline
            pipeline = Pipeline(framework="html")
            ir = pipeline.generate_ir_from_sketch(
                sketch_data=sketch_data,
                design_name=target_design.get('name', design_name),
                design_url=url,
                design_scale=design_scale,
            )

            # 构建交互分析结果
            interactions = []
            for comp in ir.components:
                if comp.interaction:
                    interaction_info = {
                        'component': comp.name,
                        'type': comp.component_type.value,
                    }
                    if comp.interaction.state_machine:
                        sm = comp.interaction.state_machine
                        interaction_info['state_machine'] = {
                            'initial': sm.initial_state,
                            'states': sm.states,
                            'transitions': [
                                {
                                    'from': t.from_state,
                                    'to': t.to_state,
                                    'trigger': t.trigger,
                                }
                                for t in sm.transitions
                            ],
                        }
                    if comp.interaction.events:
                        interaction_info['events'] = [
                            {'name': e.name, 'handler': e.handler_name}
                            for e in comp.interaction.events
                        ]
                    if comp.interaction.required_plugins:
                        interaction_info['plugins'] = comp.interaction.required_plugins
                    if comp.interaction.animation:
                        interaction_info['animation'] = comp.interaction.animation
                    interactions.append(interaction_info)

            # 依赖摘要
            from lanhu_mcp.codegen.dependency_detector import DependencyDetector
            dep_detector = DependencyDetector()
            dep_summary = dep_detector.get_dependency_summary(ir.dependencies)

            return {
                'status': 'success',
                'design_name': target_design.get('name', design_name),
                'interactions': interactions,
                'total_interactive_components': len(interactions),
                'dependencies': dep_detector.generate_package_json_deps(ir.dependencies),
                'dependency_summary': dep_summary,
            }
        finally:
            await extractor.close()

    @mcp.tool()
    async def lanhu_preview_ir(
        url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
        design_name: Annotated[str, "Design name or index number."],
        ctx: Context = None
    ) -> dict:
        """
        [IR Preview] Preview the DesignIR intermediate representation of a design

        USE THIS WHEN user says: 预览 IR, 查看中间表示, preview IR, DesignIR,
        查看分析结果, debug
        DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

        Returns: complete DesignIR JSON with tokens, components, interactions, dependencies
        """
        extractor = LanhuExtractor()
        try:
            params = extractor.parse_url(url)

            api_url = f"{BASE_URL}/api/project/images?project_id={params['project_id']}"
            if params.get('team_id'):
                api_url += f"&team_id={params['team_id']}"
            api_url += "&dds_status=1&position=1"

            response = await extractor.client.get(api_url)
            response.raise_for_status()
            data = response.json()

            if data.get('code') != '00000':
                return {'status': 'error', 'message': data.get('msg', 'Unknown error')}

            designs = data.get('data', {}).get('images', [])

            target_design = None
            if design_name.isdigit():
                idx = int(design_name)
                for d in designs:
                    if d.get('id') and len([x for x in designs if designs.index(x) < idx]) == idx - 1:
                        target_design = d
                        break
            else:
                for d in designs:
                    if d.get('name') == design_name:
                        target_design = d
                        break

            if not target_design:
                return {
                    'status': 'error',
                    'message': f"Design '{design_name}' not found",
                    'available': [d['name'] for d in designs[:20]]
                }

            sketch_data = await extractor.get_sketch_json(
                target_design['id'],
                params.get('team_id'),
                params['project_id']
            )

            device_str = sketch_data.get('device', '')
            design_scale = 2.0
            if '@3x' in device_str:
                design_scale = 3.0
            elif '@1x' in device_str:
                design_scale = 1.0

            from lanhu_mcp.codegen.pipeline import Pipeline
            pipeline = Pipeline(framework="html")
            ir = pipeline.generate_ir_from_sketch(
                sketch_data=sketch_data,
                design_name=target_design.get('name', design_name),
                design_url=url,
                design_scale=design_scale,
            )

            # 序列化 IR（跳过不可序列化的内容）
            ir_summary = {
                'name': ir.name,
                'framework': ir.framework.value,
                'styling': ir.styling.value,
                'tokens': {
                    'colors_count': len(ir.tokens.colors),
                    'font_families_count': len(ir.tokens.font_families),
                    'font_sizes_count': len(ir.tokens.font_sizes),
                    'spacing_count': len(ir.tokens.spacing),
                },
                'components': [
                    {
                        'name': c.name,
                        'type': c.component_type.value,
                        'semantic_tag': c.semantic_tag.value,
                        'children_count': len(c.children),
                        'has_aria': c.aria is not None,
                        'has_interaction': c.interaction is not None,
                        'events_count': len(c.events),
                        'props_count': len(c.props),
                    }
                    for c in ir.components
                ],
                'total_components': len(ir.components),
                'dependencies_count': len(ir.dependencies),
            }

            return {
                'status': 'success',
                'design_name': target_design.get('name', design_name),
                'ir': ir_summary,
            }
        finally:
            await extractor.close()

    return mcp
