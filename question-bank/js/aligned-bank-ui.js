/* Student-facing polish for course-aligned virtual banks. */
(function(){
  "use strict";
  const params=new URLSearchParams(location.search);
  const course=params.get("course")||"";
  function activeQuestion(){try{return Array.isArray(set)&&state&&set[state.index]?set[state.index]:null}catch(_error){return null}}
  function replaceLegacyCopy(root=document){
    root.querySelectorAll('a[href="dashboard.html"]').forEach(link=>{if(/student dashboard/i.test(link.textContent||""))link.textContent="Open Progress";});
    root.querySelectorAll(".solution").forEach(node=>{if(/publisher answer key/i.test(node.textContent||""))node.innerHTML=node.innerHTML.replace(/publisher answer key/gi,"source answer key");});
  }
  function decorateQuestion(){
    const card=document.querySelector(".questionCard"),question=activeQuestion();
    if(!card||!question)return;
    const mapping=question.classification?.course_mappings?.[course];
    if(!mapping)return;
    const pills=card.querySelector(".pillRow");
    if(pills&&!pills.querySelector("[data-aligned-mapping]")){
      const unit=document.createElement("span");unit.className="pill";unit.dataset.alignedMapping="unit";unit.textContent=`Unit ${mapping.unit}`;
      const topic=document.createElement("span");topic.className="pill";topic.dataset.alignedMapping="topic";topic.textContent=mapping.topic_title||mapping.topic||"Aligned lesson";
      const mode=pills.querySelector(".pill.gold");mode?mode.after(unit,topic):pills.append(unit,topic);
    }
    const title=card.querySelector("h2");if(title&&mapping.topic_title)title.textContent=mapping.topic_title;
    card.dataset.alignedCourse=course;card.dataset.alignedTopic=mapping.topic||"";
  }
  function polish(){replaceLegacyCopy();decorateQuestion();}
  const observer=new MutationObserver(polish);
  function start(){polish();observer.observe(document.getElementById("shell")||document.body,{childList:true,subtree:true,characterData:true});}
  document.readyState==="loading"?document.addEventListener("DOMContentLoaded",start,{once:true}):start();
})();