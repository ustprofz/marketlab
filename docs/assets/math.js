/* Pure analytics and CSV utilities; shared by the page and numerical tests. */
(function () {
  'use strict';
  const finite = x => typeof x === 'number' && Number.isFinite(x);
  const mean = values => values.length ? values.reduce((a,b)=>a+b,0)/values.length : null;
  function median(values) { if(!values.length)return null;const a=[...values].sort((x,y)=>x-y),m=Math.floor(a.length/2);return a.length%2?a[m]:(a[m-1]+a[m])/2; }
  function sampleSD(values) { if(values.length<2)return null;const m=mean(values);return Math.sqrt(values.reduce((s,x)=>s+(x-m)**2,0)/(values.length-1)); }
  function points(series,basis='close') { return series.bars.filter(b=>finite(b[basis])&&b[basis]>0).map(b=>({time:b.time,value:b[basis],bar:b})); }
  function returns(prices) { return prices.slice(1).map((p,i)=>p/prices[i]-1); }
  function summary(series,basis='close') {
    const p=points(series,basis),v=p.map(x=>x.value),r=returns(v);
    return {points:p,returns:r,count:p.length,excluded:series.bars.length-p.length,change:v.length>1?v.at(-1)/v[0]-1:null,mean:mean(r),median:median(r),sd:sampleSD(r),min:v.length?Math.min(...v):null,max:v.length?Math.max(...v):null};
  }
  function align(a,b,basis='close') {
    const key=(s,p)=>s.interval==='1d'||s.interval==='1wk'?p.time.slice(0,10):String(Date.parse(p.time));
    const pb=new Map(points(b,basis).map(p=>[key(b,p),p]));
    const pairs=points(a,basis).map(p=>({a:p,b:pb.get(key(a,p))})).filter(p=>p.b);
    const ra=returns(pairs.map(p=>p.a.value)),rb=returns(pairs.map(p=>p.b.value));
    const ma=mean(ra),mb=mean(rb),sa=sampleSD(ra),sb=sampleSD(rb);
    let correlation=null;
    if(ra.length>=2&&sa>1e-12&&sb>1e-12){const cov=ra.reduce((s,x,i)=>s+(x-ma)*(rb[i]-mb),0)/(ra.length-1);correlation=Math.max(-1,Math.min(1,cov/sa/sb));}
    return {pairs,ra,rb,correlation,sdA:sa,sdB:sb};
  }
  function histogram(values,count=12) {
    if(!values.length)return [];
    let lo=Math.min(...values),hi=Math.max(...values);
    if(lo===hi){const pad=Math.max(.001,Math.abs(lo)*.1);lo-=pad;hi+=pad;}
    const step=(hi-lo)/count,bins=Array.from({length:count},(_,i)=>({low:lo+i*step,high:lo+(i+1)*step,count:0}));
    values.forEach(v=>bins[Math.max(0,Math.min(count-1,Math.floor((v-lo)/step)))].count++);
    return bins;
  }
  function csvCell(value) {
    if(value===null||value===undefined)return '';
    if(typeof value==='number')return finite(value)?String(value):'';
    let s=String(value);if(/^[\s]*[=+\-@]/.test(s))s="'"+s;
    return '"'+s.replaceAll('"','""')+'"';
  }
  function exportCSV(series) {
    const rows=[['Timestamp','Ticker','Open','High','Low','Close','Adj Close','Volume','Dividends','Stock Splits','Currency','Interval','Exchange Timezone','Data Source','Fetched At']];
    series.bars.forEach(b=>rows.push([b.time,series.symbol,b.open,b.high,b.low,b.close,b.adj_close,b.volume,b.dividends,b.stock_splits,series.currency,series.interval,series.timezone,series.source.label,series.fetched_at]));
    return rows.map(row=>row.map(csvCell).join(',')).join('\r\n');
  }
  function parseCSV(text) {
    text=text.replace(/^\uFEFF/,'');const rows=[];let row=[],field='',quoted=false;
    for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){field+='"';i++;}else if(!quoted&&field.length){throw new Error('Unexpected quote in the CSV.');}else quoted=!quoted;}else if(c===','&&!quoted){row.push(field);field='';}else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(field);if(row.some(x=>x.trim()!==''))rows.push(row);row=[];field='';}else field+=c;}
    if(quoted)throw new Error('The CSV contains an unclosed quote.');row.push(field);if(row.some(x=>x.trim()!==''))rows.push(row);
    if(rows.length<3)throw new Error('Use a header and at least two data rows.');
    if(rows.length>6001)throw new Error('Use no more than 6,000 observations.');
    const headers=rows.shift().map(x=>x.trim().toLowerCase().replace(/[ _-]/g,''));
    const find=(...names)=>names.map(n=>headers.indexOf(n)).find(i=>i>=0)??-1;
    const date=find('timestamp','date','datetime'),close=find('close');
    if(date<0||close<0)throw new Error('The CSV needs Date (or Timestamp) and Close columns.');
    const indexes={open:find('open'),high:find('high'),low:find('low'),adj_close:find('adjclose','adjustedclose'),volume:find('volume'),dividends:find('dividends'),stock_splits:find('stocksplits')};
    const numeric=s=>{if(s===undefined||s.trim()==='')return null;const n=Number(s.trim().replaceAll(',',''));return finite(n)?n:null;};
    const bars=rows.map((r,i)=>{const t=r[date]?.trim();if(!t||!Number.isFinite(Date.parse(t)))throw new Error('Invalid timestamp on CSV row '+(i+2)+'.');const c=numeric(r[close]);if(c===null)throw new Error('Invalid Close on CSV row '+(i+2)+'.');const b={time:t,close:c};Object.entries(indexes).forEach(([key,index])=>b[key]=index<0?null:numeric(r[index]));return b;}).sort((a,b)=>Date.parse(a.time)-Date.parse(b.time));
    if(new Set(bars.map(b=>Date.parse(b.time))).size!==bars.length)throw new Error('Remove duplicate timestamps before importing.');
    // Always classify local uploads as user data, regardless of any Source column.
    return {schema_version:1,symbol:'CSV',name:'Your imported dataset',currency:null,exchange:null,timezone:'As provided in CSV',range:'Imported',interval:bars.every(b=>/^\d{4}-\d{2}-\d{2}$/.test(b.time))?'1d':'custom',source:{kind:'user_import',label:'User-imported CSV · unverified source',simulated:false},fetched_at:new Date().toISOString(),as_of:bars.at(-1).time,quote:{price:bars.at(-1).close,as_of:bars.at(-1).time,kind:'last_returned_bar'},bars};
  }
  globalThis.MarketMath=Object.freeze({mean,median,sampleSD,points,returns,summary,align,histogram,csvCell,exportCSV,parseCSV});
})();
