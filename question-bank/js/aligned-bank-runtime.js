/* Course-aligned virtual banks for AP Precalculus and IB Mathematics. */
(function(){
  "use strict";
  if(!window.ECHSBank)return;
  const B=window.ECHSBank;
  const baseCatalog=B.loadCatalog.bind(B);
  const baseBundle=B.loadBundle.bind(B);
  const baseGroups=B.bundleGroups.bind(B);
  const baseSelected=B.selectedBundleFromParams.bind(B);
  const baseClean=B.cleanStudentLabel?.bind(B)||(value=>String(value??""));

  const get=(object,path)=>String(path||"").split(".").reduce((value,key)=>value==null?undefined:value[key],object);
  const match=(question,filter={})=>Object.entries(filter).every(([path,expected])=>{
    const actual=get(question,path);
    return Array.isArray(expected)?expected.map(String).includes(String(actual)):String(actual)===String(expected);
  });
  const addSources=(row,sources=[])=>{
    const seen=new Set();
    row.mapped_sources=[...(row.mapped_sources||[]),...sources].filter(source=>{
      const key=`${source.package||source.file}#${source.entry||""}#${JSON.stringify(source.questionFilter||{})}`;
      if(seen.has(key))return false;seen.add(key);return true;
    });
  };
  const addCounts=(target={},source={})=>{for(const [key,value] of Object.entries(source))target[key]=(target[key]||0)+(Number(value)||0);return target;};
  const courseLabel=(catalog,key)=>(catalog.courses||[]).find(course=>course.key===key)?.label||({
    "ap-precalculus":"AP Precalculus",
    "ib-math-ai":"IB Mathematics: Applications and Interpretation"
  })[key]||key;
  const ensureBank=(catalog,code,title,course,source,count)=>{
    const patch={code,title,display_title:title,course_key:course,source_bank_code:source,question_count:Number(count)||0,student_accessible:true,format:"ECHS course-aligned virtual bank"};
    const bank=(catalog.banks||[]).find(row=>row.code===code);
    bank?Object.assign(bank,patch):(catalog.banks||=[]).push(patch);
  };
  const relabelSource=(catalog,source,course,code,title)=>{
    for(const row of Object.values(catalog.bundles||{}).flat()){
      if(row.bank_code!==source)continue;
      const chapter=row.source_chapter??row.chapter;
      const complete=/_ALL$/i.test(String(row.id||""))||/complete/i.test(String(row.label||""));
      row.course_key=course;row.virtual_bank_code=code;
      row.label=row.display_label=complete?`${title} · Complete Collection`:`${title} · Chapter ${chapter??""}`.trim();
    }
    const sourceBank=(catalog.banks||[]).find(row=>row.code===source);
    if(sourceBank)sourceBank.display_title=title;
  };
  const mappedSource=(source,course,code)=>({
    package:source.package,
    entry:source.entry,
    questionFilter:{[`classification.course_bank_codes.${course}`]:code}
  });

  function apply(catalog,addon){
    if(catalog.__alignedBanksApplied)return catalog;
    catalog.__alignedBanksApplied=true;
    catalog.banks||=[];catalog.bundles||={};catalog.bankAliases||={};catalog.bundles.aligned_banks||=[];

    for(const [source,config] of Object.entries(addon.numberedSources||{})){
      for(const [course,code] of Object.entries(config.aliases||{})){
        const title=config.titles?.[course]||"Course Practice Bank";
        catalog.bankAliases[source]={...(catalog.bankAliases[source]||{}),[course]:code};
        ensureBank(catalog,code,title,course,source,config.question_count);
        relabelSource(catalog,source,course,code,title);
      }
    }

    for(const source of addon.alignedSources||[]){
      for(const [course,config] of Object.entries(source.courses||{})){
        const code=config.bank_code,title=config.title;
        catalog.bankAliases[source.source_bank_code]={...(catalog.bankAliases[source.source_bank_code]||{}),[course]:code};
        ensureBank(catalog,code,title,course,source.source_bank_code,config.mapped_question_count);
        const all=(source.entries||[]).map(entry=>mappedSource({...source,entry},course,code));
        const bankRow={id:`${code}_ALL`,label:`${title} · Complete Collection`,display_label:`${title} · Complete Collection`,course_key:course,course_label:courseLabel(catalog,course),bank_code:code,mapped_sources:all,count:Number(config.mapped_question_count)||0,bank_counts:{[code]:Number(config.mapped_question_count)||0}};
        const old=catalog.bundles.aligned_banks.find(row=>row.id===bankRow.id);
        old?Object.assign(old,bankRow):catalog.bundles.aligned_banks.push(bankRow);

        const full=(catalog.bundles.course_all||[]).find(row=>row.course_key===course);
        if(full){addSources(full,all);full.count=(full.count||0)+(Number(config.mapped_question_count)||0);full.bank_counts=addCounts(full.bank_counts||{},{[code]:config.mapped_question_count});}
        for(const [unit,entries] of Object.entries(config.unit_entries||{})){
          const row=(catalog.bundles.course_units||[]).find(item=>item.course_key===course&&String(item.unit)===String(unit));
          if(!row)continue;
          addSources(row,(entries||[]).map(entry=>({package:source.package,entry,questionFilter:{[`classification.course_mappings.${course}.unit`]:Number(unit)}})));
          const count=Number(config.unit_counts?.[unit])||0;
          row.count=(row.count||0)+count;row.bank_counts=addCounts(row.bank_counts||{},{[code]:count});
        }
      }
    }
    return catalog;
  }

  B.loadCatalog=async function(){
    const catalog=await baseCatalog();
    if(!catalog.__alignedBanksApplied){
      const response=await fetch("data/aligned-bank-addon.json");
      if(!response.ok)throw new Error("Could not load aligned question-bank catalog");
      apply(catalog,await response.json());
    }
    return catalog;
  };
  B.loadMappedSource=async function(source){
    const rows=source.package?await this.loadBundleEntry(source):await this.loadFile(source.file);
    return source.questionFilter?rows.filter(question=>match(question,source.questionFilter)):rows;
  };
  const normal=value=>String(value??"").toLowerCase().replace(/[^a-z0-9.]+/g," ").replace(/\s+/g," ").trim();
  const route=(questions,row)=>{
    const params=B.params(),course=params.get("course")||row?.course_key||"",topic=params.get("topic")||"",query=normal(params.get("q")||"");
    if(course&&topic)return questions.filter(question=>String(question?.classification?.course_mappings?.[course]?.topic||question?.classification?.ap_topic||"")===String(topic));
    if(course&&query){
      const terms=query.split(" ").filter(term=>term.length>=3);
      if(terms.length)return questions.filter(question=>{
        const map=question?.classification?.course_mappings?.[course]||{},source=question?.source||{};
        const text=normal([map.topic,map.topic_title,...(map.lesson_ids||[]),source.section,source.section_title,source.skill_title,question.pool_title].join(" "));
        return terms.some(term=>text.includes(term));
      });
    }
    return questions;
  };
  const virtualCode=(question,course)=>{
    const mapped=question?.classification?.course_bank_codes?.[course];
    if(mapped)return mapped;
    const source=question?.metadata?.source_bank_code||question?.bank?.code||question?.bank_code;
    return B.catalog?.bankAliases?.[source]?.[course]||source;
  };
  B.loadBundle=async function(source){
    const row=typeof source==="string"?{file:source}:source;
    const base=await baseBundle({...row,mapped_sources:undefined});
    const extra=await Promise.all((row?.mapped_sources||[]).map(item=>this.loadMappedSource(item)));
    const seen=new Set(),all=[];
    [...base,...extra.flat()].forEach(question=>{if(question?.id&&!seen.has(question.id)){seen.add(question.id);all.push(question);}});
    const filtered=route(all,row);
    return filtered.map(original=>{
      const question=typeof structuredClone==="function"?structuredClone(original):JSON.parse(JSON.stringify(original));
      question.metadata||={};
      if(!question.metadata.source_bank_code)question.metadata.source_bank_code=question.bank?.code||question.bank_code;
      const code=virtualCode(question,row?.course_key||this.params().get("course"));
      if(code)question.bank_code=code;
      return question;
    });
  };
  B.cleanStudentLabel=value=>baseClean(value).replace(/\b(?:Pearson|Sullivan|Blitzer|Blackboard|TestGen|DLS)\b/gi,"").replace(/\s{2,}/g," ").replace(/\s*·\s*$/,"").trim();
  B.bankLabel=function(code){
    const bank=(this.catalog?.banks||[]).find(row=>row.code===code);
    if(bank?.display_title||bank?.title)return this.cleanStudentLabel(bank.display_title||bank.title);
    return ({APPC1:"AP Precalculus Bank 1",APPC2:"AP Precalculus Bank 2",APPC3:"AP Precalculus Bank 3",APPC4:"AP Precalculus Bank 4",APPC5:"AP Precalculus Bank 5",IBMATH1:"IB Mathematics Bank 1",IBMATH2:"IB Mathematics Bank 2",IBMATH3:"IB Mathematics Bank 3",IBMATH4:"IB Mathematics Bank 4"})[code]||"Course Practice Bank";
  };
  B.bundleGroups=function(catalog){
    const groups=baseGroups(catalog),aligned=(catalog.bundles?.aligned_banks||[]).length?[{key:"aligned_banks",label:"Course-Aligned Bank"}]:[];
    return [...groups.slice(0,2),...aligned,...groups.slice(2)].filter((group,index,rows)=>rows.findIndex(row=>row.key===group.key)===index);
  };
  B.selectedBundleFromParams=function(catalog){
    const id=this.params().get("bundle");
    if(id)for(const group of Object.keys(catalog.bundles||{})){const row=(catalog.bundles[group]||[]).find(item=>item.id===id);if(row)return{group,row};}
    return baseSelected(catalog);
  };
})();