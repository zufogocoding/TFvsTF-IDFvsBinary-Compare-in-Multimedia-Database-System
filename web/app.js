"use strict";
const $ = (s) => document.querySelector(s);
const fmt = (n, digits=4) => Number(n).toLocaleString('en-US',{minimumFractionDigits:digits,maximumFractionDigits:digits});
const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const methodNames = {BINARY:'Binary',TF:'TF',TFIDF:'TF-IDF'};
const methodClasses = {BINARY:'binary',TF:'tf',TFIDF:'tfidf'};
const captions = {BINARY:'Sự hiện diện của thuật ngữ',TF:'Số lần thuật ngữ xuất hiện',TFIDF:'Tần suất × độ hiếm trong kho'};
let allQueries=[], selectedQueryId=null, busy=false, polling=null, lastSummary=null;

async function api(url, options={}) {
  const response=await fetch(url,options);
  const data=await response.json();
  if(!response.ok) throw new Error(data.error || 'Không xử lý được yêu cầu');
  return data;
}
function showError(error){$('#global-error').textContent=error.message || String(error);$('#global-error').hidden=false;}
function clearError(){$('#global-error').hidden=true;}
function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;setTimeout(()=>$('#toast').hidden=true,4000);}

function activateTab(name){
  document.querySelectorAll('[data-tab]').forEach(btn=>{const active=btn.dataset.tab===name;btn.setAttribute('aria-selected',String(active));btn.tabIndex=active?0:-1;});
  ['search','experiment','data'].forEach(tab=>$('#panel-'+tab).hidden=tab!==name);
  if(name==='data')loadDatabase();
}
document.querySelectorAll('[data-tab]').forEach((btn,i,buttons)=>{
  btn.addEventListener('click',()=>activateTab(btn.dataset.tab));
  btn.addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight'].includes(event.key)){event.preventDefault();const next=buttons[(i+(event.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length];activateTab(next.dataset.tab);next.focus();}});
});

function renderSearch(result){
  const meta=[`${result.inspection.tokens.length} token`,`${result.inspection.unique_count} thuật ngữ phân biệt`,`${result.inspection.oov_tokens.length} thuật ngữ ngoài từ vựng`];
  if(result.query)meta.unshift(`Q${result.query.query_id} · ${result.query.split} · có nhãn chuẩn`);
  else meta.unshift('Truy vấn tự nhập · chưa có nhãn đánh giá');
  $('#query-meta').innerHTML=meta.map(x=>`<span>${escapeHtml(x)}</span>`).join('');$('#query-meta').hidden=false;
  $('#results').innerHTML=Object.entries(result.methods).map(([method,output])=>{
    const list=output.items.map(item=>{
      let label='';
      if(result.query)label=`<span class="relevance ${item.relevant?'positive':''}">${item.relevant?'Liên quan':item.raw_grade===null?'Chưa được gán nhãn · tính 0':'Không liên quan'}</span>`;
      return `<article class="result-item"><div class="result-top"><span class="result-rank">#${item.rank} · DOC ${escapeHtml(item.doc_id)}</span><span class="result-score">${fmt(item.score)}</span></div><button class="document-link" data-document="${escapeHtml(item.doc_id)}">${escapeHtml(item.title || 'Không có tiêu đề')}</button><p class="snippet">${escapeHtml(item.snippet)}${item.snippet.length>=350?'…':''}</p>${label}</article>`;
    }).join('');
    return `<section class="method-card ${methodClasses[method]}" aria-label="Kết quả ${methodNames[method]}"><div class="method-header"><div class="method-heading"><h3>${methodNames[method]}</h3><span class="method-badge">COSINE</span></div><p class="method-caption">${captions[method]}</p><div class="method-totals"><span><strong>${output.returned_count}</strong> văn bản khớp</span><span>Top <strong>${output.items.length}</strong></span></div>${output.metrics?`<span class="method-ap">AP ${fmt(output.metrics.AP)} · P@10 ${fmt(output.metrics['P@10'],2)}</span>`:''}</div>${list || '<p class="no-results">Không có thuật ngữ mang trọng số khớp với kho tài liệu. Hãy thử truy vấn tiếng Anh khác.</p>'}</section>`;
  }).join('');
  $('#weights-table').innerHTML=`<table><thead><tr><th>Thuật ngữ</th><th class="numeric">Binary</th><th class="numeric">TF</th><th class="numeric">IDF</th><th class="numeric">TF-IDF</th></tr></thead><tbody>${result.inspection.weights.map(w=>`<tr><td>${escapeHtml(w.term)}</td><td class="numeric">1</td><td class="numeric">${w.count}</td><td class="numeric">${fmt(w.idf)}</td><td class="numeric">${fmt(w.tfidf)}</td></tr>`).join('')}</tbody></table>`;
  $('#weights-details').hidden=false;
}

$('#search-form').addEventListener('submit',async event=>{
  event.preventDefault();clearError();const button=$('#search-button');button.disabled=true;button.textContent='Đang truy xuất…';
  try{const payload={query:$('#query').value,top_k:Number($('#top-k').value)};if(selectedQueryId)payload.query_id=selectedQueryId;renderSearch(await api('/api/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}));}
  catch(error){showError(error);}finally{button.disabled=busy;button.innerHTML='So sánh kết quả <span aria-hidden="true">↗</span>';}
});
$('#sample-query').addEventListener('change',event=>{selectedQueryId=event.target.value || null;if(selectedQueryId)$('#query').value=allQueries.find(q=>q.query_id===selectedQueryId).text;});
$('#query').addEventListener('input',()=>{selectedQueryId=null;$('#sample-query').value='';});
$('#results').addEventListener('click',async event=>{
  const button=event.target.closest('[data-document]');if(!button)return;
  try{const doc=await api('/api/documents/'+encodeURIComponent(button.dataset.document));$('#document-code').textContent='CRANFIELD · DOC '+doc.doc_id;$('#document-title').textContent=doc.title;$('#document-author').textContent=[doc.author,doc.bib].filter(Boolean).join(' · ');$('#document-body').textContent=doc.body;$('#document-dialog').showModal();}
  catch(error){showError(error);}
});
$('#close-document').addEventListener('click',()=>$('#document-dialog').close());
$('#document-dialog').addEventListener('click',event=>{const r=event.target.getBoundingClientRect();if(event.target===$('#document-dialog')&&(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom))event.target.close();});

function exportLink(id,name,label){return `<a href="/api/exports/${encodeURIComponent(id)}/${encodeURIComponent(name)}">${label} ↓</a>`;}
function renderSummary(s){
  if(!s)return;lastSummary=s;
  const rows=Object.entries(s.methods).map(([m,v])=>`<tr><td><span class="method-tag ${methodClasses[m]}">${methodNames[m]}</span></td>${['MAP','nDCG_binary@10','P@5','P@10','R@10','R@20'].map(key=>`<td class="numeric">${fmt(v[key])}</td>`).join('')}</tr>`).join('');
  const costs=Object.entries(s.methods).map(([m,v])=>`<tr><td>${methodNames[m]}</td><td class="numeric">${fmt(v.timing.p50_ms,3)}</td><td class="numeric">${fmt(v.timing.p95_ms,3)}</td><td class="numeric">${fmt(v.index.csr_bytes/1024/1024,2)}</td><td class="numeric">${v.timing.samples.toLocaleString()}</td></tr>`).join('');
  const bars=Object.entries(s.methods).map(([m,v])=>`<div class="bar-row"><span>${methodNames[m]}</span><div class="bar-track"><div class="bar-fill ${methodClasses[m]}" style="width:${Math.max(0,Math.min(100,v.MAP*100))}%"></div></div><strong>${fmt(v.MAP)}</strong></div>`).join('');
  const pairs=s.paired_comparisons.map(p=>`<tr><td>${methodNames[p.a]} − ${methodNames[p.b]}</td><td class="numeric">${fmt(p.mean_ap_difference_a_minus_b)}</td><td class="numeric">[${fmt(p.ci95_percentile[0])}, ${fmt(p.ci95_percentile[1])}]</td><td class="numeric">${p.a_wins} / ${p.b_wins} / ${p.ties}</td></tr>`).join('');
  $('#experiment-summary').innerHTML=`<div class="summary-card"><div class="summary-meta"><span>${escapeHtml(s.experiment_id)}</span><span>${s.split} · ${s.query_count} truy vấn</span><span>${s.timing_repeats} lượt đo</span><span>${new Date(s.completed_at_utc).toLocaleString('vi-VN')}</span></div><h3>Chất lượng truy xuất · trung bình theo truy vấn</h3><div class="table-scroll"><table><thead><tr><th>Biểu diễn</th><th class="numeric">MAP</th><th class="numeric">nDCG@10 (binary)</th><th class="numeric">P@5</th><th class="numeric">P@10</th><th class="numeric">R@10</th><th class="numeric">R@20</th></tr></thead><tbody>${rows}</tbody></table></div><div class="download-links">${exportLink(s.experiment_id,'summary.csv','Bảng tổng hợp CSV')}${exportLink(s.experiment_id,'per_query_metrics.csv','Chỉ số từng truy vấn')}${exportLink(s.experiment_id,'rankings.tsv','Toàn bộ thứ hạng')}${exportLink(s.experiment_id,'summary.json','Kết quả JSON')}</div></div><div class="summary-grid"><div class="summary-card"><h3>MAP · thang từ 0 đến 1</h3><div class="map-bars">${bars}</div><p class="small-note">Giá trị đo trên đúng tập truy vấn và cấu hình này. Không mặc định thứ tự tốt nhất cho mọi bộ dữ liệu.</p></div><div class="summary-card"><h3>Chi phí truy xuất và lưu trữ</h3><div class="table-scroll"><table><thead><tr><th>Biểu diễn</th><th class="numeric">p50 ms</th><th class="numeric">p95 ms</th><th class="numeric">CSR MiB</th><th class="numeric">Mẫu</th></tr></thead><tbody>${costs}</tbody></table></div><p class="small-note">Ma trận float64 cho cả ba phương pháp. Độ trễ được đo với chỉ mục trong bộ nhớ.</p>${exportLink(s.experiment_id,'timing_samples.csv','Tải mẫu thời gian')}</div></div><div class="summary-card"><h3>Chênh lệch AP ghép cặp theo truy vấn</h3><div class="table-scroll"><table><thead><tr><th>Cặp phương pháp</th><th class="numeric">Δ MAP</th><th class="numeric">Khoảng bootstrap 95%</th><th class="numeric">A hơn / B hơn / hòa</th></tr></thead><tbody>${pairs}</tbody></table></div><p class="small-note">10.000 mẫu bootstrap ghép cặp, seed 42. Phân tích thăm dò; không tuyên bố đã hiệu chỉnh nhiều phép so sánh.</p><div class="download-links">${exportLink(s.experiment_id,'config.json','Cấu hình')}${exportLink(s.experiment_id,'environment.json','Môi trường đo')}${exportLink(s.experiment_id,'manifest.json','Nguồn & dấu vết')}${exportLink(s.experiment_id,'paired_comparisons.json','Bootstrap JSON')}</div></div>`;
}
async function loadSummary(id=null){try{renderSummary(await api('/api/summary'+(id?'?experiment_id='+encodeURIComponent(id):'')));}catch(error){showError(error);}}
async function loadHistory(rows=null){
  const history=rows || (await api('/api/status')).history;
  const completed=history.filter(r=>r.status==='COMPLETED');
  const select=$('#experiment-history');select.replaceChildren();
  for(const row of completed){const option=document.createElement('option');option.value=row.experiment_id;option.textContent=`${row.split} · ${new Date(row.completed_at).toLocaleString('vi-VN')} · ${row.experiment_id}`;select.append(option);}
  if(!completed.length){const option=document.createElement('option');option.value='';option.textContent='Chưa có lần chạy hoàn tất';select.append(option);}
}
$('#experiment-history').addEventListener('change',event=>loadSummary(event.target.value));
async function loadDatabase(){try{const rows=await api('/api/database');$('#database-table').innerHTML=`<table><thead><tr><th>Bảng</th><th class="numeric">Số bản ghi</th></tr></thead><tbody>${rows.map(r=>`<tr><td><code>${escapeHtml(r.table)}</code></td><td class="numeric">${r.rows.toLocaleString()}</td></tr>`).join('')}</tbody></table>`;}catch(error){showError(error);}}
function updateProgress(state){
  busy=state.running;$('#evaluate-button').disabled=busy;$('#search-button').disabled=busy;
  $('#experiment-progress').hidden=!busy && !state.error;
  const labels={starting:'Chuẩn bị thực nghiệm',quality:'Đánh giá chất lượng',timing:'Đo thời gian truy xuất',completed:'Đã hoàn tất',failed:'Thực nghiệm gặp lỗi'};
  $('#progress-label').textContent=(labels[state.stage]||state.stage)+(state.total?` · ${state.done}/${state.total} truy vấn`:'')+(state.error?' · '+state.error:'');
  $('#progress-bar').value=state.total?state.done/state.total*100:0;
}
async function poll(){try{const state=await api('/api/experiment-status');const wasBusy=busy;updateProgress(state);if(!state.running){clearInterval(polling);polling=null;if(wasBusy){await loadHistory();await loadSummary();if(!state.error)toast('Đã hoàn tất thực nghiệm. Kết quả và tệp xuất đã sẵn sàng.');}}}catch(error){showError(error);clearInterval(polling);polling=null;busy=false;$('#evaluate-button').disabled=false;$('#search-button').disabled=false;}}
$('#evaluate-button').addEventListener('click',async()=>{clearError();try{updateProgress(await api('/api/evaluate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({split:$('#evaluation-split').value,repeats:Number($('#evaluation-repeats').value)})}));if(!polling)polling=setInterval(poll,800);}catch(error){showError(error);}});

async function init(){
  try{const [status,queries]=await Promise.all([api('/api/status'),api('/api/queries')]);allQueries=queries;
    $('#stat-docs').textContent=status.dataset.counts.documents.toLocaleString();$('#stat-queries').textContent=status.dataset.counts.queries.toLocaleString();$('#stat-qrels').textContent=status.dataset.counts.qrels.toLocaleString();$('#stat-vocab').textContent=status.index.vocabulary_size.toLocaleString();
    $('#data-quality-note').textContent=`${status.index.methods.TF.zero_documents} văn bản không tạo được token được giữ nguyên trong kho và nhận điểm 0; không xóa để bảo toàn nhãn.`;
    for(const split of ['DEV','TEST']){const group=document.createElement('optgroup');group.label=split==='DEV'?'DEV · tập phát triển':'TEST · tập kiểm thử';for(const q of queries.filter(x=>x.split===split)){const option=document.createElement('option');option.value=q.query_id;option.textContent=`Q${q.query_id} · ${q.text.slice(0,105)}`;group.append(option);}$('#sample-query').append(group);}
    updateProgress(status.experiment);if(status.experiment.running)polling=setInterval(poll,800);await loadHistory(status.history);await loadSummary();
  }catch(error){showError(error);}
}
init();
