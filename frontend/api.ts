export interface Activity { id: string; title: string; description: string; paused: boolean; status: 'active' | 'completed'; data_origin: string; record_count: number; created_at: string }
export interface Attachment { id: string; url: string; size: number }
export interface RecordItem { id: string; content: string; source_label: string; source_kind: string; kind: string; recorded_at: string; occurred_at: string | null; supersedes: string | null; derived_from: string[]; after_help_id: string | null; state: string; source_warning: boolean; attachments: Attachment[] }
export interface HelpItem { id: string; text: string; engine: string; model_label: string; source_ids: string[]; created_at: string; stale: boolean; mode: string; status: string }
export interface Feedback { id: string; assistance_id: string; kind: string; content: string }
export interface Detail { activity: Activity; records: RecordItem[]; current: RecordItem[]; assistance: HelpItem[]; feedback: Feedback[] }
export interface Research { journey: {stage:string; need:string; action:string; observe:string}[]; candidates:{title:string; failure:string; baseline:string; hypothesis:string; falsifier:string; status:string}[]; baselines:{name:string;state:string;limit:string}[]; interview:string[]; next:string[]; cases:{pair:string;condition:string;input:string;expected:string;origin:string;split:string}[] }

export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body instanceof FormData ? undefined : body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({detail:'请求失败，请检查本地服务是否仍在运行'}));
    const message = Array.isArray(payload.detail) ? payload.detail.map((d: {msg: string}) => d.msg.replace('Value error, ', '')).join('；') : payload.detail;
    throw new Error(message || '请求未完成');
  }
  return response.status === 204 ? undefined as T : response.json();
}

export async function download(path: string, name: string) {
  const r = await fetch(`/api${path}`);
  if (!r.ok) { const body = await r.json(); throw new Error(body.detail || '导出失败'); }
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement('a'); a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
}
