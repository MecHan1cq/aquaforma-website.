const API_BASE_URL = "__API_BASE_URL__";
const grid=document.getElementById("productGrid");
const notice=document.getElementById("shopNotice");
const empty=document.getElementById("emptyProducts");
let shopData={stripe_enabled:false,online_payment_limit_cents:50000,products:[]};
const esc=value=>String(value??"").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
const money=(cents,currency="EUR")=>new Intl.NumberFormat("en-IE",{style:"currency",currency,maximumFractionDigits:2}).format(cents/100);
function renderProducts(){
  grid.innerHTML="";
  if(!shopData.products.length){empty.hidden=false;notice.textContent="";return;}
  empty.hidden=true;
  for(const product of shopData.products){
    const onlineAllowed=shopData.stripe_enabled&&product.price_cents<=shopData.online_payment_limit_cents;
    const card=document.createElement("article");card.className="product-card";
    card.innerHTML=`
      <div class="product-art"><span>AQUAFORMA</span><small>WATER ARCHITECTURE</small></div>
      <div class="product-card-body">
        <span class="kicker">AQUAFORMA PRODUCT</span><h2>${esc(product.name)}</h2>
        <p>${esc(product.description)}</p><div class="product-price">${money(product.price_cents,product.currency)}</div>
        <form class="product-action-form" data-product-id="${product.id}">
          <label>Email for order<input type="email" name="email" required maxlength="254" placeholder="name@example.com"></label>
          <label>Quantity<input type="number" name="quantity" min="1" max="10" value="1" required></label>
          ${onlineAllowed?'<button class="cta" type="submit">Pay securely with Stripe ↗</button>':'<button class="cta invoice-trigger" type="button">Request invoice ↗</button>'}
          <p class="small-note">${onlineAllowed?"Secure online checkout is available for this amount.":"Large orders are invoiced. Online checkout will be enabled after Stripe is configured."}</p>
          <div class="invoice-extra" hidden>
            <label>Full name<input name="name" maxlength="160"></label>
            <label>Phone / WhatsApp<input name="phone" maxlength="60"></label>
            <label>Message<textarea name="message" rows="2" maxlength="3000"></textarea></label>
            <button class="secondary-button invoice-submit" type="button">Send invoice request</button>
          </div>
          <p class="form-status" role="status"></p>
        </form>
      </div>`;
    const form=card.querySelector("form");
    const status=form.querySelector(".form-status");
    const invoiceExtra=form.querySelector(".invoice-extra");
    const trigger=form.querySelector(".invoice-trigger");
    if(trigger)trigger.addEventListener("click",()=>{invoiceExtra.hidden=false;});
    const invoiceButton=form.querySelector(".invoice-submit");
    if(invoiceButton)invoiceButton.addEventListener("click",async()=>{
      const fd=new FormData(form);
      const name=String(fd.get("name")||"").trim(),email=String(fd.get("email")||"").trim();
      if(!name||!email){status.textContent="Please enter your full name and email.";status.className="form-status error";return;}
      invoiceButton.disabled=true;
      try{
        const response=await fetch(`${API_BASE_URL}/api/invoice-requests`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({
          product_id:product.id,product_name:product.name,name,email,phone:fd.get("phone")||"",
          quantity:Number(fd.get("quantity")||1),message:fd.get("message")||""
        })});
        const data=await response.json().catch(()=>({}));
        if(!response.ok)throw new Error(data.detail||"Could not send invoice request.");
        status.textContent=`Invoice request #${data.id} sent. The team will contact you.`;
        status.className="form-status success";invoiceExtra.hidden=true;
      }catch(error){status.textContent=error.message;status.className="form-status error";}
      finally{invoiceButton.disabled=false;}
    });
    form.addEventListener("submit",async event=>{
      event.preventDefault();
      const fd=new FormData(form);
      const button=form.querySelector('button[type="submit"]');
      button.disabled=true;button.textContent="Opening Stripe…";
      try{
        const response=await fetch(`${API_BASE_URL}/api/products/${product.id}/checkout`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:fd.get("email"),quantity:Number(fd.get("quantity")||1)})});
        const data=await response.json().catch(()=>({}));
        if(response.status===409&&data.detail?.code==="invoice_required"){
          invoiceExtra.hidden=false;
          status.textContent="This quantity is above the online payment limit. Please complete the invoice request below.";
          status.className="form-status error";
          button.disabled=false;button.textContent="Pay securely with Stripe ↗";
          return;
        }
        if(!response.ok)throw new Error(typeof data.detail==="string"?data.detail:(data.detail?.message||"Checkout is unavailable."));
        window.location.assign(data.checkout_url);
      }catch(error){status.textContent=error.message;status.className="form-status error";button.disabled=false;button.textContent="Pay securely with Stripe ↗";}
    });
    grid.appendChild(card);
  }
}
async function loadProducts(){
  try{
    const response=await fetch(`${API_BASE_URL}/api/products`);
    if(!response.ok)throw new Error("The product catalogue could not be loaded.");
    shopData=await response.json();
    notice.textContent=shopData.stripe_enabled?"Secure Stripe checkout is configured for eligible small payments.":"Stripe keys have not been connected yet. You can still request an invoice.";
    renderProducts();
    if(params.get("payment")==="success")notice.textContent="Stripe has returned you to AquaForma. Payment confirmation is updated after Stripe sends its secure webhook.";
    if(params.get("payment")==="cancelled")notice.textContent="Checkout was cancelled. You can try again or request an invoice.";
  }catch(error){notice.textContent=error.message;empty.hidden=false;}
}
const params=new URLSearchParams(window.location.search);
loadProducts();
