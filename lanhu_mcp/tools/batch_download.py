"""批量下载优化 - 一键下载设计图所有资源并按类型组织"""
import asyncio
import re
from pathlib import Path
from typing import Optional


def classify_asset(name: str, width: float = 0, height: float = 0) -> str:
    """
    根据名称和尺寸将资源分类。

    Returns:
        'icon' | 'background' | 'illustration' | 'other'
    """
    name_lower = name.lower()

    # 按名称关键字分类
    icon_keywords = ['icon', 'ico', 'logo', 'symbol', 'arrow', 'btn', 'button', 'tab']
    bg_keywords = ['bg', 'background', 'back', 'banner', 'gradient']
    illu_keywords = ['img', 'image', 'illust', 'photo', 'avatar', 'pic']

    for kw in icon_keywords:
        if kw in name_lower:
            return 'icon'
    for kw in bg_keywords:
        if kw in name_lower:
            return 'background'
    for kw in illu_keywords:
        if kw in name_lower:
            return 'illustration'

    # 按尺寸分类
    if width > 0 and height > 0:
        area = width * height
        if width <= 64 and height <= 64:
            return 'icon'
        if width >= 200 or height >= 200:
            return 'background'

    return 'other'


def generate_asset_manifest(
    slices_data: dict,
    output_dir: str,
    scale: str = '2x',
) -> dict:
    """
    生成资源下载清单和目录结构。

    Args:
        slices_data: lanhu_get_design_slices 返回的数据
        output_dir: 输出目录
        scale: 目标倍率

    Returns:
        包含 manifest 和 directory_structure 的字典
    """
    output_path = Path(output_dir)
    slices = slices_data.get('slices', [])

    manifest = {
        'design_name': slices_data.get('design_name', ''),
        'version': slices_data.get('version', ''),
        'total_assets': len(slices),
        'by_type': {'icons': 0, 'backgrounds': 0, 'illustrations': 0, 'other': 0},
        'assets': [],
    }

    directory_structure = {}

    for slice_info in slices:
        name = slice_info.get('name', 'unknown')
        download_url = slice_info.get('download_url', '')

        # 获取尺寸
        size_str = slice_info.get('size', '0x0')
        parts = size_str.split('x')
        width = float(parts[0]) if len(parts) > 0 else 0
        height = float(parts[1]) if len(parts) > 1 else 0

        # 分类
        category = classify_asset(name, width, height)
        type_key = {
            'icon': 'icons',
            'background': 'backgrounds',
            'illustration': 'illustrations',
        }.get(category, 'other')

        # 生成本地路径
        safe_name = re.sub(r'[^\w\-]', '_', name).strip('_')
        local_path = f"./assets/{category}s/{safe_name}.png"

        # 获取倍率URL
        scale_urls = slice_info.get('scale_urls', {})
        final_url = scale_urls.get(scale, download_url)

        manifest['by_type'][type_key] += 1
        manifest['assets'].append({
            'name': name,
            'category': category,
            'local_path': local_path,
            'remote_url': final_url or download_url,
            'size': size_str,
        })

        dir_key = f"{output_path}/{category}s"
        if dir_key not in directory_structure:
            directory_structure[dir_key] = []
        directory_structure[dir_key].append(f"{safe_name}.png")

    return {
        'manifest': manifest,
        'directory_structure': directory_structure,
    }


async def batch_download_assets(
    client,
    slices_data: dict,
    output_dir: str,
    scale: str = '2x',
    concurrency: int = 5,
) -> dict:
    """
    批量下载所有资源。

    Args:
        client: httpx.AsyncClient
        slices_data: lanhu_get_design_slices 返回的数据
        output_dir: 输出目录
        scale: 目标倍率
        concurrency: 并发数

    Returns:
        下载结果
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    slices = slices_data.get('slices', [])
    results = {'success': [], 'failed': [], 'skipped': []}

    semaphore = asyncio.Semaphore(concurrency)

    async def _download_one(slice_info: dict):
        async with semaphore:
            name = slice_info.get('name', 'unknown')
            download_url = slice_info.get('download_url', '')
            scale_urls = slice_info.get('scale_urls', {})
            final_url = scale_urls.get(scale, download_url)

            if not final_url:
                results['skipped'].append({'name': name, 'reason': 'no_url'})
                return

            category = classify_asset(name)
            safe_name = re.sub(r'[^\w\-]', '_', name).strip('_')
            local_path = output_path / category / f"{safe_name}.png"
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # 跳过已存在的文件
            if local_path.exists():
                results['skipped'].append({'name': name, 'reason': 'exists', 'path': str(local_path)})
                return

            try:
                response = await client.get(final_url)
                response.raise_for_status()
                local_path.write_bytes(response.content)
                results['success'].append({'name': name, 'path': str(local_path)})
            except Exception as e:
                results['failed'].append({'name': name, 'error': str(e)})

    # 并发下载
    tasks = [_download_one(s) for s in slices]
    await asyncio.gather(*tasks, return_exceptions=True)

    return {
        'total': len(slices),
        'success_count': len(results['success']),
        'failed_count': len(results['failed']),
        'skipped_count': len(results['skipped']),
        'results': results,
    }
