const ECHSBank={
  catalog:null,
  storeKey:"echs_qbank_attempts_v20",
  payloadCache:new Map(),
  mergeCounts(target={},source={}){Object.entries(source||{}).forEach(([key,value])=>target[key]=(target[key]||0)+(Number(value)||0));return target;},
  appendFiles(row,files){row.files=[...new Set([...(row.files||[row.file]).filter(Boolean),...(files||[])])];},
  appendBundleEntries(row,entries){
    const merged=[...(row.bundle_entries||[]),...(entries||[])],seen=new Set();
    row.bundle_entries=merged.filter(entry=>{const key=`${entry.package}#${entry.entry}`;if(seen.has(key))return false;seen.add(key);return true;});
  },
  appendMappedSources(row,sources){
    const merged=[...(row.mapped_sources||[]),...(sources||[])],seen=new Set();
    row.mapped_sources=merged.filter(source=>{const key=`${source.file||source.package}#${source.entry||""}#${JSON.stringify(source.questionFilter||{})}`;if(seen.has(key))return false;seen.add(key);return true;});
  },
  applyBundleOverrides(catalog,overrides={}){
    Object.entries(overrides||{}).forEach(([id,patch])=>{
      Object.values(catalog.bundles||{}).flat().filter(row=>row.id===id).forEach(row=>{
        if(typeof patch==="string")row.display_label=patch;else Object.assign(row,patch||{});
      });
    });
  },
  mergeAddon(catalog,addon){
    if(!addon)return catalog;
    catalog.banks=catalog.banks||[];
    catalog.bankAliases={...(catalog.bankAliases||{}),...(addon.bankAliases||{})};
    (addon.banks||[]).forEach(bank=>{const existing=catalog.banks.find(item=>item.code===bank.code);if(existing)Object.assign(existing,bank);else catalog.banks.push(bank);});
    Object.entries(addon.bankDisplayOverrides||{}).forEach(([code,title])=>{const bank=catalog.banks.find(item=>item.code===code);if(bank){bank.display_title=title;}else catalog.banks.push({code,title,display_title:title});});
    catalog.bundles=catalog.bundles||{};
    Object.entries(addon.bundles||{}).forEach(([key,rows])=>{
      catalog.bundles[key]=catalog.bundles[key]||[];
      (rows||[]).forEach(row=>{const existing=catalog.bundles[key].find(item=>item.id===row.id);if(existing)Object.assign(existing,row);else catalog.bundles[key].push(row);});
    });
    this.applyBundleOverrides(catalog,addon.bundleDisplayOverrides);
    this.applyBundleOverrides(catalog,addon.bundleOverrides);
    (addon.courseUnitAugments||[]).forEach(augment=>{
      const row=(catalog.bundles.course_units||[]).find(item=>item.course_key===augment.course_key&&String(item.unit)===String(augment.unit));
      if(!row)return;
      this.appendFiles(row,augment.files);this.appendBundleEntries(row,augment.bundle_entries);this.appendMappedSources(row,augment.mapped_sources);
      row.count=(row.count||0)+(augment.count||0);row.auto_gradable_count=(row.auto_gradable_count||0)+(augment.auto_gradable_count||0);
      row.bank_counts=this.mergeCounts(row.bank_counts||{},augment.bank_counts||{});row.type_counts=this.mergeCounts(row.type_counts||{},augment.type_counts||{});
      if(augment.questionFilter)row.questionFilter=augment.questionFilter;
    });
    (addon.courseAllAugments||[]).forEach(augment=>{
      const row=(catalog.bundles.course_all||[]).find(item=>item.course_key===augment.course_key);if(!row)return;
      this.appendFiles(row,augment.files);this.appendBundleEntries(row,augment.bundle_entries);this.appendMappedSources(row,augment.mapped_sources);
      row.count=(row.count||0)+(augment.count||0);row.auto_gradable_count=(row.auto_gradable_count||0)+(augment.auto_gradable_count||0);
      row.bank_counts=this.mergeCounts(row.bank_counts||{},augment.bank_counts||{});row.type_counts=this.mergeCounts(row.type_counts||{},augment.type_counts||{});
    });
    return catalog;
  },
  async loadCatalog(){
    if(!this.catalog){
      const response=await fetch("data/catalog.json");if(!response.ok)throw new Error("Could not load question bank catalog");
      const catalog=await response.json();
      for(const file of ["data/blackboard-addon.json","data/aligned-bank-addon.json"]){
        try{const addonResponse=await fetch(file);if(addonResponse.ok)this.mergeAddon(catalog,await addonResponse.json());}catch(error){console.warn(`Optional catalog addon ${file} was not loaded`,error);}
      }
      this.catalog=catalog;
    }
    return this.catalog;
  },
  pathValue(object,path){return String(path||"").split(".").reduce((value,key)=>value==null?undefined:value[key],object);},
  matchesQuestionFilter(question,filter){return Object.entries(filter||{}).every(([path,expected])=>{const actual=this.pathValue(question,path);return Array.isArray(expected)?expected.map(String).includes(String(actual)):String(actual)===String(expected);});},
  async loadFile(file){
    const key=`file:${file}`;if(this.payloadCache.has(key))return this.payloadCache.get(key);
    const task=(async()=>{const response=await fetch(file);if(!response.ok)throw new Error("Could not load "+file);const data=await response.json();const rows=Array.isArray(data)?data:data.questions;if(!Array.isArray(rows))throw new Error("Invalid question payload in "+file);return rows;})();
    this.payloadCache.set(key,task);try{return await task;}catch(error){this.payloadCache.delete(key);throw error;}
  },
  async loadBundleEntry(source){
    const key=`bundle:${source.package}#${source.entry}`;if(this.payloadCache.has(key))return this.payloadCache.get(key);
    const task=(async()=>{if(!window.ECHSBlackboardAssets)throw new Error("Packaged question-bank loader is unavailable");const zip=await ECHSBlackboardAssets.loadZip(source.package);const file=zip.file(source.entry);if(!file)throw new Error(`Could not find ${source.entry} in ${source.package}`);const data=JSON.parse(await file.async("string"));const rows=Array.isArray(data)?data:data.questions;if(!Array.isArray(rows))throw new Error(`Invalid question payload in ${source.entry}`);return rows;})();
    this.payloadCache.set(key,task);try{return await task;}catch(error){this.payloadCache.delete(key);throw error;}
  },
  async loadMappedSource(source){
    const rows=source.package?await this.loadBundleEntry(source):await this.loadFile(source.file);
    return source.questionFilter?rows.filter(question=>this.matchesQuestionFilter(question,source.questionFilter)):rows;
  },
  questionBankCode(question,courseKey){
    const mapped=question?.classification?.course_bank_codes?.[courseKey];
    if(mapped)return mapped;
    return this.catalog?.bankAliases?.[question?.bank_code]?.[courseKey]||question?.bank_code;
  },
  async loadBundle(source){
    const row=typeof source==="string"?{file:source}:source;
    const jobs=[...new Set((row?.files||[row?.file]).filter(Boolean))].map(file=>({key:file,run:()=>this.loadFile(file)}));
    (row?.bundle_entries||[]).filter(entry=>entry?.package&&entry?.entry).forEach(entry=>jobs.push({key:`${entry.package}#${entry.entry}`,run:()=>this.loadBundleEntry(entry)}));
    (row?.mapped_sources||[]).filter(entry=>(entry?.file||(entry?.package&&entry?.entry))).forEach(entry=>jobs.push({key:`mapped:${entry.file||entry.package}#${entry.entry||""}`,run:()=>this.loadMappedSource(entry)}));
    if(!jobs.length)return[];
    const groups=new Array(jobs.length);let cursor=0,completed=0;
    const worker=async()=>{while(cursor<jobs.length){const index=cursor++;groups[index]=await jobs[index].run();completed++;window.dispatchEvent(new CustomEvent("echs:bundle-progress",{detail:{completed,total:jobs.length,source:jobs[index].key,bundle:row?.id||null}}));}};
    await Promise.all(Array.from({length:Math.min(4,jobs.length)},worker));
    const seen=new Set(),out=[];groups.flat().forEach(question=>{if(question&&question.id&&!seen.has(question.id)){seen.add(question.id);out.push(question);}});
    const filtered=row?.questionFilter?out.filter(question=>this.matchesQuestionFilter(question,row.questionFilter)):out;
    filtered.forEach(question=>{
      question.metadata=question.metadata||{};
      if(!question.metadata.source_bank_code)question.metadata.source_bank_code=question.bank_code;
      const virtualCode=this.questionBankCode(question,row?.course_key);
      if(virtualCode)question.bank_code=virtualCode;
    });
    return filtered;
  },
  escape(value){return String(value??"").replace(/[&<>\"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'\"':"&quot;","'":"&#39;"}[char]));},
  shuffle(items){const rows=[...items];for(let index=rows.length-1;index>0;index--){const swap=Math.floor(Math.random()*(index+1));[rows[index],rows[swap]]=[rows[swap],rows[index]];}return rows;},
  choiceOrder(question){const rows=(question.choices||[]).map((choice,index)=>({...choice,_sourceIndex:index}));return question.metadata?.shuffle_choices?this.shuffle(rows):rows;},
  params(){return new URLSearchParams(location.search);},
  getAttempts(){try{const value=JSON.parse(localStorage.getItem(this.storeKey)||"[]");return Array.isArray(value)?value:[];}catch{return[];}},
  saveAttempt(question,correct,response,context={}){
    const params=this.params(),attempts=this.getAttempts(),scope=(question.classification?.course_scope||"").toLowerCase();
    const inferredCourse=scope.includes("precalculus")?"ap-precalculus":scope.includes("ib mathematics")?"ib-math-ai":scope.includes("calculus")?"ap-calculus":null;
    const course=params.get("course")||inferredCourse;
    const mapping=question.classification?.course_mappings?.[course]||{};
    const legacy={id:question.id,bank_code:question.bank_code,source_bank_code:question.metadata?.source_bank_code||question.bank?.code||null,type:question.type,correct:Boolean(correct),response:String(response??""),topic:mapping.topic||question.classification?.ap_topic||params.get("topic")||null,unit:mapping.unit||question.classification?.ap_unit||params.get("unit")||null,course,lesson:params.get("from")||mapping.lesson_ids?.[0]||null,section:question.source?.section||null,at:new Date().toISOString(),mode:context.mode||params.get("mode")||"practice",sessionId:context.sessionId||null,assignmentId:context.assignmentId||params.get("assignment")||null};
    attempts.push(legacy);localStorage.setItem(this.storeKey,JSON.stringify(attempts.slice(-5000)));
    if(window.ECHSLearning)ECHSLearning.recordAttempt({question,correct,response,mode:legacy.mode,sessionId:legacy.sessionId,durationMs:context.durationMs,context:{course:legacy.course,unit:legacy.unit,topic:legacy.topic,assignmentId:legacy.assignmentId}});
    return legacy;
  },
  normalizeAnswer(value){return String(value??"").trim().toLowerCase().replace(/\s+/g," ");},
  isAutoGradable(question){return["mcq","true_false","fill_blank"].includes(question.type)&&((question.correct_choice_ids||[]).length||(question.accepted_answers||[]).length);},
  answerIsCorrect(question,response){if(["mcq","true_false"].includes(question.type))return(question.correct_choice_ids||[]).includes(response);if(question.type==="fill_blank"){const actual=this.normalizeAnswer(response);return(question.accepted_answers||[]).some(answer=>this.normalizeAnswer(answer)===actual);}return null;},
  filterQuestions(questions,filters){return questions.filter(question=>{if(filters.bank&&filters.bank!=="all"&&question.bank_code!==filters.bank)return false;if(filters.type&&filters.type!=="all"&&question.type!==filters.type)return false;const difficulty=question.metadata?.difficulty;if(filters.difficulty&&filters.difficulty!=="all"){if(filters.difficulty==="unrated"&&difficulty!=null)return false;if(filters.difficulty!=="unrated"&&String(difficulty)!==filters.difficulty)return false;}if(filters.section&&filters.section!=="all"&&String(question.source?.section||"unmapped")!==filters.section)return false;return true;});},
  labelType(type){return({mcq:"Multiple choice",true_false:"True / False",fill_blank:"Fill in the blank",essay:"Open response"})[type]||type;},
  cleanStudentLabel(value){return String(value??"").replace(/\s*·\s*(Initial Import|Pilot|Preview)\b/gi,"").replace(/\b(Initial Import|Pilot|Preview)\b/gi,"").replace(/\b(?:Pearson|Sullivan|Blitzer|Blackboard|TestGen|DLS)\b/gi,"").replace(/\s{2,}/g," ").replace(/\s*·\s*$/g,"").trim();},
  bankLabel(code){const bank=(this.catalog?.banks||[]).find(item=>item.code===code);if(bank?.display_title||bank?.title)return this.cleanStudentLabel(bank.display_title||bank.title);return({PCALRT5S:"AP Precalculus Bank 1",CAF5S:"AP Precalculus Bank 2",APPC1:"AP Precalculus Bank 1",APPC2:"AP Precalculus Bank 2",APPC3:"AP Precalculus Bank 3",APPC4:"AP Precalculus Bank 4",APPC5:"AP Precalculus Bank 5",IBMATH1:"IB Mathematics Bank 1",IBMATH2:"IB Mathematics Bank 2",IBMATH3:"IB Mathematics Bank 3",IBMATH4:"IB Mathematics Bank 4"})[code]||"Course Practice Bank";},
  bundleGroups(catalog){return[{key:"course_units",label:"Course and Unit"},{key:"course_all",label:"Full Course"},{key:"aligned_banks",label:"Course-Aligned Bank"},{key:"aligned_chapters",label:"Course-Aligned Chapter"},{key:"blackboard_banks",label:"Practice Bank"},{key:"topics",label:"AP Calculus Topic"},{key:"ap_units",label:"AP Calculus Unit"},{key:"source_chapters",label:"Practice Chapter"},{key:"scopes",label:"Coverage / Readiness"}].filter(group=>(catalog.bundles[group.key]||[]).length);},
  selectedBundleFromParams(catalog){
    const params=this.params(),course=params.get("course"),topic=params.get("topic"),unit=params.get("unit"),bundle=params.get("bundle");
    if(course&&unit){const row=(catalog.bundles.course_units||[]).find(item=>item.course_key===course&&String(item.unit)===String(unit));if(row)return{group:"course_units",row};}
    if(course){const row=(catalog.bundles.course_all||[]).find(item=>item.course_key===course);if(row)return{group:"course_all",row};}
    if(topic){const row=(catalog.bundles.topics||[]).find(item=>item.topic===topic);if(row)return{group:"topics",row};}
    if(unit){const row=(catalog.bundles.ap_units||[]).find(item=>String(item.unit)===String(unit));if(row)return{group:"ap_units",row};}
    if(bundle){for(const group of Object.keys(catalog.bundles)){const row=(catalog.bundles[group]||[]).find(item=>item.id===bundle);if(row)return{group,row};}}
    const row=(catalog.bundles.course_units||[])[0]||(catalog.bundles.aligned_banks||[])[0]||(catalog.bundles.blackboard_banks||[])[0]||(catalog.bundles.topics||[])[0]||(catalog.bundles.ap_units||[])[0];
    return{group:row?.course_key?"course_units":row?.bank_code?"aligned_banks":row?.topic?"topics":"ap_units",row};
  },
  courseLabel(catalog,key){return(catalog.courses||[]).find(course=>course.key===key)?.label||key||"Course";}
};