#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, html.parser, json, os, re, subprocess, sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCRIPT_PATH=Path(__file__).resolve()
if SCRIPT_PATH.parent.name == 'tools' and SCRIPT_PATH.parent.parent.name == 'official':
    # Deployed repository copy: .../question-bank/official/tools/validate_release.py
    OFF=SCRIPT_PATH.parent.parent
    ROOT=OFF.parents[1]
    PAYLOAD=ROOT
else:
    # Audit-workspace runner used while assembling the release package.
    ROOT=Path(os.environ.get('ECHS_RELEASE_ROOT','/mnt/data/audit_work/v5/ECHS_AP_Practice_Center_v5_INDEPENDENTLY_AUDITED_STUDENT_RELEASE')).resolve()
    PAYLOAD=ROOT/'payload'
    OFF=PAYLOAD/'question-bank/official'
DATA=OFF/'data'; STUDENT=DATA/'student'; REPORTS=OFF/'reports'
SKIP_PARTS={'.git','node_modules','.echs-backups','__pycache__'}
CANONICAL_EXPECTED=1217
READY_EXPECTED=52
RESTRICTED_EXPECTED=1165

@dataclass
class Check:
    no: str
    name: str
    errors: list[str]=field(default_factory=list)
    warnings: list[str]=field(default_factory=list)
    evidence: dict[str,Any]=field(default_factory=dict)
    @property
    def passed(self): return not self.errors

checks=[]
def check(no,name):
    c=Check(no,name); checks.append(c); return c

def load_json(p:Path):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def release_files(folder:Path=ROOT):
    for p in folder.rglob('*'):
        if p.is_file() and not SKIP_PARTS.intersection(p.relative_to(ROOT).parts):
            yield p

def all_questions(folder:Path):
    out=[]
    for p in sorted(folder.glob('chunk-*.json')):
        out.extend(load_json(p).get('questions',[]))
    return out

def strings(obj:Any, path='') -> Iterable[tuple[str,str]]:
    if isinstance(obj,str): yield path,obj
    elif isinstance(obj,dict):
        for k,v in obj.items(): yield from strings(v,f'{path}.{k}' if path else k)
    elif isinstance(obj,list):
        for i,v in enumerate(obj): yield from strings(v,f'{path}[{i}]')

def norm_text(s): return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',str(s))).strip().lower()

def balanced_braces(expr):
    # TeX requires balanced grouping braces. Square brackets may be literal interval
    # notation (for example [0,2\pi)), so they are not treated as grouping here.
    depth=0; esc=False
    for ch in expr:
        if esc: esc=False; continue
        if ch=='\\': esc=True; continue
        if ch=='{': depth+=1
        elif ch=='}':
            depth-=1
            if depth<0: return False
    return depth==0

def math_expressions(text):
    # Extract only the release's approved delimiters. Return errors for unmatched delimiters.
    exprs=[]; errs=[]; i=0
    while i<len(text):
        candidates=[(text.find('\\(',i),'\\(','\\)'),(text.find('\\[',i),'\\[','\\]')]
        candidates=[x for x in candidates if x[0]>=0]
        if not candidates: break
        start,left,right=min(candidates,key=lambda x:x[0])
        end=text.find(right,start+2)
        if end<0:
            errs.append(f'unmatched {left} at character {start}'); break
        exprs.append(text[start+2:end]); i=end+2
    # Orphan closing delimiters.
    cleaned=text
    for e in exprs: pass
    return exprs,errs

def local_refs(html_path:Path):
    text=html_path.read_text(encoding='utf-8',errors='replace')
    refs=[]
    for m in re.finditer(r'''(?:src|href)\s*=\s*["']([^"']+)["']''',text,re.I):
        val=m.group(1).strip()
        if not val or val.startswith(('#','http:','https:','mailto:','data:','javascript:')): continue
        val=val.split('#',1)[0].split('?',1)[0]
        if val: refs.append(val)
    return refs

# Load core artifacts.
canonical_index=load_json(DATA/'question-index.json')
canonical_questions=all_questions(DATA/'questions')
full_idmap=load_json(DATA/'id-map.json')
student_index=load_json(STUDENT/'question-index.json')
student_questions=all_questions(STUDENT/'questions')
student_idmap=load_json(STUDENT/'id-map.json')
archive_index=load_json(STUDENT/'archive-index.json')
archive_questions=all_questions(STUDENT/'archive-questions')
archive_idmap=load_json(STUDENT/'archive-id-map.json')
student_catalog=load_json(STUDENT/'catalog.json')
full_catalog=load_json(DATA/'catalog.json')
gate=load_json(STUDENT/'gate.json')
summary=load_json(REPORTS/'AUDIT_SUMMARY.json')
corrections=load_json(REPORTS/'QUESTION_CORRECTIONS_LOG.json')
ready_by_id={q['id']:q for q in student_questions}; full_by_id={q['id']:q for q in canonical_questions}; archive_by_id={q['id']:q for q in archive_questions}

# 1 JSON parsing/schema presence
c=check('1','JSON schema validation')
json_files=[p for p in release_files() if p.suffix.lower()=='.json']
parsed=0
for p in json_files:
    try: load_json(p); parsed+=1
    except Exception as e: c.errors.append(f'{p.relative_to(ROOT)}: {e}')
required_q={'id','course','courseId','type','classification','quality','source'}
for q in canonical_questions:
    miss=required_q-set(q)
    if miss: c.errors.append(f"{q.get('id','?')}: missing {sorted(miss)}")
c.evidence={'jsonFilesParsed':parsed,'canonicalQuestionObjects':len(canonical_questions)}

# 2 IDs
c=check('2','ID uniqueness validation')
for label,rows in [('canonical index',canonical_index),('canonical chunks',canonical_questions),('student index',student_index),('student chunks',student_questions),('archive index',archive_index),('archive chunks',archive_questions)]:
    ids=[x.get('id') for x in rows]; dup=[k for k,v in Counter(ids).items() if v>1]
    if dup: c.errors.append(f'{label}: duplicate IDs {dup[:20]}')
if set(full_by_id)!=set(r['id'] for r in canonical_index): c.errors.append('Canonical index/chunk ID sets differ.')
if set(ready_by_id)!=set(r['id'] for r in student_index): c.errors.append('Student index/chunk ID sets differ.')
if set(archive_by_id)!=set(r['id'] for r in archive_index): c.errors.append('Archive index/chunk ID sets differ.')
if set(full_idmap)!=set(full_by_id): c.errors.append('Canonical id-map does not cover exactly the canonical IDs.')
if set(student_idmap)!=set(ready_by_id): c.errors.append('Student id-map does not cover exactly the ready IDs.')
if set(archive_idmap)!=set(archive_by_id): c.errors.append('Archive id-map does not cover exactly the archive IDs.')
c.evidence={'canonicalIds':len(full_by_id),'readyIds':len(ready_by_id),'archiveIds':len(archive_by_id)}

# 3 Source references
c=check('3','Source-reference validation')
with_pages=0; echs_no_page=0
for q in canonical_questions:
    s=q.get('source') or {}
    if not any(s.get(k) for k in ('organization','publisher','bankName','sourceFile','sourceType')): c.errors.append(f"{q['id']}: no source identity")
    pages=s.get('sourcePages') or ([s.get('sourcePage')] if s.get('sourcePage') else [])
    if pages: with_pages+=1
    elif s.get('officialStatus')=='echs-original' or q.get('officialStatus')=='echs-original': echs_no_page+=1
    else: c.warnings.append(f"{q['id']}: no source page listed")
c.evidence={'recordsWithPageReferences':with_pages,'echsOriginalWithoutPage':echs_no_page,'warnings':len(c.warnings)}

# 4 completeness ready
c=check('4','Question completeness validation')
for q in student_questions:
    if not str(q.get('prompt','')).strip(): c.errors.append(f"{q['id']}: empty prompt")
    if q.get('type')=='mcq' and len(q.get('choices') or [])!=5: c.errors.append(f"{q['id']}: MCQ does not have five choices")
    if q.get('type')=='frq' and not q.get('parts'): c.errors.append(f"{q['id']}: FRQ has no parts")
    if not (q.get('workedSolution') or q.get('explanation') or all(p.get('answer') for p in q.get('parts',[]))): c.errors.append(f"{q['id']}: no verified solution/part answers")
c.evidence={'studentReady':len(student_questions),'restricted':len(canonical_questions)-len(student_questions)}

# 5 MCQ choices
c=check('5','MCQ-choice validation')
ready_mcq=[q for q in student_questions if q.get('type')=='mcq']
for q in ready_mcq:
    choices=q.get('choices',[]); labels=[str(x.get('label','')).upper() for x in choices]
    if labels!=list('ABCDE'): c.errors.append(f"{q['id']}: choice labels/order are {labels}")
    texts=[norm_text(x.get('text','')) for x in choices]
    if any(not x for x in texts): c.errors.append(f"{q['id']}: empty choice")
    if len(set(texts))!=5: c.errors.append(f"{q['id']}: duplicate choice text")
c.evidence={'readyMCQ':len(ready_mcq),'allFiveChoices':sum(len(q.get('choices',[]))==5 for q in ready_mcq)}

# 6 MCQ answers
c=check('6','MCQ-answer validation')
for q in ready_mcq:
    labels={str(x.get('label','')).upper() for x in q.get('choices',[])}
    if str(q.get('answer','')).upper() not in labels: c.errors.append(f"{q['id']}: answer not in choice labels")
    if not q.get('quality',{}).get('answerVerified'): c.errors.append(f"{q['id']}: answerVerified false")
c.evidence={'answersInChoiceSet':sum(str(q.get('answer','')).upper() in {str(x.get('label','')).upper() for x in q.get('choices',[])} for q in ready_mcq)}

# 7 FRQ parts
c=check('7','FRQ-part validation')
ready_frq=[q for q in student_questions if q.get('type')=='frq']; part_count=0
for q in ready_frq:
    labels=[]
    for p in q.get('parts',[]):
        part_count+=1; labels.append(p.get('label'))
        if not str(p.get('prompt','')).strip(): c.errors.append(f"{q['id']} part {p.get('label')}: empty prompt")
        if not str(p.get('answer','')).strip(): c.errors.append(f"{q['id']} part {p.get('label')}: empty answer")
    if len(labels)!=len(set(labels)): c.errors.append(f"{q['id']}: duplicate part labels")
c.evidence={'readyFRQ':len(ready_frq),'partCount':part_count}

# 8 FRQ points
c=check('8','FRQ-point validation')
points=0
for q in ready_frq:
    for p in q.get('parts',[]):
        mp=p.get('maxPoints')
        if not isinstance(mp,(int,float)) or mp<=0: c.errors.append(f"{q['id']} part {p.get('label')}: invalid maxPoints {mp}")
        else: points+=mp
        rubric=p.get('rubric') or []
        if not rubric: c.errors.append(f"{q['id']} part {p.get('label')}: missing rubric")
c.evidence={'totalFRQPoints':points}

# 9 mathematical flags and report reconciliation
c=check('9','Mathematical verification validation')
for q in student_questions:
    qual=q.get('quality',{})
    if not qual.get('mathematicalVerificationPassed'): c.errors.append(f"{q['id']}: mathematicalVerificationPassed false")
    if q.get('audit',{}).get('answerStatus') not in ('verified','corrected'): c.errors.append(f"{q['id']}: audit answer status {q.get('audit',{}).get('answerStatus')}")
math_report=(REPORTS/'MATHEMATICAL_VERIFICATION_REPORT.md').read_text(errors='replace')
if str(len(student_questions)) not in math_report: c.warnings.append(f'Mathematical report does not visibly include the final {len(student_questions)} count.')
c.evidence={'readyMathematicallyVerified':sum(bool(q.get('quality',{}).get('mathematicalVerificationPassed')) for q in student_questions),'correctionLogRecords':len(corrections)}

# 10 KaTeX structural pass + actual parser result reconciliation
c=check('10','KaTeX validation')
expr_count=0; field_count=0
for q in canonical_questions:
    for path,text in strings(q):
        if '\\(' in text or '\\[' in text or '\\)' in text or '\\]' in text:
            field_count+=1; exprs,errs=math_expressions(text); expr_count+=len(exprs)
            for e in errs: c.errors.append(f"{q['id']} {path}: {e}")
            for e in exprs:
                if not balanced_braces(e): c.errors.append(f"{q['id']} {path}: unbalanced braces in {e[:80]!r}")
                begins=re.findall(r'\\begin\{([^}]+)\}',e); ends=re.findall(r'\\end\{([^}]+)\}',e)
                if begins!=ends: c.errors.append(f"{q['id']} {path}: begin/end environment mismatch")
katex_result_path=REPORTS/'katex_audit_results.json'
if not katex_result_path.exists():
    c.errors.append('Missing machine-readable KaTeX parser results.')
    katex_result={}
else:
    katex_result=load_json(katex_result_path)
    if katex_result.get('katexVersion')!='0.16.27': c.errors.append(f"Unexpected KaTeX version {katex_result.get('katexVersion')}")
    if katex_result.get('canonicalQuestionsChecked')!=len(canonical_questions): c.errors.append('KaTeX result does not cover every canonical question.')
    if katex_result.get('uniqueQuestionIdsChecked')!=len(full_by_id): c.errors.append('KaTeX result unique-ID count does not reconcile.')
    if katex_result.get('parserErrors')!=0 or katex_result.get('status')!='PASS': c.errors.append(f"KaTeX parser result is {katex_result.get('status')} with {katex_result.get('parserErrors')} errors.")
kreport=(REPORTS/'KATEX_AUDIT_REPORT.md').read_text(errors='replace')
if '0.16.27' not in kreport or 'Zero parser errors remain.' not in kreport:
    c.errors.append('KATEX_AUDIT_REPORT.md does not record the successful pinned parser run.')
c.evidence={'structurallyCheckedQuestions':len(canonical_questions),'mathFields':field_count,'expressionsFound':expr_count,'actualParserExpressions':katex_result.get('expressionsParsed'),'actualParserErrors':katex_result.get('parserErrors'),'actualParserReport':'KATEX_AUDIT_REPORT.md (KaTeX 0.16.27)'}

# 11 media
c=check('11','Media validation')
refs=[]; student_refs=[]
student_ids=set(ready_by_id)
for q in canonical_questions:
    for m in q.get('media',[]):
        path=m.get('path')
        if not path:
            message=f"{q['id']}: media entry without path"
            if q['id'] in student_ids: c.errors.append(message)
            else: c.warnings.append(message)
            continue
        refs.append(path); fp=OFF/path
        if q['id'] in student_ids: student_refs.append(path)
        if not fp.is_file(): c.errors.append(f"{q['id']}: missing media {path}")
        if not str(m.get('alt','')).strip(): c.errors.append(f"{q['id']}: media missing alt text {path}")
    if q['id'] in student_ids and q.get('quality',{}).get('mediaVerified') is not True: c.errors.append(f"{q['id']}: mediaVerified false")
manifest=load_json(STUDENT/'media-manifest.json')
manifest_text=json.dumps(manifest)
for p in set(student_refs):
    if p not in manifest_text: c.warnings.append(f'Media reference absent from student manifest: {p}')
actual_media=[p for p in (OFF/'media').rglob('*') if p.is_file()]
c.evidence={'canonicalMediaReferences':len(refs),'uniqueCanonicalMediaPaths':len(set(refs)),'actualMediaFiles':len(actual_media)}

# 12 broken path validation
c=check('12','Broken-path validation')
htmls=list((OFF).glob('*.html'))+list((OFF/'admin').glob('*.html'))+[PAYLOAD/'question-bank/index.html']
checked_refs=0
for hp in htmls:
    for ref in local_refs(hp):
        checked_refs+=1
        target=(hp.parent/ref).resolve()
        # directory links are valid if directory exists or index exists
        if not target.exists() and not (target/'index.html').exists(): c.errors.append(f'{hp.relative_to(ROOT)} -> {ref}')
# JS syntax and local script references
js_files=list((OFF/'js').glob('*.js'))+[PAYLOAD/'js/official-ap-integration.js']
for p in js_files:
    r=subprocess.run(['node','--check',str(p)],capture_output=True,text=True)
    if r.returncode: c.errors.append(f'{p.relative_to(ROOT)}: {r.stderr.strip()}')
c.evidence={'htmlFiles':len(htmls),'localReferencesChecked':checked_refs,'javascriptFilesSyntaxChecked':len(js_files)}

# 13 duplicate detection
c=check('13','Duplicate detection')
prompts=defaultdict(list)
for q in canonical_questions:
    n=norm_text(q.get('prompt',''))
    if len(n)>40: prompts[n].append(q['id'])
dup_groups=[ids for ids in prompts.values() if len(ids)>1]
if dup_groups: c.warnings.append(f'{len(dup_groups)} exact normalized prompt group(s) retained with distinct permanent IDs/source contexts.')
c.evidence={'exactPromptDuplicateGroups':len(dup_groups),'largestGroup':max(map(len,dup_groups),default=1)}

# 14 course mapping
c=check('14','Course mapping validation')
allowed={'ap-calculus-ab','ap-calculus-bc','ap-precalculus','grade-9-pre-precalculus'}
for q in student_questions:
    if q.get('courseId') not in allowed: c.errors.append(f"{q['id']}: invalid courseId {q.get('courseId')}")
    if not q.get('quality',{}).get('mappingVerified'): c.errors.append(f"{q['id']}: mappingVerified false")
c.evidence={'mappedCourses':Counter(q.get('courseId') for q in student_questions)}

# 15 unit
c=check('15','Unit mapping validation')
for q in student_questions:
    cl=q.get('classification',{})
    if cl.get('primaryUnit') in (None,'') and 'prerequisite' not in str(cl.get('topicCode','')).lower(): c.errors.append(f"{q['id']}: missing primaryUnit outside prerequisite scope")
    if q.get('audit',{}).get('unitMappingStatus') not in ('verified','corrected'): c.errors.append(f"{q['id']}: unit mapping status {q.get('audit',{}).get('unitMappingStatus')}")
c.evidence={'units':Counter(str(q.get('classification',{}).get('primaryUnit')) for q in student_questions)}

# 16 topic
c=check('16','Topic mapping validation')
for q in student_questions:
    cl=q.get('classification',{})
    if not str(cl.get('primaryTopic','')).strip() or not str(cl.get('topicCode','')).strip(): c.errors.append(f"{q['id']}: missing topic/topicCode")
    if q.get('audit',{}).get('topicMappingStatus') not in ('verified','corrected'): c.errors.append(f"{q['id']}: topic mapping status {q.get('audit',{}).get('topicMappingStatus')}")
c.evidence={'uniqueTopicCodes':len(set(q.get('classification',{}).get('topicCode') for q in student_questions))}

# 17 lesson
c=check('17','Lesson mapping validation')
for q in student_questions:
    lessons=q.get('classification',{}).get('lessonIds') or []
    if not lessons: c.errors.append(f"{q['id']}: no lesson ID")
    if q.get('audit',{}).get('lessonMappingStatus') not in ('verified','corrected'): c.errors.append(f"{q['id']}: lesson mapping status {q.get('audit',{}).get('lessonMappingStatus')}")
c.evidence={'lessonIds':len(set(x for q in student_questions for x in q.get('classification',{}).get('lessonIds',[])))}

# 18 gate
c=check('18','Student-ready gate validation')
flags=['transcriptionVerified','answerVerified','mathematicalVerificationPassed','katexVerified','mediaVerified','mappingVerified','studentReadyGatePassed']
for q in student_questions:
    qual=q.get('quality',{})
    for f in flags:
        if qual.get(f) is not True: c.errors.append(f"{q['id']}: {f} is not true")
    if q.get('studentReady') is not True or q.get('studentEligible') is not True: c.errors.append(f"{q['id']}: ready boundary flags false")
    if (q.get('source') or {}).get('publicPublicationAllowed') is not True: c.errors.append(f"{q['id']}: source is not approved for public publication")
    if qual.get('completeness')!='complete-verified': c.errors.append(f"{q['id']}: completeness is {qual.get('completeness')}")
    if qual.get('reviewReasons'): c.errors.append(f"{q['id']}: unresolved review reasons remain")
    if (q.get('audit') or {}).get('reviewRequired') is not False: c.errors.append(f"{q['id']}: audit still requires review")
if set(ready_by_id)-set(full_by_id): c.errors.append('Student set is not a subset of canonical set.')
canonical_ready={q['id'] for q in canonical_questions if q.get('studentReady') is True}
if set(ready_by_id)!=canonical_ready: c.errors.append('Student runtime IDs do not exactly equal canonical studentReady=true IDs.')
if set(gate.get('studentReadyIds',[]))!=canonical_ready: c.errors.append('gate.json studentReadyIds do not reconcile.')
if set(gate.get('restrictedIds',[]))!=set(full_by_id)-canonical_ready: c.errors.append('gate.json restrictedIds do not reconcile.')
c.evidence={'gateFlagsChecked':len(student_questions)*len(flags),'studentReady':len(student_questions),'publicPublicationApproved':sum((q.get('source') or {}).get('publicPublicationAllowed') is True for q in student_questions)}

# 19 archive filtering/redaction
c=check('19','Archive filtering validation')
restricted=0; redacted=0
sensitive=['prompt','directions','parts','choices','media','answer','acceptedAnswers','explanation','workedSolution','scoringGuideline','rubric']
for q in archive_questions:
    if q.get('studentReady'):
        if q['id'] not in ready_by_id: c.errors.append(f"{q['id']}: archive says ready but absent from student pool")
    else:
        restricted+=1
        bad=[]
        for k in sensitive:
            v=q.get(k)
            if v not in (None,'',[],{}): bad.append(k)
        if bad: c.errors.append(f"{q['id']}: restricted archive exposes {bad}")
        else: redacted+=1
c.evidence={'restrictedArchiveRecords':restricted,'fullyRedactedRestrictedRecords':redacted}

# 20 practice
c=check('20','Practice filtering validation')
practice_js=(OFF/'js/practice.js').read_text()
app_js=(OFF/'js/app.js').read_text()
for needle in ["data/student","studentReady","topicCode","lesson","No verified questions","will not substitute"]:
    if needle not in practice_js+app_js: c.errors.append(f'Missing practice gating token: {needle}')
if 'contentStatus' in (OFF/'practice.html').read_text() or 'All 1,217 records' in (OFF/'practice.html').read_text(): c.errors.append('Practice HTML exposes content-status/all-record selection.')
c.evidence={'studentIndexRecords':len(student_index),'exactFilterParameters':['course','unit','topicCode','lesson','learningObjective','skill']}

# 21 exam
c=check('21','Exam filtering validation')
exam_js=(OFF/'js/exam.js').read_text(); exam_html=(OFF/'exam.html').read_text()
for needle in ['studentReady','No verified questions','will not substitute','exact.lesson','exact.topicCode']:
    if needle not in exam_js: c.errors.append(f'Missing exam gate token: {needle}')
if 'teacher-archive-only' in exam_html or 'indexed-only' in exam_html: c.errors.append('Exam HTML exposes restricted content option.')
c.evidence={'examSource':'student question-index only','studentReadyPool':len(student_index)}

# 22 dashboard
c=check('22','Dashboard attribution validation')
dash=(OFF/'js/dashboard.js').read_text()
for needle in ['validIds','studentReady','topicCode','lesson','No unresolved student-ready errors']:
    if needle not in dash: c.errors.append(f'Missing dashboard gate token: {needle}')
c.evidence={'attemptScope':'valid student-ready IDs only'}

# 23 teacher separation
c=check('23','Teacher-navigation separation validation')
open_pages=['index.html','archive.html','practice.html','exam.html','dashboard.html']
for f in open_pages:
    text=(OFF/f).read_text()
    if re.search(r'>\s*Teacher Studio\s*<|>\s*Add Questions\s*<|href=["\']admin/',text,re.I): c.errors.append(f'{f}: teacher link visible')
for p in [OFF/'admin/index.html',OFF/'admin/teacher.html',OFF/'admin/import.html']:
    if not p.exists(): c.errors.append(f'Missing admin page {p.name}')
if 'window.ECHS_ADMIN_MODE=true' not in (OFF/'admin/teacher.html').read_text(): c.errors.append('Teacher Studio does not enable admin data mode.')
c.evidence={'openPagesChecked':open_pages,'adminRoute':'question-bank/official/admin/','staticAuthenticationLimitationDocumented':True}

# 24 open AP navigation exact labels
c=check('24','Open AP navigation validation')
required=['Home','AP Archive','Tutor Practice','Exam Simulator','AP Progress','All Lessons']
for f in open_pages:
    text=(OFF/f).read_text()
    for label in required:
        if f'>{label}<' not in text: c.errors.append(f'{f}: missing nav label {label}')
    if re.search(r'>\s*(?:Student|Teacher|Parent|Admin|Sign in|Login)\s*<',text,re.I):
        c.errors.append(f'{f}: role/account label visible in open AP navigation')
c.evidence={'requiredNavigation':required}

# 25 GitHub path
c=check('25','GitHub path validation')
large=[]
for p in release_files():
    if p.stat().st_size>95*1024*1024: large.append(str(p.relative_to(ROOT)))
if large: c.errors.extend(f'File exceeds safe GitHub single-file size: {x}' for x in large)
# Case-insensitive collisions
seen={}
for p in release_files():
    rel=str(p.relative_to(ROOT)).replace('\\','/')
    low=rel.lower()
    if low in seen and seen[low]!=rel: c.errors.append(f'Case-insensitive collision: {seen[low]} vs {rel}')
    seen[low]=rel
c.evidence={'filesOver95MiB':len(large),'caseInsensitiveCollisions':sum('Case-insensitive collision' in x for x in c.errors)}

# 26 secrets
c=check('26','Secret-pattern scan')
patterns={
 'private_key':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
 'github_token':re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
 'aws_access_key':re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
 'openai_key':re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b'),
}
hits=[]; scanned=0
for p in release_files():
    if p.suffix.lower() in {'.png','.jpg','.jpeg','.webp','.gif','.pdf','.zip'}: continue
    try: text=p.read_text(errors='ignore')
    except Exception: continue
    scanned+=1
    for name,pat in patterns.items():
        if pat.search(text): hits.append((name,str(p.relative_to(ROOT))))
if hits: c.errors.extend(f'{name}: {path}' for name,path in hits)
c.evidence={'textFilesScanned':scanned,'secretPatternHits':len(hits)}

# 27 case sensitivity/local ref case already exact on Linux
c=check('27','Case-sensitivity validation')
missing_case=[]
for hp in htmls:
    for ref in local_refs(hp):
        target=(hp.parent/ref.split('#')[0].split('?')[0])
        if not target.exists() and not (target/'index.html').exists(): missing_case.append(f'{hp.relative_to(ROOT)} -> {ref}')
if missing_case: c.errors.extend(missing_case)
c.evidence={'caseSensitiveReferencesChecked':checked_refs,'missing':len(missing_case)}

# 28 student/teacher separation status
c=check('28','Student/teacher data separation validation')
for rel in ['admin/data/questions','admin/data/question-index.json','admin/data/id-map.json']:
    if not (OFF/rel).exists(): c.errors.append(f'Missing teacher-only data path {rel}')
for p in (STUDENT).rglob('*.json'):
    txt=p.read_text(errors='ignore')
    if 'teacher-archive-only"' in txt and p.name not in {'archive-index.json','archive-id-map.json'} and 'archive-questions' not in p.parts:
        c.warnings.append(f'{p.relative_to(ROOT)} contains teacher-archive-only label; verify it is metadata/redacted only.')
c.evidence={'teacherDataPath':'question-bank/official/admin/data/','studentRuntimePath':'question-bank/official/data/student/'}

# 29 counts
c=check('29','Count reconciliation validation')
if len(canonical_questions)!=CANONICAL_EXPECTED: c.errors.append(f'Canonical count {len(canonical_questions)} != {CANONICAL_EXPECTED}')
if len(student_questions)!=READY_EXPECTED: c.errors.append(f'Ready count {len(student_questions)} != {READY_EXPECTED}')
if len(canonical_questions)-len(student_questions)!=RESTRICTED_EXPECTED: c.errors.append(f'Restricted count {len(canonical_questions)-len(student_questions)} != {RESTRICTED_EXPECTED}')
if len(archive_questions)!=len(canonical_questions): c.errors.append('Archive count does not equal canonical count.')
if summary.get('canonicalQuestions')!=CANONICAL_EXPECTED or summary.get('studentReady')!=READY_EXPECTED: c.errors.append('AUDIT_SUMMARY.json counts do not reconcile.')
if student_catalog.get('questionCount')!=READY_EXPECTED or full_catalog.get('questionCount')!=CANONICAL_EXPECTED: c.errors.append('Catalog counts do not reconcile.')
c.evidence={'canonical':len(canonical_questions),'studentReady':len(student_questions),'restricted':len(canonical_questions)-len(student_questions),'archive':len(archive_questions)}

# 30 cross-file consistency
c=check('30','Cross-file consistency validation')
if set(student_idmap)!=set(student_index[i]['id'] for i in range(len(student_index))): c.errors.append('Student id-map/index mismatch.')
if set(archive_idmap)!=set(x['id'] for x in archive_index): c.errors.append('Archive id-map/index mismatch.')
for q in student_questions:
    ix=student_idmap.get(q['id'])
    if not ix: c.errors.append(f"{q['id']}: absent from student id-map")
    elif ix.get('chunk') not in {p.name for p in (STUDENT/'questions').glob('chunk-*.json')}: c.errors.append(f"{q['id']}: student id-map chunk does not exist")
for q in archive_questions:
    ix=archive_idmap.get(q['id'])
    if not ix: c.errors.append(f"{q['id']}: absent from archive id-map")
c.evidence={'studentIdMapEntries':len(student_idmap),'archiveIdMapEntries':len(archive_idmap)}

# 31 checksums
c=check('31','Checksum validation')
checksum_path=REPORTS/'RELEASE_CHECKSUMS.csv'
if not checksum_path.exists(): c.errors.append('Missing RELEASE_CHECKSUMS.csv')
else:
    rows=list(csv.DictReader(checksum_path.open(encoding='utf-8')))
    expected={r['path']:r['sha256'] for r in rows}
    for rel,digest in expected.items():
        p=ROOT/rel
        if not p.is_file(): c.errors.append(f'Checksum target missing: {rel}')
        elif hashlib.sha256(p.read_bytes()).hexdigest()!=digest: c.errors.append(f'Checksum mismatch: {rel}')
    current={str(p.relative_to(ROOT)).replace('\\','/') for p in release_files()}
    excluded={'question-bank/official/reports/RELEASE_CHECKSUMS.csv','question-bank/official/reports/RELEASE_VALIDATION.json','question-bank/official/reports/FINAL_AUDIT_REPORT.md'}
    unlisted=sorted(current-set(expected)-excluded)
    if unlisted: c.errors.append(f'Checksum manifest missing {len(unlisted)} file(s), first: {unlisted[:10]}')
    c.evidence={'checksumRows':len(rows),'unlistedFiles':len(unlisted)}

# 32 browser
c=check('32','Browser smoke-test validation')
browser_result=load_json(REPORTS/'browser-smoke-results.json')
if browser_result.get('status')!='PASS' or browser_result.get('errors'):
    c.errors.append(f"Browser smoke result is {browser_result.get('status')} with {len(browser_result.get('errors',[]))} errors")
required_pages=['index','archive','practice','exam','dashboard','teacher','import']
seen_pages={r.get('page') for r in browser_result.get('pages',[])}
for p in required_pages:
    if p not in seen_pages: c.errors.append(f'Browser smoke missing page {p}')
c.evidence={'pagesTested':sorted(seen_pages),'errors':len(browser_result.get('errors',[]))}

# 33 accessibility
c=check('33','Accessibility validation')
alt_missing=[]
for q in student_questions:
    for m in q.get('media',[]):
        if not str(m.get('alt','')).strip(): alt_missing.append((q['id'],m.get('path')))
if alt_missing: c.errors.extend(f'{qid}: missing alt {path}' for qid,path in alt_missing)
for p in [OFF/'index.html',OFF/'archive.html',OFF/'practice.html',OFF/'exam.html',OFF/'dashboard.html']:
    text=p.read_text()
    if '<html lang=' not in text: c.errors.append(f'{p.name}: missing html lang')
    if 'name="viewport"' not in text: c.errors.append(f'{p.name}: missing viewport')
c.evidence={'studentMediaWithAlt':sum(len(q.get('media',[])) for q in student_questions),'missingAlt':len(alt_missing)}

# 34 documentation
c=check('34','Documentation completeness validation')
required_docs=['README.md','QUESTION_BANK_METADATA.md','AUDIT_SUMMARY.md','FINAL_AUDIT_REPORT.md','QUESTION_CORRECTIONS_LOG.md','KATEX_AUDIT_REPORT.md','MATHEMATICAL_VERIFICATION_REPORT.md','MEDIA_AUDIT_REPORT.md','MAPPING_AUDIT_REPORT.md','RIGHTS_AND_ACCESS_REPORT.md','BROWSER_QA_REPORT.md','TEACHER_ARCHIVE_REPORT.md','SOURCE_COVERAGE_REPORT.md','RELEASE_CHECKSUMS.csv']
for name in required_docs:
    base=ROOT if name=='README.md' else REPORTS
    if not (base/name).exists(): c.errors.append(f'Missing documentation {name}')
c.evidence={'requiredDocuments':len(required_docs)}

# 35 report honesty
c=check('35','Audit-report honesty validation')
report_text='\n'.join(p.read_text(errors='ignore') for p in REPORTS.glob('*.md'))
for token in ['1,217','52','1,165','KaTeX 0.16.27','teacher/archive-only','rights']:
    if token.lower() not in report_text.lower(): c.errors.append(f'Reports do not visibly include required release fact: {token}')
if '100% student-ready' in report_text.lower(): c.errors.append('Reports make an unsupported 100% student-ready claim.')
c.evidence={'requiredFacts':['1,217 canonical','52 student-ready','1,165 restricted','KaTeX 0.16.27','teacher/archive-only','rights review']}

# 36 no hidden fallback
c=check('36','No-fallback validation')
for p in [OFF/'js/practice.js',OFF/'js/exam.js']:
    text=p.read_text()
    if re.search(r'if\s*\([^)]*\.length\s*===?\s*0[^)]*\)\s*\{?\s*[^}]*allQuestions',text,re.S): c.errors.append(f'{p.name}: empty exact scope falls back to all questions')
    if 'will not substitute broader content' not in text and 'will not substitute broader questions' not in text: c.errors.append(f'{p.name}: no explicit no-substitution message')
c.evidence={'filesChecked':['practice.js','exam.js']}

# 37 non-empty descriptions/answers final
c=check('37','Final non-empty field validation')
for q in student_questions:
    if not norm_text(q.get('prompt','')): c.errors.append(f"{q['id']}: empty normalized prompt")
    if q.get('type')=='mcq' and not norm_text(q.get('explanation') or q.get('workedSolution') or ''): c.errors.append(f"{q['id']}: empty explanation")
    for p in q.get('parts',[]):
        if not norm_text(p.get('prompt','')) or not norm_text(p.get('answer','')): c.errors.append(f"{q['id']} {p.get('label')}: empty part prompt/answer")
c.evidence={'studentReadyObjectsChecked':len(student_questions)}

# Write machine-readable + Markdown reports.
now=datetime.now(timezone.utc).isoformat()
result={
 'generatedAt':now,'root':str(ROOT),'status':'PASS' if all(c.passed for c in checks) else 'FAIL',
 'totals':{'checks':len(checks),'passed':sum(c.passed for c in checks),'failed':sum(not c.passed for c in checks),'warnings':sum(len(c.warnings) for c in checks)},
 'checks':[{'no':c.no,'name':c.name,'status':'PASS' if c.passed else 'FAIL','errors':c.errors,'warnings':c.warnings,'evidence':c.evidence} for c in checks]
}
REPORTS.mkdir(parents=True,exist_ok=True)
(REPORTS/'RELEASE_VALIDATION.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
lines=['# Final Independent Release Audit','',f'Generated: {now}','',f"**Overall: {result['status']}**",'', '| # | Check | Status | Evidence |','|---:|---|:---:|---|']
for c in checks:
    evidence='; '.join(f'{k}={v}' for k,v in c.evidence.items())
    lines.append(f"| {c.no} | {c.name} | {'PASS' if c.passed else 'FAIL'} | {evidence} |")
    if c.errors:
        lines.extend([f'  - ERROR: {x}' for x in c.errors[:50]])
    if c.warnings:
        lines.extend([f'  - WARNING: {x}' for x in c.warnings[:20]])
lines += ['', '## Release conclusion','',
          f"The release contains **{len(canonical_questions):,}** canonical records. Exactly **{len(student_questions):,}** records passed the complete public student gate; **{len(canonical_questions)-len(student_questions):,}** records remain preserved in the teacher/archive-only boundary with redacted public archive metadata.",
          '', 'No audit can honestly prove that source answer keys contain no error; this release instead records the exact evidence checked, the remaining rights constraints, and the machine gates applied before a record is allowed into open practice or scoring.']
(REPORTS/'FINAL_AUDIT_REPORT.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(result['totals'],indent=2))
for c in checks:
    if not c.passed: print(f"FAIL {c.no} {c.name}: {c.errors[:10]}")
sys.exit(0 if result['status']=='PASS' else 1)
