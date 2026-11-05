p = 'C:/Users/hosup/aiproj2/presentation/_build/build_midterm.js'
s = open(p, encoding='utf-8').read()
def rep(a, b):
    global s
    assert a in s, a[:60]; s = s.replace(a, b)
rep('''{ text: "미분리 건전지 → 파쇄·압축 공정 화재", options''', '''{ text: "파쇄 전 위험 부품 분리, 아직 수작업", options''')
rep('''{ text: "해체는 아직 수작업. 기기 외형은 달라도 셀 규격(AA·AAA)과 커버 방식은 몇 가지뿐 → 한 절차로 범용화",''',
    '''{ text: "대표 사례로 교체형 원통형 셀(AA·AAA, 18650 리튬) 분리. 접착된 내장 배터리는 공구가 필요해 범위 밖 · 향후 과제",''')
rep('''  s.addText("TV 리모컨 (AA) · 셋톱박스 리모컨 (AAA) · 에어컨 리모컨 (AA, 대형) · 조명 리모컨 (AAA)", {''',
    '''  s.addText("TV(AA) · 셋톱박스(AAA) · 에어컨(AA, 대형) · 조명(AAA) 리모컨 → 다음: 18650 리튬 셀 기기 (손전등·휴대용 선풍기)", {''')
open(p, 'w', encoding='utf-8').write(s); print('ok')
