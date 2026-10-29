const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const root = path.join(__dirname, '..');
const transpile = text => ts.transpileModule(text, {compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS}}).outputText;

function translated(lang) {
  const exports = {};
  vm.runInNewContext(transpile(fs.readFileSync(path.join(root,'src/i18n.ts'),'utf8')),
    {exports,window:{},navigator:{language:lang}});
  const warning = {};
  vm.runInNewContext(transpile(fs.readFileSync(path.join(root,'src/Utils/installerWarning.ts'),'utf8')),
    {exports:warning,require:()=>exports});
  return {t:exports.t, warning:warning.installerWarning};
}

(async()=>{
  for(const lang of ['en','fr','de','es','it','pt','nl','pl','ru']) {
    const {warning}=translated(lang);
    const text=warning({InstallerExitCode:3});
    assert.ok(text.includes('3')&&!text.includes('{code}')&&text!=='ea_installer_warning',lang);
    for(const value of [undefined,null,0,'3','<script>',NaN,Infinity,1.2,{}])
      assert.equal(warning({InstallerExitCode:value}),'');
  }
  const {t,warning}=translated('fr');
  const queue=fs.readFileSync(path.join(root,'src/Utils/downloadQueue.ts'),'utf8');
  const start=queue.indexOf('async function tick()');
  const end=queue.indexOf('export function startQueueRunner',start);
  assert.ok(start>=0&&end>start);
  for(const failed of [false,true]) {
    const state={current:{set:'EAActions',shortname:'fixture',name:'Fixture Game'},pending:[]};
    const notices=[];let finished=0,saved=0;
    const context={api:{},busy:false,load:async()=>state,save:async()=>saved++,
      executeAction:async()=>({Content:{Percentage:100,InstallerExitCode:3,...(failed?{Error:'fixture',ErrorCode:'unknown'}:{})}}),
      notify:n=>notices.push(n),t,installerWarning:warning,errorText:()=>'',
      finishInstall:async()=>{finished++;return 123;},
      logger:{error:e=>{throw e;},log:()=>{}}};
    vm.createContext(context);
    vm.runInContext(transpile(queue.slice(start,end)+'\nexports.run=tick;'),Object.assign(context,{exports:{}}));
    await context.exports.run();
    assert.equal(notices.length,1);
    assert.equal(saved,1);
    assert.equal(state.current,null);
    assert.equal(finished,failed?0:1);
    if(!failed)assert.ok(notices[0].body.includes('installeur EA')&&notices[0].body.includes('code 3'));
  }
  console.log('EA warnings: 9 locales, invalid input rejection, real queue completion/error paths passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
