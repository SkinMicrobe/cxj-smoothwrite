// smoothwrite v3 editor. The copy button puts a WeChat-safe body on the clipboard:
// only inline styles plus src/href/alt survive; ids, classes, data-* and controls are removed.
const $=s=>document.querySelector(s);
let editing=false,photoTarget=null;
const status=t=>{$('#status').textContent=t;};
function showImage(img){$('#zoom-img').src=img.src;$('#zoom-img').alt=img.alt;$('#zoom').showModal();}
document.addEventListener('click',e=>{const img=e.target.closest('img[data-zoom]');if(img&&!editing)showImage(img);});
$('#close-zoom').onclick=()=>$('#zoom').close();
$('#edit').onclick=()=>{
  editing=!editing;document.body.classList.toggle('edit-on',editing);
  document.querySelectorAll('[data-edit]').forEach(e=>e.contentEditable=String(editing));
  $('#edit').setAttribute('aria-pressed',String(editing));$('#edit').textContent=editing?'完成编辑':'编辑文字与二维码';
  status(editing?'点击文字修改；点击二维码可替换图片。':'编辑已结束，请下载草稿保存修改。');
};
document.addEventListener('paste',e=>{if(e.target.closest('[data-edit]')){e.preventDefault();document.execCommand('insertText',false,e.clipboardData.getData('text/plain'));}});
document.addEventListener('click',e=>{if(editing&&e.target.closest('[data-link]'))e.preventDefault();});
const read=f=>new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(r.result);r.onerror=no;r.readAsDataURL(f);});
document.querySelectorAll('.photo-slot').forEach(el=>el.onclick=()=>{if(editing){photoTarget=el;$('#photo-file').click();}});
$('#photo-file').onchange=async e=>{
  try{const f=e.target.files[0];if(!f)return;if(!/^image\/(png|jpeg|webp)$/.test(f.type))throw Error('请选择 PNG、JPG 或 WebP 图片。');
    const img=new Image();img.src=await read(f);img.alt='课题组二维码';img.style.cssText='display:block;width:76px;height:auto;margin:0;';
    photoTarget.replaceChildren(img);status('图片已替换，请下载草稿保存。');
  }catch(err){status(err.message);}e.target.value='';
};
document.querySelectorAll('[data-link-input]').forEach(input=>input.addEventListener('input',()=>{
  const els=document.querySelectorAll(`[data-link="${input.dataset.linkInput}"]`),u=input.value.trim();
  let valid=false;try{valid=['https:','http:'].includes(new URL(u).protocol);}catch{}
  els.forEach(el=>{if(valid)el.href=u;else el.removeAttribute('href');});
  input.setCustomValidity(valid||!u?'':'请输入 http 或 https 链接');
}));
const KEEP_ATTR=['style','src','href','alt'];
function sanitize(root){
  root.querySelectorAll('[data-editor-only],button,svg,script,input,dialog').forEach(e=>e.remove());
  [root,...root.querySelectorAll('*')].forEach(e=>[...e.attributes].forEach(a=>{if(!KEEP_ATTR.includes(a.name))e.removeAttribute(a.name);}));
  root.querySelectorAll('img').forEach(i=>{i.style.maxWidth='100%';});
  return root.outerHTML;
}
function cleanArticle(){return sanitize($('#article').cloneNode(true));}
async function copyHtml(html,okMsg){
  const text=new DOMParser().parseFromString(html,'text/html').body.innerText||'';
  try{
    if(!navigator.clipboard?.write||typeof ClipboardItem==='undefined')throw Error();
    await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([html],{type:'text/html'}),'text/plain':new Blob([text],{type:'text/plain'})})]);
    status(okMsg);
  }catch{
    const box=document.createElement('div');box.style.cssText='position:fixed;left:-9999px;top:0;width:438px;';box.innerHTML=html;document.body.appendChild(box);
    const sel=getSelection(),r=document.createRange();r.selectNodeContents(box);sel.removeAllRanges();sel.addRange(r);
    let ok=false;try{ok=document.execCommand('copy');}catch{}
    sel.removeAllRanges();box.remove();
    status(ok?okMsg:'浏览器未允许自动复制，请用 Chrome / Edge 打开本文件后再点复制。');
  }
}
$('#copy').onclick=()=>copyHtml(cleanArticle(),'已复制。粘贴到公众号正文后，等图片上传完成再保存，并用手机预览检查横滑。');
function download(content,name,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([content],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),5000);}
$('#save').onclick=()=>{
  const d=document.documentElement.cloneNode(true);d.querySelector('body').classList.remove('edit-on');d.querySelectorAll('[contenteditable]').forEach(e=>e.removeAttribute('contenteditable'));
  d.querySelector('#edit').textContent='编辑文字与二维码';d.querySelector('#edit').setAttribute('aria-pressed','false');d.querySelector('#status').textContent='';
  d.querySelectorAll('[data-link-input]').forEach(e=>e.setAttribute('value',document.querySelector(`[data-link-input="${e.dataset.linkInput}"]`).value));
  d.querySelector('#zoom').removeAttribute('open');d.querySelector('#zoom-img').removeAttribute('src');
  download('<!DOCTYPE html>\n'+d.outerHTML,'SMOOTH-可编辑草稿.html','text/html;charset=utf-8');status('已下载包含当前文字、图片和链接的草稿。');
};
$('#export').onclick=()=>{download('<!DOCTYPE html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>公众号正文</title><body style="margin:0;padding:16px">'+cleanArticle()+'</body></html>','SMOOTH-正文排版.html','text/html;charset=utf-8');status('已下载纯正文 HTML（与“复制到公众号”内容一致）。');};
