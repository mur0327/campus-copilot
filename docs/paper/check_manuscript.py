"""원고를 정본 §15.3.2 규칙으로 점검한다. python3 docs/paper/check_manuscript.py"""
import re, os, collections

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, '21-manuscript.md'), encoding='utf-8').read()
b = s.split('## Abstract', 1)[1]
body, ref = b.split('## REFERENCE', 1)
kor = re.sub(r'^(#|\||!|Table|Note|Fig|\$\$).*$', '', body[body.find('## 1.'):], flags=re.M)
P = [p.strip() for p in kor.split('\n\n') if p.strip()]
def sents(p): return [x.strip() for x in re.split(r'(?<=다)(?:\[[\d,]+\])?\.\s+', p) if x.strip()]
bad = []
def chk(no, name, fail, detail=''):
    print(f"{'✗' if fail else '✓'} {no:>4} {name}" + (f"  → {detail}" if fail and detail else ''))
    if fail: bad.append(no)

chk('1', "소절 1단계", bool(re.search(r'^#### ', body, re.M)))
paren = re.findall(r'\((?:Table|Fig\. )\d\)', body)
late = [f'T{n}' for n in range(1, 7) if not (re.search(rf'Table {n}[과와]', body) and re.search(rf'Table {n}[과와]', body).start() < body.find(f'Table {n}. '))]
late += [f'F{n}' for n in range(1, 6) if not (re.search(rf'Fig\. {n}[과와은는]', body) and re.search(rf'Fig\. {n}[과와은는]', body).start() < body.find(f'Fig. {n}. '))]
chk('2a', "참조 서술형·언급 선행", bool(paren or late), f"{paren}{late}")
# 2b 인접성: 참조 문단과 표·그림 사이에 다른 본문 문단이 없어야 한다
blocks = [x.strip() for x in body.split('\n\n') if x.strip()]
far = []
for n in range(1, 7):
    cap = next((i for i, x in enumerate(blocks) if x.startswith(f'Table {n}.')), None)
    men = max((i for i, x in enumerate(blocks) if re.search(rf'Table {n}[과와에의를은는]', x) and not x.startswith(('Table', '|'))), default=None)
    if cap is not None and men is not None and any(not blocks[i].startswith(('|', 'Table', 'Fig', '!')) for i in range(men + 1, cap)):
        far.append(f'Table {n}')
for n in range(1, 6):
    cap = next((i for i, x in enumerate(blocks) if x.startswith(f'![Fig. {n}]')), None)
    men = max((i for i, x in enumerate(blocks) if re.search(rf'Fig\. {n}[과와은는의를에]', x) and not x.startswith(('Fig', '!'))), default=None)
    if cap is not None and men is not None and any(not blocks[i].startswith(('|', 'Table', 'Fig', '!')) for i in range(men + 1, cap)):
        far.append(f'Fig. {n}')
chk('2b', "표·그림이 참조 문단 바로 뒤", bool(far), str(far))
chk('3', "소절 월권 없음", '이상의 결과는 검색 회수 지표와' in body)
chk('4', "수치 나열 전 안내", '품질 축 분포는 다음과 같다' in body)
one = [p[:28] for p in P if len(sents(p)) == 1 and len(p) > 60]
chk('5', "한 문장 문단 없음", bool(one), str(one))
chk('6', "이상의 오용 없음", bool([m for m in re.finditer('이상의', kor) if '하나 이상의' not in kor[max(0, m.start()-4):m.start()+6]]))
allow = ['확인하지 못하였다', '실제 사용자 성공률이 아니다', '보장되는 것은 아니다', '어느 층위에서 났는지 드러나지 않는다', '해석하지 않는다']
neg = [sents(p)[-1][:32] for p in P if re.search(r'(아니다|않는다|못하였다|없다)\.?$', sents(p)[-1].rstrip('.')) and not any(a in sents(p)[-1] for a in allow)]
chk('7', "부정 종결 허용 범위", bool(neg), str(neg))
chk('9', "번역투 피동 없음", bool(re.search(r'지지되[다더는]|회수되[다더는]', kor)))
chk('12', "미정의 축 이름 없음", '근거성' in body)
chk('14', "세기 요구 없음", bool(re.search(r'앞의 [가-힣]+ ?가지', body)))
chk('15', "문항/개 구분", bool(re.findall(r'\d+개 문항', body)))
tp = sorted(set(re.findall(r'Table \d[와과]', body))); fp = sorted(set(re.findall(r'Fig\. \d[와과]', body)))
chk('16', "번호 뒤 조사", tp != ['Table 1과','Table 2와','Table 3과','Table 4와','Table 5와','Table 6과'] or fp != ['Fig. 1과','Fig. 2와','Fig. 3과','Fig. 5와'], f"{tp}{fp}")
order = []
for tok in re.findall(r'\[(\d+(?:,\d+)*)\]', body):
    for x in map(int, tok.split(',')):
        if x not in order: order.append(x)
chk('17', "인용 1~30·REFERENCE 30편", order != list(range(1, 31)) or re.findall(r'^\[(\d+)\]', ref, re.M) != [str(i) for i in range(1, 31)])
imgs = re.findall(r'!\[Fig\. (\d)\]\(figures/(fig\d[^)]+)\)', body)
chk('18', "캡션·파일명 일치", re.findall(r'^Table (\d+)\.', body, re.M) != [str(i) for i in range(1, 7)] or re.findall(r'^Fig\. (\d)\. ', body, re.M) != ['1','2','3','4','5'] or any(not f.startswith(f'fig{n}-') or not os.path.exists(os.path.join(HERE, 'figures', f)) for n, f in imgs))
chk('19', "지시어 대상 존재", bool(re.search(r'^이를 [가-힣]', kor, re.M)))
chk('20', "동일 문장 중복 없음", bool([k for k, v in collections.Counter(x for p in P for x in sents(p) if len(x) > 45).items() if v > 1]))
# §15.3.1 결론 구성
cp = [p.strip() for p in body[body.find('## 6.'):].split('\n\n') if p.strip() and not p.startswith('##')]
chk('15.3.1', "결론 3문단(요약/보완·산출물/향후)", len(cp) != 3, f"{len(cp)}문단")
miss = [k for k in ['31/50(62.0%)','30/49(61.2%)','13문항(59.1%)','46/50(92.0%)','424행','626행','87개 묶음','고위험 사례 67개','층화 표본 20개','4,087','20,788','237개','45개 사이트','0.0192','0.0526','a718a76a'] if k not in body]
chk('15.4', "수치 빠른 참조 전항", bool(miss), str(miss))
print(f"\n{'-'*46}\n미해결: {bad if bad else '없음'}  |  본문 문단 {len(P)}개")

# 21 격식: 이 세션에서 반복해 내려간 서술어·표현
casual = {
    '쓰였|쓰고 있|데만 쓰|쓰지 않|쓸 수 있는지': '쓰다 → 사용하다',
    '넣는 입력|함께 넣고|넣고,': '넣다 → 사용하다/보강하다',
    '매기고|매긴다': '매기다 → 부여하다',
    '세지 않는다': '세다 → 인정하다',
    '가린 |가리고 |가린다': '가리다 → 공개하지 않다',
    '지를 본다|다고 본다|지를 보는 반면': '보다 → 판정하다/간주하다',
    '보고 판정|보지 않은 상태': '보다 → ~만으로/확인할 수 없는',
}
hit = [v for k, v in casual.items() if re.search(k, kor)]
chk('21', "격식 낮은 서술어 없음", bool(hit), str(hit))

# 22 리듬: 한 문단에서 비슷한 길이 문장이 넷 이상 연속하면 다다다가 된다
flat = []
enum = ('다음 네 조건', '다음 세 조건', '다음과 같다')
for p in P:
    if any(e in p for e in enum):  # 병렬 열거는 평탄이 의도다
        continue
    L = [len(x) for x in sents(p)]
    for i in range(len(L) - 3):
        w = L[i:i + 4]
        if max(w) - min(w) <= 12:
            flat.append(f"{p[:14]}…{w}")
            break
chk('22', "문장 길이 평탄 구간 없음", bool(flat), str(flat))

# 23 어미: 같은 어미가 셋 이상 연속하면 다다다가 된다(병렬 열거 문단은 제외)
same = []
for p in P:
    if any(e in p for e in enum):
        continue
    E = [x.rstrip('.')[-3:] for x in sents(p)]
    for i in range(len(E) - 2):
        if E[i] == E[i + 1] == E[i + 2]:
            same.append(f"{p[:12]}…[{E[i]}]")
            break
chk('23', "어미 3연속 없음", bool(same), str(same))

# 24 짧은 문장이 셋 이상 연속하면 끊긴다
short = []
for p in P:
    if any(e in p for e in enum):
        continue
    L = [len(x) for x in sents(p)]
    for i in range(len(L) - 2):
        if max(L[i:i + 3]) < 45:
            short.append(f"{p[:12]}…{L[i:i+3]}")
            break
chk('24', "짧은 문장 3연속 없음", bool(short), str(short))
