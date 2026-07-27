(async()=>{
  const $=id=>document.getElementById(id);
  try{
    const catalog=await ECHSBank.loadCatalog(),banks=catalog.banks||[];
    const sum=codes=>codes.reduce((total,code)=>total+(Number(banks.find(bank=>bank.code===code)?.question_count)||0),0);
    const apCodes=["APPC1","APPC2","APPC3","APPC4","APPC5"],ibCodes=["IBMATH1","IBMATH2","IBMATH3","IBMATH4"];
    const apTotal=sum(apCodes),ibTotal=sum(ibCodes);
    const apUnits=new Set((catalog.bundles?.course_units||[]).filter(row=>row.course_key==="ap-precalculus").map(row=>String(row.unit)));
    const ibUnits=new Set((catalog.bundles?.course_units||[]).filter(row=>row.course_key==="ib-math-ai"&&(Number(row.count)||0)>0).map(row=>String(row.unit)));
    const labels=[...apCodes,...ibCodes].map(code=>ECHSBank.bankLabel(code));
    const clean=labels.every(label=>/^(AP Precalculus|IB Mathematics) Bank \d+$/.test(label)&&!/Pearson|Sullivan|Blitzer|Blackboard|TestGen|DLS/i.test(label));
    const complete=apCodes.every(code=>banks.some(bank=>bank.code===code))&&ibCodes.every(code=>banks.some(bank=>bank.code===code))&&apUnits.size>=4&&ibUnits.size>=4&&clean;
    if($("precalcTotal"))$("precalcTotal").textContent=apTotal.toLocaleString();
    if($("precalcBanks"))$("precalcBanks").textContent=apCodes.length.toLocaleString();
    if($("ibTotal"))$("ibTotal").textContent=ibTotal.toLocaleString();
    if($("ibBanks"))$("ibBanks").textContent=ibCodes.length.toLocaleString();
    if($("alignedStatus"))$("alignedStatus").textContent=complete?"Aligned":"Review";
    if($("alignedStatusCard")){
      $("alignedStatusCard").classList.toggle("warning",!complete);
      $("alignedStatusCard").title=complete?"AP Precalculus and IB Mathematics banks are numbered, course-aligned, and source names remain hidden from the student interface.":"One or more aligned-bank release conditions require review.";
    }
    window.ECHSAlignedBankAudit={complete,apTotal,ibTotal,apCodes,ibCodes,apUnits:[...apUnits],ibUnits:[...ibUnits],labels};
  }catch(error){
    if($("alignedStatus"))$("alignedStatus").textContent="Unavailable";
    if($("alignedStatusCard"))$("alignedStatusCard").classList.add("warning");
    console.error("Aligned bank audit failed",error);
  }
})();