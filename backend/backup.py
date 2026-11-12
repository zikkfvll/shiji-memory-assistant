"""Restore only into a new/empty directory; never overwrite live data."""
from io import BytesIO
import json
from pathlib import Path
import re
import zipfile
from PIL import Image
from .store import Store, identifier


def restore_backup(archive, target):
    target = Path(target).resolve()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ValueError('恢复目标必须是新目录或空目录')
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or len(names) > 5000 or sum(i.file_size for i in z.infolist()) > 256 * 1024 * 1024:
            raise ValueError('备份存在重复项目或超过大小限制')
        if any(n != 'manifest.json' and not re.fullmatch(r'attachments/[a-f0-9]{32}\.(png|jpg|webp)', n) for n in names):
            raise ValueError('备份包含不允许的文件路径')
        manifest = json.loads(z.read('manifest.json'))
        categories = ['activity', 'record', 'assistance', 'feedback', 'attachment']
        if manifest.get('schema_version') != 1 or set(manifest.get('collections', {})) != set(categories):
            raise ValueError('备份格式或版本不支持')
        collections = manifest['collections']
        ids = set()
        for category in categories:
            if not isinstance(collections[category], list):
                raise ValueError('备份集合格式错误')
            for item in collections[category]:
                if not isinstance(item, dict) or not re.fullmatch(r'[a-f0-9]{32}', item.get('id', '')) or item['id'] in ids:
                    raise ValueError('备份中的标识错误或重复')
                if not isinstance(item.get('created_at'), str):
                    raise ValueError('备份缺少记录时间')
                ids.add(item['id'])
        activity_ids = {a['id'] for a in collections['activity']}
        record_ids = {r['id']: r['activity_id'] for r in collections['record']}
        for category in categories[1:]:
            for item in collections[category]:
                if item.get('activity_id') not in activity_ids:
                    raise ValueError('备份中有无所属活动的记录')
        contents = {}
        expected_names = {'manifest.json'}
        for a in collections['attachment']:
            filename = a.get('filename', '')
            if not re.fullmatch(a['id'] + r'\.(png|jpg|webp)', filename) or record_ids.get(a.get('record_id')) != a['activity_id']:
                raise ValueError('附件关联或文件名错误')
            name = 'attachments/' + filename
            expected_names.add(name)
            content = z.read(name)
            if len(content) > 8 * 1024 * 1024:
                raise ValueError('附件超过 8 MB')
            with Image.open(BytesIO(content)) as image:
                if image.format not in ('PNG', 'JPEG', 'WEBP'):
                    raise ValueError('附件并非受支持的图片')
                image.verify()
            a['url'] = f"/api/attachments/{a['id']}"
            a['size'] = len(content)
            contents[filename] = content
        if set(names) != expected_names:
            raise ValueError('备份存在未在清单中登记的文件')
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.parent / ('.restore-' + identifier())
    store = Store(stage)
    for category in categories:
        for item in collections[category]:
            store.put(category, item)
    for filename, content in contents.items():
        (store.files / filename).write_bytes(content)
    if target.exists():
        target.rmdir()  # Only the explicitly selected empty destination.
    stage.rename(target)
    return target
