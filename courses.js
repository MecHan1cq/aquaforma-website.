const API_BASE_URL = "__API_BASE_URL__";
const courseForm=document.getElementById("courseForm");
const courseFormat=document.getElementById("courseFormat");
const priceLabel=document.getElementById("selectedCoursePrice");
const statusBox=document.getElementById("courseStatus");
let coursePrices={group:250000,private:500000};
function euro(cents){return new Intl.NumberFormat("en-IE",{style:"currency",currency:"EUR",maximumFractionDigits:0}).format(cents/100);}
function updateCoursePrice(){priceLabel.textContent=`Course fee: ${euro(coursePrices[courseFormat.value]||250000)}${courseFormat.value==="group"?" per person":""}`;}
fetch(`${API_BASE_URL}/api/courses`).then(r=>r.ok?r.json():null).then(data=>{
  if(!data?.courses?.length)return;
  coursePrices.group=data.courses[0].group_price_cents;
  coursePrices.private=data.courses[0].private_price_cents;
  updateCoursePrice();
}).catch(()=>{});
courseFormat.addEventListener("change",updateCoursePrice);
courseForm.addEventListener("submit",async event=>{
  event.preventDefault();
  const button=courseForm.querySelector("button");
  const payload=Object.fromEntries(new FormData(courseForm).entries());
  button.disabled=true;button.textContent="Sending…";
  try{
    const response=await fetch(`${API_BASE_URL}/api/courses/enroll`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(data.detail||"Could not send request.");
    courseForm.reset();updateCoursePrice();
    statusBox.textContent=`Request #${data.id} received. AquaForma will contact you with availability and invoice details.`;
    statusBox.className="form-status success";
  }catch(error){statusBox.textContent=error.message;statusBox.className="form-status error";}
  finally{button.disabled=false;button.textContent="Request course details ↗";}
});
updateCoursePrice();
