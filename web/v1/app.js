let token = "";
let householdId = "";
let packetId = "";
const $ = (id) => document.getElementById(id);
const status = (message) => { $("status").textContent = message; };
const api = async (path, options = {}) => {
  const response = await fetch(path, { ...options, headers: { ...(options.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) } });
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(body.detail || "Request failed.");
  return body;
};

$("request-link").onclick = async () => {
  try { const result = await api("/v1/auth/magic-links", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({email:$("email").value}) }); $("token").value = result.development_token; $("dev-link").hidden = $("verify-link").hidden = false; status("For local development, use the token shown to sign in."); } catch (error) { status(error.message); }
};
$("verify-link").onclick = async () => { try { const result = await api("/v1/auth/magic-links/verify", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({token:$("token").value})}); token=result.access_token; $("household-panel").hidden=false; status("Signed in. Create your household packet."); } catch (error) { status(error.message); } };
$("create-household").onclick = async () => { try { const result=await api("/v1/households", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:$("household-name").value,authority_attested:$("authority").checked})}); householdId=result.id; $("upload-panel").hidden=false; status("Household created. Upload a document for review."); } catch (error) { status(error.message); } };
$("upload").onclick = async () => { try { const file=$("document").files[0]; if (!file) throw new Error("Choose a document first."); const form=new FormData(); form.append("document_type", $("document-type").value); form.append("file", file); const result=await api(`/v1/households/${householdId}/documents`,{method:"POST",body:form}); $("review-panel").hidden=false; $("fields").innerHTML = result.fields.length ? result.fields.map((field) => `<label>${field.name} <input data-field="${field.id}" value="${field.value}"><button data-confirm="${field.id}">Confirm</button></label>`).join("") : "<p>No AI candidates were accepted. A reviewer must confirm evidence manually.</p>"; document.querySelectorAll("[data-confirm]").forEach((button)=>button.onclick=async()=>{const id=button.dataset.confirm; try {await api(`/v1/households/${householdId}/documents/${result.id}/fields/${id}`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({value:document.querySelector(`[data-field='${id}']`).value})});status("Field confirmed.");}catch(error){status(error.message)}}); status(result.review_reason || "Document processed. Review every candidate."); } catch (error) { status(error.message); } };
$("create-packet").onclick = async () => { try { const result=await api(`/v1/households/${householdId}/packets`,{method:"POST"}); packetId=result.id; $("packet").textContent=JSON.stringify(result,null,2); $("share").hidden=false; status("Readiness packet created. It is not an eligibility decision."); } catch(error) { status(error.message); } };
$("share").onclick = async () => { try { const result=await api(`/v1/households/${householdId}/shares`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({packet_id:packetId})}); $("share-result").textContent=`Share URL: ${result.share_url}\nAccess code (send separately): ${result.access_code}\nExpires in ${result.expires_in_days} days`; status("Share link created. You can revoke it from the packet dashboard API."); } catch(error) {status(error.message);} };
