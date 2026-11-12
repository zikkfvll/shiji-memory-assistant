from io import BytesIO
import json
from pathlib import Path
import zipfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import create_app
from backend.backup import restore_backup


def test_backup_restores_records_without_overwriting_original(tmp_path):
    original = tmp_path / 'original'
    with TestClient(create_app(original)) as c:
        activity = c.post('/api/activities', json={'title': '备份后仍能继续'}).json()
        record = c.post(f"/api/activities/{activity['id']}/records", json={'content': '准备带植物手册'}).json()
        picture = BytesIO()
        Image.new('RGB', (12, 8), '#386861').save(picture, format='PNG')
        attachment = c.post(f"/api/records/{record['id']}/attachments", files={
            'file': ('constructed.png', picture.getvalue(), 'image/png')})
        assert attachment.status_code == 201
        attachment_id = attachment.json()['id']
        archive = tmp_path / 'backup.zip'
        archive.write_bytes(c.get('/api/backup').content)
    restored = tmp_path / 'restored'
    restore_backup(archive, restored)
    with TestClient(create_app(restored)) as c:
        d = c.get(f"/api/activities/{activity['id']}").json()
        assert d['current'][0]['content'] == '准备带植物手册'
        assert d['current'][0]['attachments'][0]['id'] == attachment_id
        assert c.get(f'/api/attachments/{attachment_id}').content == picture.getvalue()
    with pytest.raises(ValueError, match='空目录'):
        restore_backup(archive, original)


def test_restore_rejects_traversal_without_writing_outside(tmp_path):
    archive = tmp_path / 'unsafe.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('manifest.json', json.dumps({'schema_version': 1, 'collections': {}}))
        z.writestr('../outside.txt', 'must never be written')
    with pytest.raises(ValueError):
        restore_backup(archive, tmp_path / 'new')
    assert not (tmp_path / 'outside.txt').exists()
