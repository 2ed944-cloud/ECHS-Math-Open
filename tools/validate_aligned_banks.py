#!/usr/bin/env python3
"""Validate numbered AP Precalculus and IB Mathematics banks."""
from __future__ import annotations
import json, re, sys, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
QB=ROOT/'question-bank'
ADDON=QB/'data/aligned-bank-addon.json'
CROSS=QB/'data/mappings/aligned-bank-crosswalk.json'
ERRORS=[]
EXPECTED_SOURCE={'CAEGU9':3604,'ACS10L':4285,'CA9Z':2837,'ATEGU9':4945}
EXPECTED_AP={'APPC3':4606,'APPC4':3265,'APPC5':2713}
EXPECTED_IB={'IBMATH1':4093,'IBMATH2':4883,'IBMATH3':3542,'IBMATH4':2837}
FORBIDDEN=re.compile(r'Pearson|Sullivan|Blitzer|Blackboard|TestGen|DLS',re.I)
IMG_RE=re.compile(r'data-bbzip-package=["\']([^"\']+)["\'][^>]*data-bbzip-path=["\']([^"\']+)["\']',re.I)

def fail(message): ERRORS.append(message)
def read(path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc: fail(f'{path.relative_to(ROOT)}: {exc}');return {}
def nested(obj,path):
    value=obj
    for key in path.split('.'):
        if not isinstance(value,dict):return None
        value=value.get(key)
    return value

def main():
    addon=read(ADDON);cross=read(CROSS)
    if addon.get('schemaVersion')!='4.0.0':fail('Unexpected aligned addon schema version')
    if cross.get('alignmentTotals',{}).get('importedUniqueQuestions')!=15671:fail('Crosswalk imported total mismatch')
    if cross.get('alignmentTotals',{}).get('apPrecalculusMappings')!=10584:fail('Crosswalk AP mapping total mismatch')
    if cross.get('alignmentTotals',{}).get('ibMathematicsMappings')!=15355:fail('Crosswalk IB mapping total mismatch')

    numbered=addon.get('numberedSources',{})
    expected_existing={'PCALRT5S':('APPC1','AP Precalculus Bank 1',4528),'CAF5S':('APPC2','AP Precalculus Bank 2',3101)}
    for source,(code,title,count) in expected_existing.items():
        row=numbered.get(source,{})
        if row.get('aliases',{}).get('ap-precalculus')!=code:fail(f'{source}: missing {code} alias')
        if row.get('titles',{}).get('ap-precalculus')!=title:fail(f'{source}: incorrect student title')
        if row.get('question_count')!=count:fail(f'{source}: count mismatch')

    all_ids=set();source_counts={};ap_counts={};ib_counts={};image_refs=0
    for source in addon.get('alignedSources',[]):
        source_code=source.get('source_bank_code');package=QB/source.get('package','')
        if source_code not in EXPECTED_SOURCE:fail(f'Unexpected aligned source {source_code}');continue
        if not package.is_file():fail(f'Missing runtime package {package.relative_to(ROOT)}');continue
        entries=source.get('entries',[]);declared=source.get('entry_counts',{})
        local_ids=set();course_seen={'ap-precalculus':set(),'ib-math-ai':set()}
        with zipfile.ZipFile(package) as archive:
            names=set(archive.namelist())
            for entry in entries:
                if entry not in names:fail(f'{source_code}: missing {entry}');continue
                try:questions=json.loads(archive.read(entry).decode('utf-8'))
                except Exception as exc:fail(f'{source_code} {entry}: invalid JSON: {exc}');continue
                if not isinstance(questions,list):fail(f'{source_code} {entry}: expected question array');continue
                if len(questions)!=int(declared.get(entry,-1)):fail(f'{source_code} {entry}: count mismatch')
                for question in questions:
                    qid=str(question.get('id',''))
                    if not qid:fail(f'{source_code} {entry}: question without ID');continue
                    if qid in local_ids:fail(f'{source_code}: duplicate ID {qid}')
                    local_ids.add(qid)
                    if qid in all_ids:fail(f'Cross-source duplicate ID {qid}')
                    classification=question.get('classification',{})
                    for course in course_seen:
                        mapping=classification.get('course_mappings',{}).get(course)
                        code=classification.get('course_bank_codes',{}).get(course)
                        if mapping and code:
                            course_seen[course].add(qid)
                            if not mapping.get('unit') or not mapping.get('topic'):fail(f'{qid}: incomplete {course} mapping')
                            if course=='ap-precalculus' and int(mapping.get('unit'))==4 and mapping.get('exam_assessed') is not False:fail(f'{qid}: AP Unit 4 must be non-exam-assessed')
                    html=' '.join(str(value) for key,value in question.items() if key.endswith('_html') or key in {'prompt_html','solution_html'})
                    for package_ref,asset_ref in IMG_RE.findall(html):
                        image_refs+=1
                        if package_ref!=source.get('package'):fail(f'{qid}: wrong runtime package reference {package_ref}')
                        if asset_ref not in names:fail(f'{qid}: missing packaged image {asset_ref}')
        all_ids.update(local_ids);source_counts[source_code]=len(local_ids)
        if len(local_ids)!=EXPECTED_SOURCE[source_code]:fail(f'{source_code}: expected {EXPECTED_SOURCE[source_code]}, found {len(local_ids)}')
        for course,config in source.get('courses',{}).items():
            code=config.get('bank_code');title=config.get('title','');count=len(course_seen.get(course,set()))
            if FORBIDDEN.search(title):fail(f'{code}: source identity leaked into student title')
            expected=(EXPECTED_AP if course=='ap-precalculus' else EXPECTED_IB).get(code)
            if expected is None:fail(f'Unexpected virtual bank {code}')
            elif count!=expected or int(config.get('mapped_question_count',0))!=expected:fail(f'{code}: expected {expected}, found {count}')
            (ap_counts if course=='ap-precalculus' else ib_counts)[code]=count

    if source_counts!=EXPECTED_SOURCE:fail(f'Source totals mismatch: {source_counts}')
    if ap_counts!=EXPECTED_AP:fail(f'AP bank totals mismatch: {ap_counts}')
    if ib_counts!=EXPECTED_IB:fail(f'IB bank totals mismatch: {ib_counts}')
    if len(all_ids)!=15671:fail(f'Expected 15,671 unique questions, found {len(all_ids)}')
    if image_refs!=37441:fail(f'Expected 37,441 packaged image references, found {image_refs}')

    visible=(QB/'index.html').read_text(encoding='utf-8')+(QB/'practice.html').read_text(encoding='utf-8')+(QB/'exam.html').read_text(encoding='utf-8')
    for label in [f'AP Precalculus Bank {n}' for n in range(1,6)]+[f'IB Mathematics Bank {n}' for n in range(1,5)]:
        if label not in visible and label not in json.dumps(addon):fail(f'Missing student label {label}')
    if FORBIDDEN.search(visible):fail('Publisher/import identity appears in student-facing aligned-bank pages')
    practice=(QB/'practice.html').read_text(encoding='utf-8')
    exam=(QB/'exam.html').read_text(encoding='utf-8')
    for page,text in [('practice',practice),('exam',exam)]:
        if 'js/aligned-bank-runtime.js' not in text:fail(f'{page}: aligned runtime not loaded')
        if text.index('js/bank.js')>text.index('js/aligned-bank-runtime.js'):fail(f'{page}: aligned runtime loads before base bank engine')
    integration=(ROOT/'js/practice-integration.js').read_text(encoding='utf-8')
    for marker in ['key==="ap-precalculus"','key==="ib-math-ai"','params.set("topic",topic)','params.set("q",q)']:
        if marker not in integration:fail(f'Lesson routing missing marker: {marker}')

    print('ECHS aligned-bank validation')
    print(f'Unique imported questions: {len(all_ids):,}')
    print(f'AP Precalculus mappings: {sum(ap_counts.values()):,}')
    print(f'IB Mathematics mappings: {sum(ib_counts.values()):,}')
    print(f'Packaged image references: {image_refs:,}')
    print(f'Errors: {len(ERRORS)}')
    for error in ERRORS[:200]:print(f'  ERROR: {error}')
    if ERRORS:return 1
    print('Status: PASS');return 0

if __name__=='__main__':sys.exit(main())
