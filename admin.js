const API_BASE_URL="__API_BASE_URL__";
const loginBox=document.getElementById("adminLogin");
const dashboard=document.getElementById("adminDashboard");
const loginForm=document.getElementById("adminLoginForm");
const loginStatus=document.getElementById("adminLoginStatus");
const panel=document.getElementById("adminPanel");
const summary=document.getElementById("adminSummary");
let auth=sessionStorage.getItem("aquaformaAdminAuth")||"";
let dashboardData={};
let activeTab="applications";

const esc=value=>String(value??"").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
const money=(cents,currency="EUR")=>new Intl.NumberFormat("en-IE",{style:"currency",currency,maximumFractionDigits:2}).format((cents||0)/100);
const date=value=>value?new Date(value).toLocaleString():"—";
const statusOptions=["new","in_progress","contacted","invoice_requested","completed","paid","closed","cancelled"];
function setLoginMessage(message,ok=false){loginStatus.textContent=message;loginStatus.className=`form-status ${ok?"success":"error"}`;}
async function api(path,options={}){
  const headers=new Headers(options.headers||{});
  headers.set("Authorization",`Basic ${auth}`);
  if(options.body&&!(options.body instanceof FormData)&&!headers.has("Content-Type"))headers.set("Content-Type","application/json");
  const response=await fetch(`${API_BASE_URL}${path}`,{...options,headers});
  const data=await response.json().catch(()=>({}));
  if(response.status===401){logout(false);throw new Error("Your session has expired. Please sign in again.");}
  if(!response.ok)throw new Error(data.detail||"Request failed.");
  return data;
}
function logout(show=true){
  auth="";sessionStorage.removeItem("aquaformaAdminAuth");
  dashboard.hidden=true;loginBox.hidden=false;
  if(show)setLoginMessage("You have signed out.",true);
}
loginForm.addEventListener("submit",async event=>{
  event.preventDefault();
  const fd=new FormData(loginForm);
  const raw=`${fd.get("username")}:${fd.get("password")}`;
  auth=btoa(unescape(encodeURIComponent(raw)));
  const button=loginForm.querySelector("button");button.disabled=true;
  try{
    await api("/api/admin/verify");
    sessionStorage.setItem("aquaformaAdminAuth",auth);
    loginBox.hidden=true;dashboard.hidden=false;
    await loadDashboard();
  }catch(error){auth="";setLoginMessage(error.message);}
  finally{button.disabled=false;}
});
document.getElementById("adminLogout").addEventListener("click",()=>logout());
document.getElementById("adminRefresh").addEventListener("click",()=>loadDashboard());
document.getElementById("adminTabs").addEventListener("click",event=>{
  const button=event.target.closest("button[data-tab]");if(!button)return;
  activeTab=button.dataset.tab;
  document.querySelectorAll(".admin-tabs button").forEach(item=>item.classList.toggle("active",item===button));
  renderPanel();
});
async function loadDashboard(){
  try{
    dashboardData=await api("/api/admin/overview");
    loginBox.hidden=true;dashboard.hidden=false;
    renderSummary();renderPanel();
  }catch(error){if(auth){logout(false);setLoginMessage(error.message);}}
}
function renderSummary(){
  const items=[
    ["Applications",dashboardData.applications?.length||0],
    ["Consultations",dashboardData.consultations?.length||0],
    ["Course requests",dashboardData.courses?.length||0],
    ["Invoice requests",dashboardData.invoice_requests?.length||0],
    ["Products",dashboardData.products?.length||0],
    ["Payments",dashboardData.payments?.length||0]
  ];
  summary.innerHTML=items.map(([label,count])=>`<div><strong>${count}</strong><span>${label}</span></div>`).join("");
}
function statusControl(resource,item){
  return `<div class="status-control"><select data-status-select="${esc(resource)}:${item.id}">${statusOptions.map(s=>`<option value="${s}" ${item.status===s?"selected":""}>${s.replaceAll("_"," ")}</option>`).join("")}</select><button class="secondary-button" data-save-status="${esc(resource)}:${item.id}">Save status</button></div>`;
}
function fileLinks(files=[]){
  if(!files.length)return `<p class="admin-muted">No attachments.</p>`;
  return `<div class="admin-files">${files.map(file=>`<button class="file-download" data-file-id="${file.id}" data-filename="${esc(file.filename)}">Download ${esc(file.filename)} · ${(file.size_bytes/1024/1024).toFixed(1)} MB</button>`).join("")}</div>`;
}
function recordCard(title,subtitle,details,resource,item,files=[]){
  return `<article class="admin-record"><div class="record-head"><div><span class="record-id">#${item.id} · ${date(item.created_at)}</span><h3>${esc(title)}</h3><p>${esc(subtitle)}</p></div>${resource?statusControl(resource,item):""}</div><div class="record-details">${details}</div>${files.length||resource==="applications"||resource==="consultations"?fileLinks(files):""}</article>`;
}
function renderPanel(){
  const rows=dashboardData[activeTab]||[];
  if(activeTab==="products"){
    panel.innerHTML=`
      <div class="admin-add-product"><h3>Add a product</h3><form id="adminProductForm" class="admin-product-form">
        <label>Product name<input name="name" required maxlength="160"></label>
        <label>Price in EUR<input name="price_eur" type="number" min="0.01" step="0.01" required></label>
        <label class="span-2">Description<textarea name="description" rows="2" maxlength="4000"></textarea></label>
        <button class="cta" type="submit">Add product</button><p class="form-status" id="productCreateStatus" role="status"></p>
      </form></div>
      ${rows.length?rows.map(p=>`<article class="admin-record"><div class="record-head"><div><span class="record-id">PRODUCT #${p.id}</span><h3>${esc(p.name)}</h3><p>${money(p.price_cents,p.currency)} · ${p.active?"Active":"Hidden"}</p></div><button class="secondary-button" data-toggle-product="${p.id}" data-active="${p.active}">${p.active?"Hide product":"Activate product"}</button></div><p>${esc(p.description)}</p></article>`).join(""):`<p class="admin-empty">No products yet. Add the first product above.</p>`}`;
    document.getElementById("adminProductForm").addEventListener("submit",createProduct);
    return;
  }
  if(activeTab==="applications"){
    panel.innerHTML=rows.length?rows.map(x=>recordCard(`${x.first_name} ${x.last_name}`,`${x.email} · ${x.phone}`,`
      <p><b>Address:</b> ${esc(x.address)}, ${esc(x.country_city)}</p>
      <p><b>Owner / investor:</b> ${esc(x.investor_type)} · <b>Location:</b> ${esc(x.location_type)}</p>
      <p><b>Waterfall:</b> ${esc(x.waterfall_type)} · <b>Budget:</b> ${esc(x.budget)} · <b>Start:</b> ${esc(x.timeline)}</p>
      <p><b>Additional information:</b><br>${esc(x.additional_info||"Not provided").replace(/\n/g,"<br>")}</p>`,
      "applications",x,x.files)).join(""):`<p class="admin-empty">No project applications yet.</p>`;
  }else if(activeTab==="consultations"){
    panel.innerHTML=rows.length?rows.map(x=>recordCard(x.name,`${x.email} · ${x.phone||"No phone"}`,`<p>${esc(x.question).replace(/\n/g,"<br>")}</p>`,"consultations",x,x.files)).join(""):`<p class="admin-empty">No consultation requests yet.</p>`;
  }else if(activeTab==="courses"){
    panel.innerHTML=rows.length?rows.map(x=>recordCard(x.name,`${x.email} · ${x.phone||"No phone"}`,`<p><b>Course:</b> ${esc(x.course)} · <b>Format:</b> ${esc(x.course_format)}</p><p><b>Fee:</b> ${money(x.price_cents,x.currency)}</p><p>${esc(x.message||"No additional message")}</p>`,"courses",x)).join(""):`<p class="admin-empty">No course requests yet.</p>`;
  }else if(activeTab==="invoice_requests"){
    panel.innerHTML=rows.length?rows.map(x=>recordCard(x.name,`${x.email} · ${x.phone||"No phone"}`,`<p><b>Product:</b> ${esc(x.product_name)} · <b>Quantity:</b> ${x.quantity}</p><p>${esc(x.message||"No additional message")}</p>`,"invoice-requests",x)).join(""):`<p class="admin-empty">No invoice requests yet.</p>`;
  }else if(activeTab==="payments"){
    panel.innerHTML=rows.length?rows.map(x=>`<article class="admin-record"><div class="record-head"><div><span class="record-id">PAYMENT #${x.id} · ${date(x.created_at)}</span><h3>${money(x.amount_total,x.currency)}</h3><p>${esc(x.customer_email)}</p></div><span class="payment-state">${esc(x.status)}</span></div></article>`).join(""):`<p class="admin-empty">No Stripe payments yet.</p>`;
  }else if(activeTab==="enquiries"){
    panel.innerHTML=rows.length?rows.map(x=>recordCard(x.name,`${x.email} · ${x.country||"Location not provided"}`,`<p><b>Type:</b> ${esc(x.project_type)} · <b>Language:</b> ${esc(x.language)}</p><p>${esc(x.message).replace(/\n/g,"<br>")}</p>`,"enquiries",x)).join(""):`<p class="admin-empty">No general enquiries yet.</p>`;
  }
}
async function saveStatus(button){
  const [resource,id]=button.dataset.saveStatus.split(":");
  const select=panel.querySelector(`[data-status-select="${resource}:${id}"]`);
  button.disabled=true;
  try{
    await api(`/api/admin/status/${resource}/${id}`,{method:"PATCH",body:JSON.stringify({status:select.value})});
    await loadDashboard();
  }catch(error){alert(error.message);}
  finally{button.disabled=false;}
}
async function createProduct(event){
  event.preventDefault();
  const form=event.currentTarget,fd=new FormData(form),status=document.getElementById("productCreateStatus"),button=form.querySelector("button");
  button.disabled=true;
  try{
    await api("/api/admin/products",{method:"POST",body:JSON.stringify({
      name:fd.get("name"),description:fd.get("description"),price_eur:Number(fd.get("price_eur")),active:true
    })});
    form.reset();status.textContent="Product added.";status.className="form-status success";
    await loadDashboard();activeTab="products";document.querySelector('[data-tab="products"]').classList.add("active");renderPanel();
  }catch(error){status.textContent=error.message;status.className="form-status error";}
  finally{button.disabled=false;}
}
async function toggleProduct(button){
  const id=button.dataset.toggleProduct,active=button.dataset.active!=="true";
  button.disabled=true;
  try{await api(`/api/admin/products/${id}`,{method:"PATCH",body:JSON.stringify({active})});await loadDashboard();}
  catch(error){alert(error.message);}
  finally{button.disabled=false;}
}
async function downloadFile(button){
  button.disabled=true;
  try{
    const response=await fetch(`${API_BASE_URL}/api/admin/files/${button.dataset.fileId}`,{headers:{Authorization:`Basic ${auth}`}});
    if(!response.ok)throw new Error("Could not download attachment.");
    const blob=await response.blob(),url=URL.createObjectURL(blob),a=document.createElement("a");
    a.href=url;a.download=button.dataset.filename||"attachment";document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);
  }catch(error){alert(error.message);}
  finally{button.disabled=false;}
}
panel.addEventListener("click",event=>{
  const statusButton=event.target.closest("[data-save-status]");
  const productButton=event.target.closest("[data-toggle-product]");
  const fileButton=event.target.closest("[data-file-id]");
  if(statusButton)saveStatus(statusButton);
  if(productButton)toggleProduct(productButton);
  if(fileButton)downloadFile(fileButton);
});
if(auth)loadDashboard();
