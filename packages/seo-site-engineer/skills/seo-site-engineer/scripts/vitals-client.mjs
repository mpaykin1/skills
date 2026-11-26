// Browser adapter. Bundle with a verified locally installed web-vitals@5.1.0.
import {onCLS,onINP,onLCP} from 'web-vitals';
let started = false;
const token = /^[A-Za-z0-9._-]{1,80}$/;
export function startVitals({route,device,release,allowedRoutes,enabled,sink} = {}) {
  if (started || typeof enabled !== 'function' || typeof sink !== 'function' || !enabled()) return false;
  if (!Array.isArray(allowedRoutes) || !allowedRoutes.includes(route) || !token.test(route) || !token.test(release) || !['mobile','desktop','unknown'].includes(device)) throw new Error('Use fixed approved route/release/device labels');
  started = true;
  const report = (m) => {
    if (!enabled() || !['LCP','INP','CLS'].includes(m.name) || !Number.isFinite(m.value) || m.value < 0 || !token.test(m.id)) return;
    const value = m.name === 'CLS' ? Math.round(m.value * 10000)/10000 : Math.round(m.value);
    // No URL, query, attribution, text, user identifier, or storage.
    const row = {schema:1,source:'field',route,device,release,metric:m.name,value,id:m.id};
    try { const result = sink(Object.freeze(row)); if(result?.catch) result.catch(()=>{}); } catch { /* metrics must never break UI */ }
  };
  const opts = {reportAllChanges:false};
  onCLS(report,opts); onINP(report,opts); onLCP(report,opts);
  return true;
}
