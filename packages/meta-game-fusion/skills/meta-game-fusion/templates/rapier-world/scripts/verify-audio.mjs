/* Fail-closed verification for original, locally packaged audio assets.
 * Runs before Vite dev/build, never touches user source audio or remote URLs.
 */
import {readFile, lstat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {resolve, join, sep} from 'node:path';
const ROOT=resolve(import.meta.dirname,'..');
const WORLD=join(ROOT,'public','world.json');
const hex=/^[a-f0-9]{64}$/;
const allowed=new Set(['wind','drone','step','rune']);
function check(value,message){if(!value)throw Error('Audio preflight: '+message)}
const world=JSON.parse(await readFile(WORLD,'utf8'));
const spec=world.audio;
check(spec?.schema==='meta-game-fusion.spatial-audio.v1'&&spec?.engine==='howler@2.2.4','missing authored audio plan');
check(spec?.external_audio===false&&spec?.audio_locked_until_user_gesture===true,'unexpected remote or autoplay policy');
check(Object.keys(spec.assets??{}).length===allowed.size,'unexpected audio list');
const dir=await lstat(resolve(ROOT,'public','audio'));
check(dir.isDirectory()&&!dir.isSymbolicLink(),'audio pack directory cannot be a symlink');
for(const [key,entry] of Object.entries(spec.assets??{})){
  check(allowed.has(key)&&entry?.origin==='original-synthesized'&&entry.license==='authored-demo','unknown provenance: '+key);
  check(entry.sources?.length===2,'expected Ogg and MP3 versions');
  for(const src of entry.sources){
    check(src?.uri===`/audio/${key}.ogg`||src?.uri===`/audio/${key}.mp3`,'unsafe audio URI');
    check(hex.test(src.sha256)&&src.bytes>200&&src.bytes<=2_000_000,'invalid SHA/size');
    const file=resolve(ROOT,'public',src.uri.slice(1));
    check(file.startsWith(resolve(ROOT,'public','audio')+sep),'audio path escaped root');
    const stat=await lstat(file);
    check(stat.isFile()&&!stat.isSymbolicLink()&&stat.size===src.bytes,'audio changed: '+src.uri);
    const sum=createHash('sha256').update(await readFile(file)).digest('hex');
    check(sum===src.sha256,'audio SHA-256 mismatch: '+src.uri);
  }
}
console.log('Audio assets verified: 8 original local files');
