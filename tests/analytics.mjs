import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const root=new URL('../',import.meta.url),context={Date,URL};
for(const name of ['math.js','practice.js'])vm.runInNewContext(fs.readFileSync(new URL('docs/assets/'+name,root),'utf8'),context);
const M=context.MarketMath,P=context.MarketPractice;let checks=0;
function eq(a,b,tol=1e-10){assert.ok(Number.isFinite(a)&&Math.abs(a-b)<tol,`${a} != ${b}`);checks++;}
function ok(value){assert.ok(value);checks++;}
function throws(fn){assert.throws(fn);checks++;}
function series(values,dates){return {interval:'1d',bars:values.map((close,i)=>({time:dates?.[i]||`2025-01-${String(i+1).padStart(2,'0')}`,close,adj_close:close}))};}
eq(M.mean([1,2,3]),2);eq(M.median([1,2,100]),2);eq(M.median([1,2,3,4]),2.5);eq(M.sampleSD([1,2,3]),1);ok(M.sampleSD([1])===null);ok(M.mean([])===null);
const a=series([100,110,99]),s=M.summary(a);eq(s.change,-.01);eq(s.mean,0);eq(s.median,0);eq(s.sd,Math.sqrt(.02));ok(s.count===3);ok(s.returns.length===2);
const positive=M.align(a,series([200,240,192]));eq(positive.correlation,1);
const negative=M.align(a,series([100,90,99]));eq(negative.correlation,-1);
ok(M.align(series([100,100,100]),a).correlation===null);
ok(M.align(series([100,110,121,133.1]),series([2,3,2,5])).correlation===null);
const matches=M.align(series([100,105,110,120]),series([50,55,60],['2025-01-02','2025-01-03','2025-01-04']));ok(matches.pairs.length===3);eq(matches.ra[0],110/105-1);eq(matches.rb[0],.1);
const invalid=series([100,0,-1,110]);ok(M.summary(invalid).excluded===2);eq(M.summary(invalid).change,.1);
const missing=series([100,110]);missing.bars[1].adj_close=null;ok(M.summary(missing,'adj_close').count===1);ok(M.summary(missing,'adj_close').sd===null);
for(const n of [6,12,20]){const bins=M.histogram([-.1,0,0,.01,.1],n);ok(bins.length===n);ok(bins.reduce((t,b)=>t+b.count,0)===5);}
ok(M.histogram([0,0,0]).reduce((t,b)=>t+b.count,0)===3);
const imported=M.parseCSV('Date,Open,High,Low,Close,Adj Close,Volume\r\n2025-01-02,98,101,97,100,99,1000\r\n2025-01-03,100,112,99,110,109,2000\r\n');ok(imported.bars.length===2);eq(imported.bars[0].adj_close,99);ok(imported.source.kind==='user_import');
throws(()=>M.parseCSV('Date,Open\n2025-01-02,100\n2025-01-03,110'));
throws(()=>M.parseCSV('Date,Close\n2025-01-02,100\n2025-01-02,110'));
throws(()=>M.parseCSV('Date,Close\n2025-01-02,100\n2025-01-03,no'));
throws(()=>M.parseCSV('Date,Close\n2025-01-02,100\n2025-01-03,"110'));
const quoted=M.parseCSV('Date,Close,Volume\n"2025-01-02","100","1,000"\n"2025-01-03","110","2,000"');eq(quoted.bars[0].volume,1000);
ok(M.csvCell('=1+1').startsWith('"\''));ok(M.csvCell(-10)==='-10');ok(M.csvCell('a"b')==='"a""b"');
for(const symbol of ['AAPL','MSFT','NKE','DIS','TGT','NVDA','GOOGL','SPY'])for(const range of ['1D','5D','1M','6M','1Y','5Y']){const data=P.get(symbol,range);ok(data.source.kind==='practice_simulated');ok(data.source.simulated===true);ok(data.bars.length>=2);ok(data.fetched_at===null);ok(data.bars.every(b=>b.close>0&&b.high>=Math.max(b.open,b.close)&&b.low<=Math.min(b.open,b.close)));ok(M.summary(data).returns.length===data.bars.length-1);const csv=M.exportCSV(data);ok(csv.includes('SIMULATED'));ok(csv.split('\r\n').length===data.bars.length+1);}
const practice=P.get('AAPL','1Y'),copy=P.get('AAPL','1Y');eq(practice.bars[0].close,copy.bars[0].close);practice.bars[0].close=0;ok(P.get('AAPL','1Y').bars[0].close>0);
const reimported=M.parseCSV(M.exportCSV(P.get('AAPL','1M')));ok(reimported.source.kind==='user_import');ok(reimported.bars.length===22);
throws(()=>P.get('FAKE','1Y'));
const html=fs.readFileSync(new URL('docs/index.html',root),'utf8'),app=fs.readFileSync(new URL('docs/assets/app.js',root),'utf8');
new vm.Script(app);for(const id of [...app.matchAll(/\$\('([^']+)'\)/g)].map(m=>m[1]))if(!['hover-line','hover-dot'].includes(id))ok(html.includes('id="'+id+'"'));
ok(html.includes('The Opus Way of Teaching'));ok(html.includes('Ventures in Business Engineering'));ok(html.includes('Jiang (Will) Zhang'));
console.log(`Passed ${checks} analytics, CSV, simulation-provenance, and UI-reference checks.`);
