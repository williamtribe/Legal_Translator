# 3_daily_to_legal_relation.py
import requests
import xml.etree.ElementTree as ET

OC = "turtle816"


def parse_relation_item(node):
    """ <연계용어> 파싱 """
    def text(tag):
        child = node.find(tag)
        return child.text.strip() if child is not None and child.text else ""

    return {
        "연계용어id": node.attrib.get("id", ""),
        "법령용어명": text("법령용어명"),
        "비고": text("비고"),
        "용어관계코드": text("용어관계코드"),
        "용어관계": text("용어관계"),
        "용어간관계링크": text("용어간관계링크"),
        "조문간관계링크": text("조문간관계링크"),
    }


def fetch_daily_to_legal(MST: str):
    url = (
        "https://www.law.go.kr/DRF/lawService.do"
        f"?OC={OC}&target=dlytrmRlt&type=XML&MST={MST}"
    )

    res = requests.get(url)
    res.raise_for_status()
    root = ET.fromstring(res.text)

    # <일상용어> 노드 찾기
    daily_node = root.find("일상용어")
    if daily_node is None:
        return {"일상용어명": "", "출처": "", "연계법령용어목록": []}

    # 일상어 정보
    daily_term = daily_node.findtext("일상용어명", "")
    source = daily_node.findtext("출처", "")

    # 연계용어 목록
    relations = []
    for rel_node in daily_node.findall("연계용어"):
        relations.append(parse_relation_item(rel_node))

    return {
        "일상용어명": daily_term,
        "출처": source,
        "연계법령용어목록": relations,
    }


if __name__ == "__main__":
    result = fetch_daily_to_legal("349505")  # 보험자산
    from pprint import pprint
    pprint(result)
