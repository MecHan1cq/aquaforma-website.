const API_BASE_URL = "__API_BASE_URL__";
const form = document.getElementById("applicationForm");
const statusBox = document.getElementById("applicationStatus");
const fileInput = document.getElementById("applicationFiles");
const MAX_FILE = 25 * 1024 * 1024;
const MAX_TOTAL = 50 * 1024 * 1024;

function showStatus(el, message, ok=false){el.textContent=message;el.classList.toggle("success",ok);el.classList.toggle("error",!ok);}
fileInput.addEventListener("change",()=>{
  const files=Array.from(fileInput.files||[]);
  const total=files.reduce((sum,file)=>sum+file.size,0);
  if(files.some(file=>file.size>MAX_FILE)||total>MAX_TOTAL){
    fileInput.value="";
    showStatus(statusBox,"Please choose files up to 25 MB each and 50 MB combined.");
  } else {
    showStatus(statusBox,files.length?`${files.length} file(s) selected.`:"No files selected.",true);
  }
});
form.addEventListener("submit",async event=>{
  event.preventDefault();
  const consent=form.elements.consent;
  if(!consent.checked){showStatus(statusBox,"Please confirm that we may use your details to respond.");return;}
  const files=Array.from(fileInput.files||[]);
  if(files.some(file=>file.size>MAX_FILE)||files.reduce((s,f)=>s+f.size,0)>MAX_TOTAL){
    showStatus(statusBox,"File size limit exceeded. Maximum 25 MB per file and 50 MB combined.");return;
  }
  const button=form.querySelector('button[type="submit"]');
  const body=new FormData(form);
  body.delete("consent");
  button.disabled=true;button.textContent="Submitting…";
  try{
    const response=await fetch(`${API_BASE_URL}/api/applications`,{method:"POST",body});
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(data.detail?.message||data.detail||"Could not submit the application.");
    form.reset();
    showStatus(statusBox,`Thank you. Your project application #${data.id} has been received. We will review it and contact you.`,true);
  }catch(error){showStatus(statusBox,typeof error.message==="string"?error.message:"Could not submit the application. Please try again.");}
  finally{button.disabled=false;button.textContent="Submit project application ↗";}
});
