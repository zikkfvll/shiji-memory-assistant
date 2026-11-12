from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import time
import warnings
import zipfile

from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .models import ActivityInput, ActivityPatch, RecordInput, HelpInput, ImportInput, FeedbackInput
from .store import Store, now, identifier
from .memory import organize_record, update_memory, choose_assistance

PROJECT = Path(__file__).resolve().parents[1]
MAX_IMAGE_BYTES = 8 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000


def create_app(data_dir=None):
    store = Store(Path(data_dir or os.environ.get('MEMORY_DATA_DIR', PROJECT / 'data')))
    app = FastAPI(title='拾记 本地研究原型', version='0.1.0', docs_url='/api/docs')
    app.state.store = store
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])

    @app.middleware('http')
    async def local_requests(request: Request, call_next):
        origin = request.headers.get('origin')
        allowed = {str(request.base_url).rstrip('/'), 'http://127.0.0.1:5173', 'http://localhost:5173'}
        if request.headers.get('sec-fetch-site') == 'cross-site' or (origin and origin not in allowed):
            return JSONResponse({'detail': '仅接受本机页面的请求'}, status_code=403)
        result = await call_next(request)
        result.headers['X-Content-Type-Options'] = 'nosniff'
        result.headers['Referrer-Policy'] = 'no-referrer'
        if request.url.path.startswith('/api/'):
            result.headers['Cache-Control'] = 'no-store'
        result.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        return result

    def need(category, item_id):
        item = store.get(category, item_id)
        if not item:
            raise HTTPException(404, '没有找到这条内容，可能已被删除')
        return item

    def detail(aid, at=None):
        activity = need('activity', aid)
        records, current = update_memory(store.all('record', aid), at)
        attachments = store.all('attachment', aid)
        for r in records:
            r['attachments'] = [a for a in attachments if a['record_id'] == r['id'] and (at is None or a['created_at'] <= at)]
        active_ids = {r['id'] for r in current}
        assistance = store.all('assistance', aid)
        if at:
            assistance = [h for h in assistance if h['created_at'] <= at]
        for h in assistance:
            h['stale'] = any(rid not in active_ids for rid in h['source_ids'])
        feedback = store.all('feedback', aid)
        if at:
            feedback = [f for f in feedback if f['created_at'] <= at]
        return {'activity': activity, 'records': records, 'current': current,
                'assistance': assistance, 'feedback': feedback, 'as_of': at}

    def enabled(aid):
        activity = need('activity', aid)
        if activity['paused']:
            raise HTTPException(409, '这个活动已暂停帮助；仍可查看和整理记录')
        return activity

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'mode': 'local_rules', 'api_connected': False, 'cash_spend': 0, 'version': '0.1.0'}

    @app.get('/api/activities')
    def activities():
        result = store.all('activity')
        for a in result:
            a['record_count'] = len(store.all('record', a['id']))
        return result[::-1]

    @app.post('/api/activities', status_code=201)
    def add_activity(payload: ActivityInput):
        item = {**payload.model_dump(), 'id': identifier(), 'created_at': now(),
                'paused': False, 'status': 'active', 'data_origin': 'user_entered'}
        return store.put('activity', item)

    @app.get('/api/activities/{aid}')
    def get_activity(aid: str):
        return detail(aid)

    @app.patch('/api/activities/{aid}')
    def patch_activity(aid: str, payload: ActivityPatch):
        with store.lock:
            item = need('activity', aid)
            item.update(payload.model_dump(exclude_none=True))
            return store.put('activity', item)

    @app.post('/api/activities/{aid}/records', status_code=201)
    def add_record(aid: str, payload: RecordInput):
        with store.lock:
            snapshot = detail(aid)
            visible = {r['id'] for r in snapshot['records']}
            active = {r['id'] for r in snapshot['current']}
            if payload.supersedes and payload.supersedes not in active:
                raise HTTPException(422, '只能更正本活动中当前有效的记录')
            if any(rid not in visible for rid in payload.derived_from):
                raise HTTPException(422, '转述来源必须来自本活动')
            if payload.after_help_id:
                h = need('assistance', payload.after_help_id)
                if h['activity_id'] != aid:
                    raise HTTPException(422, '帮助记录不属于当前活动')
            stamp = now()
            item = organize_record({**payload.model_dump(), 'id': identifier(), 'activity_id': aid,
                                    'created_at': stamp, 'recorded_at': stamp, 'retracted_at': None,
                                    'data_origin': snapshot['activity']['data_origin']})
            return store.put('record', item)

    @app.post('/api/records/{rid}/retract')
    def retract(rid: str):
        with store.lock:
            item = need('record', rid)
            item['retracted_at'] = item.get('retracted_at') or now()
            return store.put('record', item)

    @app.post('/api/activities/{aid}/assistance', status_code=201)
    def help_activity(aid: str, payload: HelpInput):
        with store.lock:
            enabled(aid)
            started = time.perf_counter()
            snapshot = detail(aid)
            answer = choose_assistance(snapshot['current'], payload.mode, payload.question)
            item = {**answer, **payload.model_dump(), 'id': identifier(), 'activity_id': aid,
                    'created_at': now(), 'engine': 'local_rules', 'model_label': 'source-rules-v1',
                    'input_snapshot': {'records': snapshot['records'], 'prior_help_ids': [h['id'] for h in snapshot['assistance']]},
                    'cost_usd': 0, 'latency_ms': round((time.perf_counter() - started) * 1000, 2)}
            return store.put('assistance', item)

    @app.post('/api/activities/{aid}/assistance/import', status_code=201)
    def import_help(aid: str, payload: ImportInput):
        with store.lock:
            enabled(aid)
            snapshot = detail(aid)
            active = {r['id']: r for r in snapshot['current']}
            visible = {r['id']: r for r in snapshot['records']}
            input_ids = payload.input_record_ids if payload.input_record_ids is not None else payload.source_ids
            if any(rid not in visible for rid in input_ids) or len(set(input_ids)) != len(input_ids):
                raise HTTPException(422, '输入材料必须来自本活动，且不能重复')
            if not set(payload.source_ids).issubset(set(input_ids)):
                raise HTTPException(422, '引用必须来自当时提供的输入材料')
            if any(rid not in active for rid in payload.source_ids):
                raise HTTPException(422, '请仅引用本活动中当前有效的记录')
            if len(set(payload.source_ids)) != len(payload.source_ids):
                raise HTTPException(422, '引用不能重复')
            item = {**payload.model_dump(), 'id': identifier(), 'activity_id': aid, 'created_at': now(),
                    'mode': 'answer', 'status': 'unverified', 'engine': 'manual_import',
                    'input_snapshot': {'records': [visible[rid] for rid in input_ids],
                                       'prior_help_ids': [h['id'] for h in snapshot['assistance']]},
                    'cost_usd': None, 'latency_ms': None}
            return store.put('assistance', item)

    @app.post('/api/assistance/{hid}/feedback', status_code=201)
    def feedback(hid: str, payload: FeedbackInput):
        h = need('assistance', hid)
        return store.put('feedback', {**payload.model_dump(), 'id': identifier(), 'created_at': now(),
                                     'activity_id': h['activity_id'], 'assistance_id': hid})

    @app.post('/api/records/{rid}/attachments', status_code=201)
    async def attach(rid: str, file: UploadFile = File(...)):
        content = await file.read(MAX_IMAGE_BYTES + 1)
        await file.close()
        if len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(413, '照片最大为 8 MB')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as im:
                    image_format = im.format
                    if image_format not in ('PNG', 'JPEG', 'WEBP'):
                        raise ValueError()
                    im.verify()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise HTTPException(422, '请选择有效的 JPG、PNG 或 WebP 照片，像素总数不超过 2000 万')
        with store.lock:
            r = need('record', rid)
            if len([a for a in store.all('attachment', r['activity_id']) if a['record_id'] == rid]) >= 5:
                raise HTTPException(422, '每条记录最多保存 5 张照片')
            fid = identifier()
            extension = {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp'}[image_format]
            filename = f'{fid}.{extension}'
            path = store.files / filename
            path.write_bytes(content)
            item = {'id': fid, 'record_id': rid, 'activity_id': r['activity_id'], 'created_at': now(),
                    'filename': filename, 'url': f'/api/attachments/{fid}', 'size': len(content),
                    'media_type': f'image/{"jpeg" if extension == "jpg" else extension}'}
            try:
                return store.put('attachment', item)
            except Exception:
                path.unlink(missing_ok=True)
                raise

    @app.get('/api/attachments/{fid}')
    def attachment(fid: str):
        a = need('attachment', fid)
        path = store.files / a['filename']
        if not path.is_file():
            raise HTTPException(404, '照片文件缺失，请检查备份')
        return FileResponse(path, media_type=a['media_type'])

    @app.get('/api/activities/{aid}/replay')
    def replay(aid: str, at: str):
        try:
            stamp = datetime.fromisoformat(at)
            if stamp.tzinfo is None:
                raise ValueError()
            cutoff = stamp.astimezone(timezone.utc).isoformat(timespec='microseconds')
        except ValueError:
            raise HTTPException(422, '回放时间必须包含时区')
        return detail(aid, cutoff)

    @app.get('/api/activities/{aid}/export')
    def export_activity(aid: str):
        return JSONResponse({'schema_version': 1, 'exported_at': now(), **detail(aid)},
                            headers={'Content-Disposition': 'attachment; filename="activity.json"'})

    @app.get('/api/backup')
    def backup():
        with store.lock:
            buffer = BytesIO()
            categories = ['activity', 'record', 'assistance', 'feedback', 'attachment']
            manifest = {'schema_version': 1, 'exported_at': now(), 'collections': {c: store.all(c) for c in categories}}
            if sum(a['size'] for a in manifest['collections']['attachment']) > 240 * 1024 * 1024:
                raise HTTPException(413, '当前照片超过原型的内存备份上限，请停止服务后复制整个 data 目录备份')
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
                z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
                for a in manifest['collections']['attachment']:
                    path = store.files / a['filename']
                    if not path.is_file():
                        raise HTTPException(409, '有照片文件缺失，本次备份未完成')
                    z.write(path, f"attachments/{a['filename']}")
            return Response(buffer.getvalue(), media_type='application/zip',
                            headers={'Content-Disposition': 'attachment; filename="memory-backup.zip"'})

    @app.delete('/api/activities/{aid}', status_code=204)
    def delete_activity(aid: str):
        with store.lock:
            need('activity', aid)
            files = [store.files / a['filename'] for a in store.all('attachment', aid)]
            for path in files:
                if path.resolve().parent != store.files.resolve():
                    raise HTTPException(409, '附件路径异常，未执行删除')
                path.unlink(missing_ok=True)
            store.delete_activity(aid)
        return Response(status_code=204)

    @app.get('/api/research')
    def research():
        path = PROJECT / 'research' / 'startup.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

    @app.post('/api/demo', status_code=201)
    def demo():
        with store.lock:
            existing = [a for a in store.all('activity') if a['data_origin'] == 'synthetic_demo']
            if existing:
                return existing[0]
            a = add_activity(ActivityInput(title='周末和家人去植物园', description='人工构造的体验示例，可删除。不是任何人的真实经历。'))
            a['data_origin'] = 'synthetic_demo'
            store.put('activity', a)
            initial = add_record(a['id'], RecordInput(content='原计划周六下午两点在植物园南门见面。', kind='plan'))
            add_record(a['id'], RecordInput(content='家人商量后改成周日下午两点，仍在南门见面。', kind='change',
                                         supersedes=initial['id'], source_kind='family', source_label='家人', source_authorized=True))
            add_record(a['id'], RecordInput(content='想带上上次一起看的植物手册，接着聊那棵树。', kind='experience'))
            return a

    if (PROJECT / 'dist').is_dir():
        app.mount('/', StaticFiles(directory=PROJECT / 'dist', html=True), name='frontend')
    return app
