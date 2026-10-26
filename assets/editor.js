const $=s=>document.querySelector(s);
let editing=false,photoTarget=null;
const status=t=>{$('#status').textContent=t;};
const strip=$('#page-strip'),counter=$('#page-number'),total=$('#page-total'),jump=$('#jump-page');
function currentIndex(){
  const pages=[...strip.children];if(!pages.length)return 0;
  return pages.reduce((best,p,i)=>Math.abs(p.offsetLeft-pages[0].offsetLeft-strip.scrollLeft)<Math.abs(pages[best].offsetLeft-pages[0].offsetLeft-strip.scrollLeft)?i:best,0);
}
function updatePages(){
  const i=currentIndex(),n=strip.children.length;
  counter.textContent=String(i+1).padStart(2,'0');total.textContent=String(n).padStart(2,'0');
  $('#prev-page').disabled=i===0;$('#next-page').disabled=i>=n-1;jump.value=String(i);
}
function goTo(i){
  const pages=[...strip.children];if(!pages.length)return;
  i=Math.max(0,Math.min(pages.length-1,i));
  strip.scrollTo({left:pages[i].offsetLeft-pages[0].offsetLeft,behavior:'auto'});
  updatePages();
}
$('#prev-page').onclick=()=>goTo(currentIndex()-1);
$('#next-page').onclick=()=>goTo(currentIndex()+1);
strip.addEventListener('scroll',updatePages,{passive:true});
strip.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();goTo(currentIndex()+(e.key==='ArrowRight'?1:-1));}});
jump.onchange=()=>{goTo(Number(jump.value));strip.scrollIntoView({block:'center'});};
updatePages();
function showImage(img){$('#zoom-img').src=img.src;$('#zoom-img').alt=img.alt;$('#zoom').showModal();}
document.addEventListener('click',e=>{const img=e.target.closest('img[data-zoom]');if(img&&!editing)showImage(img);});
document.addEventListener('keydown',e=>{if(e.target.matches('img[data-zoom]')&&['Enter',' '].includes(e.key)){e.preventDefault();showImage(e.target);}});
$('#close-zoom').onclick=()=>$('#zoom').close();
$('#edit').onclick=()=>{
  editing=!editing;document.body.classList.toggle('edit-on',editing);
  document.querySelectorAll('[data-edit]').forEach(e=>e.contentEditable=String(editing));
  $('#edit').setAttribute('aria-pressed',String(editing));$('#edit').textContent=editing?'完成文字编辑':'编辑文字与照片';
  status(editing?'点击文字修改；点击作者照片或二维码替换图片。':'编辑已结束，请下载草稿保存修改。');
};
document.addEventListener('paste',e=>{if(e.target.closest('[data-edit]')){e.preventDefault();document.execCommand('insertText',false,e.clipboardData.getData('text/plain'));}});
document.addEventListener('click',e=>{if(editing&&e.target.closest('[data-link]'))e.preventDefault();});
const read=f=>new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(r.result);r.onerror=no;r.readAsDataURL(f);});
document.querySelectorAll('.photo-slot').forEach(el=>el.onclick=()=>{if(editing){photoTarget=el;$('#photo-file').click();}});
$('#photo-file').onchange=async e=>{
  try{const f=e.target.files[0];if(!f)return;if(!/^image\/(png|jpeg|webp)$/.test(f.type))throw Error('请选择 PNG、JPG 或 WebP 图片。');
    const img=new Image();img.src=await read(f);img.alt=photoTarget.dataset.photo==='qr'?'课题组二维码':'作者照片';img.style.cssText='display:block;width:100%;height:100%;object-fit:'+(photoTarget.dataset.photo==='qr'?'contain':'cover')+';';photoTarget.replaceChildren(img);status('图片已替换，请下载草稿保存。');
  }catch(err){status(err.message);}e.target.value='';
};
$('#choose-pages').onclick=()=>$('#page-files').click();
$('#page-files').onchange=async e=>{
  try{const files=[...e.target.files];if(!files.length)return;if(files.some(f=>!/^image\/(png|jpeg|webp)$/.test(f.type)))throw Error('请选择逐页导出的 PNG、JPG 或 WebP 图片。');
    files.sort((a,b)=>a.name.localeCompare(b.name,undefined,{numeric:true}));
    const urls=await Promise.all(files.map(read)),fragment=document.createDocumentFragment();
    urls.forEach((src,i)=>{const img=new Image();img.src=src;img.alt=`论文原文第${i+1}页`;img.className='paper-page';img.dataset.zoom='';img.tabIndex=0;img.style.cssText='display:inline-block;width:92%;height:auto;vertical-align:top;margin-right:10px;border:1px solid #e5e8eb;box-sizing:border-box;scroll-snap-align:start;background:white;';fragment.appendChild(img);});
    strip.replaceChildren(fragment);jump.replaceChildren(...urls.map((_,i)=>new Option(`第 ${i+1} 页`,String(i))));goTo(0);status(`已替换${urls.length}页。请下载草稿保存；本地原始PDF下载链接仍对应原输入文件。`);
  }catch(err){status(err.message);}e.target.value='';
};
document.querySelectorAll('[data-link-input]').forEach(input=>input.addEventListener('input',()=>{
  const el=document.querySelector(`[data-link="${input.dataset.linkInput}"]`),u=input.value.trim();if(!el)return;
  let valid=false;try{valid=['https:','http:'].includes(new URL(u).protocol);}catch{}
  if(valid){el.href=u;el.target='_blank';el.rel='noopener noreferrer';input.setCustomValidity('');}
  else{el.removeAttribute('href');input.setCustomValidity(u?'请输入http或https链接':'');}
}));
function cleanArticle(){
  const a=$('#article').cloneNode(true);a.querySelectorAll('[data-editor-only]').forEach(e=>e.remove());
  a.querySelectorAll('[contenteditable],[data-edit],[data-photo],[data-link],img[data-zoom]').forEach(e=>{
    ['contenteditable','data-edit','data-photo','data-link','data-zoom','tabindex','role'].forEach(k=>e.removeAttribute(k));
  });return a.outerHTML;
}
$('#copy').onclick=async()=>{
  try{if(!navigator.clipboard?.write||typeof ClipboardItem==='undefined')throw Error();
    await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([cleanArticle()],{type:'text/html'}),'text/plain':new Blob([$('#article').innerText],{type:'text/plain'})})]);status('正文已复制。微信后台需重新上传图片并配置滑动组件，最后手机预览。');
  }catch{const r=document.createRange();r.selectNodeContents($('#article'));const sel=window.getSelection();sel.removeAllRanges();sel.addRange(r);status('已选中正文，请按 ⌘C / Ctrl+C 复制。');}
};
function download(content,name,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([content],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),5000);}
$('#save').onclick=()=>{
  const d=document.documentElement.cloneNode(true);d.querySelector('body').classList.remove('edit-on');d.querySelectorAll('[contenteditable]').forEach(e=>e.removeAttribute('contenteditable'));
  d.querySelector('#edit').textContent='编辑文字与照片';d.querySelector('#edit').setAttribute('aria-pressed','false');d.querySelector('#status').textContent='';
  d.querySelectorAll('[data-link-input]').forEach(e=>e.setAttribute('value',document.querySelector(`[data-link-input="${e.dataset.linkInput}"]`).value));
  d.querySelector('#zoom').removeAttribute('open');d.querySelector('#zoom-img').removeAttribute('src');
  download('<!DOCTYPE html>\n'+d.outerHTML,'SMOOTH-可编辑草稿.html','text/html;charset=utf-8');status('已下载包含当前文字、图片和链接的草稿。');
};
$('#export').onclick=()=>download('<!DOCTYPE html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>公众号正文</title><body style="margin:0;padding:24px">'+cleanArticle()+'</body></html>','SMOOTH-正文排版.html','text/html;charset=utf-8');
