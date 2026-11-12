const API_BASE_URL = "__API_BASE_URL__";
const form=document.getElementById("consultationForm");
const fileInput=document.getElementById("consultationFile");
const statusBox=document.getElementById("consultationStatus");
const MAX_FILE=25*1024*1024;
fileInput.addEventListener("change",()=>{
  const file=fileInput.files?.[0];
  if(file&&file.size>MAX_FILE){fileInput.value="";statusBox.textContent="The attachment must be 25 MB or smaller.";statusBox.className="form-status error";}
});
form.addEventListener("submit",async event=>{
  event.preventDefault();
  if(!form.elements.consent.checked){statusBox.textContent="Please confirm that we may store the request.";statusBox.className="form-status error";return;}
  const file=fileInput.files?.[0];
  if(file&&file.size>MAX_FILE){statusBox.textContent="The attachment must be 25 MB or smaller.";statusBox.className="form-status error";return;}
  const button=form.querySelector("button");const body=new FormData(form);body.delete("consent");
  button.disabled=true;button.textContent="Sending…";
  try{
    const response=await fetch(`${API_BASE_URL}/api/consultations`,{method:"POST",body});
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(data.detail||"Could not send your question.");
    form.reset();statusBox.textContent=`Thank you. Consultation request #${data.id} has been saved.`;
    statusBox.className="form-status success";
  }catch(error){statusBox.textContent=error.message;statusBox.className="form-status error";}
  finally{button.disabled=false;button.textContent="Send consultation request ↗";}
});
