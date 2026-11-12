"""Transparent rule baselines, not a learned cognitive model."""
import re


def organize_record(item):
    return {**item, 'derived_from': list(dict.fromkeys(item.get('derived_from', [])))}


def update_memory(records, at=None):
    visible = [r.copy() for r in records if at is None or r['recorded_at'] <= at]
    by_id = {r['id']: r for r in visible}
    retracted = {r['id'] for r in visible if r.get('retracted_at') and (at is None or r['retracted_at'] <= at)}
    suppressed = set()
    # A surviving correction supersedes all earlier links in its correction chain.
    for r in visible:
        if r['id'] in retracted:
            continue
        parent, seen = r.get('supersedes'), set()
        while parent and parent in by_id and parent not in seen:
            seen.add(parent)
            suppressed.add(parent)
            parent = by_id[parent].get('supersedes')
    for r in visible:
        r['state'] = 'retracted' if r['id'] in retracted else 'superseded' if r['id'] in suppressed else 'active'
        if at and r.get('retracted_at') and r['retracted_at'] > at:
            r['retracted_at'] = None
        r['source_warning'] = any(x in retracted or x not in by_id for x in r.get('derived_from', []))
    return visible, [r for r in visible if r['state'] == 'active']


def choose_assistance(current, mode, question=''):
    candidates = current
    if question.strip():
        # Deliberately conservative lexical retrieval. No semantic/LLM claim.
        terms = [t for t in re.split(r'[\s，。！？、?]+', question.strip()) if t]
        candidates = [r for r in current if any(t in r['content'] or t in r['source_label'] for t in terms)]
    candidates = candidates[-5:]
    if not candidates:
        return {'text': '还没有找到相符的记录。可以换一个记录中出现的关键词，或先留下一条线索。',
                'source_ids': [], 'status': 'unknown'}
    lines = [f"{r['source_label']}的记录：{r['content']}" for r in candidates]
    prefix = '可以从这些真实记录开始回想。你也可以直接查看内容，或随时停止。' if mode == 'cue' else '当前仍有效的记录如下。内容反映各来源的说法，未独立确认现实状态。'
    return {'text': prefix + '\n\n' + '\n\n'.join(lines),
            'source_ids': [r['id'] for r in candidates], 'status': 'available'}
