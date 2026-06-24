"""
Lanhu MCP Server - 新版入口

导入原有工具并注册新的设计分析工具。
"""
import sys
from pathlib import Path
from typing import Annotated, Optional, List, Union

# 确保项目根目录在 sys.path 中
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 从原有文件导入 MCP 服务器实例和所有现有工具
from lanhu_mcp_server import mcp, LanhuExtractor, BASE_URL

# 导入新工具模块
from lanhu_mcp.tools.design_system import extract_design_system
from lanhu_mcp.tools.layout_spec import extract_layout_spec
from lanhu_mcp.tools.components import extract_component_patterns
from lanhu_mcp.tools.interactions import extract_interactions_from_axure
from lanhu_mcp.tools.quality_check import design_quality_check
from lanhu_mcp.tools.code_gen import generate_framework_code
from lanhu_mcp.tools.compare import compare_design_versions
from lanhu_mcp.tools.batch_download import classify_asset, generate_asset_manifest
from lanhu_mcp.tools.annotations import extract_design_annotations, format_annotations_for_ai
from lanhu_mcp.tools.version_history import extract_version_history, format_version_history_for_ai
from lanhu_mcp.tools.svg_extract import extract_all_svgs, format_svgs_for_ai
from lanhu_mcp.tools.measurements import measure_all_elements, format_measurements_for_ai
from lanhu_mcp.tools.animation import extract_animation_specs, format_animation_specs_for_ai
from lanhu_mcp.tools.export_options import get_export_options, format_export_options_for_ai
from lanhu_mcp.tools.responsive import extract_responsive_variants, format_responsive_for_ai

from fastmcp import Context


# ============================================
# 新增工具：设计系统提取
# ============================================

@mcp.tool()
async def lanhu_extract_design_system(
    url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
    design_name: Annotated[str, "Design name or index number. Get names from lanhu_get_designs first."],
    ctx: Context = None
) -> dict:
    """
    [Design System] Extract complete design system from a Lanhu design - colors, typography, spacing, shadows, component patterns

    USE THIS WHEN user says: 设计规范, 设计系统, 色板, 字体规范, 间距规范, design system, style guide, 颜色提取, 字体提取
    DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

    Purpose: Extract a comprehensive design system from a design image, including:
    - Color palette (all unique colors with frequency)
    - Typography (font families, sizes, weights)
    - Spacing patterns (margin/padding values)
    - Border radius values
    - Shadow definitions
    - CSS variables output

    Returns structured design system data + CSS variables for direct use.
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

        # 提取设计系统
        device_str = sketch_data.get('device', '')
        design_scale = 2.0
        if '@3x' in device_str:
            design_scale = 3.0
        elif '@1x' in device_str:
            design_scale = 1.0

        result = extract_design_system(sketch_data, design_scale)
        result['design_name'] = target_design.get('name', design_name)
        result['status'] = 'success'

        return result
    finally:
        await extractor.close()


# ============================================
# 新增工具：布局规格提取
# ============================================

@mcp.tool()
async def lanhu_get_layout_spec(
    url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
    design_name: Annotated[str, "Design name or index number."],
    max_depth: Annotated[int, "Max extraction depth (0=all, 1=top-level only). Default: 0"] = 0,
    ctx: Context = None
) -> dict:
    """
    [Layout Spec] Extract detailed layout specification from a Lanhu design - positions, sizes, flex layouts, spacing measurements

    USE THIS WHEN user says: 布局规格, 布局信息, 元素位置, 间距测量, layout spec, layout tree, flex布局
    DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

    Purpose: Extract precise layout information including:
    - Element positions and sizes
    - Flex/Grid layout detection
    - Spacing measurements between elements
    - Layout tree hierarchy
    - Canvas dimensions

    Returns structured layout tree with measurements.
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

        result = extract_layout_spec(sketch_data, design_scale, max_depth)
        result['design_name'] = target_design.get('name', design_name)
        result['status'] = 'success'

        return result
    finally:
        await extractor.close()


# ============================================
# 新增工具：组件模式识别
# ============================================

@mcp.tool()
async def lanhu_extract_component_patterns(
    url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
    design_name: Annotated[str, "Design name or index number."],
    ctx: Context = None
) -> dict:
    """
    [Component Patterns] Extract reusable component patterns from a Lanhu design - buttons, cards, inputs, avatars, badges

    USE THIS WHEN user says: 组件模式, 可复用组件, 按钮样式, 卡片样式, 输入框样式, component patterns
    DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

    Purpose: Identify and extract reusable component patterns including:
    - Button variants (primary, secondary, etc.)
    - Card layouts
    - Input field styles
    - Avatar/badge patterns
    - Icon sizes and styles

    Returns component specs with instance counts.
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

        result = extract_component_patterns(sketch_data, design_scale)
        result['design_name'] = target_design.get('name', design_name)
        result['status'] = 'success'

        return result
    finally:
        await extractor.close()


# ============================================
# 新增工具：设计质量检查
# ============================================

@mcp.tool()
async def lanhu_design_qa(
    url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
    design_name: Annotated[str, "Design name or index number."],
    ctx: Context = None
) -> dict:
    """
    [Design QA] Check design quality - consistency, accessibility, color contrast, typography

    USE THIS WHEN user says: 设计检查, 设计质量, 一致性检查, 对比度检查, accessibility, design QA
    DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

    Purpose: Automatically check design quality including:
    - Color palette consistency
    - Text contrast ratio (WCAG 2.1)
    - Font usage consistency
    - Spacing system consistency
    - Border radius consistency

    Returns quality score and list of issues with severity levels.
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

        result = design_quality_check(sketch_data, design_scale)
        result['design_name'] = target_design.get('name', design_name)
        result['status'] = 'success'

        return result
    finally:
        await extractor.close()


# ============================================
# 新增工具：设计对比
# ============================================

@mcp.tool()
async def lanhu_compare_designs(
    url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
    design_name: Annotated[str, "Design name or index number."],
    ctx: Context = None
) -> dict:
    """
    [Design Compare] Compare two versions of a design - added, removed, modified elements

    USE THIS WHEN user says: 设计对比, 版本对比, 变更追踪, 改了什么, what changed
    DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

    Purpose: Compare the latest two versions of a design image and identify:
    - Added elements
    - Removed elements
    - Modified elements (position, size, color, text)

    Returns change summary with detailed diffs.
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

        # 获取最新两个版本
        image_id = target_design['id']
        image_detail_url = f"{BASE_URL}/api/project/image"
        detail_params = {
            'dds_status': 1,
            'image_id': image_id,
            'project_id': params['project_id']
        }
        if params.get('team_id'):
            detail_params['team_id'] = params['team_id']

        detail_resp = await extractor.client.get(image_detail_url, params=detail_params)
        detail_data = detail_resp.json()

        if detail_data.get('code') != '00000':
            return {'status': 'error', 'message': 'Failed to get design versions'}

        versions = detail_data.get('result', {}).get('versions', [])
        if len(versions) < 2:
            return {
                'status': 'info',
                'message': f"Design '{design_name}' only has {len(versions)} version(s), cannot compare",
            }

        # 获取两个版本的 JSON
        version_a_url = versions[1]['json_url']  # 较旧版本
        version_b_url = versions[0]['json_url']  # 最新版本

        resp_a = await extractor.client.get(version_a_url)
        sketch_a = resp_a.json()

        resp_b = await extractor.client.get(version_b_url)
        sketch_b = resp_b.json()

        device_str = sketch_data_b = sketch_b.get('device', '')
        design_scale = 2.0
        if '@3x' in device_str:
            design_scale = 3.0
        elif '@1x' in device_str:
            design_scale = 1.0

        result = compare_design_versions(sketch_a, sketch_b, design_scale)
        result['design_name'] = target_design.get('name', design_name)
        result['version_a'] = versions[1].get('version_info', 'unknown')
        result['version_b'] = versions[0].get('version_info', 'unknown')
        result['status'] = 'success'

        return result
    finally:
        await extractor.close()


# ============================================
# 新增工具：框架代码生成
# ============================================

@mcp.tool()
async def lanhu_generate_framework_code(
    url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
    design_name: Annotated[str, "Design name or index number."],
    framework: Annotated[str, "Target framework: react/vue/flutter/html/svelte. Default: html"] = "html",
    styling: Annotated[str, "Styling approach: inline/css-modules/tailwind/styled-components. Default: inline"] = "inline",
    component_name: Annotated[str, "Component class name. Default: DesignComponent"] = "DesignComponent",
    ctx: Context = None
) -> dict:
    """
    [Framework Code Gen] Generate framework-specific component code from a Lanhu design

    USE THIS WHEN user says: 生成代码, 生成组件, React组件, Vue组件, Flutter组件, framework code
    DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

    Purpose: Convert a Lanhu design into framework-specific component code:
    - React: JSX + CSS Modules / Tailwind / Inline styles
    - Vue: Single File Component (.vue) with <style scoped>
    - Flutter: StatelessWidget with EdgeInsets/BoxDecoration
    - Svelte: Component.svelte with <style>
    - HTML: Self-contained .html file with inline <style>

    Returns file contents ready for copy-paste.
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

        # 获取 Schema JSON 并生成 HTML
        schema_json = await extractor.get_design_schema_json(
            target_design['id'],
            params.get('team_id'),
            params['project_id']
        )

        from lanhu_mcp_server import convert_lanhu_to_html, minify_html
        html_code = minify_html(convert_lanhu_to_html(schema_json))

        # 生成框架代码
        result = generate_framework_code(
            html_code=html_code,
            framework=framework,
            styling=styling,
            component_name=component_name,
        )
        result['design_name'] = target_design.get('name', design_name)
        result['status'] = 'success'

        return result
    finally:
        await extractor.close()


# ============================================
# 新增工具：批量下载资产
# ============================================

@mcp.tool()
async def lanhu_batch_download_assets(
    url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
    design_name: Annotated[str, "Design name or index number."],
    output_dir: Annotated[str, "Output directory for downloaded assets. Default: ./assets"] = "./assets",
    scale: Annotated[str, "Target scale: 1x/2x/3x. Default: 2x"] = "2x",
    ctx: Context = None
) -> dict:
    """
    [Batch Download] Download all assets from a Lanhu design - icons, backgrounds, illustrations, organized by type

    USE THIS WHEN user says: 批量下载, 下载所有切图, 下载资源, batch download, download all assets
    DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)
    DO NOT USE for: 单个切图下载 (use lanhu_get_design_slices instead)

    Purpose: Download all design assets at once, organized by type:
    - icons/ (small elements < 64px)
    - backgrounds/ (large elements > 200px)
    - illustrations/ (images/photos)
    - other/ (unclassified)

    Returns download manifest with paths and status.
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

        # 获取切图信息
        from lanhu_mcp_server import LanhuExtractor as OrigExtractor
        orig_ext = OrigExtractor()
        try:
            slices_data = await orig_ext.get_design_slices_info(
                image_id=target_design['id'],
                team_id=params.get('team_id'),
                project_id=params['project_id'],
                include_metadata=False
            )
        finally:
            await orig_ext.close()

        # 生成清单
        manifest_result = generate_asset_manifest(slices_data, output_dir, scale)

        return {
            'status': 'success',
            'design_name': target_design.get('name', design_name),
            'total_assets': slices_data.get('total_slices', 0),
            'manifest': manifest_result['manifest'],
            'directory_structure': manifest_result['directory_structure'],
            'message': f"Manifest generated. Use curl/PowerShell to download {slices_data.get('total_slices', 0)} assets.",
        }
    finally:
        await extractor.close()


# ============================================
# 新增工具：交互提取
# ============================================

@mcp.tool()
async def lanhu_extract_interactions(
    url: Annotated[str, "Lanhu URL with docId (PRD/prototype document). Example: https://lanhuapp.com/web/#/item/project/product?tid=xxx&pid=xxx&docId=xxx"],
    page_names: Annotated[Union[str, List[str]], "Page name(s) to analyze. Use 'all' for all pages."],
    ctx: Context = None
) -> dict:
    """
    [Interactions] Extract interaction patterns from Lanhu Axure prototype pages

    USE THIS WHEN user says: 交互提取, 点击区域, 表单输入, 交互规格, interaction patterns, click areas
    DO NOT USE for: UI设计图, 设计稿 (use lanhu_get_designs instead)

    Purpose: Extract interaction specifications from Axure prototype including:
    - Click areas and navigation targets
    - Form inputs with validation rules
    - Scroll behavior
    - State changes

    Returns structured interaction specification.
    """
    from lanhu_mcp.tools.interactions import extract_interactions_from_axure, extract_interactions_from_screenshot
    from lanhu_mcp_server import (
        LanhuExtractor as OrigExtractor,
        screenshot_page_internal,
        fix_html_files,
        DATA_DIR,
    )

    extractor = OrigExtractor()
    try:
        params = extractor.parse_url(url)
        doc_id = params.get('doc_id')

        # 下载资源
        resource_dir = str(DATA_DIR / f"axure_extract_{doc_id[:8]}")
        output_dir = str(DATA_DIR / f"axure_extract_{doc_id[:8]}_screenshots")

        download_result = await extractor.download_resources(url, resource_dir)
        if download_result['status'] in ['downloaded', 'updated']:
            fix_html_files(resource_dir)

        # 获取页面列表
        pages_info = await extractor.get_pages_list(url)
        all_pages = pages_info['pages']

        # 处理page_names
        page_map = {p['name']: p['filename'].replace('.html', '') for p in all_pages}

        if isinstance(page_names, str) and page_names.lower() == 'all':
            target_pages = [p['filename'].replace('.html', '') for p in all_pages]
            target_page_names = [p['name'] for p in all_pages]
        elif isinstance(page_names, str):
            if page_names in page_map:
                target_pages = [page_map[page_names]]
                target_page_names = [page_names]
            else:
                target_pages = [page_names]
                target_page_names = [page_names]
        else:
            target_pages = []
            target_page_names = []
            for pn in page_names:
                if pn in page_map:
                    target_pages.append(page_map[pn])
                    target_page_names.append(pn)
                else:
                    target_pages.append(pn)
                    target_page_names.append(pn)

        # 截图并提取交互
        version_id = download_result.get('version_id', '')
        results = await screenshot_page_internal(
            resource_dir, target_pages, output_dir,
            return_base64=False, version_id=version_id
        )

        # 提取交互信息
        interactions = {}
        for idx, r in enumerate(results):
            if not r.get('success'):
                continue

            page_name = target_page_names[idx] if idx < len(target_page_names) else r['page_name']

            # 从页面文本中提取交互线索
            page_text = r.get('page_text', '')
            text_clues = extract_interactions_from_screenshot(page_text)

            # 从Axure标注中提取交互
            axure_annotations = r.get('page_annotations', {})
            axure_interactions = extract_interactions_from_axure(axure_annotations)

            interactions[page_name] = {
                'text_clues': text_clues,
                'axure_interactions': axure_interactions,
                'has_screenshot': 'screenshot_path' in r,
            }

        return {
            'status': 'success',
            'total_pages': len(target_pages),
            'pages_with_interactions': len(interactions),
            'interactions': interactions,
        }
    finally:
        await extractor.close()


# ============================================
# 新增工具：设计标注/评论
# ============================================

@mcp.tool()
async def lanhu_get_design_annotations(
    url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
    design_name: Annotated[str, "Design name or index number."],
    ctx: Context = None
) -> dict:
    """
    [Annotations] Get comments and annotations on a Lanhu design

    USE THIS WHEN user says: 设计评论, 标注, 评论, comments, annotations, 谁说了什么
    DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

    Purpose: Extract all comments and annotations on a design image including:
    - Comment content and author
    - Reply threads
    - Position markers
    - Resolution status (open/resolved)

    Returns structured annotation data.
    """
    extractor = LanhuExtractor()
    try:
        params = extractor.parse_url(url)

        api_url = f"{BASE_URL}/api/project/images?project_id={params['project_id']}"
        if params.get('team_id'):
            api_url += f"&team_id={params['team_id']}"
        api_url += "&dds_status=1&position=1&comment=1"

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

        # 获取标注数据
        annotations_data = target_design.get('comments', [])
        result = extract_design_annotations(annotations_data)
        result['design_name'] = target_design.get('name', design_name)
        result['status'] = 'success'

        return result
    finally:
        await extractor.close()


# ============================================
# 新增工具：版本历史
# ============================================

@mcp.tool()
async def lanhu_get_version_history(
    url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
    design_name: Annotated[str, "Design name or index number."],
    ctx: Context = None
) -> dict:
    """
    [Version History] Get version history of a Lanhu design

    USE THIS WHEN user says: 版本历史, 版本记录, 改过几次, version history, 旧版本
    DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

    Purpose: Get the version history of a design image including:
    - All version numbers
    - Authors and timestamps
    - Version descriptions

    Returns version history data.
    """
    extractor = LanhuExtractor()
    try:
        params = extractor.parse_url(url)

        # 获取设计图详情（包含版本列表）
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

        # 获取版本详情
        detail_url = f"{BASE_URL}/api/project/image"
        detail_params = {
            'dds_status': 1,
            'image_id': target_design['id'],
            'project_id': params['project_id']
        }
        if params.get('team_id'):
            detail_params['team_id'] = params['team_id']

        detail_resp = await extractor.client.get(detail_url, params=detail_params)
        detail_data = detail_resp.json()

        versions = detail_data.get('result', {}).get('versions', [])
        result = extract_version_history(versions)
        result['design_name'] = target_design.get('name', design_name)
        result['status'] = 'success'

        return result
    finally:
        await extractor.close()


# ============================================
# 新增工具：SVG提取
# ============================================

@mcp.tool()
async def lanhu_extract_svg(
    url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
    design_name: Annotated[str, "Design name or index number."],
    ctx: Context = None
) -> dict:
    """
    [SVG Extract] Extract SVG vector graphics from a Lanhu design

    USE THIS WHEN user says: SVG, 矢量图, 矢量图形, 提取SVG, SVG代码
    DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

    Purpose: Extract SVG code from design elements including:
    - SVG URLs from export-ready layers
    - Generated SVG from shape layers
    - Vector graphics code for direct use

    Returns SVG list with code or URLs.
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

        svgs = extract_all_svgs(sketch_data, design_scale)
        return {
            'status': 'success',
            'design_name': target_design.get('name', design_name),
            'total_svgs': len(svgs),
            'svgs': svgs,
        }
    finally:
        await extractor.close()


# ============================================
# 新增工具：精确测量
# ============================================

@mcp.tool()
async def lanhu_measure_elements(
    url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
    design_name: Annotated[str, "Design name or index number."],
    ctx: Context = None
) -> dict:
    """
    [Measurements] Get precise measurements of all elements in a Lanhu design

    USE THIS WHEN user says: 测量, 尺寸, 距离, 元素大小, measurements, 尺寸信息
    DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

    Purpose: Get precise measurements including:
    - Element positions (x, y)
    - Element sizes (width, height)
    - Element areas
    - Total element count

    Returns measurement data for all elements.
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

        result = measure_all_elements(sketch_data, design_scale)
        result['design_name'] = target_design.get('name', design_name)
        result['status'] = 'success'

        return result
    finally:
        await extractor.close()


# ============================================
# 新增工具：动效规格
# ============================================

@mcp.tool()
async def lanhu_extract_animation_specs(
    url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
    design_name: Annotated[str, "Design name or index number."],
    ctx: Context = None
) -> dict:
    """
    [Animation Specs] Extract animation and transition specifications from a Lanhu design

    USE THIS WHEN user says: 动效, 动画, 过渡, transition, animation, 微交互
    DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

    Purpose: Extract animation specifications including:
    - Animation types and durations
    - Transition properties
    - Easing functions
    - Delay values

    Returns animation spec data.
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

        result = extract_animation_specs(sketch_data, design_scale)
        result['design_name'] = target_design.get('name', design_name)
        result['status'] = 'success'

        return result
    finally:
        await extractor.close()


# ============================================
# 新增工具：导出选项
# ============================================

@mcp.tool()
async def lanhu_get_export_options(
    url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
    design_name: Annotated[str, "Design name or index number."],
    ctx: Context = None
) -> dict:
    """
    [Export Options] Get available export formats and configurations for a Lanhu design

    USE THIS WHEN user says: 导出选项, 导出格式, export, 导出配置, 切图格式
    DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

    Purpose: Get export options including:
    - Available formats (PNG, SVG, etc.)
    - Available scales (1x, 2x, 3x, iOS, Android)
    - Size range of all slices
    - Export recommendations per platform

    Returns export configuration data.
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

        # 获取切图信息
        from lanhu_mcp_server import LanhuExtractor as OrigExtractor
        orig_ext = OrigExtractor()
        try:
            slices_data = await orig_ext.get_design_slices_info(
                image_id=target_design['id'],
                team_id=params.get('team_id'),
                project_id=params['project_id'],
                include_metadata=False
            )
        finally:
            await orig_ext.close()

        result = get_export_options(slices_data)
        result['design_name'] = target_design.get('name', design_name)
        result['status'] = 'success'

        return result
    finally:
        await extractor.close()


# ============================================
# 新增工具：响应式变体
# ============================================

@mcp.tool()
async def lanhu_get_responsive_variants(
    url: Annotated[str, "Lanhu URL WITHOUT docId (UI design project). Example: https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"],
    design_name: Annotated[str, "Design name or index number."],
    ctx: Context = None
) -> dict:
    """
    [Responsive] Get responsive design variants and breakpoint suggestions

    USE THIS WHEN user says: 响应式, 多设备, 断点, responsive, breakpoint, 适配
    DO NOT USE for: 需求文档, PRD (use lanhu_get_pages instead)

    Purpose: Analyze responsive design including:
    - Device type detection (mobile/tablet/desktop)
    - Canvas dimensions and aspect ratio
    - Layout hints (full-width, fixed-width elements)
    - Breakpoint suggestions

    Returns responsive analysis data.
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

        result = extract_responsive_variants(sketch_data, design_scale)
        result['design_name'] = target_design.get('name', design_name)
        result['status'] = 'success'

        return result
    finally:
        await extractor.close()


# ============================================
# Codegen 引擎工具注册
# ============================================
try:
    from lanhu_mcp.codegen.mcp_tools import register_codegen_tools
    register_codegen_tools(mcp)
except ImportError as _codegen_err:
    import warnings
    warnings.warn(f"Codegen tools not loaded: {_codegen_err}", ImportWarning)


if __name__ == "__main__":
    import os
    MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "http").lower()
    if MCP_TRANSPORT == "stdio":
        mcp.run(transport="stdio")
    else:
        SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
        SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
        mcp.run(transport="http", path="/mcp", host=SERVER_HOST, port=SERVER_PORT)
